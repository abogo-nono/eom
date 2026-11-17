"""EOM – Eye On Metadata – application entry point.

MainWindow is intentionally minimal: window chrome, page navigation, drag &
drop, and instantiation of the feature controllers.

``python main.py``                       → GUI
``python main.py photo.jpg``             → GUI with the file loaded on the Extract page
``python main.py --remove a.jpg b.pdf``  → GUI with the files loaded on the Remove page
``python main.py extract photo.jpg``     → command-line interface (see cli.py)
"""

from __future__ import annotations

import platform
import sys
from enum import IntEnum
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import cli
import exiftool_backend
import i18n
import settings
import theme
import updater
from app_ui import Ui_MainWindow
from controllers.extraction import ExtractionController
from controllers.removal import RemovalController
from controllers.settings_page import SettingsController
from version import __version__


def _resource_path(rel: str) -> str:
    """Resolve a resource path for both dev and PyInstaller frozen modes."""
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
    return str(base / rel)


class PageIndex(IntEnum):
    HOME = 0
    EXTRACT = 1
    REMOVE = 2
    REPORT = 3
    SETTINGS = 4


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(_resource_path("images/app-logo.ico")))

        # Frameless window — custom drag + chrome buttons.
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.draggable = True
        self.old_pos = None
        self.ui.header_widget.mousePressEvent = self.mouse_press_event
        self.ui.header_widget.mouseMoveEvent = self.mouse_move_event
        self.ui.header_widget.mouseReleaseEvent = self.mouse_release_event

        self.update_maximize_button_icon()
        self.ui.minimize_btn.clicked.connect(self.showMinimized)
        self.ui.maximize_btn.clicked.connect(self.toggle_maximized)
        self.ui.close_btn.clicked.connect(self.close)

        self.setWindowTitle("Eye On Metadata")
        self.ui.title_label.setText("Eye On Metadata")  # app.ui says "Eyes On Metadata"
        self.setMinimumSize(900, 620)
        self.ui.eom_version_label.setText(self.tr("E.O.M v%1 — open source, MIT licence").replace("%1", __version__))

        # Default page.
        self.ui.stackedWidget.setCurrentIndex(PageIndex.HOME)
        self.ui.menu_docs_btn.setChecked(True)

        # Page navigation.
        self.ui.about_btn.clicked.connect(self.on_about_btn_clicked)
        self.ui.menu_extract_btn.clicked.connect(self.on_menu_extract_btn_toggled)
        self.ui.menu_remove_btn.clicked.connect(self.on_menu_remove_btn_toggled)
        self.ui.menu_docs_btn.clicked.connect(self.on_menu_docs_btn_toggled)
        self.ui.menu_report_btn.clicked.connect(self.on_menu_report_btn_toggled)

        # Feature controllers — they wire their own signals.
        self._extraction = ExtractionController(self.ui, self)
        self._removal = RemovalController(self.ui, self)
        self._setup_settings_page()
        self._setup_home_page()
        self._setup_report_page()

        # Drag & drop anywhere on the window. Line edits and tables would
        # otherwise swallow the drop as text.
        self.setAcceptDrops(True)
        for widget in (
            self.ui.extract_file_path,
            self.ui.remove_file_path,
            self.ui.extracted_table_data,
            self.ui.removed_table_data,
        ):
            widget.setAcceptDrops(False)

        # ExifTool status label — inserted left of the window chrome buttons.
        self._exiftool_label = QLabel(self.ui.header_widget)
        available = exiftool_backend.is_available()
        self._exiftool_label.setObjectName("exiftool_ok" if available else "exiftool_missing")
        self._exiftool_label.setText("ExifTool ✓" if available else "ExifTool ✗")
        self._exiftool_label.setToolTip(
            self.tr("ExifTool is installed and active as the primary metadata backend.")
            if available
            else self.tr("ExifTool not found in PATH. Using built-in backends (Pillow / mutagen / pypdf).")
        )
        # Insert before the chrome-buttons layout (index 1 in horizontalLayout_6).
        self.ui.horizontalLayout_6.insertWidget(1, self._exiftool_label)

        # "Update available" link — only shown after an opt-in check finds one.
        self._update_label = QLabel(self.ui.header_widget)
        self._update_label.setObjectName("exiftool_missing")
        self._update_label.setOpenExternalLinks(True)
        self._update_label.hide()
        self.ui.horizontalLayout_6.insertWidget(1, self._update_label)
        self._update_checker: updater.UpdateChecker | None = None
        if settings.get("check_updates"):
            QTimer.singleShot(1500, self._check_updates)

    # ------------------------------------------------------------------
    # Window chrome
    # ------------------------------------------------------------------

    def mouse_press_event(self, event) -> None:
        # startSystemMove() delegates to the window manager — works on Wayland,
        # X11, Windows, and macOS. Falls back to manual delta on unsupported
        # platforms (e.g. offscreen in tests).
        if (
            event.button() == Qt.LeftButton
            and self.draggable
            and (not self.windowHandle() or not self.windowHandle().startSystemMove())
        ):
            self.old_pos = event.globalPosition().toPoint()

    def mouse_move_event(self, event) -> None:
        # Only reached when startSystemMove() was unavailable (fallback path).
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouse_release_event(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.old_pos = None

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.update_maximize_button_icon()

    def update_maximize_button_icon(self) -> None:
        icon = (
            ":/outline/icons/outline/minimize-2.svg" if self.isMaximized() else ":/outline/icons/outline/maximize-2.svg"
        )
        self.ui.maximize_btn.setIcon(QIcon(icon))

    # ------------------------------------------------------------------
    # Drag & drop / opening files
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 — Qt override
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            return
        event.acceptProposedAction()
        mode = "remove" if self.ui.stackedWidget.currentIndex() == PageIndex.REMOVE else "extract"
        self.open_paths(paths, mode)

    def open_paths(self, paths: list[str], mode: str = "extract") -> bool:
        """Load *paths* on the Extract page (and run it) or on the Remove page."""
        if mode == "remove":
            self.ui.menu_remove_btn.setChecked(True)
            self.on_menu_remove_btn_toggled()
            return self._removal.load_paths(paths)
        self.ui.menu_extract_btn.setChecked(True)
        self.on_menu_extract_btn_toggled()
        return self._extraction.load_paths(paths)

    # ------------------------------------------------------------------
    # Page navigation
    # ------------------------------------------------------------------

    def on_about_btn_clicked(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("About EOM"))
        dlg.setFixedSize(440, 340)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(10)

        title = QLabel("👁️ Eye On Metadata")
        title.setObjectName("about_title")
        layout.addWidget(title)

        version = QLabel(self.tr("v%1  ·  open-source  ·  MIT license").replace("%1", __version__))
        version.setObjectName("muted_label")
        layout.addWidget(version)

        sep = QLabel()
        sep.setObjectName("separator")
        layout.addWidget(sep)

        desc = QLabel(
            self.tr(
                "EOM reads, exports, cleans and edits metadata from your files — "
                "locally, with no upload, no account, no cloud.\n\n"
                "Supports JPEG · PNG · TIFF · WebP · GIF · HEIC · MP3 · FLAC · OGG · WAV · AIFF · "
                "M4A · WMA · MP4 · MOV · MKV · WebM · PDF · DOCX · XLSX · PPTX"
            )
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        links = QLabel(
            '<a href="https://github.com/abogo-nono/eom">GitHub repository</a>'
            "  ·  "
            '<a href="https://github.com/abogo-nono">Abogo Lincoln</a>'
        )
        links.setOpenExternalLinks(True)
        layout.addWidget(links)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        dlg.exec()

    def on_menu_home_btn_toggled(self) -> None:
        self.ui.stackedWidget.setCurrentIndex(PageIndex.HOME)

    def on_menu_extract_btn_toggled(self) -> None:
        self.ui.stackedWidget.setCurrentIndex(PageIndex.EXTRACT)

    def on_menu_remove_btn_toggled(self) -> None:
        self.ui.stackedWidget.setCurrentIndex(PageIndex.REMOVE)

    def on_menu_docs_btn_toggled(self) -> None:
        self.ui.stackedWidget.setCurrentIndex(PageIndex.HOME)

    def on_menu_report_btn_toggled(self) -> None:
        self.ui.stackedWidget.setCurrentIndex(PageIndex.REPORT)

    def on_menu_settings_btn_toggled(self) -> None:
        self._settings.reload()
        self.ui.stackedWidget.setCurrentIndex(PageIndex.SETTINGS)

    # ------------------------------------------------------------------
    # Settings page
    # ------------------------------------------------------------------

    def _setup_settings_page(self) -> None:
        page = QWidget()
        self.ui.stackedWidget.addWidget(page)  # index PageIndex.SETTINGS
        self._settings = SettingsController(page, self)
        self._settings.theme_changed.connect(self._on_theme_changed)
        self._settings.settings_changed.connect(self._extraction.reload_settings)
        self._settings.settings_changed.connect(self._removal.reload_settings)

        btn = QPushButton(self.tr("Settings"), self.ui.menu_widget)
        btn.setObjectName("menu_settings_btn")
        btn.setCursor(Qt.PointingHandCursor)
        icon = QIcon()
        icon.addFile(_resource_path("icons/light/settings.svg"), mode=QIcon.Normal, state=QIcon.Off)
        icon.addFile(_resource_path("icons/dark/settings.svg"), mode=QIcon.Normal, state=QIcon.On)
        btn.setIcon(icon)
        btn.setIconSize(self.ui.menu_report_btn.iconSize())
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.clicked.connect(self.on_menu_settings_btn_toggled)
        self.ui.verticalLayout.addWidget(btn)
        self.ui.menu_settings_btn = btn

    def _on_theme_changed(self, name: str) -> None:
        app = QApplication.instance()
        if app is not None:
            theme.apply(app, name)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _check_updates(self) -> None:
        self._update_checker = updater.UpdateChecker(self)
        self._update_checker.finished.connect(self._on_update_result)
        self._update_checker.check()

    def _on_update_result(self, tag: str, url: str, _error: str) -> None:
        if tag:
            self._update_label.setText(
                self.tr("<a href='%2'>Update available: %1</a>").replace("%1", tag).replace("%2", url)
            )
            self._update_label.show()

    # ------------------------------------------------------------------
    # Report page (built programmatically — app_ui.py page is empty)
    # ------------------------------------------------------------------

    def _setup_report_page(self) -> None:
        page = self.ui.report_page

        # Remove the stray generated label.
        for child in page.findChildren(QLabel):
            child.deleteLater()

        root = QVBoxLayout(page)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(14)

        title = QLabel(self.tr("Report a Bug"))
        title.setObjectName("page_title")
        root.addWidget(title)

        hint = QLabel(
            self.tr(
                "Include the system info below when opening a bug report — "
                "it helps reproduce the problem faster.\n"
                "Click ‘Open GitHub Issue’ to go straight to the new-issue form."
            )
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted_label")
        root.addWidget(hint)

        info_heading = QLabel(self.tr("System info"))
        info_heading.setObjectName("section_title")
        root.addWidget(info_heading)

        self._report_info_box = QPlainTextEdit(self._report_system_info())
        self._report_info_box.setObjectName("mono_box")
        self._report_info_box.setReadOnly(True)
        self._report_info_box.setMaximumHeight(110)
        root.addWidget(self._report_info_box)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        open_btn = QPushButton(self.tr("Open GitHub Issue"))
        open_btn.setObjectName("primary_btn")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/abogo-nono/eom/issues/new")))

        self._copy_btn = QPushButton(self.tr("Copy System Info"))
        self._copy_btn.setObjectName("secondary_btn")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.clicked.connect(self._on_copy_report_info)

        btn_row.addWidget(open_btn)
        btn_row.addWidget(self._copy_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)
        root.addStretch()

    @staticmethod
    def _report_system_info() -> str:
        exiftool_status = exiftool_backend._EXIFTOOL_PATH if exiftool_backend.is_available() else "not found"
        return "\n".join(
            [
                f"EOM version : v{__version__}",
                f"Python      : {sys.version.split()[0]}",
                f"Platform    : {platform.system()} {platform.release()} ({platform.machine()})",
                f"ExifTool    : {exiftool_status}",
            ]
        )

    def _on_copy_report_info(self) -> None:
        QGuiApplication.clipboard().setText(self._report_system_info())
        self._copy_btn.setText(self.tr("Copied!"))
        QTimer.singleShot(2000, lambda: self._copy_btn.setText(self.tr("Copy System Info")))

    # ------------------------------------------------------------------
    # Home page (replaces generated scroll area with a welcome screen)
    # ------------------------------------------------------------------

    def _setup_home_page(self) -> None:
        # Keep the original docScrollArea with its HTML how-to content.
        # Append the hero + feature cards below the existing label_4 content
        # inside scrollAreaWidgetContents (gridLayout_8).
        grid = self.ui.gridLayout_8  # row 0 already has label_4
        # app_ui.py sets an unscoped "background: transparent" on the scroll area,
        # which cascades to every child button. Scope it to the containers only.
        self.ui.docScrollArea.setStyleSheet("QScrollArea#docScrollArea { background: transparent; border: none; }")
        self.ui.scrollAreaWidgetContents.setStyleSheet("#scrollAreaWidgetContents { background: transparent; }")

        # ── Hero ──────────────────────────────────────────────────────
        hero_row = QHBoxLayout()
        hero_row.setContentsMargins(0, 24, 0, 8)
        hero_row.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(QIcon(_resource_path("images/app-logo.ico")).pixmap(56, 56))
        logo.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        hero_row.addWidget(logo)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        title = QLabel("Eye On Metadata")
        title.setObjectName("hero_title")
        tagline = QLabel(
            self.tr("Read · Export · Clean · Edit metadata — locally, privately. Drop files anywhere to start.")
        )
        tagline.setObjectName("muted_label")
        hero_text.addWidget(title)
        hero_text.addWidget(tagline)
        hero_row.addLayout(hero_text)
        hero_row.addStretch()

        grid.addLayout(hero_row, 1, 0)

        # ── Feature cards ─────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        cards_row.setContentsMargins(0, 8, 0, 24)
        cards_row.addWidget(
            self._make_feature_card(
                "🔍",
                self.tr("Extract"),
                self.tr(
                    "See every metadata field with a privacy-risk score, preview and map. Export to JSON, CSV or HTML."
                ),
                lambda: self.ui.menu_extract_btn.click(),
            )
        )
        cards_row.addWidget(
            self._make_feature_card(
                "🗑️",
                self.tr("Remove"),
                self.tr("Strip everything or only what matters (GPS, author, serials…), in place or as clean copies."),
                lambda: self.ui.menu_remove_btn.click(),
            )
        )
        cards_row.addWidget(
            self._make_feature_card(
                "⚙️",
                self.tr("Settings"),
                self.tr("Theme, language, default cleaning profile and right-click menu integration."),
                lambda: self.ui.menu_settings_btn.click(),
            )
        )
        grid.addLayout(cards_row, 2, 0)

    def _make_feature_card(self, icon_text: str, title: str, description: str, on_click) -> QFrame:
        card = QFrame()
        card.setObjectName("feature_card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon_text)
        icon_lbl.setObjectName("card_icon")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("card_title")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setObjectName("muted_label")
        layout.addWidget(desc_lbl)

        layout.addStretch()

        btn = QPushButton(self.tr("Open →"))
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(on_click)
        layout.addWidget(btn)

        return card


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_gui_args(argv: list[str]) -> tuple[str, list[str]]:
    """``[--extract|--remove] PATH...`` → ``(mode, paths)``; relative paths resolved against CWD."""
    mode = "extract"
    paths: list[str] = []
    for arg in argv:
        if arg in ("--extract", "--remove"):
            mode = arg[2:]
        elif not arg.startswith("-"):
            paths.append(str(Path(arg).expanduser().resolve()))
    return mode, paths


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and (argv[0] in cli.COMMANDS or argv[0] in ("-h", "--help", "--version")):
        return cli.main(argv)

    mode, paths = parse_gui_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Eye On Metadata")
    app.setApplicationVersion(__version__)
    i18n.install(app, settings.get("language"))
    theme.apply(app, settings.get("theme"))

    window = MainWindow()
    window.show()
    if paths:
        QTimer.singleShot(0, lambda: window.open_paths(paths, mode))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
