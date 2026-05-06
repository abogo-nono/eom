"""Qt smoke test: MainWindow boots and pages switch."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")


def test_main_window_boots(qtbot) -> None:
    from main import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "Eye On Metadata"
    # Default page is index 0.
    assert window.ui.stackedWidget.currentIndex() == 0


def test_menu_buttons_switch_pages(qtbot) -> None:
    from main import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)

    window.on_menu_extract_btn_toggled()
    assert window.ui.stackedWidget.currentIndex() == 1

    window.on_menu_remove_btn_toggled()
    assert window.ui.stackedWidget.currentIndex() == 2

    window.on_menu_report_btn_toggled()
    assert window.ui.stackedWidget.currentIndex() == 3
