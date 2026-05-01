"""RemovalController — owns all remove and export-and-remove logic."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from workers import RemovalWorker

_SUPPORTED_FILTER = "Media files (*.jpg *.JPG *.jpeg *.JPEG *.png *.PNG *.tif *.tiff *.TIF *.TIFF *.pdf *.PDF)"
_SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf"}


class RemovalController:
    """Manages the Remove page: browse and remove flows.

    Takes a reference to the *ui* object (from Ui_MainWindow), the parent
    QWidget, and a callable *trigger_export* so export-and-remove can
    delegate to ExtractionController without a circular dependency.
    """

    def __init__(self, ui, parent, trigger_export) -> None:
        self._ui = ui
        self._parent = parent
        self._trigger_export = trigger_export
        self._worker: RemovalWorker | None = None

        ui.remove_browse_btn.clicked.connect(self.on_remove_browse_btn_clicked)
        ui.remove_btn.clicked.connect(self.on_remove_btn_clicked)
        ui.export_and_remove_btn.clicked.connect(self.on_export_and_remove_btn_clicked)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_remove_browse_btn_clicked(self) -> None:
        if self._ui.remove_type.currentIndex() == 0:
            image_path = QFileDialog.getOpenFileName(self._parent, filter=_SUPPORTED_FILTER)[0]
            self._ui.remove_file_path.setText(image_path)
        else:
            dir_path = QFileDialog.getExistingDirectory(self._parent)
            self._ui.remove_file_path.setText(dir_path)

    def on_remove_btn_clicked(self) -> None:
        path = self._ui.remove_file_path.text().strip()
        self._ui.removed_table_data.setRowCount(0)
        is_batch = self._ui.remove_type.currentIndex() != 0

        if not path:
            QMessageBox.warning(self._parent, "Data Remove Error", "Select a file first, before removing its data!")
            return

        images = self._build_image_dict(path) if is_batch else {}
        self._worker = RemovalWorker(path, is_batch, images)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.finished_all.connect(self._on_finished)
        self._ui.remove_btn.setEnabled(False)
        self._ui.export_and_remove_btn.setEnabled(False)
        self._worker.start()

    def on_export_and_remove_btn_clicked(self) -> None:
        path = self._ui.remove_file_path.text().strip()
        if not path:
            QMessageBox.warning(
                self._parent,
                "Data Export Error",
                "Select an image or directory path to export data and remove metadata.",
            )
            return
        self._ui.extract_file_path.setText(path)
        self._trigger_export()
        self.on_remove_btn_clicked()

    # ------------------------------------------------------------------
    # Worker slots
    # ------------------------------------------------------------------

    def _on_result(self, name: str, status: object) -> None:
        row = self._ui.removed_table_data.rowCount()
        self._ui.removed_table_data.insertRow(row)
        self._ui.removed_table_data.setItem(row, 0, QTableWidgetItem(name))
        self._ui.removed_table_data.setItem(row, 1, QTableWidgetItem("Done!" if status else "Error!"))

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self._parent, "Data Remove Error", f"Removal failed: {message}")

    def _on_finished(self) -> None:
        self._ui.removed_table_data.resizeColumnsToContents()
        self._ui.remove_btn.setEnabled(True)
        self._ui.export_and_remove_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_image_dict(directory: str) -> dict:
        files = [f for f in os.listdir(directory) if Path(f).suffix.lower() in _SUPPORTED_EXTS]
        return {f: f for f in files}
