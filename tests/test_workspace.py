"""Tests for the session model and the workspace view."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

import Extractor
import settings
from session import CLEANED, PENDING, READY, CleaningPlan, FileEntry, Session, expand
from views.workspace import WorkspaceView

# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------


def test_expand_files_and_folders(tmp_path: Path) -> None:
    (tmp_path / "trip" / "day1").mkdir(parents=True)
    for rel in ("trip/a.jpg", "trip/day1/b.png", "trip/notes.txt", "c.pdf"):
        (tmp_path / rel).write_bytes(b"x")
    flat = expand([str(tmp_path / "trip"), str(tmp_path / "c.pdf")], recursive=False)
    assert flat == [(str(tmp_path / "trip" / "a.jpg"), "trip/a.jpg"), (str(tmp_path / "c.pdf"), "c.pdf")]
    deep = expand([str(tmp_path / "trip")], recursive=True)
    assert (str(tmp_path / "trip" / "day1" / "b.png"), "trip/day1/b.png") in deep
    assert expand([str(tmp_path / "trip" / "notes.txt"), "/does/not/exist"], recursive=True) == []


def test_session_add_dedupes_and_signals(qtbot) -> None:
    session = Session()
    with qtbot.waitSignal(session.added) as blocker:
        assert session.add([("/a.jpg", "a.jpg"), ("/b.jpg", "b.jpg")]) == ["/a.jpg", "/b.jpg"]
    assert blocker.args == [["/a.jpg", "/b.jpg"]]
    assert session.add([("/a.jpg", "a.jpg")]) == []
    session.set_metadata("/a.jpg", {"IFD0:Artist": "Bob"})
    assert session.get("/a.jpg").state == READY
    assert session.pending() == 1
    session.remove(["/b.jpg"])
    assert session.paths() == ["/a.jpg"]


def test_set_report_in_place_updates_metadata() -> None:
    session = Session()
    session.add([("/a.jpg", "a.jpg")])
    session.set_metadata("/a.jpg", {"IFD0:Artist": "Bob"})
    session.set_report("/a.jpg", {"status": True, "target": "/a.jpg", "after": {"IFD0:Make": "x"}, "diff": {}})
    entry = session.get("/a.jpg")
    assert entry.state == CLEANED and entry.metadata == {"IFD0:Make": "x"}


def test_set_report_copy_keeps_original_metadata() -> None:
    session = Session()
    session.add([("/a.jpg", "a.jpg")])
    session.set_metadata("/a.jpg", {"IFD0:Artist": "Bob"})
    session.set_report("/a.jpg", {"status": True, "target": "/out/a.jpg", "after": {}, "diff": {}})
    assert session.get("/a.jpg").metadata == {"IFD0:Artist": "Bob"}


def test_cleaning_plan_preview() -> None:
    entry = FileEntry("/a.jpg", "a.jpg", {"IFD0:Artist": "a", "IFD0:Copyright": "c", "System:FileSize": "1"}, READY)
    assert CleaningPlan("all").keys_removed(entry) == {"IFD0:Artist", "IFD0:Copyright"}
    assert CleaningPlan("social").keys_removed(entry) == {"IFD0:Artist"}
    custom = CleaningPlan("custom", frozenset({"copyright"}))
    assert custom.keys_removed(entry) == {"IFD0:Copyright"}
    entry.custom_keys = {"IFD0:Artist"}
    assert custom.for_entry(entry) == (None, ["IFD0:Artist"])


# ---------------------------------------------------------------------------
# workspace view
# ---------------------------------------------------------------------------


@pytest.fixture
def ws(qtbot):
    view = WorkspaceView()
    qtbot.addWidget(view)
    view.resize(1200, 800)
    return view


def _wait_scanned(qtbot, ws):
    qtbot.waitUntil(lambda: len(ws.session) > 0 and ws.session.pending() == 0, timeout=5000)


def _wait_cleaned(qtbot, ws):
    qtbot.waitUntil(lambda: ws._clean_worker is not None and not ws._clean_worker.isRunning(), timeout=5000)
    qtbot.waitUntil(lambda: ws.action_bar.progress.isHidden(), timeout=5000)


def test_add_paths_switches_from_drop_zone(qtbot, ws, jpeg_with_exif: Path) -> None:
    assert ws.stack.currentIndex() == 0
    assert ws.add_paths([str(jpeg_with_exif)]) == 1
    assert ws.stack.currentIndex() == 1
    _wait_scanned(qtbot, ws)
    entry = ws.session.get(str(jpeg_with_exif))
    assert entry.metadata["Make"] == "EOM-Test"
    assert str(jpeg_with_exif) in settings.recent()
    # Detail panel shows the selected file and the cleaning preview.
    assert ws.detail.name.text() == jpeg_with_exif.name
    assert "Remove everything" in ws.detail.summary.text()
    assert ws.action_bar.clean_btn.isEnabled()


def test_unsupported_files_are_ignored(qtbot, ws, tmp_path: Path) -> None:
    bad = tmp_path / "x.txt"
    bad.write_text("hi")
    messages = []
    ws.message.connect(messages.append)
    assert ws.add_paths([str(bad)]) == 0
    assert ws.stack.currentIndex() == 0 and messages


def test_tree_groups_by_category_and_marks_removals(qtbot, ws, jpeg_with_exif: Path) -> None:
    settings.set("profile", "location")
    ws.reload_settings()
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    tree = ws.detail.tree
    groups = {tree.topLevelItem(i).text(0): tree.topLevelItem(i) for i in range(tree.topLevelItemCount())}
    device = groups["Camera / device"]
    assert device.childCount() == 2
    assert {device.child(i).text(2) for i in range(2)} == {"Keep"}  # location profile keeps the device
    assert not ws.action_bar.clean_btn.isEnabled()  # nothing to remove → disabled


def test_search_filters_tree(qtbot, ws, jpeg_with_exif: Path) -> None:
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    ws.detail.search.setText("model")
    tree = ws.detail.tree
    visible = [
        tree.topLevelItem(i).child(j).text(0)
        for i in range(tree.topLevelItemCount())
        for j in range(tree.topLevelItem(i).childCount())
        if not tree.topLevelItem(i).isHidden() and not tree.topLevelItem(i).child(j).isHidden()
    ]
    assert visible == ["Model"]


def test_clean_in_place_asks_confirmation(qtbot, ws, jpeg_with_exif: Path) -> None:
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    with patch("views.common.QMessageBox.exec", return_value=QMessageBox.Cancel):
        ws.clean()
    assert ws._clean_worker is None
    assert Extractor.single_image_extractor(str(jpeg_with_exif))


def test_clean_to_copies_and_compare(qtbot, ws, tmp_path: Path, jpeg_with_exif: Path) -> None:
    out = tmp_path / "clean"
    settings.set("output_dir", str(out))
    settings.set("output_mode", True)
    ws.reload_settings()
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    ws.clean()
    _wait_cleaned(qtbot, ws)
    entry = ws.session.get(str(jpeg_with_exif))
    assert entry.state == CLEANED
    assert Extractor.single_image_extractor(str(out / jpeg_with_exif.name)) is None
    assert Extractor.single_image_extractor(str(jpeg_with_exif))["Make"] == "EOM-Test"
    assert ws.detail.compare_btn.isEnabled()
    with patch("views.workspace.BeforeAfterDialog") as dialog:
        ws.compare_current()
    dialog.assert_called_once()


def test_custom_per_tag_selection(qtbot, ws, jpeg_with_exif: Path) -> None:
    settings.set("confirm_in_place", False)
    settings.set("profile", "custom")
    settings.set("custom_categories", ["device"])
    ws.reload_settings()
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    ws._on_custom_keys({"Model"})
    ws.clean()
    _wait_cleaned(qtbot, ws)
    data = Extractor.single_image_extractor(str(jpeg_with_exif))
    assert "Model" not in data and data["Make"] == "EOM-Test"


def test_export_uses_session_data(qtbot, ws, tmp_path: Path, jpeg_with_exif: Path) -> None:
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    out = tmp_path / "out.json"
    with patch("views.common.QFileDialog.getSaveFileName", return_value=(str(out), "")):
        ws.export("json")
    assert json.loads(out.read_text())[str(jpeg_with_exif)]["metadata"]["Make"] == "EOM-Test"


def test_export_then_clean_exports_before_data(qtbot, ws, tmp_path: Path, jpeg_with_exif: Path) -> None:
    settings.set("confirm_in_place", False)
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    out = tmp_path / "before.csv"
    with patch("views.common.QFileDialog.getSaveFileName", return_value=(str(out), "")):
        ws.export("csv", then_clean=True)
    _wait_cleaned(qtbot, ws)
    qtbot.waitUntil(out.exists, timeout=5000)
    assert "EOM-Test" in out.read_text()
    assert Extractor.single_image_extractor(str(jpeg_with_exif)) is None


def test_edit_rescans(qtbot, ws, jpeg_with_exif: Path) -> None:
    settings.set("confirm_in_place", False)
    ws.add_paths([str(jpeg_with_exif)])
    _wait_scanned(qtbot, ws)
    with patch("views.workspace.EditDialog") as dlg_cls:
        dlg = dlg_cls.return_value
        dlg.exec.return_value = QDialog.Accepted
        dlg.fields.return_value = {"Author": "Zed"}
        dlg.shift.return_value = None
        ws.edit_targets()
    qtbot.waitUntil(lambda: (ws.session.get(str(jpeg_with_exif)).metadata or {}).get("Artist") == "Zed", timeout=5000)


def test_remove_and_clear(qtbot, ws, jpeg_with_exif: Path, jpeg_without_exif: Path) -> None:
    ws.add_paths([str(jpeg_with_exif), str(jpeg_without_exif)])
    assert ws.file_list.count() == 2
    ws.file_list.setCurrentRow(0)
    ws.remove_selected()
    assert ws.file_list.count() == 1 and len(ws.session) == 1
    ws.clear()
    assert ws.stack.currentIndex() == 0


def test_risk_filter(qtbot, ws, jpeg_with_exif: Path, jpeg_without_exif: Path) -> None:
    ws.add_paths([str(jpeg_with_exif), str(jpeg_without_exif)])
    _wait_scanned(qtbot, ws)
    ws.risk_filter.setCurrentIndex(ws.risk_filter.findData("medium"))
    visible = [ws.file_list.item(i).data(0x0100) for i in range(2) if not ws.file_list.item(i).isHidden()]
    assert visible == [str(jpeg_with_exif)]
    assert ws.session.get(str(jpeg_without_exif)).state != PENDING
