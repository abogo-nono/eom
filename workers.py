"""Background QThread workers for long-running file operations.

Every worker takes explicit absolute paths (files may come from several
folders) and emits per-file signals so the UI updates progressively.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from PySide6.QtCore import QThread, Signal

import Extractor
import profiles


class _Worker(QThread):
    progress: Signal = Signal(int, int)
    error: Signal = Signal(str)
    finished_all: Signal = Signal()

    def _loop(self, items: list, handle) -> None:
        try:
            total = len(items)
            for i, item in enumerate(items, 1):
                if self.isInterruptionRequested():
                    break
                handle(item)
                self.progress.emit(i, total)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self.finished_all.emit()


class ExtractionWorker(_Worker):
    """Read metadata of each path. ``result_ready(path, dict_or_None)``."""

    result_ready: Signal = Signal(str, object)

    def __init__(self, paths: list[str]) -> None:
        super().__init__()
        self._paths = list(paths)

    def run(self) -> None:
        self._loop(self._paths, lambda p: self.result_ready.emit(p, Extractor.single_image_extractor(p)))


@dataclass
class CleanTask:
    path: str
    rel: str
    profile: profiles.Profile | None = None
    keys: list[str] | None = None


class RemovalWorker(_Worker):
    """Clean each task. ``report_ready(path, report)`` where report is
    ``{"status", "target", "before", "after", "diff"}`` (*target* is the file
    actually modified — a copy when *output_dir* is set)."""

    report_ready: Signal = Signal(str, object)

    def __init__(self, tasks: list[CleanTask], output_dir: str | None = None, verify: bool = True) -> None:
        super().__init__()
        self._tasks = list(tasks)
        self._output_dir = output_dir
        self._verify = verify

    def run(self) -> None:
        self._loop(self._tasks, lambda t: self.report_ready.emit(t.path, self._process(t)))

    def _process(self, task: CleanTask) -> dict:
        report: dict = {"status": None, "target": task.path, "before": None, "after": None, "diff": {}}
        before = Extractor.single_image_extractor(task.path) if self._verify else None
        target = task.path
        if self._output_dir:
            try:
                target = Extractor.copy_to_output(task.path, self._output_dir, task.rel)
            except OSError:
                return report
        report["target"] = target
        report["status"] = Extractor.remove_metadata(target, task.profile, task.keys)
        if self._verify:
            after = Extractor.single_image_extractor(target)
            report.update(before=before, after=after, diff=Extractor.diff_metadata(before, after))
        return report


class EditWorker(_Worker):
    """Apply field edits and/or a date shift. ``result_ready(path, success)``."""

    result_ready: Signal = Signal(str, object)

    def __init__(
        self,
        items: list[tuple[str, str]],
        *,
        fields: dict[str, str] | None = None,
        shift: timedelta | None = None,
        output_dir: str | None = None,
    ) -> None:
        super().__init__()
        self._items = list(items)  # (path, rel)
        self._fields = fields or {}
        self._shift = shift
        self._output_dir = output_dir

    def run(self) -> None:
        self._loop(self._items, lambda item: self.result_ready.emit(item[0], self._process(*item)))

    def _process(self, path: str, rel: str) -> bool | None:
        target = Extractor.copy_to_output(path, self._output_dir, rel) if self._output_dir else path
        status: bool | None = True
        if self._fields:
            status = Extractor.write_metadata(target, self._fields)
        if status and self._shift:
            status = Extractor.shift_dates(target, self._shift)
        return status
