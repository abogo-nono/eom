"""EOM – Eye On Metadata – application entry point.

The window is built in code (no Qt Designer file): a frameless window with a
custom title bar, a slim navigation sidebar, three pages (workspace, settings,
about) and a status bar.

``python main.py``                       → GUI
``python main.py photo.jpg folder/``     → GUI with those files loaded
``python main.py extract photo.jpg``     → command-line interface (see cli.py)
"""

from __future__ import annotations

import sys
from enum import IntEnum
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizeGrip,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import cli
import exiftool_backend
import i18n
import icons
import settings
import theme
import updater
from version import __version__
from views.about import AboutView
from views.settings_view import SettingsView
from views.workspace import WorkspaceView
from widgets import set_badge, styled

RESIZE_MARGIN = 6
NAV_ICONS = {0: "layers", 1: "settings", 2: "info"}


def _resource_path(rel: str) -> str:
    """Resolve a resource path for both dev and PyInstaller frozen modes."""
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
    return str(base / rel)


class PageIndex(IntEnum):
    WORKSPACE = 0
    SETTINGS = 1
    ABOUT = 2


class TitleBar(QWidget):
    """Logo, title, status chips and window buttons. Drag to move, double-click to maximise."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(42)
        self._window = window
        self._drag_from: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 6, 0)
        layout.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(window.windowIcon().pixmap(22, 22))
        layout.addWidget(logo)
        layout.addWidget(styled(QLabel("Eye On Metadata"), role="brand"))
        layout.addStretch()

        self.update_chip = QLabel()
        self.update_chip.setOpenExternalLinks(True)
        set_badge(self.update_chip, "info")
        self.update_chip.hide()
        layout.addWidget(self.update_chip, 0, Qt.AlignVCenter)

        available = exiftool_backend.is_available()
        self.exiftool_chip = QLabel(self.tr("ExifTool on") if available else self.tr("ExifTool off"))
        set_badge(self.exiftool_chip, "low" if available else "medium")
        self.exiftool_chip.setToolTip(
            self.tr("ExifTool is installed and active as the primary metadata backend.")
            if available
            else self.tr("ExifTool not found in PATH. Using built-in backends (Pillow / mutagen / pypdf).")
        )
        layout.addWidget(self.exiftool_chip, 0, Qt.AlignVCenter)
        layout.addSpacing(8)

        self.min_btn = self._win_button("minus", self.tr("Minimize"), window.showMinimized)
        self.max_btn = self._win_button("maximize", self.tr("Maximize"), window.toggle_maximized)
        self.close_btn = self._win_button("x", self.tr("Close"), window.close, close=True)
        for b in (self.min_btn, self.max_btn, self.close_btn):
            layout.addWidget(b)

    def _win_button(self, name: str, tip: str, slot, close: bool = False) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("WinClose" if close else "WinButton")
        btn.setToolTip(tip)
        btn.setFixedSize(34, 30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(slot)
        icons.bind(btn, name, "muted", 16)
        return btn

    def refresh_max_icon(self) -> None:
        maximized = self._window.isMaximized()
        icons.bind(self.max_btn, "minimize" if maximized else "maximize", "muted", 16)
        self.max_btn.setToolTip(self.tr("Restore") if maximized else self.tr("Maximize"))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        handle = self._window.windowHandle()
        # startSystemMove() delegates to the window manager (Wayland, X11, Windows, macOS);
        # fall back to manual moving when it is unavailable (e.g. offscreen tests).
        if not handle or not handle.startSystemMove():
            self._drag_from = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is not None:
            delta = event.globalPosition().toPoint() - self._drag_from
            self._window.move(self._window.pos() + delta)
            self._drag_from = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_from = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._window.toggle_maximized()


class Sidebar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(84)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(8, 12, 8, 12)
        self.layout_.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[int, QToolButton] = {}

    def add(self, index: int, text: str, tooltip: str, bottom: bool = False) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("NavButton")
        btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setFixedSize(68, 60)
        self.group.addButton(btn, index)
        if bottom:
            self.layout_.addStretch()
        self.layout_.addWidget(btn, 0, Qt.AlignHCenter)
        self.buttons[index] = btn
        return btn


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(_resource_path("images/app-logo.ico")))
        self.setWindowTitle("Eye On Metadata")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setMinimumSize(980, 640)
        self.resize(1280, 800)
        self.setAcceptDrops(True)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar(self)
        outer.addWidget(self.title_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.sidebar = Sidebar()
        body.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        outer.addLayout(body, 1)

        self.workspace = WorkspaceView()
        self.settings_view = SettingsView()
        self.about_view = AboutView(self.windowIcon())
        for page in (self.workspace, self.settings_view, self.about_view):
            self.pages.addWidget(page)

        self.sidebar.add(PageIndex.WORKSPACE, self.tr("Files"), self.tr("Inspect and clean files (Ctrl+1)"))
        self.sidebar.add(PageIndex.SETTINGS, self.tr("Settings"), self.tr("Settings (Ctrl+,)"), bottom=True)
        self.sidebar.add(PageIndex.ABOUT, self.tr("About"), self.tr("About EOM and bug reports"))
        self.sidebar.group.idClicked.connect(self.show_page)

        # Status bar with a resize grip.
        status = QWidget()
        status.setObjectName("StatusBar")
        status.setAttribute(Qt.WA_StyledBackground, True)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(12, 3, 2, 3)
        self.status_label = QLabel(self.tr("Ready — drop files anywhere to start."))
        sl.addWidget(self.status_label, 1)
        sl.addWidget(QLabel(f"v{__version__}"))
        sl.addWidget(QSizeGrip(status), 0, Qt.AlignBottom | Qt.AlignRight)
        outer.addWidget(status)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.setInterval(10000)
        self._status_timer.timeout.connect(lambda: self.status_label.setText(""))

        self.workspace.message.connect(self.show_message)
        self.settings_view.theme_changed.connect(self._on_theme_changed)
        self.settings_view.settings_changed.connect(self.workspace.reload_settings)

        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.show_page(PageIndex.SETTINGS))
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.show_page(PageIndex.WORKSPACE))

        # Edge resizing for the frameless window.
        QApplication.instance().installEventFilter(self)

        self._update_checker: updater.UpdateChecker | None = None
        if settings.get("check_updates"):
            QTimer.singleShot(1500, self._check_updates)

        self.show_page(PageIndex.WORKSPACE)

    # ------------------------------------------------------------------
    # Pages & messages
    # ------------------------------------------------------------------

    def show_page(self, index: int) -> None:
        if index == PageIndex.SETTINGS:
            self.settings_view.reload()
        self.pages.setCurrentIndex(index)
        self.sidebar.buttons[index].setChecked(True)
        for i, btn in self.sidebar.buttons.items():
            icons.bind(btn, NAV_ICONS[i], "primary" if i == index else "muted", 22)

    def show_message(self, text: str) -> None:
        self.status_label.setText(text)
        self._status_timer.start()

    def open_paths(self, paths: list[str]) -> int:
        """Add *paths* to the workspace and show it."""
        self.show_page(PageIndex.WORKSPACE)
        return self.workspace.add_paths(paths)

    # ------------------------------------------------------------------
    # Window chrome
    # ------------------------------------------------------------------

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self.title_bar.refresh_max_icon()

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.WindowStateChange:
            self.title_bar.refresh_max_icon()
        super().changeEvent(event)

    def _edges_at(self, global_pos: QPoint) -> Qt.Edge:
        edges = Qt.Edge(0)
        if self.isMaximized():
            return edges
        pos = self.mapFromGlobal(global_pos)
        rect = QRect(0, 0, self.width(), self.height())
        if not rect.contains(pos):
            return edges
        if pos.x() <= RESIZE_MARGIN:
            edges |= Qt.LeftEdge
        if pos.x() >= rect.width() - RESIZE_MARGIN:
            edges |= Qt.RightEdge
        if pos.y() <= RESIZE_MARGIN:
            edges |= Qt.TopEdge
        if pos.y() >= rect.height() - RESIZE_MARGIN:
            edges |= Qt.BottomEdge
        return edges

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        etype = event.type()
        if etype not in (QEvent.MouseMove, QEvent.MouseButtonPress):
            return False
        if not isinstance(obj, QWidget) or obj.window() is not self:
            return False
        edges = self._edges_at(event.globalPosition().toPoint())
        if etype == QEvent.MouseMove and not event.buttons():
            horizontal = bool(edges & (Qt.LeftEdge | Qt.RightEdge))
            vertical = bool(edges & (Qt.TopEdge | Qt.BottomEdge))
            if horizontal and vertical:
                main_diag = (edges & Qt.LeftEdge and edges & Qt.TopEdge) or (
                    edges & Qt.RightEdge and edges & Qt.BottomEdge
                )
                self.setCursor(Qt.SizeFDiagCursor if main_diag else Qt.SizeBDiagCursor)
            elif horizontal:
                self.setCursor(Qt.SizeHorCursor)
            elif vertical:
                self.setCursor(Qt.SizeVerCursor)
            else:
                self.unsetCursor()
        elif etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton and edges:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemResize(edges):
                return True
        return False

    def closeEvent(self, event) -> None:  # noqa: N802
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.workspace.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Drag & drop (any page → workspace)
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.open_paths(paths)

    # ------------------------------------------------------------------
    # Theme / updates
    # ------------------------------------------------------------------

    def _on_theme_changed(self, name: str) -> None:
        theme.apply(QApplication.instance(), name)
        icons.refresh_bound()
        self.show_page(self.pages.currentIndex())
        self.workspace.retheme()

    def _check_updates(self) -> None:
        self._update_checker = updater.UpdateChecker(self)
        self._update_checker.finished.connect(self._on_update_result)
        self._update_checker.check()

    def _on_update_result(self, tag: str, url: str, _error: str) -> None:
        if tag:
            self.title_bar.update_chip.setText(
                self.tr("<a href='%2'>Update available: %1</a>").replace("%1", tag).replace("%2", url)
            )
            self.title_bar.update_chip.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_gui_args(argv: list[str]) -> list[str]:
    """Paths to open. ``--extract`` / ``--remove`` (file-manager entries) are accepted and ignored."""
    return [str(Path(a).expanduser().resolve()) for a in argv if not a.startswith("-")]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and (argv[0] in cli.COMMANDS or argv[0] in ("-h", "--help", "--version")):
        return cli.main(argv)

    paths = parse_gui_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Eye On Metadata")
    app.setApplicationVersion(__version__)
    i18n.install(app, settings.get("language"))
    theme.apply(app, settings.get("theme"))

    window = MainWindow()
    window.show()
    if paths:
        QTimer.singleShot(0, lambda: window.open_paths(paths))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
