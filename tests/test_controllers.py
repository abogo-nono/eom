"""Tests for ExtractionController and RemovalController."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from controllers.extraction import ExtractionController
from controllers.removal import RemovalController


def _make_ui():
    """Return a minimal mock that satisfies controller __init__ wiring."""
    ui = MagicMock()
    # TableWidget-like attrs controllers call
    ui.extracted_table_data.rowCount.return_value = 0
    ui.removed_table_data.rowCount.return_value = 0
    return ui


def test_extraction_controller_browse_single(qtbot):
    ui = _make_ui()
    parent = MagicMock()
    ctrl = ExtractionController(ui, parent)

    ui.extraction_type.currentIndex.return_value = 0
    with patch("controllers.extraction.QFileDialog.getOpenFileName", return_value=("/tmp/a.jpg", "")):
        ctrl.on_extract_browse_btn_clicked()

    ui.extract_file_path.setText.assert_called_with("/tmp/a.jpg")


def test_extraction_controller_browse_batch(qtbot):
    ui = _make_ui()
    parent = MagicMock()
    ctrl = ExtractionController(ui, parent)

    ui.extraction_type.currentIndex.return_value = 1
    with patch("controllers.extraction.QFileDialog.getExistingDirectory", return_value="/tmp/images"):
        ctrl.on_extract_browse_btn_clicked()

    ui.extract_file_path.setText.assert_called_with("/tmp/images")


def test_extraction_controller_no_path_shows_warning(qtbot):
    ui = _make_ui()
    parent = MagicMock()
    ctrl = ExtractionController(ui, parent)

    ui.extract_file_path.text.return_value = ""
    ui.extraction_type.currentIndex.return_value = 0

    with patch("controllers.extraction.QMessageBox.warning") as mock_warn:
        ctrl.on_extract_btn_clicked()

    mock_warn.assert_called_once()


def test_removal_controller_browse_single(qtbot):
    ui = _make_ui()
    parent = MagicMock()
    ctrl = RemovalController(ui, parent, MagicMock())

    ui.remove_type.currentIndex.return_value = 0
    with patch("controllers.removal.QFileDialog.getOpenFileName", return_value=("/tmp/b.jpg", "")):
        ctrl.on_remove_browse_btn_clicked()

    ui.remove_file_path.setText.assert_called_with("/tmp/b.jpg")


def test_removal_controller_no_path_shows_warning(qtbot):
    ui = _make_ui()
    parent = MagicMock()
    ctrl = RemovalController(ui, parent, MagicMock())

    ui.remove_file_path.text.return_value = ""
    ui.remove_type.currentIndex.return_value = 0

    with patch("controllers.removal.QMessageBox.warning") as mock_warn:
        ctrl.on_remove_btn_clicked()

    mock_warn.assert_called_once()


def test_build_image_dict_filters_extensions(tmp_path: Path) -> None:
    (tmp_path / "photo.jpg").touch()
    (tmp_path / "photo.jpeg").touch()
    (tmp_path / "document.txt").touch()
    (tmp_path / "image.png").touch()

    result = ExtractionController._build_image_dict(str(tmp_path))
    assert "photo.jpg" in result
    assert "photo.jpeg" in result
    assert "image.png" in result
    assert "document.txt" not in result
