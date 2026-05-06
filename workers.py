"""Background QThread workers for long-running file operations.

Each worker emits signals so the UI can update progressively without
blocking the Qt event loop.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

import Extractor


class ExtractionWorker(QThread):
    """Run single-file or batch EXIF extraction in a background thread.

    Signals
    -------
    result_ready(name, data)
        Emitted for every processed file.  *name* is the display label
        (file path for single, filename for batch); *data* is a dict or None.
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

    def run(self) -> None:
        try:
            if not self._is_batch:
                data = Extractor.single_image_extractor(self._path)
                self.result_ready.emit(self._path, data)
                self.progress.emit(1, 1)
            else:
                total = len(self._images)
                for i, (key, value) in enumerate(self._images.items(), start=1):
                    safe_path = Extractor._safe_join(self._path, value)
                    data = Extractor.single_image_extractor(str(safe_path)) if safe_path else None
                    self.result_ready.emit(key, data)
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
    progress(current, total)
        Emitted after each file is processed.
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

    def run(self) -> None:
        try:
            if not self._is_batch:
                result = Extractor.remove_image_metadata(self._path)
                self.result_ready.emit(self._path, result)
                self.progress.emit(1, 1)
            else:
                total = len(self._images)
                for i, (key, value) in enumerate(self._images.items(), start=1):
                    safe_path = Extractor._safe_join(self._path, value)
                    result = Extractor.remove_image_metadata(str(safe_path)) if safe_path else None
                    self.result_ready.emit(key, result)
                    self.progress.emit(i, total)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self.finished_all.emit()
