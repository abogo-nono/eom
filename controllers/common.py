"""Shared building blocks for the Extract and Remove pages."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Qt
from PySide6.QtWidgets import QCheckBox, QFileDialog, QMenu, QMessageBox, QToolButton

import exporters
import formats
import settings

FILE_MODE, FOLDER_MODE = 0, 1


class FileSelection(QObject):
    """Owns a page's "file or folder" selection.

    Adds a *Sub-folders* checkbox and a *Recent* menu to the page toolbar and
    supports explicit multi-file selections (drag & drop of several files).
    """

    def __init__(self, parent_widget, type_combo, path_edit, toolbar, on_activate: Callable[[], None]) -> None:
        super().__init__(parent_widget)
        self._parent = parent_widget
        self._type = type_combo
        self._path = path_edit
        self._on_activate = on_activate
        # Explicit selection from a multi-file drop: (base_dir, {name: rel_path}).
        self._explicit: tuple[str, dict[str, str]] | None = None

        self.recursive = QCheckBox(QCoreApplication.translate("Common", "Sub-folders"))
        self.recursive.setToolTip(QCoreApplication.translate("Common", "Also process files inside sub-folders"))
        self.recursive.setChecked(settings.get("recursive"))
        self.recursive.toggled.connect(lambda v: settings.set("recursive", v))
        toolbar.insertWidget(1, self.recursive)

        self.recent_btn = QToolButton()
        self.recent_btn.setObjectName("recent_btn")
        self.recent_btn.setText(QCoreApplication.translate("Common", "Recent ▾"))
        self.recent_btn.setToolTip(QCoreApplication.translate("Common", "Recently opened files and folders"))
        self.recent_btn.setPopupMode(QToolButton.InstantPopup)
        self.recent_btn.setCursor(Qt.PointingHandCursor)
        self._menu = QMenu(self.recent_btn)
        self._menu.aboutToShow.connect(self._fill_recent)
        self.recent_btn.setMenu(self._menu)
        toolbar.insertWidget(3, self.recent_btn)

        self._type.currentIndexChanged.connect(self._sync_mode)
        self._path.textEdited.connect(self._clear_explicit)
        self._sync_mode()

    # -- state ------------------------------------------------------------

    def is_batch(self) -> bool:
        return self._type.currentIndex() != FILE_MODE

    def _sync_mode(self) -> None:
        self.recursive.setVisible(self.is_batch())
        self._explicit = None

    def _clear_explicit(self, *_args) -> None:
        self._explicit = None

    def reload_settings(self) -> None:
        self.recursive.setChecked(settings.get("recursive"))

    # -- recent -----------------------------------------------------------

    def _fill_recent(self) -> None:
        self._menu.clear()
        items = settings.recent()
        if not items:
            action = self._menu.addAction(QCoreApplication.translate("Common", "No recent files"))
            action.setEnabled(False)
            return
        for path in items:
            action = self._menu.addAction(path)
            action.triggered.connect(lambda _=False, p=path: self.load_paths([p], activate=True))
        self._menu.addSeparator()
        self._menu.addAction(QCoreApplication.translate("Common", "Clear recent"), settings.clear_recent)

    # -- selection --------------------------------------------------------

    def browse(self) -> None:
        start = settings.get("last_dir") or str(Path.home())
        if not self.is_batch():
            path = QFileDialog.getOpenFileName(
                self._parent, QCoreApplication.translate("Common", "Choose a file"), start, formats.FILE_DIALOG_FILTER
            )[0]
        else:
            path = QFileDialog.getExistingDirectory(
                self._parent, QCoreApplication.translate("Common", "Choose a folder"), start
            )
        if path:
            self._explicit = None
            self._path.setText(path)
            settings.set("last_dir", str(Path(path).parent if not self.is_batch() else path))

    def load_paths(self, paths: list[str], activate: bool = False) -> bool:
        """Select *paths* (one file, one folder, or several files). Returns False if nothing usable."""
        paths = [str(Path(p).expanduser().resolve()) for p in paths if p]
        files = [p for p in paths if Path(p).is_file()]
        dirs = [p for p in paths if Path(p).is_dir()]
        if not files and not dirs:
            return False
        if len(paths) == 1:
            self._type.setCurrentIndex(FILE_MODE if files else FOLDER_MODE)
            self._explicit = None
            self._path.setText(paths[0])
        else:
            # Several items: process them as one batch relative to their common folder.
            base = os.path.commonpath([p if Path(p).is_dir() else str(Path(p).parent) for p in paths])
            images: dict[str, str] = {}
            for f in files:
                rel = Path(f).relative_to(base).as_posix()
                images[rel] = rel
            for d in dirs:
                for rel in formats.scan_directory(d, self.recursive.isChecked()):
                    full = (Path(d) / rel).relative_to(base).as_posix()
                    images[full] = full
            self._type.setCurrentIndex(FOLDER_MODE)
            self._path.setText(base)
            self._explicit = (base, images)
        if activate:
            self._on_activate()
        return True

    def resolve(self) -> tuple[str, bool, dict] | None:
        """Return ``(path, is_batch, images)`` for the current selection, or None (+warning)."""
        path = self._path.text().strip()
        if not path:
            QMessageBox.warning(
                self._parent,
                QCoreApplication.translate("Common", "Nothing selected"),
                QCoreApplication.translate("Common", "Select a file or a folder first."),
            )
            return None
        if self._explicit and self._explicit[0] == path:
            return path, True, dict(self._explicit[1])
        if not self.is_batch():
            if not Path(path).is_file():
                QMessageBox.warning(
                    self._parent,
                    QCoreApplication.translate("Common", "File not found"),
                    QCoreApplication.translate("Common", "This file does not exist:\n%1").replace("%1", path),
                )
                return None
            settings.add_recent(path)
            return path, False, {}
        if not Path(path).is_dir():
            QMessageBox.warning(
                self._parent,
                QCoreApplication.translate("Common", "Folder not found"),
                QCoreApplication.translate("Common", "This folder does not exist:\n%1").replace("%1", path),
            )
            return None
        images = formats.scan_directory(path, self.recursive.isChecked())
        settings.add_recent(path)
        return path, True, images

    def describe(self) -> str:
        path = self._path.text().strip()
        if self._explicit and self._explicit[0] == path:
            return (
                QCoreApplication.translate("Common", "%1 selected file(s) in %2")
                .replace("%1", str(len(self._explicit[1])))
                .replace("%2", path)
            )
        return path


def ask_export_path(parent, default_name: str = "metadata") -> tuple[str, str] | None:
    """Show a save dialog offering every export format; returns ``(path, fmt)``."""
    filters = [
        QCoreApplication.translate("Common", "JSON (*.json)"),
        QCoreApplication.translate("Common", "CSV spreadsheet (*.csv)"),
        QCoreApplication.translate("Common", "HTML report (*.html)"),
        QCoreApplication.translate("Common", "Text (*.txt)"),
    ]
    fmts = ["json", "csv", "html", "txt"]
    start = str(Path(settings.get("last_dir") or Path.home()) / f"{default_name}.json")
    path, chosen = QFileDialog.getSaveFileName(
        parent, QCoreApplication.translate("Common", "Export metadata"), start, ";;".join(filters)
    )
    if not path:
        return None
    fmt = exporters.format_for_path(path, default="")
    if not fmt:
        fmt = fmts[filters.index(chosen)] if chosen in filters else "json"
        path = f"{path}.{fmt}"
    return path, fmt


def confirm_in_place(parent, count: int) -> bool:
    """Ask before modifying originals (unless the user opted out)."""
    if not settings.get("confirm_in_place"):
        return True
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(QCoreApplication.translate("Common", "Modify original files?"))
    box.setText(
        QCoreApplication.translate("Common", "%1 original file(s) will be modified. This cannot be undone.").replace(
            "%1", str(count)
        )
        + "\n\n"
        + QCoreApplication.translate("Common", "Tip: enable “Save copies to…” to keep the originals untouched.")
    )
    dont_ask = QCheckBox(QCoreApplication.translate("Common", "Don't ask again"))
    box.setCheckBox(dont_ask)
    box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    box.button(QMessageBox.Ok).setText(QCoreApplication.translate("Common", "Modify originals"))
    accepted = box.exec() == QMessageBox.Ok
    if accepted and dont_ask.isChecked():
        settings.set("confirm_in_place", False)
    return accepted
