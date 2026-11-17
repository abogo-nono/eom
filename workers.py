"""Background QThread workers for long-running file operations.

Each worker emits signals so the UI can update progressively without
blocking the Qt event loop.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import QThread, Signal

import Extractor
import profiles


def _iter_targets(path: str, is_batch: bool, images: dict):
    """Yield ``(display_name, absolute_path_or_None, relative_name)``."""
    if not is_batch:
        yield path, path, Path(path).name
        return
    for key, value in images.items():
        safe_path = Extractor._safe_join(path, value)
        yield key, (str(safe_path) if safe_path else None), value


class ExtractionWorker(QThread):
    """Run single-file or batch extraction in a background thread.

    Signals
    -------
    result_ready(name, data)
        Emitted for every processed file.  *name* is the display label
        (file path for single, relative path for batch); *data* is a dict or None.
    progress(current, total)
        Emitted after each file is processed (total=1 for single-file mode).
    error(message)
        Emitted when an unrecoverable error occurs.
    finished_all()
        Emitted once after all files are processed.
    """

    result_ready: Signal = Signal(str, object)
    progress: Signal = Signal(int, int)
    error: Signal = Signal(str)
    finished_all: Signal = Signal()

    def __init__(self, path: str, is_batch: bool, images: dict | None = None) -> None:
        super().__init__()
        self._path = path
        self._is_batch = is_batch
        self._images = images or {}

    @property
    def is_batch(self) -> bool:
        return self._is_batch

    def run(self) -> None:
        try:
            total = 1 if not self._is_batch else len(self._images)
            for i, (name, target, _rel) in enumerate(_iter_targets(self._path, self._is_batch, self._images), 1):
                if self.isInterruptionRequested():
                    break
                data = Extractor.single_image_extractor(target) if target else None
                self.result_ready.emit(name, data)
                self.progress.emit(i, total)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self.finished_all.emit()


class RemovalWorker(QThread):
    """Run single-file or batch metadata removal in a background thread.

    Signals
    -------
    result_ready(name, success)
        Emitted for every processed file.  *success* is True or None.
    report_ready(name, report)
        Emitted right after ``result_ready`` with a dict:
        ``{"status", "target", "before", "after", "diff"}`` where *target* is the
        file actually modified (a copy when *output_dir* is set) and *diff* is
        :func:`Extractor.diff_metadata` (empty when *verify* is False).
    progress(current, total)
        Emitted after each file is processed.
    error(message)
        Emitted when an unrecoverable error occurs.
    finished_all()
        Emitted once after all files are processed.
    """

    result_ready: Signal = Signal(str, object)
    report_ready: Signal = Signal(str, object)
    progress: Signal = Signal(int, int)
    error: Signal = Signal(str)
    finished_all: Signal = Signal()

    def __init__(
        self,
        path: str,
        is_batch: bool,
        images: dict | None = None,
        *,
        profile: profiles.Profile | None = None,
        keys: list[str] | None = None,
        output_dir: str | None = None,
        verify: bool = True,
    ) -> None:
        super().__init__()
        self._path = path
        self._is_batch = is_batch
        self._images = images or {}
        self._profile = profile
        self._keys = keys
        self._output_dir = output_dir
        self._verify = verify

    @property
    def is_batch(self) -> bool:
        return self._is_batch

    def run(self) -> None:
        try:
            total = 1 if not self._is_batch else len(self._images)
            for i, (name, source, rel) in enumerate(_iter_targets(self._path, self._is_batch, self._images), 1):
                if self.isInterruptionRequested():
                    break
                report = self._process(source, rel)
                self.result_ready.emit(name, report["status"])
                self.report_ready.emit(name, report)
                self.progress.emit(i, total)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self.finished_all.emit()

    def _process(self, source: str | None, rel: str) -> dict:
        report: dict = {"status": None, "target": source, "before": None, "after": None, "diff": {}}
        if source is None:
            return report
        before = Extractor.single_image_extractor(source) if self._verify else None
        target = source
        if self._output_dir:
            try:
                target = Extractor.copy_to_output(source, self._output_dir, rel)
            except OSError:
                return report
        report["target"] = target
        report["status"] = Extractor.remove_metadata(target, self._profile, self._keys)
        if self._verify:
            after = Extractor.single_image_extractor(target)
            report.update(before=before, after=after, diff=Extractor.diff_metadata(before, after))
        return report


class EditWorker(QThread):
    """Apply field edits and/or a date shift to one or many files.

    Signals mirror :class:`RemovalWorker` (``result_ready(name, success)``).
    """

    result_ready: Signal = Signal(str, object)
    progress: Signal = Signal(int, int)
    error: Signal = Signal(str)
    finished_all: Signal = Signal()

    def __init__(
        self,
        path: str,
        is_batch: bool,
        images: dict | None = None,
        *,
        fields: dict[str, str] | None = None,
        shift: timedelta | None = None,
        output_dir: str | None = None,
    ) -> None:
        super().__init__()
        self._path = path
        self._is_batch = is_batch
        self._images = images or {}
        self._fields = fields or {}
        self._shift = shift
        self._output_dir = output_dir

    def run(self) -> None:
        try:
            total = 1 if not self._is_batch else len(self._images)
            for i, (name, source, rel) in enumerate(_iter_targets(self._path, self._is_batch, self._images), 1):
                if self.isInterruptionRequested():
                    break
                self.result_ready.emit(name, self._process(source, rel))
                self.progress.emit(i, total)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self.finished_all.emit()

    def _process(self, source: str | None, rel: str) -> bool | None:
        if source is None:
            return None
        target = Extractor.copy_to_output(source, self._output_dir, rel) if self._output_dir else source
        status: bool | None = True
        if self._fields:
            status = Extractor.write_metadata(target, self._fields)
        if status and self._shift:
            status = Extractor.shift_dates(target, self._shift)
        return status
