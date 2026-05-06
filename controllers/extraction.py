"""ExtractionController — owns all extract and export logic."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from workers import ExtractionWorker

_SUPPORTED_FILTER = (
    "Media files "
    "(*.jpg *.JPG *.jpeg *.JPEG *.png *.PNG *.tif *.tiff *.TIF *.TIFF *.pdf *.PDF "
    "*.mp3 *.flac *.ogg *.oga *.opus *.wav *.aiff *.aif *.m4a *.m4b *.wma *.ape *.wv *.tta "
    "*.mp4 *.m4v *.mkv *.webm)"
)
_SUPPORTED_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".pdf",
    ".mp3",
    ".flac",
    ".ogg",
    ".oga",
    ".opus",
    ".wav",
    ".aiff",
    ".aif",
    ".m4a",
    ".m4b",
    ".wma",
    ".ape",
    ".wv",
    ".tta",
    ".mp4",
    ".m4v",
    ".mkv",
    ".webm",
}


class ExtractionController:
    """Manages the Extract page: browse, extract, and export flows.

    Takes a reference to the *ui* object (from Ui_MainWindow) and the parent
    QWidget so dialogs and message boxes are parented correctly.
    """

    def __init__(self, ui, parent) -> None:
        self._ui = ui
        self._parent = parent
        self._worker: ExtractionWorker | None = None

        ui.extract_browse_btn.clicked.connect(self.on_extract_browse_btn_clicked)
        ui.extract_btn.clicked.connect(self.on_extract_btn_clicked)
        ui.export_btn.clicked.connect(self.on_export_btn_clicked)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_extract_browse_btn_clicked(self) -> None:
        if self._ui.extraction_type.currentIndex() == 0:
            image_path = QFileDialog.getOpenFileName(self._parent, filter=_SUPPORTED_FILTER)[0]
            self._ui.extract_file_path.setText(image_path)
        else:
            dir_path = QFileDialog.getExistingDirectory(self._parent)
            self._ui.extract_file_path.setText(dir_path)

    def on_extract_btn_clicked(self) -> None:
        path = self._ui.extract_file_path.text().strip()
        self._ui.extracted_table_data.setRowCount(0)
        is_batch = self._ui.extraction_type.currentIndex() != 0

        if not path:
            QMessageBox.warning(
                self._parent,
                "Data Extract Error",
                "Select a file / directory first, before extracting data from image(s)!",
            )
            return

        images = self._build_image_dict(path) if is_batch else {}
        self._worker = ExtractionWorker(path, is_batch, images)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.finished_all.connect(self._on_finished)
        self._ui.extract_btn.setEnabled(False)
        self._ui.export_btn.setEnabled(False)
        self._worker.start()

    def on_export_btn_clicked(self) -> None:
        if not self._ui.extract_file_path.text():
            QMessageBox.warning(self._parent, "Empty file path", "Select a file first, before exporting its data.")
            return

        self.on_extract_btn_clicked()

        if not self._ui.extracted_table_data.rowCount():
            QMessageBox.warning(self._parent, "Data Export Error", "The image(s) don't contain any metadata!")
            return

        file_path, _ = QFileDialog.getSaveFileName(self._parent, "Save Extracted Data At", "", "Text Files (*.txt)")
        if not file_path:
            return

        try:
            with open(file_path, "w") as f:
                for i in range(self._ui.extracted_table_data.rowCount()):
                    key = self._ui.extracted_table_data.item(i, 0).text()
                    val = self._ui.extracted_table_data.item(i, 1).text()
                    f.write(f"{key}: {val}\n")
            QMessageBox.information(self._parent, "Data Exported Successfully", f"Data saved at: {file_path}")
        except OSError:
            QMessageBox.warning(self._parent, "Data Export Error", "Error while saving the file!")

    # ------------------------------------------------------------------
    # Worker slots
    # ------------------------------------------------------------------

    def _on_result(self, name: str, data: object) -> None:
        is_batch = self._worker and self._worker._is_batch
        if is_batch:
            row = self._ui.extracted_table_data.rowCount()
            self._ui.extracted_table_data.insertRow(row)
            self._ui.extracted_table_data.setItem(row, 0, QTableWidgetItem("Image Name"))
            self._ui.extracted_table_data.setItem(row, 1, QTableWidgetItem(name))
        if data:
            for prop, value in data.items():
                row = self._ui.extracted_table_data.rowCount()
                self._ui.extracted_table_data.insertRow(row)
                self._ui.extracted_table_data.setItem(row, 0, QTableWidgetItem(prop))
                self._ui.extracted_table_data.setItem(row, 1, QTableWidgetItem(str(value)))
        elif not is_batch:
            QMessageBox.warning(self._parent, "Data Extract Error", "The file doesn't contain any metadata!")

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self._parent, "Data Extract Error", f"Extraction failed: {message}")

    def _on_finished(self) -> None:
        self._ui.extracted_table_data.resizeColumnsToContents()
        self._ui.extract_btn.setEnabled(True)
        self._ui.export_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_image_dict(directory: str) -> dict:
        files = [f for f in os.listdir(directory) if Path(f).suffix.lower() in _SUPPORTED_EXTS]
        return {f: f for f in files}
