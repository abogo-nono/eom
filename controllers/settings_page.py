"""SettingsController — builds the Settings page (appearance, behaviour, privacy, integration)."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
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

LANGUAGES = (("system", "System default"), ("en", "English"), ("fr", "Français"))


class SettingsController(QObject):
    """Owns the Settings page widget.

    Signals
    -------
    theme_changed(name)      user picked another theme (applied immediately)
    language_changed(code)   user picked another language (applies after restart)
    settings_changed()       any behaviour setting changed; pages should reload
    """

    theme_changed = Signal(str)
    language_changed = Signal(str)
    settings_changed = Signal()

    def __init__(self, page: QWidget, parent: QWidget) -> None:
        super().__init__(parent)
        self._parent = parent
        self.page = page
        page.setObjectName("settings_page")
        self._checker: updater.UpdateChecker | None = None

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("settings_scroll")
        scroll.setWidgetResizable(True)
        contents = QWidget()
        contents.setObjectName("settings_contents")
        scroll.setWidget(contents)
        outer.addWidget(scroll)

        root = QVBoxLayout(contents)
        root.setContentsMargins(40, 24, 40, 24)
        root.setSpacing(12)
        title = QLabel(self.tr("Settings"))
        title.setObjectName("page_title")
        root.addWidget(title)

        # -- Appearance ------------------------------------------------------
        box = QGroupBox(self.tr("Appearance"))
        form = QFormLayout(box)
        self.theme_combo = QComboBox()
        for value, label in (
            ("dark", self.tr("Dark")),
            ("light", self.tr("Light")),
            ("system", self.tr("Follow system")),
        ):
            self.theme_combo.addItem(label, value)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(settings.get("theme"))))
        self.theme_combo.activated.connect(self.on_theme_combo_activated)
        form.addRow(self.tr("Theme"), self.theme_combo)

        self.language_combo = QComboBox()
        for code, label in LANGUAGES:
            self.language_combo.addItem(self.tr("System default") if code == "system" else label, code)
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(settings.get("language"))))
        self.language_combo.activated.connect(self.on_language_combo_activated)
        form.addRow(self.tr("Language"), self.language_combo)
        self.language_note = QLabel(self.tr("Restart EOM to apply a new language."))
        self.language_note.setObjectName("muted_label")
        self.language_note.hide()
        form.addRow("", self.language_note)
        root.addWidget(box)

        # -- Cleaning --------------------------------------------------------
        box = QGroupBox(self.tr("Cleaning"))
        form = QFormLayout(box)
        self.profile_combo = QComboBox()
        for profile in profiles.PROFILES.values():
            self.profile_combo.addItem(QCoreApplication.translate("profiles", profile.name), profile.id)
        self.profile_combo.addItem(self.tr("Custom selection"), "custom")
        self.profile_combo.activated.connect(lambda _i: self._set("profile", self.profile_combo.currentData()))
        form.addRow(self.tr("Default profile"), self.profile_combo)

        self.recursive_check = QCheckBox(self.tr("Include sub-folders when a folder is selected"))
        self.recursive_check.toggled.connect(lambda v: self._set("recursive", v))
        form.addRow(self.recursive_check)

        self.copy_check = QCheckBox(self.tr("Save cleaned / edited copies instead of modifying originals"))
        self.copy_check.toggled.connect(lambda v: self._set("output_mode", v))
        form.addRow(self.copy_check)

        row = QHBoxLayout()
        self.output_label = QLabel()
        self.output_label.setObjectName("muted_label")
        self.output_label.setWordWrap(True)
        row.addWidget(self.output_label, 1)
        choose = QPushButton(self.tr("Choose…"))
        choose.clicked.connect(self.on_choose_output_clicked)
        row.addWidget(choose)
        form.addRow(self.tr("Copies folder"), row)

        self.confirm_check = QCheckBox(self.tr("Ask before modifying original files"))
        self.confirm_check.toggled.connect(lambda v: self._set("confirm_in_place", v))
        form.addRow(self.confirm_check)
        root.addWidget(box)

        # -- Privacy & network ----------------------------------------------
        box = QGroupBox(self.tr("Privacy && network"))
        form = QFormLayout(box)
        note = QLabel(
            self.tr("EOM works fully offline. These options are the only network access, and are off by default.")
        )
        note.setObjectName("muted_label")
        note.setWordWrap(True)
        form.addRow(note)
        self.map_check = QCheckBox(self.tr("Load map tiles from OpenStreetMap for geotagged files"))
        self.map_check.toggled.connect(lambda v: self._set("allow_map_tiles", v))
        form.addRow(self.map_check)
        self.update_check = QCheckBox(self.tr("Check GitHub for a new version at startup"))
        self.update_check.toggled.connect(lambda v: self._set("check_updates", v))
        form.addRow(self.update_check)
        row = QHBoxLayout()
        self.check_now_btn = QPushButton(self.tr("Check now"))
        self.check_now_btn.clicked.connect(self.on_check_now_clicked)
        row.addWidget(self.check_now_btn)
        self.update_status = QLabel()
        self.update_status.setObjectName("muted_label")
        self.update_status.setOpenExternalLinks(True)
        row.addWidget(self.update_status, 1)
        form.addRow(row)
        root.addWidget(box)

        # -- Integration -----------------------------------------------------
        box = QGroupBox(self.tr("File manager integration"))
        form = QFormLayout(box)
        self.integration_status = QLabel()
        self.integration_status.setObjectName("muted_label")
        self.integration_status.setWordWrap(True)
        form.addRow(self.integration_status)
        row = QHBoxLayout()
        self.install_btn = QPushButton(self.tr("Add to right-click menu"))
        self.install_btn.clicked.connect(self.on_install_clicked)
        self.uninstall_btn = QPushButton(self.tr("Remove from right-click menu"))
        self.uninstall_btn.clicked.connect(self.on_uninstall_clicked)
        row.addWidget(self.install_btn)
        row.addWidget(self.uninstall_btn)
        row.addStretch()
        form.addRow(row)
        root.addWidget(box)

        # -- History ---------------------------------------------------------
        box = QGroupBox(self.tr("History"))
        form = QFormLayout(box)
        clear = QPushButton(self.tr("Clear recent files"))
        clear.clicked.connect(self.on_clear_recent_clicked)
        form.addRow(clear)
        root.addWidget(box)
        root.addStretch()

        self.reload()

    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Refresh every control from QSettings (other pages may have changed them)."""
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
        self.profile_combo.setCurrentIndex(max(0, self.profile_combo.findData(settings.get("profile"))))
        folder = settings.get("output_dir")
        self.output_label.setText(folder or self.tr("Not set"))
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

    def on_choose_output_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self._parent, self.tr("Save copies to"), settings.get("output_dir"))
        if folder:
            self._set("output_dir", folder)
            self.output_label.setText(folder)

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
            QMessageBox.warning(self._parent, self.tr("Integration failed"), str(exc))
            return
        self._refresh_integration()
        QMessageBox.information(
            self._parent,
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
        QMessageBox.information(
            self._parent, self.tr("History cleared"), self.tr("The recent files list is now empty.")
        )
