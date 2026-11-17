"""ExtractionController — owns the Extract page: browse, extract, filter, risk, preview, map, export, edit."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
)

import exporters
import Extractor
import risk
import settings
import theme
from controllers.common import FileSelection, ask_export_path, confirm_in_place
from widgets import (
    EditDialog,
    MapWidget,
    PreviewWidget,
    category_label,
    risk_summary,
    severity_color,
    severity_label,
)
from workers import EditWorker, ExtractionWorker

_FILE_ROLE = Qt.UserRole  # stored on column 0: the display name of the file the row belongs to
_HEADER_ROLE = Qt.UserRole + 1  # True on per-file header rows (batch mode)


class ExtractionController(QObject):
    """Manages the Extract page.

    Takes a reference to the *ui* object (from Ui_MainWindow) and the parent
    QWidget so dialogs and message boxes are parented correctly.
    """

    def __init__(self, ui, parent) -> None:
        super().__init__(parent)
        self._ui = ui
        self._parent = parent
        self._worker: ExtractionWorker | None = None
        self._edit_worker: EditWorker | None = None
        self._results: dict[str, dict | None] = {}
        self._paths: dict[str, str] = {}  # display name -> absolute path
        self._base: str = ""
        self._is_batch = False

        self.selection = FileSelection(
            parent, ui.extraction_type, ui.extract_file_path, ui.horizontalLayout_9, self.on_extract_btn_clicked
        )
        ui.extract_browse_btn.clicked.connect(self.on_extract_browse_btn_clicked)
        ui.extract_btn.clicked.connect(self.on_extract_btn_clicked)
        ui.export_btn.clicked.connect(self.on_export_btn_clicked)
        ui.extract_file_path.returnPressed.connect(self.on_extract_btn_clicked)
        ui.extract_file_path.setPlaceholderText(self.tr("Drop files here, or browse…"))
        ui.export_btn.setToolTip(self.tr("Export the results as JSON, CSV, HTML or text"))

        layout = ui.extract_page.layout()
        table = ui.extracted_table_data
        layout.removeWidget(table)

        # Row 1 — filter, risk banner, edit.
        options = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName("filter_edit")
        self.filter_edit.setPlaceholderText(self.tr("Filter tags or values…"))
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self.on_filter_edit_textChanged)
        options.addWidget(self.filter_edit, 2)
        self.risk_banner = QLabel()
        self.risk_banner.setObjectName("risk_banner")
        self.risk_banner.setWordWrap(True)
        self.risk_banner.hide()
        options.addWidget(self.risk_banner, 3)
        self.edit_btn = QPushButton(self.tr("Edit…"))
        self.edit_btn.setObjectName("secondary_btn")
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.setToolTip(self.tr("Change author, title, copyright, dates…"))
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self.on_edit_btn_clicked)
        options.addWidget(self.edit_btn)
        layout.addLayout(options, 1, 0)

        # Row 2 — table | side panel (preview + map).
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(table)
        side = QFrame()
        side.setObjectName("side_panel")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(10, 10, 10, 10)
        self.preview = PreviewWidget()
        side_layout.addWidget(self.preview, 1)
        self.location_label = QLabel()
        self.location_label.setObjectName("muted_label")
        self.location_label.setOpenExternalLinks(True)
        self.location_label.setWordWrap(True)
        side_layout.addWidget(self.location_label)
        self.map = MapWidget()
        self.map.consent_requested.connect(self.on_map_consent_requested)
        side_layout.addWidget(self.map, 1)
        self.splitter.addWidget(side)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.side_panel = side
        side.hide()
        layout.addWidget(self.splitter, 2, 0)

        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([self.tr("Tag"), self.tr("Value")])
        table.horizontalHeader().setStretchLastSection(True)
        table.itemSelectionChanged.connect(self.on_extracted_table_data_itemSelectionChanged)
        table.itemDoubleClicked.connect(self.on_extracted_table_data_itemDoubleClicked)

        # Row 3 — progress; row 4 — empty state.
        self._progress = QProgressBar()
        self._progress.setObjectName("extract_progress")
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress, 3, 0)

        self._empty_state = QLabel(self.tr("Drop files or a folder here, or browse, then click Extract."))
        self._empty_state.setAlignment(Qt.AlignCenter)
        self._empty_state.setObjectName("empty_state_label")
        layout.addWidget(self._empty_state, 4, 0)

        if settings.get("allow_map_tiles"):
            self.map.enable_network()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def on_extract_browse_btn_clicked(self) -> None:
        self.selection.browse()

    def on_extract_btn_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        selection = self.selection.resolve()
        table = self._ui.extracted_table_data
        table.setRowCount(0)
        if selection is None:
            return
        path, is_batch, images = selection
        if is_batch and not images:
            QMessageBox.information(
                self._parent, self.tr("No supported files"), self.tr("This folder contains no supported files.")
            )
            return

        self._results.clear()
        self._paths.clear()
        self._base, self._is_batch = path, is_batch
        self.preview.clear_preview()
        self.map.set_points([])
        self.location_label.clear()
        self.risk_banner.hide()

        self._worker = ExtractionWorker(path, is_batch, images)
        self._worker.result_ready.connect(self._on_result)
        self._worker.progress.connect(self._on_progress)
        self._worker.error.connect(self._on_error)
        self._worker.finished_all.connect(self._on_finished)
        self._set_busy(True, total=len(images) if is_batch else 1)
        self._worker.start()

    def on_export_btn_clicked(self) -> None:
        if not self._results:
            QMessageBox.warning(self._parent, self.tr("Nothing to export"), self.tr("Run an extraction first."))
            return
        if not any(self._results.values()):
            QMessageBox.warning(
                self._parent, self.tr("Nothing to export"), self.tr("The selected file(s) contain no metadata.")
            )
            return
        default = Path(self._base).stem or "metadata"
        choice = ask_export_path(self._parent, f"{default}-metadata")
        if choice is None:
            return
        path, fmt = choice
        try:
            exporters.export(self._results, path, fmt)
        except OSError as exc:
            QMessageBox.warning(
                self._parent, self.tr("Export failed"), self.tr("Could not save the file:\n%1").replace("%1", str(exc))
            )
            return
        QMessageBox.information(self._parent, self.tr("Export complete"), self.tr("Saved to:\n%1").replace("%1", path))

    def on_filter_edit_textChanged(self, text: str) -> None:  # noqa: N802 — handler naming convention
        table = self._ui.extracted_table_data
        needle = text.strip().lower()
        header_row = None
        header_has_match = False
        for row in range(table.rowCount()):
            key_item, val_item = table.item(row, 0), table.item(row, 1)
            if key_item is None:
                continue
            if key_item.data(_HEADER_ROLE):
                if header_row is not None:
                    table.setRowHidden(header_row, bool(needle) and not header_has_match)
                header_row, header_has_match = row, False
                continue
            haystack = f"{key_item.text()} {val_item.text() if val_item else ''}".lower()
            visible = not needle or needle in haystack
            table.setRowHidden(row, not visible)
            header_has_match = header_has_match or visible
        if header_row is not None:
            table.setRowHidden(header_row, bool(needle) and not header_has_match)

    def on_extracted_table_data_itemSelectionChanged(self) -> None:  # noqa: N802
        items = self._ui.extracted_table_data.selectedItems()
        name = None
        if items:
            key_item = self._ui.extracted_table_data.item(items[0].row(), 0)
            name = key_item.data(_FILE_ROLE) if key_item else None
        self._show_file(name)

    def on_extracted_table_data_itemDoubleClicked(self, item: QTableWidgetItem) -> None:  # noqa: N802
        value = self._ui.extracted_table_data.item(item.row(), 1)
        if value and value.text().startswith(("https://", "http://")):
            QDesktopServices.openUrl(QUrl(value.text()))

    def on_map_consent_requested(self) -> None:
        box = QMessageBox(self._parent)
        box.setWindowTitle(self.tr("Load the map?"))
        box.setText(
            self.tr(
                "Showing the map downloads tiles from openstreetmap.org. "
                "The OpenStreetMap servers will see your IP address and the area being displayed."
            )
        )
        always = box.addButton(self.tr("Always allow"), QMessageBox.AcceptRole)
        once = box.addButton(self.tr("Allow once"), QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is always:
            settings.set("allow_map_tiles", True)
            self.map.enable_network()
        elif box.clickedButton() is once:
            self.map.enable_network()

    def on_edit_btn_clicked(self) -> None:
        if not self._results:
            return
        output_mode = settings.get("output_mode") and settings.get("output_dir")
        if self._is_batch:
            label = self.tr("%1 file(s) in %2").replace("%1", str(len(self._paths))).replace("%2", self._base)
            current = None
        else:
            label = self._base
            current = self._results.get(self._base)
        if output_mode:
            label += "\n" + self.tr("Edited copies will be saved to: %1").replace("%1", settings.get("output_dir"))
        dlg = EditDialog(label, current, self._parent)
        if dlg.exec() != QDialog.Accepted:
            return
        if not output_mode and not confirm_in_place(self._parent, len(self._paths)):
            return
        images = (
            {name: Path(p).relative_to(self._base).as_posix() for name, p in self._paths.items()}
            if self._is_batch
            else {}
        )
        self._edit_worker = EditWorker(
            self._base,
            self._is_batch,
            images,
            fields=dlg.fields(),
            shift=dlg.shift() or None,
            output_dir=settings.get("output_dir") if output_mode else None,
        )
        failures: list[str] = []
        self._edit_worker.result_ready.connect(lambda name, ok: None if ok else failures.append(name))
        self._edit_worker.progress.connect(self._on_progress)
        self._edit_worker.error.connect(self._on_error)
        self._edit_worker.finished_all.connect(lambda: self._on_edit_finished(failures, bool(output_mode)))
        self._set_busy(True, total=max(1, len(images)))
        self._edit_worker.start()

    # ------------------------------------------------------------------
    # Public helpers (drag & drop, CLI arguments)
    # ------------------------------------------------------------------

    def load_paths(self, paths: list[str]) -> bool:
        return self.selection.load_paths(paths, activate=True)

    def reload_settings(self) -> None:
        self.selection.reload_settings()
        if settings.get("allow_map_tiles"):
            self.map.enable_network()

    @property
    def results(self) -> dict[str, dict | None]:
        return dict(self._results)

    # ------------------------------------------------------------------
    # Worker slots
    # ------------------------------------------------------------------

    def _on_result(self, name: str, data: object) -> None:
        self._empty_state.hide()
        table = self._ui.extracted_table_data
        self._results[name] = data
        self._paths[name] = str(Path(self._base) / name) if self._is_batch else name

        if self._is_batch:
            report = risk.assess(data)
            row = table.rowCount()
            table.insertRow(row)
            header = QTableWidgetItem(f"📄 {name}")
            font = QFont(header.font())
            font.setBold(True)
            header.setFont(font)
            header.setData(_FILE_ROLE, name)
            header.setData(_HEADER_ROLE, True)
            summary = QTableWidgetItem(risk_summary(report) if data else self.tr("No metadata"))
            color = severity_color(report.level)
            if color:
                summary.setForeground(color)
            table.setItem(row, 0, header)
            table.setItem(row, 1, summary)

        if data:
            # Most sensitive first; file-system properties (size, path…) last and dimmed.
            ordered = sorted(data.items(), key=lambda kv: (risk.is_file_property(kv[0]), -risk.severity_of(kv[0])))
            muted = QColor(theme.color("muted"))
            for prop, value in ordered:
                row = table.rowCount()
                table.insertRow(row)
                key_item = QTableWidgetItem(prop)
                key_item.setData(_FILE_ROLE, name)
                value_item = QTableWidgetItem(str(value))
                sev = risk.severity_of(prop)
                color = severity_color(sev)
                if color:
                    key_item.setForeground(color)
                if risk.is_file_property(prop) and sev == risk.Severity.NONE:
                    key_item.setForeground(muted)
                    value_item.setForeground(muted)
                    key_item.setToolTip(self.tr("File property (not embedded metadata)"))
                else:
                    key_item.setToolTip(f"{severity_label(sev)} · {category_label(risk.categorize(prop))}")
                table.setItem(row, 0, key_item)
                table.setItem(row, 1, value_item)
        elif not self._is_batch:
            QMessageBox.information(
                self._parent, self.tr("No metadata"), self.tr("This file doesn't contain any metadata.")
            )

    def _on_progress(self, current: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(current)

    def _on_error(self, message: str) -> None:
        QMessageBox.warning(self._parent, self.tr("Extraction failed"), message)

    def _on_finished(self) -> None:
        table = self._ui.extracted_table_data
        table.resizeColumnToContents(0)
        self._set_busy(False)
        self.on_filter_edit_textChanged(self.filter_edit.text())
        has_rows = table.rowCount() > 0
        self._empty_state.setVisible(not has_rows)
        self.side_panel.setVisible(bool(self._results))
        self.edit_btn.setEnabled(bool(self._results))
        self._update_risk_banner()
        self._show_file(None if self._is_batch else self._base)

    def _on_edit_finished(self, failures: list[str], output_mode: bool) -> None:
        self._set_busy(False)
        if failures:
            QMessageBox.warning(
                self._parent,
                self.tr("Some files were not edited"),
                self.tr("These files could not be edited (unsupported format or field):\n%1").replace(
                    "%1", "\n".join(failures[:20])
                ),
            )
        if output_mode:
            QMessageBox.information(
                self._parent,
                self.tr("Edit complete"),
                self.tr("Edited copies saved to:\n%1").replace("%1", settings.get("output_dir")),
            )
        else:
            self.on_extract_btn_clicked()  # refresh with the new values

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool, total: int = 0) -> None:
        self._ui.extract_btn.setEnabled(not busy)
        self._ui.export_btn.setEnabled(not busy)
        self.edit_btn.setEnabled(not busy and bool(self._results))
        if busy:
            self._empty_state.hide()
            self._progress.setRange(0, total if total > 1 else 0)
            self._progress.setValue(0)
        self._progress.setVisible(busy)

    def _update_risk_banner(self) -> None:
        if not self._results:
            self.risk_banner.hide()
            return
        if not self._is_batch:
            report = risk.assess(next(iter(self._results.values())))
            text = self.tr("Privacy risk: %1").replace("%1", risk_summary(report))
            level = report.level
        else:
            levels = [risk.assess(d).level for d in self._results.values()]
            level = max(levels, default=risk.Severity.NONE)
            text = self.tr("%1 file(s) · %2 high risk · %3 medium risk").replace("%1", str(len(levels)))
            text = text.replace("%2", str(levels.count(risk.Severity.HIGH))).replace(
                "%3", str(levels.count(risk.Severity.MEDIUM))
            )
        self.risk_banner.setText(text)
        self.risk_banner.setProperty("level", level.name.lower())
        self.risk_banner.style().unpolish(self.risk_banner)
        self.risk_banner.style().polish(self.risk_banner)
        self.risk_banner.show()

    def _show_file(self, name: str | None) -> None:
        """Preview + map for one file, or every geotagged file when *name* is None."""
        if name is not None:
            self.preview.set_file(self._paths.get(name))
            coords = Extractor.gps_coordinates(self._results.get(name))
            points = [coords] if coords else []
        else:
            self.preview.clear_preview()
            points = [c for c in (Extractor.gps_coordinates(d) for d in self._results.values()) if c]
        self.map.set_points(points)
        if len(points) == 1:
            lat, lon = points[0]
            url = f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}"
            self.location_label.setText(
                self.tr("📍 Location: %1, %2 — <a href='%3'>open in browser</a>")
                .replace("%1", f"{lat:.5f}")
                .replace("%2", f"{lon:.5f}")
                .replace("%3", url)
            )
        elif points:
            self.location_label.setText(self.tr("📍 %1 geotagged file(s)").replace("%1", str(len(points))))
        else:
            self.location_label.setText(self.tr("No GPS location"))
