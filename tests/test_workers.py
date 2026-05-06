"""Tests for QThread workers (ExtractionWorker, RemovalWorker)."""

from __future__ import annotations

from pathlib import Path

from workers import ExtractionWorker, RemovalWorker


def test_extraction_worker_emits_result(qtbot, jpeg_with_exif: Path) -> None:
    worker = ExtractionWorker(str(jpeg_with_exif), is_batch=False)
    results = []

    worker.result_ready.connect(lambda name, data: results.append((name, data)))

    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()

    assert results, "Expected at least one result_ready emission"
    _name, data = results[0]
    assert data is not None
    assert data.get("Make") == "EOM-Test"


def test_extraction_worker_batch(qtbot, jpeg_with_exif: Path) -> None:
    directory = str(jpeg_with_exif.parent)
    images = {jpeg_with_exif.name: jpeg_with_exif.name}
    worker = ExtractionWorker(directory, is_batch=True, images=images)
    results = []

    worker.result_ready.connect(lambda name, data: results.append((name, data)))

    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()

    names = [r[0] for r in results]
    assert jpeg_with_exif.name in names


def test_removal_worker_emits_result(qtbot, jpeg_with_exif: Path) -> None:
    worker = RemovalWorker(str(jpeg_with_exif), is_batch=False)
    results = []

    worker.result_ready.connect(lambda name, status: results.append((name, status)))

    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()

    assert results
    _name, status = results[0]
    assert status is True


def test_removal_worker_batch(qtbot, jpeg_with_exif: Path) -> None:
    directory = str(jpeg_with_exif.parent)
    images = {jpeg_with_exif.name: jpeg_with_exif.name}
    worker = RemovalWorker(directory, is_batch=True, images=images)
    results = []

    worker.result_ready.connect(lambda name, status: results.append((name, status)))

    with qtbot.waitSignal(worker.finished_all, timeout=5000):
        worker.start()

    assert any(s is True for _, s in results)
