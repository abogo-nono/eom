"""RemovalController — owns the Remove page: profiles, custom selection, copies, verification, export-and-remove."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
)

import exporters
import Extractor
import profiles
import risk
import settings
import theme
from controllers.common import FileSelection, ask_export_path, confirm_in_place
from widgets import BeforeAfterDialog, CustomSelectionDialog, risk_summary, severity_color
from workers import RemovalWorker

CUSTOM = "custom"


class RemovalController(QObject):
    """Manages the Remove page.

    Takes a reference to the *ui* object (from Ui_MainWindow) and the parent
    QWidget.  *trigger_export* is accepted for backward compatibility and
    ignored: export-and-remove now exports the metadata captured by the
    removal worker itself, so no second extraction is needed.
    """

    def __init__(self, ui, parent, trigger_export=None) -> None:  # noqa: ARG002
        super().__init__(parent)
        self._ui = ui
        self._parent = parent
        self._worker: RemovalWorker | None = None
        self._reports: dict[str, dict] = {}
        self._export_target: tuple[str, str] | None = None
        self._custom_keys: list[str] | None = None  # per-tag selection, valid for _custom_keys_path only
        self._custom_keys_path: str | None = None

        self.selection = FileSelection(
            parent, ui.remove_type, ui.remove_file_path, ui.horizontalLayout_10, self.on_remove_btn_clicked
        )
        ui.remove_browse_btn.clicked.connect(self.on_remove_browse_btn_clicked)
        ui.remove_btn.clicked.connect(self.on_remove_btn_clicked)
        ui.export_and_remove_btn.clicked.connect(self.on_export_and_remove_btn_clicked)
        ui.remove_file_path.setPlaceholderText(self.tr("Drop files here, or browse…"))
        ui.export_and_remove_btn.setToolTip(self.tr("Save the current metadata to a file, then remove it"))

        layout = ui.remove_page.layout()
        table = ui.removed_table_data
        layout.removeWidget(table)

        # Row 1 — profile + copies.
        options = QHBoxLayout()
        options.addWidget(QLabel(self.tr("Remove:")))
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("profile_combo")
        for profile in profiles.PROFILES.values():
            self.profile_combo.addItem(QCoreApplication.translate("profiles", profile.name), profile.id)
            self.profile_combo.setItemData(
                self.profile_combo.count() - 1,
                QCoreApplication.translate("profiles", profile.description),
                Qt.ToolTipRole,
            )
        self.profile_combo.addItem(self.tr("Custom selection…"), CUSTOM)
        self.profile_combo.activated.connect(self.on_profile_combo_activated)
        options.addWidget(self.profile_combo)
        self.customize_btn = QPushButton(self.tr("Choose…"))
        self.customize_btn.setObjectName("secondary_btn")
        self.customize_btn.setCursor(Qt.PointingHandCursor)
        self.customize_btn.clicked.connect(self.on_customize_btn_clicked)
        options.addWidget(self.customize_btn)
        options.addSpacing(16)

        self.copy_check = QCheckBox(self.tr("Save copies to:"))
        self.copy_check.setToolTip(self.tr("Keep originals untouched and write cleaned copies to another folder"))
        self.copy_check.toggled.connect(self.on_copy_check_toggled)
        options.addWidget(self.copy_check)
        self.output_btn = QPushButton()
        self.output_btn.setObjectName("secondary_btn")
        self.output_btn.setCursor(Qt.PointingHandCursor)
        self.output_btn.clicked.connect(self.on_output_btn_clicked)
        options.addWidget(self.output_btn)
        options.addStretch()
        layout.addLayout(options, 1, 0)

        self.profile_hint = QLabel()
        self.profile_hint.setObjectName("muted_label")
        self.profile_hint.setWordWrap(True)
        layout.addWidget(self.profile_hint, 2, 0)

        # Row 3 — results table.
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            [self.tr("File"), self.tr("Status"), self.tr("Removed"), self.tr("Remaining risk")]
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        table.setToolTip(self.tr("Double-click a row to compare before / after"))
        table.itemDoubleClicked.connect(self.on_removed_table_data_itemDoubleClicked)
        layout.addWidget(table, 3, 0)

        self._progress = QProgressBar()
        self._progress.setObjectName("remove_progress")
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress, 4, 0)

        self._empty_state = QLabel(self.tr("Drop files or a folder here, or browse, then click Remove."))
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._empty_state.setObjectName("empty_state_label")
        layout.addWidget(self._empty_state, 5, 0)

        self.reload_settings()

    # ------------------------------------------------------------------
    # Settings sync
    # ------------------------------------------------------------------

    def reload_settings(self) -> None:
        self.selection.reload_settings()
        index = self.profile_combo.findData(settings.get("profile"))
        self.profile_combo.setCurrentIndex(max(index, 0))
        self.copy_check.blockSignals(True)
        self.copy_check.setChecked(settings.get("output_mode"))
        self.copy_check.blockSignals(False)
        self._refresh_output_label()
        self._refresh_profile_hint()

    def _refresh_output_label(self) -> None:
        folder = settings.get("output_dir")
        self.output_btn.setText(Path(folder).name or folder if folder else self.tr("Choose folder…"))
        self.output_btn.setToolTip(folder or self.tr("Choose where cleaned copies are written"))
        self.output_btn.setEnabled(self.copy_check.isChecked())

    def _refresh_profile_hint(self) -> None:
        pid = self.profile_combo.currentData()
        self.customize_btn.setVisible(pid == CUSTOM)
        if pid == CUSTOM:
            if self._custom_keys is not None and self._custom_keys_path == self._current_path():
                text = self.tr("%1 tag(s) hand-picked for this file.").replace("%1", str(len(self._custom_keys)))
            else:
                cats = settings.get("custom_categories")
                names = ", ".join(
                    QCoreApplication.translate("risk", risk.CATEGORIES[c]) for c in cats if c in risk.CATEGORIES
                )
                text = self.tr("Categories: %1").replace("%1", names or self.tr("none selected"))
        else:
            text = QCoreApplication.translate("profiles", profiles.get(pid).description)
        self.profile_hint.setText(text)

    def _current_path(self) -> str:
        return self._ui.remove_file_path.text().strip()

    def _current_profile(self) -> tuple[profiles.Profile | None, list[str] | None]:
        pid = self.profile_combo.currentData()
        if pid != CUSTOM:
            return profiles.get(pid), None
        if self._custom_keys is not None and self._custom_keys_path == self._current_path():
            return None, list(self._custom_keys)
        cats = {c for c in settings.get("custom_categories") if c in risk.CATEGORIES}
        return profiles.custom(cats), None

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_remove_browse_btn_clicked(self) -> None:
        self.selection.browse()
        self._refresh_profile_hint()

    def on_profile_combo_activated(self, _index: int) -> None:
        pid = self.profile_combo.currentData()
        settings.set("profile", pid)
        if pid == CUSTOM and not settings.get("custom_categories") and self._custom_keys is None:
            self.on_customize_btn_clicked()
        self._refresh_profile_hint()

    def on_customize_btn_clicked(self) -> None:
        path = self._current_path()
        metadata = None
        if path and not self.selection.is_batch() and Path(path).is_file():
            metadata = Extractor.single_image_extractor(path)
        selected = set(settings.get("custom_categories")) or {
            c for c, s in risk.CATEGORY_SEVERITY.items() if s >= risk.Severity.MEDIUM
        }
        dlg = CustomSelectionDialog(metadata, selected, self._parent)
        if dlg.exec() != QDialog.Accepted:
            return
        settings.set("custom_categories", sorted(dlg.categories()))
        keys = dlg.keys()
        if keys is not None:
            self._custom_keys, self._custom_keys_path = keys, path
        else:
            self._custom_keys = self._custom_keys_path = None
        self.profile_combo.setCurrentIndex(self.profile_combo.findData(CUSTOM))
        settings.set("profile", CUSTOM)
        self._refresh_profile_hint()

    def on_copy_check_toggled(self, checked: bool) -> None:
        settings.set("output_mode", checked)
        if checked and not settings.get("output_dir"):
            self.on_output_btn_clicked()
            if not settings.get("output_dir"):
                self.copy_check.setChecked(False)
                return
        self._refresh_output_label()

    def on_output_btn_clicked(self) -> None:
        start = settings.get("output_dir") or settings.get("last_dir") or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self._parent, self.tr("Save cleaned copies to"), start)
        if folder:
            settings.set("output_dir", folder)
        self._refresh_output_label()

    def on_remove_btn_clicked(self) -> None:
        self._start(export=None)

    def on_export_and_remove_btn_clicked(self) -> None:
        if not self._current_path():
            QMessageBox.warning(self._parent, self.tr("Nothing selected"), self.tr("Select a file or a folder first."))
            return
        target = ask_export_path(self._parent, f"{Path(self._current_path()).stem or 'metadata'}-before-cleaning")
        if target is None:
            return
        self._start(export=target)

    def on_removed_table_data_itemDoubleClicked(self, item: QTableWidgetItem) -> None:  # noqa: N802
        name_item = self._ui.removed_table_data.item(item.row(), 0)
        report = self._reports.get(name_item.data(Qt.UserRole)) if name_item else None
        if not report:
            return
        BeforeAfterDialog(name_item.text(), report.get("before"), report.get("after"), self._parent).exec()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def load_paths(self, paths: list[str]) -> bool:
        ok = self.selection.load_paths(paths, activate=False)
        self._refresh_profile_hint()
        return ok

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _start(self, export: tuple[str, str] | None) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._ui.removed_table_data.setRowCount(0)
        selection = self.selection.resolve()
        if selection is None:
            return
        path, is_batch, images = selection
        if is_batch and not images:
            QMessageBox.information(
                self._parent, self.tr("No supported files"), self.tr("This folder contains no supported files.")
            )
            return

        output_dir = settings.get("output_dir") if self.copy_check.isChecked() else None
        if self.copy_check.isChecked() and not output_dir:
            QMessageBox.warning(
                self._parent, self.tr("No output folder"), self.tr("Choose where to save the cleaned copies.")
            )
            return
        if output_dir is None and not confirm_in_place(self._parent, len(images) if is_batch else 1):
            return

        profile, keys = self._current_profile()
        if keys is not None and is_batch:
            profile, keys = profiles.custom(set(settings.get("custom_categories"))), None

        self._reports.clear()
        self._export_target = export
        self._worker = RemovalWorker(
            path, is_batch, images, profile=profile, keys=keys, output_dir=output_dir, verify=True
        )
        self._worker.report_ready.connect(self._on_report)
        self._worker.progress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished_all.connect(self._on_finished)
        self._ui.remove_btn.setEnabled(False)
        self._ui.export_and_remove_btn.setEnabled(False)
        self._empty_state.hide()
        self._progress.setRange(0, len(images) if is_batch and len(images) > 1 else 0)
        self._progress.setValue(0)
        self._progress.show()
        self._worker.start()

    # ------------------------------------------------------------------
    # Worker slots
    # ------------------------------------------------------------------

    def _on_report(self, name: str, report: dict) -> None:
        self._reports[name] = report
        table = self._ui.removed_table_data
        row = table.rowCount()
        table.insertRow(row)
        name_item = QTableWidgetItem(name if self.selection.is_batch() else Path(name).name)
        name_item.setData(Qt.UserRole, name)
        tooltip = name if report.get("target") in (None, name) else f"{name}\n→ {report['target']}"
        name_item.setToolTip(tooltip)
        table.setItem(row, 0, name_item)
        ok = bool(report["status"])
        status = QTableWidgetItem(self.tr("Done") if ok else self.tr("Error"))
        status.setForeground(QColor(theme.color("low" if ok else "high")))
        table.setItem(row, 1, status)
        diff = report.get("diff") or {}
        table.setItem(row, 2, QTableWidgetItem(str(len(diff.get("removed", []))) if ok else "—"))
        if ok:
            residual = risk.assess({k: "" for k in diff.get("remaining", [])})
            item = QTableWidgetItem(risk_summary(residual))
            color = severity_color(residual.level)
            if color:
                item.setForeground(color)
        else:
            item = QTableWidgetItem("—")
        table.setItem(row, 3, item)

    def _on_progress(self, current: int, total: int) -> None:
        if total > 1:
            self._progress.setRange(0, total)
            self._progress.setValue(current)

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self._parent, self.tr("Removal failed"), message)

    def _on_finished(self) -> None:
        table = self._ui.removed_table_data
        self._ui.remove_btn.setEnabled(True)
        self._ui.export_and_remove_btn.setEnabled(True)
        self._progress.hide()
        self._empty_state.setVisible(table.rowCount() == 0)

        if self._export_target and self._reports:
            path, fmt = self._export_target
            try:
                exporters.export({n: r.get("before") for n, r in self._reports.items()}, path, fmt)
            except OSError as exc:
                QMessageBox.warning(
                    self._parent,
                    self.tr("Export failed"),
                    self.tr("Could not save the file:\n%1").replace("%1", str(exc)),
                )
        self._export_target = None

        failures = [n for n, r in self._reports.items() if not r["status"]]
        if failures:
            QMessageBox.warning(
                self._parent,
                self.tr("Some files were not cleaned"),
                self.tr("%1 file(s) could not be cleaned (unsupported format or read-only):\n%2")
                .replace("%1", str(len(failures)))
                .replace("%2", "\n".join(failures[:20])),
            )
        elif self.copy_check.isChecked() and self._reports:
            box = QMessageBox(self._parent)
            box.setWindowTitle(self.tr("Done"))
            box.setText(self.tr("Cleaned copies saved to:\n%1").replace("%1", settings.get("output_dir")))
            open_btn = box.addButton(self.tr("Open folder"), QMessageBox.ActionRole)
            box.addButton(QMessageBox.Ok)
            box.exec()
            if box.clickedButton() is open_btn:
                QDesktopServices.openUrl(QUrl.fromLocalFile(settings.get("output_dir")))
