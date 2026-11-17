"""Qt smoke tests: the window boots, navigates, routes drops and resizes from its edges."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent

import main
import settings


def test_main_window_boots(qtbot) -> None:
    window = main.MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Eye On Metadata"
    assert window.pages.currentIndex() == main.PageIndex.WORKSPACE
    assert window.workspace.stack.currentIndex() == 0  # empty state = drop zone


def test_sidebar_switches_pages(qtbot) -> None:
    window = main.MainWindow()
    qtbot.addWidget(window)
    window.sidebar.buttons[main.PageIndex.SETTINGS].click()
    assert window.pages.currentIndex() == main.PageIndex.SETTINGS
    window.sidebar.buttons[main.PageIndex.ABOUT].click()
    assert window.pages.currentIndex() == main.PageIndex.ABOUT
    window.sidebar.buttons[main.PageIndex.WORKSPACE].click()
    assert window.pages.currentIndex() == main.PageIndex.WORKSPACE


def test_drop_on_any_page_goes_to_workspace(qtbot, jpeg_with_exif: Path) -> None:
    window = main.MainWindow()
    qtbot.addWidget(window)
    window.show_page(main.PageIndex.ABOUT)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(jpeg_with_exif))])
    window.dropEvent(QDropEvent(QPointF(10, 10), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert window.pages.currentIndex() == main.PageIndex.WORKSPACE
    assert str(jpeg_with_exif.resolve()) in window.workspace.session


def test_settings_changes_reach_workspace(qtbot, tmp_path: Path) -> None:
    window = main.MainWindow()
    qtbot.addWidget(window)
    settings.set("output_dir", str(tmp_path))
    window.settings_view.copy_check.setChecked(True)
    assert settings.get("output_mode") is True
    assert window.workspace.plan.output_dir == str(tmp_path)
    assert window.workspace.action_bar.copies.isChecked()


def test_theme_switch_rerenders(qtbot, qapp) -> None:
    window = main.MainWindow()
    qtbot.addWidget(window)
    window._on_theme_changed("light")
    assert main.theme.current() == "light"
    window._on_theme_changed("dark")


def test_edge_detection(qtbot) -> None:
    window = main.MainWindow()
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.move(0, 0)
    origin = window.mapToGlobal(window.rect().topLeft())
    assert window._edges_at(origin + window.rect().center()) == Qt.Edge(0)
    assert window._edges_at(origin + window.rect().bottomRight()) == Qt.RightEdge | Qt.BottomEdge
