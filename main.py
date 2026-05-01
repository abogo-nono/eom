"""EOM – Eye On Metadata – application entry point.

MainWindow is intentionally minimal: window chrome, page navigation,
and instantiation of the two feature controllers.
"""

from __future__ import annotations

import sys
from enum import IntEnum

from PySide6.QtCore import QFile, Qt, QTextStream
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from app_ui import Ui_MainWindow
from controllers.extraction import ExtractionController
from controllers.removal import RemovalController


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

        # Frameless window — custom drag + chrome buttons.
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.draggable = True
        self.old_pos = None
        self.ui.header_widget.mousePressEvent = self.mouse_press_event
        self.ui.header_widget.mouseMoveEvent = self.mouse_move_event

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

    # ------------------------------------------------------------------
    # Window chrome
    # ------------------------------------------------------------------

    def mouse_press_event(self, event) -> None:
        if event.button() == Qt.LeftButton and self.draggable:
            self.old_pos = event.globalPosition().toPoint()

    def mouse_move_event(self, event) -> None:
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

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
        QMessageBox.about(
            self,
            "About E.O.M",
            """
<p><span style="font-size:x-large;font-weight:600;">What is EOM?</span></p>
<p>Eye On Metadata (E.O.M) is an open-source desktop application that displays,
exports and removes metadata from media files. EOM is cross-platform (Windows,
Linux, macOS) and was developed by
<a href="https://github.com/abogo-nono">Abogo Lincoln</a>.</p>
""",
        )

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


if __name__ == "__main__":
    app = QApplication(sys.argv)

    style_file = QFile("style.qss")
    style_file.open(QFile.ReadOnly | QFile.Text)
    style_stream = QTextStream(style_file)
    app.setStyleSheet(style_stream.readAll())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
