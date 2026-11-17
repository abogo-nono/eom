"""Settings page: appearance, cleaning defaults, privacy & network, integration, history."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import integration
import profiles
import settings
import updater
from widgets import styled

LANGUAGES = (("system", "System default"), ("en", "English"), ("fr", "Français"))


class SettingsView(QWidget):
    """Settings page.

    Signals
    -------
    theme_changed(name)      user picked another theme (applied immediately)
    language_changed(code)   user picked another language (applies after restart)
    settings_changed()       a behaviour setting changed; the workspace should reload
    """

    theme_changed = Signal(str)
    language_changed = Signal(str)
    settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checker: updater.UpdateChecker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        contents = QWidget()
        scroll.setWidget(contents)
        column = QHBoxLayout(contents)
        column.addStretch(1)
        body = QWidget()
        body.setMaximumWidth(760)
        column.addWidget(body, 6)
        column.addStretch(1)

        root = QVBoxLayout(body)
        root.setContentsMargins(8, 28, 8, 28)
        root.setSpacing(14)
        root.addWidget(styled(QLabel(self.tr("Settings")), role="title"))

        # -- Appearance ------------------------------------------------------
        card, grid = self._card(self.tr("Appearance"))
        self.theme_combo = QComboBox()
        for value, label in (
            ("dark", self.tr("Dark")),
            ("light", self.tr("Light")),
            ("system", self.tr("Follow system")),
        ):
            self.theme_combo.addItem(label, value)
        self.theme_combo.activated.connect(self.on_theme_combo_activated)
        self._row(grid, 0, self.tr("Theme"), self.theme_combo)
        self.language_combo = QComboBox()
        for code, label in LANGUAGES:
            self.language_combo.addItem(self.tr("System default") if code == "system" else label, code)
        self.language_combo.activated.connect(self.on_language_combo_activated)
        self._row(grid, 1, self.tr("Language"), self.language_combo)
        self.language_note = styled(QLabel(self.tr("Restart EOM to apply the new language.")), badge="info")
        self.language_note.hide()
        grid.addWidget(self.language_note, 2, 1, Qt.AlignLeft)
        root.addWidget(card)

        # -- Cleaning --------------------------------------------------------
        card, grid = self._card(self.tr("Cleaning"))
        self.profile_combo = QComboBox()
        for profile in profiles.PROFILES.values():
            self.profile_combo.addItem(QCoreApplication.translate("profiles", profile.name), profile.id)
        self.profile_combo.addItem(self.tr("Custom selection"), "custom")
        self.profile_combo.activated.connect(lambda _i: self._set("profile", self.profile_combo.currentData()))
        self._row(grid, 0, self.tr("Default profile"), self.profile_combo)

        self.recursive_check = QCheckBox(self.tr("Include sub-folders when adding a folder"))
        self.recursive_check.toggled.connect(lambda v: self._set("recursive", v))
        grid.addWidget(self.recursive_check, 1, 0, 1, 2)
        self.copy_check = QCheckBox(self.tr("Save cleaned / edited copies instead of modifying originals"))
        self.copy_check.toggled.connect(self.on_copy_check_toggled)
        grid.addWidget(self.copy_check, 2, 0, 1, 2)
        row = QHBoxLayout()
        self.output_label = styled(QLabel(), role="muted")
        self.output_label.setWordWrap(True)
        row.addWidget(self.output_label, 1)
        choose = QPushButton(self.tr("Choose…"))
        choose.clicked.connect(self.on_choose_output_clicked)
        row.addWidget(choose)
        self._row(grid, 3, self.tr("Copies folder"), row)
        self.confirm_check = QCheckBox(self.tr("Ask before modifying original files"))
        self.confirm_check.toggled.connect(lambda v: self._set("confirm_in_place", v))
        grid.addWidget(self.confirm_check, 4, 0, 1, 2)
        root.addWidget(card)

        # -- Privacy & network ----------------------------------------------
        card, grid = self._card(self.tr("Privacy && network"))
        note = styled(
            QLabel(
                self.tr("EOM works fully offline. These options are the only network access, and are off by default.")
            ),
            role="muted",
        )
        note.setWordWrap(True)
        grid.addWidget(note, 0, 0, 1, 2)
        self.map_check = QCheckBox(self.tr("Load map tiles from OpenStreetMap for geotagged files"))
        self.map_check.toggled.connect(lambda v: self._set("allow_map_tiles", v))
        grid.addWidget(self.map_check, 1, 0, 1, 2)
        self.update_check = QCheckBox(self.tr("Check GitHub for a new version at startup"))
        self.update_check.toggled.connect(lambda v: self._set("check_updates", v))
        grid.addWidget(self.update_check, 2, 0, 1, 2)
        row = QHBoxLayout()
        self.check_now_btn = QPushButton(self.tr("Check now"))
        self.check_now_btn.clicked.connect(self.on_check_now_clicked)
        row.addWidget(self.check_now_btn)
        self.update_status = styled(QLabel(), role="muted")
        self.update_status.setOpenExternalLinks(True)
        self.update_status.setWordWrap(True)
        row.addWidget(self.update_status, 1)
        grid.addLayout(row, 3, 0, 1, 2)
        root.addWidget(card)

        # -- Integration -----------------------------------------------------
        card, grid = self._card(self.tr("File manager integration"))
        self.integration_status = styled(QLabel(), role="muted")
        self.integration_status.setWordWrap(True)
        grid.addWidget(self.integration_status, 0, 0, 1, 2)
        row = QHBoxLayout()
        self.install_btn = QPushButton(self.tr("Add to right-click menu"))
        self.install_btn.clicked.connect(self.on_install_clicked)
        self.uninstall_btn = QPushButton(self.tr("Remove from right-click menu"))
        self.uninstall_btn.clicked.connect(self.on_uninstall_clicked)
        row.addWidget(self.install_btn)
        row.addWidget(self.uninstall_btn)
        row.addStretch()
        grid.addLayout(row, 1, 0, 1, 2)
        root.addWidget(card)

        # -- History ---------------------------------------------------------
        card, grid = self._card(self.tr("History"))
        row = QHBoxLayout()
        row.addWidget(
            styled(QLabel(self.tr("Recently opened files and folders are listed on the start screen.")), role="muted"),
            1,
        )
        clear = QPushButton(self.tr("Clear recent files"))
        clear.clicked.connect(self.on_clear_recent_clicked)
        row.addWidget(clear)
        grid.addLayout(row, 0, 0, 1, 2)
        root.addWidget(card)
        root.addStretch()

        for widget in (self.check_now_btn, self.install_btn, self.uninstall_btn, choose, clear):
            widget.setCursor(Qt.PointingHandCursor)
        self.reload()

    # ------------------------------------------------------------------

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QGridLayout]:
        card = styled(QFrame(), panel="true")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(styled(QLabel(title.replace("&&", "&")), role="h2"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return card, grid

    @staticmethod
    def _row(grid: QGridLayout, row: int, label: str, field) -> None:
        grid.addWidget(styled(QLabel(label), role="muted"), row, 0)
        if isinstance(field, QWidget):
            grid.addWidget(field, row, 1)
        else:
            grid.addLayout(field, row, 1)

    def reload(self) -> None:
        """Refresh every control from QSettings (the workspace may have changed them)."""
        for widget, key in (
            (self.recursive_check, "recursive"),
            (self.copy_check, "output_mode"),
            (self.confirm_check, "confirm_in_place"),
            (self.map_check, "allow_map_tiles"),
            (self.update_check, "check_updates"),
        ):
            widget.blockSignals(True)
            widget.setChecked(settings.get(key))
            widget.blockSignals(False)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(settings.get("theme"))))
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(settings.get("language"))))
        self.profile_combo.setCurrentIndex(max(0, self.profile_combo.findData(settings.get("profile"))))
        self.output_label.setText(settings.get("output_dir") or self.tr("Not set"))
        self._refresh_integration()

    def _set(self, key: str, value) -> None:
        settings.set(key, value)
        self.settings_changed.emit()

    def _refresh_integration(self) -> None:
        if not integration.supported():
            self.integration_status.setText(
                self.tr(
                    "Not available on this system. On macOS, create a Quick Action in Automator that runs: %1"
                ).replace("%1", " ".join(integration.launch_command()) + " --extract")
            )
            self.install_btn.setEnabled(False)
            self.uninstall_btn.setEnabled(False)
            return
        installed = integration.is_installed()
        where = self.tr("Windows Explorer") if sys.platform == "win32" else self.tr("Files/Nautilus, Nemo and Dolphin")
        self.integration_status.setText(
            (
                self.tr("Installed for %1.") if installed else self.tr("Adds “Inspect” and “Clean” entries to %1.")
            ).replace("%1", where)
        )
        self.install_btn.setEnabled(not installed)
        self.uninstall_btn.setEnabled(installed)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_theme_combo_activated(self, _index: int) -> None:
        value = self.theme_combo.currentData()
        settings.set("theme", value)
        self.theme_changed.emit(value)

    def on_language_combo_activated(self, _index: int) -> None:
        value = self.language_combo.currentData()
        settings.set("language", value)
        self.language_note.show()
        self.language_changed.emit(value)

    def on_copy_check_toggled(self, checked: bool) -> None:
        if checked and not settings.get("output_dir"):
            self.on_choose_output_clicked()
            if not settings.get("output_dir"):
                self.copy_check.setChecked(False)
                return
        self._set("output_mode", checked)

    def on_choose_output_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self.tr("Save copies to"), settings.get("output_dir"))
        if folder:
            settings.set("output_dir", folder)
            self.output_label.setText(folder)
            self.settings_changed.emit()

    def on_check_now_clicked(self) -> None:
        self.check_now_btn.setEnabled(False)
        self.update_status.setText(self.tr("Checking…"))
        self._checker = updater.UpdateChecker(self)
        self._checker.finished.connect(self._on_update_result)
        self._checker.check()

    def _on_update_result(self, tag: str, url: str, error: str) -> None:
        self.check_now_btn.setEnabled(True)
        if error:
            self.update_status.setText(self.tr("Could not check: %1").replace("%1", error))
        elif tag:
            self.update_status.setText(
                self.tr("Version %1 is available — <a href='%2'>download</a>").replace("%1", tag).replace("%2", url)
            )
        else:
            self.update_status.setText(self.tr("You have the latest version (%1).").replace("%1", updater.__version__))

    def on_install_clicked(self) -> None:
        try:
            created = integration.install()
        except OSError as exc:
            QMessageBox.warning(self, self.tr("Integration failed"), str(exc))
            return
        self._refresh_integration()
        QMessageBox.information(
            self,
            self.tr("Integration added"),
            self.tr(
                "Right-click a file and look for “Inspect metadata with EOM”. "
                "You may need to restart your file manager.\n\nCreated:\n%1"
            ).replace("%1", "\n".join(created)),
        )

    def on_uninstall_clicked(self) -> None:
        integration.uninstall()
        self._refresh_integration()

    def on_clear_recent_clicked(self) -> None:
        settings.clear_recent()
        self.settings_changed.emit()
