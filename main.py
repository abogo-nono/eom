"""EOM – Eye On Metadata – application entry point.

MainWindow is intentionally minimal: window chrome, page navigation,
and instantiation of the two feature controllers.
"""

from __future__ import annotations

import platform
import sys
from enum import IntEnum
from pathlib import Path

from PySide6.QtCore import QFile, Qt, QTextStream, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

import exiftool_backend
from app_ui import Ui_MainWindow
from controllers.extraction import ExtractionController
from controllers.removal import RemovalController


def _resource_path(rel: str) -> str:
    """Resolve a resource path for both dev and PyInstaller frozen modes."""
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
    return str(base / rel)


class PageIndex(IntEnum):
    HOME = 0
    EXTRACT = 1
    REMOVE = 2
    REPORT = 3


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
        self.setMinimumSize(850, 600)

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
        self._removal = RemovalController(self.ui, self, self._extraction.on_export_btn_clicked)
        self._setup_home_page()
        self._setup_report_page()

        # ExifTool status label — inserted left of the window chrome buttons.
        self._exiftool_label = QLabel(self.ui.header_widget)
        if exiftool_backend.is_available():
            self._exiftool_label.setText("ExifTool ✓")
            self._exiftool_label.setStyleSheet("color: #4caf50; font-size: 11px; padding-right: 8px;")
        else:
            self._exiftool_label.setText("ExifTool ✗")
            self._exiftool_label.setStyleSheet("color: #ff9800; font-size: 11px; padding-right: 8px;")
        self._exiftool_label.setToolTip(
            "ExifTool is installed and active as the primary metadata backend."
            if exiftool_backend.is_available()
            else "ExifTool not found in PATH. Using built-in backends (Pillow / mutagen / pypdf)."
        )
        # Insert before the chrome-buttons layout (index 1 in horizontalLayout_6).
        self.ui.horizontalLayout_6.insertWidget(1, self._exiftool_label)

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
    # Page navigation
    # ------------------------------------------------------------------

    def on_about_btn_clicked(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("About EOM")
        dlg.setFixedSize(420, 320)
        dlg.setStyleSheet("background: #0f1515; color: #e0e0e0;")

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(10)

        # Title row
        title = QLabel("👁️ Eye On Metadata")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #00bcd4;")
        layout.addWidget(title)

        version = QLabel("v2  ·  open-source  ·  MIT license")
        version.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(version)

        # Separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #1e2c2c; margin: 4px 0;")
        layout.addWidget(sep)

        # Description
        desc = QLabel(
            "EOM reads, exports, and strips metadata from your files — "
            "locally, with no upload, no account, no cloud.\n\n"
            "Supports JPEG · PNG · TIFF · MP3 · FLAC · OGG · WAV · AIFF · "
            "M4A · WMA · MP4 · MKV · WebM · PDF"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #ccc; line-height: 1.5;")
        layout.addWidget(desc)

        layout.addStretch()

        # Links row
        links = QLabel(
            '<a href="https://github.com/abogo-nono/eom" style="color:#00bcd4;">GitHub repository</a>'
            "  ·  "
            '<a href="https://github.com/abogo-nono" style="color:#00bcd4;">Abogo Lincoln</a>'
        )
        links.setOpenExternalLinks(True)
        links.setStyleSheet("font-size: 12px;")
        layout.addWidget(links)

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.setStyleSheet(
            "QPushButton { background: #00bcd4; color: #0b0f0f; font-weight: 600;"
            " padding: 6px 20px; border-radius: 4px; border: none; }"
            "QPushButton:hover { background: #00acc1; }"
        )
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

        title = QLabel("Report a Bug")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        hint = QLabel(
            "Include the system info below when opening a bug report \u2014 "
            "it helps reproduce the problem faster.\n"
            "Click \u2018Open GitHub Issue\u2019 to go straight to the new-issue form."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #aaa; font-size: 13px;")
        root.addWidget(hint)

        info_heading = QLabel("System info")
        info_heading.setStyleSheet("font-size: 12px; color: #888; margin-top: 6px;")
        root.addWidget(info_heading)

        self._report_info_box = QPlainTextEdit(self._report_system_info())
        self._report_info_box.setReadOnly(True)
        self._report_info_box.setMaximumHeight(110)
        self._report_info_box.setStyleSheet(
            "font-family: monospace; font-size: 12px; background: #131a1a; border-radius: 4px; padding: 8px;"
        )
        root.addWidget(self._report_info_box)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        open_btn = QPushButton("Open GitHub Issue")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setStyleSheet(
            "QPushButton { background: #00bcd4; color: #0b0f0f; font-weight: 600;"
            " padding: 8px 18px; border-radius: 4px; border: none; }"
            "QPushButton:hover { background: #00acc1; }"
        )
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/abogo-nono/eom/issues/new")))

        self._copy_btn = QPushButton("Copy System Info")
        self._copy_btn.setCursor(Qt.PointingHandCursor)
        self._copy_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #00bcd4; font-weight: 500;"
            " padding: 8px 18px; border-radius: 4px; border: 1px solid #00bcd4; }"
            "QPushButton:hover { background: rgba(0, 188, 212, 0.1); }"
        )
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
                "EOM version : v2",
                f"Python      : {sys.version.split()[0]}",
                f"Platform    : {platform.system()} {platform.release()} ({platform.machine()})",
                f"ExifTool    : {exiftool_status}",
            ]
        )

    def _on_copy_report_info(self) -> None:
        QGuiApplication.clipboard().setText(self._report_system_info())
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(2000, lambda: self._copy_btn.setText("Copy System Info"))

    # ------------------------------------------------------------------
    # Home page (replaces generated scroll area with a welcome screen)
    # ------------------------------------------------------------------

    def _setup_home_page(self) -> None:
        # Detach the generated scroll area, leaving gridLayout_7 free.
        self.ui.gridLayout_7.removeWidget(self.ui.docScrollArea)
        self.ui.docScrollArea.setParent(None)

        root = QVBoxLayout()
        root.setContentsMargins(60, 50, 60, 40)
        root.setSpacing(0)
        self.ui.gridLayout_7.addLayout(root, 0, 0)

        # ── Hero ──────────────────────────────────────────────────────
        logo = QLabel()
        logo.setPixmap(QIcon(_resource_path("images/app-logo.ico")).pixmap(72, 72))
        logo.setAlignment(Qt.AlignCenter)
        root.addWidget(logo)

        root.addSpacing(14)

        title = QLabel("Eye On Metadata")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 26px; font-weight: 700; color: #33c6cb;")
        root.addWidget(title)

        tagline = QLabel("Read · Export · Strip metadata — locally, privately.")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setStyleSheet("font-size: 13px; color: #788596; margin-top: 4px;")
        root.addWidget(tagline)

        root.addSpacing(40)

        # ── Feature cards ─────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        cards_row.addWidget(
            self._make_feature_card(
                "🔍",
                "Extract",
                "View every metadata field from images, audio, video and PDF files.",
                lambda: self.ui.menu_extract_btn.click(),
            )
        )
        cards_row.addWidget(
            self._make_feature_card(
                "🗑️",
                "Remove",
                "Strip all metadata from a single file or an entire folder at once.",
                lambda: self.ui.menu_remove_btn.click(),
            )
        )
        cards_row.addWidget(
            self._make_feature_card(
                "🐛",
                "Report a Bug",
                "Found something wrong? Help improve EOM by opening a GitHub issue.",
                lambda: self.ui.menu_report_btn.click(),
            )
        )
        root.addLayout(cards_row)
        root.addStretch()

    def _make_feature_card(self, icon_text: str, title: str, description: str, on_click) -> QFrame:
        card = QFrame()
        card.setObjectName("feature_card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon_text)
        icon_lbl.setStyleSheet("font-size: 30px;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #33c6cb;")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 12px; color: #788596;")
        layout.addWidget(desc_lbl)

        layout.addStretch()

        btn = QPushButton("Open →")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(on_click)
        layout.addWidget(btn)

        return card


if __name__ == "__main__":
    app = QApplication(sys.argv)

    style_file = QFile("style.qss")
    style_file.open(QFile.ReadOnly | QFile.Text)
    style_stream = QTextStream(style_file)
    app.setStyleSheet(style_stream.readAll())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
