"""Tests for the QThread workers (path-list API)."""

from __future__ import annotations

from pathlib import Path

import Extractor
import profiles
from workers import CleanTask, EditWorker, ExtractionWorker, RemovalWorker


def test_extraction_worker_emits_per_path(qtbot, jpeg_with_exif: Path, jpeg_without_exif: Path) -> None:
    worker = ExtractionWorker([str(jpeg_with_exif), str(jpeg_without_exif)])
    results = {}
    worker.result_ready.connect(lambda path, data: results.__setitem__(path, data))
    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()
    assert results[str(jpeg_with_exif)]["Make"] == "EOM-Test"
    assert results[str(jpeg_without_exif)] is None


def test_removal_worker_in_place(qtbot, jpeg_with_exif: Path) -> None:
    worker = RemovalWorker([CleanTask(str(jpeg_with_exif), jpeg_with_exif.name)])
    reports = []
    worker.report_ready.connect(lambda path, report: reports.append(report))
    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()
    assert reports[0]["status"] is True
    assert set(reports[0]["diff"]["removed"]) == {"Make", "Model"}
    assert Extractor.single_image_extractor(str(jpeg_with_exif)) is None


def test_removal_worker_copies_keep_structure(qtbot, tmp_path: Path, jpeg_with_exif: Path) -> None:
    out = tmp_path / "out"
    task = CleanTask(str(jpeg_with_exif), "trip/day1/photo.jpg", profiles.get("all"))
    worker = RemovalWorker([task], output_dir=str(out))
    reports = []
    worker.report_ready.connect(lambda path, report: reports.append(report))
    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()
    assert reports[0]["target"] == str(out / "trip" / "day1" / "photo.jpg")
    assert Extractor.single_image_extractor(str(jpeg_with_exif))["Make"] == "EOM-Test"


def test_edit_worker(qtbot, jpeg_with_exif: Path) -> None:
    worker = EditWorker([(str(jpeg_with_exif), jpeg_with_exif.name)], fields={"Author": "Zed"})
    results = []
    worker.result_ready.connect(lambda path, ok: results.append(ok))
    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()
    assert results == [True]
    assert Extractor.single_image_extractor(str(jpeg_with_exif))["Artist"] == "Zed"
