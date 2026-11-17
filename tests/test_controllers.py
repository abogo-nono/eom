"""Tests for ExtractionController and RemovalController, driven through the real MainWindow UI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

import Extractor
import profiles
import settings


@pytest.fixture
def window(qtbot):
    from main import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    return win


def _wait_extract(qtbot, window):
    worker = window._extraction._worker
    if worker is not None and worker.isRunning():
        qtbot.waitUntil(lambda: not worker.isRunning(), timeout=5000)
    qtbot.waitUntil(lambda: window.ui.extract_btn.isEnabled(), timeout=5000)


def _wait_remove(qtbot, window):
    qtbot.waitUntil(lambda: window.ui.remove_btn.isEnabled() and window._removal._worker is not None, timeout=5000)
    qtbot.waitUntil(lambda: not window._removal._worker.isRunning(), timeout=5000)
    qtbot.waitUntil(lambda: window.ui.remove_btn.isEnabled(), timeout=5000)


def test_extraction_controller_browse_single(window):
    window.ui.extraction_type.setCurrentIndex(0)
    with patch("controllers.common.QFileDialog.getOpenFileName", return_value=("/tmp/a.jpg", "")):
        window._extraction.on_extract_browse_btn_clicked()
    assert window.ui.extract_file_path.text() == "/tmp/a.jpg"


def test_extraction_controller_browse_batch(window):
    window.ui.extraction_type.setCurrentIndex(1)
    with patch("controllers.common.QFileDialog.getExistingDirectory", return_value="/tmp/images"):
        window._extraction.on_extract_browse_btn_clicked()
    assert window.ui.extract_file_path.text() == "/tmp/images"


def test_extraction_controller_no_path_shows_warning(window):
    window.ui.extract_file_path.setText("")
    with patch("controllers.common.QMessageBox.warning") as mock_warn:
        window._extraction.on_extract_btn_clicked()
    mock_warn.assert_called_once()


def test_extract_single_file_shows_risk_and_rows(qtbot, window, jpeg_with_exif: Path):
    assert window.open_paths([str(jpeg_with_exif)])
    _wait_extract(qtbot, window)
    table = window.ui.extracted_table_data
    keys = [table.item(r, 0).text() for r in range(table.rowCount())]
    assert "Make" in keys
    assert window._extraction.risk_banner.property("level") == "medium"
    assert str(jpeg_with_exif) in settings.recent()

    window._extraction.filter_edit.setText("model")
    visible = [table.item(r, 0).text() for r in range(table.rowCount()) if not table.isRowHidden(r)]
    assert visible == ["Model"]


def test_extract_multi_drop_batch(qtbot, window, tmp_path: Path, jpeg_with_exif: Path, jpeg_without_exif: Path):
    assert window.open_paths([str(jpeg_with_exif), str(jpeg_without_exif)])
    _wait_extract(qtbot, window)
    assert set(window._extraction.results) == {jpeg_with_exif.name, jpeg_without_exif.name}


def test_export_uses_cached_results(qtbot, window, tmp_path: Path, jpeg_with_exif: Path):
    window.open_paths([str(jpeg_with_exif)])
    _wait_extract(qtbot, window)
    out = tmp_path / "out.json"
    with (
        patch("controllers.common.QFileDialog.getSaveFileName", return_value=(str(out), "")),
        patch("controllers.extraction.QMessageBox.information"),
        patch("controllers.extraction.ExtractionWorker") as worker_cls,
    ):
        window._extraction.on_export_btn_clicked()
    worker_cls.assert_not_called()  # no second extraction
    assert json.loads(out.read_text())[str(jpeg_with_exif)]["metadata"]["Make"] == "EOM-Test"


def test_removal_controller_browse_single(window):
    window.ui.remove_type.setCurrentIndex(0)
    with patch("controllers.common.QFileDialog.getOpenFileName", return_value=("/tmp/b.jpg", "")):
        window._removal.on_remove_browse_btn_clicked()
    assert window.ui.remove_file_path.text() == "/tmp/b.jpg"


def test_removal_controller_no_path_shows_warning(window):
    window.ui.remove_file_path.setText("")
    with patch("controllers.common.QMessageBox.warning") as mock_warn:
        window._removal.on_remove_btn_clicked()
    mock_warn.assert_called_once()


def test_remove_in_place_asks_confirmation(qtbot, window, jpeg_with_exif: Path):
    window.open_paths([str(jpeg_with_exif)], mode="remove")
    with patch("controllers.common.QMessageBox.exec", return_value=QMessageBox.Cancel):
        window._removal.on_remove_btn_clicked()
    assert window._removal._worker is None
    assert Extractor.single_image_extractor(str(jpeg_with_exif))  # untouched


def test_remove_to_output_folder_with_report(qtbot, window, tmp_path: Path, jpeg_with_exif: Path):
    out = tmp_path / "clean"
    settings.set("output_dir", str(out))
    settings.set("output_mode", True)
    settings.set("profile", "all")
    window._removal.reload_settings()
    window.open_paths([str(jpeg_with_exif)], mode="remove")
    with patch("controllers.removal.QMessageBox.exec"):
        window._removal.on_remove_btn_clicked()
        _wait_remove(qtbot, window)
    assert Extractor.single_image_extractor(str(out / jpeg_with_exif.name)) is None
    assert Extractor.single_image_extractor(str(jpeg_with_exif))["Make"] == "EOM-Test"  # original kept
    table = window.ui.removed_table_data
    assert table.rowCount() == 1 and table.item(0, 2).text() == "2"


def test_custom_selection_per_tag(qtbot, window, jpeg_with_exif: Path):
    settings.set("confirm_in_place", False)
    window.open_paths([str(jpeg_with_exif)], mode="remove")
    with patch("controllers.removal.CustomSelectionDialog") as dlg_cls:
        dlg = dlg_cls.return_value
        dlg.exec.return_value = QDialog.Accepted
        dlg.categories.return_value = {"device"}
        dlg.keys.return_value = ["Model"]
        window._removal.on_customize_btn_clicked()
    profile, keys = window._removal._current_profile()
    assert profile is None and keys == ["Model"]
    window._removal.on_remove_btn_clicked()
    _wait_remove(qtbot, window)
    data = Extractor.single_image_extractor(str(jpeg_with_exif))
    assert "Model" not in data and data["Make"] == "EOM-Test"


def test_export_and_remove_exports_before_data(qtbot, window, tmp_path: Path, jpeg_with_exif: Path):
    settings.set("confirm_in_place", False)
    window.open_paths([str(jpeg_with_exif)], mode="remove")
    out = tmp_path / "before.csv"
    with patch("controllers.common.QFileDialog.getSaveFileName", return_value=(str(out), "")):
        window._removal.on_export_and_remove_btn_clicked()
        _wait_remove(qtbot, window)
    assert "EOM-Test" in out.read_text()
    assert Extractor.single_image_extractor(str(jpeg_with_exif)) is None


def test_profile_combo_persists(window):
    combo = window._removal.profile_combo
    combo.setCurrentIndex(combo.findData("social"))
    window._removal.on_profile_combo_activated(combo.currentIndex())
    assert settings.get("profile") == "social"
    assert window._removal._current_profile()[0] == profiles.get("social")
