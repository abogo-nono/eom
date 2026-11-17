"""Small dialogs shared by several views."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QCheckBox, QFileDialog, QMessageBox

import exporters
import settings

EXPORT_FORMATS = ("json", "csv", "html", "txt")


def export_filters() -> list[str]:
    return [
        QCoreApplication.translate("Common", "JSON (*.json)"),
        QCoreApplication.translate("Common", "CSV spreadsheet (*.csv)"),
        QCoreApplication.translate("Common", "HTML report (*.html)"),
        QCoreApplication.translate("Common", "Text (*.txt)"),
    ]


def ask_export_path(parent, default_name: str = "metadata", fmt: str = "json") -> tuple[str, str] | None:
    """Save dialog offering every export format; returns ``(path, fmt)``."""
    filters = export_filters()
    start = str(Path(settings.get("last_dir") or Path.home()) / f"{default_name}.{fmt}")
    selected = filters[EXPORT_FORMATS.index(fmt)]
    path, chosen = QFileDialog.getSaveFileName(
        parent, QCoreApplication.translate("Common", "Export metadata"), start, ";;".join(filters), selected
    )
    if not path:
        return None
    detected = exporters.format_for_path(path, default="")
    if not detected:
        detected = EXPORT_FORMATS[filters.index(chosen)] if chosen in filters else fmt
        path = f"{path}.{detected}"
    return path, detected


def confirm_in_place(parent, count: int) -> bool:
    """Ask before modifying originals (unless the user opted out)."""
    if not settings.get("confirm_in_place"):
        return True
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(QCoreApplication.translate("Common", "Modify original files?"))
    box.setText(
        QCoreApplication.translate("Common", "%1 original file(s) will be modified. This cannot be undone.").replace(
            "%1", str(count)
        )
        + "\n\n"
        + QCoreApplication.translate("Common", "Tip: enable “Save copies to…” to keep the originals untouched.")
    )
    dont_ask = QCheckBox(QCoreApplication.translate("Common", "Don't ask again"))
    box.setCheckBox(dont_ask)
    box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    box.button(QMessageBox.Ok).setText(QCoreApplication.translate("Common", "Modify originals"))
    accepted = box.exec() == QMessageBox.Ok
    if accepted and dont_ask.isChecked():
        settings.set("confirm_in_place", False)
    return accepted
