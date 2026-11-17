"""Reusable widgets and dialogs: preview, map, before/after, edit, custom selection."""

from __future__ import annotations

import io
import math
import zipfile
from datetime import timedelta
from pathlib import Path

from PySide6.QtCore import QByteArray, QCoreApplication, QPointF, QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QImage, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import Extractor
import risk
import theme
from version import __version__


def category_label(category: str) -> str:
    return QCoreApplication.translate("risk", risk.CATEGORIES[category])


def severity_label(level: risk.Severity) -> str:
    names = {
        risk.Severity.NONE: QCoreApplication.translate("risk", "Clean"),
        risk.Severity.LOW: QCoreApplication.translate("risk", "Low"),
        risk.Severity.MEDIUM: QCoreApplication.translate("risk", "Medium"),
        risk.Severity.HIGH: QCoreApplication.translate("risk", "High"),
    }
    return names[level]


def risk_summary(report: risk.RiskReport) -> str:
    sensitive = [
        category_label(cat)
        for cat in sorted(report.findings, key=lambda c: -risk.CATEGORY_SEVERITY[c])
        if risk.CATEGORY_SEVERITY[cat] >= risk.Severity.MEDIUM
    ]
    label = severity_label(report.level)
    return f"{label} — {', '.join(sensitive)}" if sensitive else label


def severity_color(level: risk.Severity) -> QColor | None:
    token = {risk.Severity.HIGH: "high", risk.Severity.MEDIUM: "medium"}.get(level)
    return QColor(theme.color(token)) if token else None


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def _image_from_bytes(data: bytes, max_size: QSize) -> QImage | None:
    image = QImage.fromData(QByteArray(data))
    if image.isNull():
        return None
    return image.scaled(max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _audio_cover(path: str) -> bytes | None:
    try:
        from mutagen import File as MutagenFile

        f = MutagenFile(path)
    except Exception:  # noqa: BLE001
        return None
    if f is None:
        return None
    pictures = getattr(f, "pictures", None)  # FLAC
    if pictures:
        return pictures[0].data
    tags = getattr(f, "tags", None)
    if tags is None:
        return None
    if hasattr(tags, "getall"):  # ID3
        apic = tags.getall("APIC")
        if apic:
            return apic[0].data
    covr = tags.get("covr") if hasattr(tags, "get") else None  # MP4
    if covr:
        return bytes(covr[0])
    return None


def render_preview(path: str, max_size: QSize) -> QImage | None:
    """Best-effort thumbnail for images, PDFs, Office files and audio covers."""
    suffix = Path(path).suffix.lower()
    if suffix in Extractor._PDF_EXTENSIONS:
        try:
            from PySide6.QtPdf import QPdfDocument
        except ImportError:  # pragma: no cover - QtPdf missing
            return None
        doc = QPdfDocument()
        if doc.load(path) != QPdfDocument.Error.None_ or doc.pageCount() < 1:
            return None
        page = doc.pagePointSize(0)
        if page.isEmpty():
            return None
        scale = min(max_size.width() / page.width(), max_size.height() / page.height())
        image = doc.render(0, QSize(max(1, int(page.width() * scale)), max(1, int(page.height() * scale))))
        doc.close()
        return None if image.isNull() else image
    if suffix in Extractor._OFFICE_EXTENSIONS:
        try:
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    if name.lower().startswith("docprops/thumbnail.") and name.lower().endswith(
                        (".jpeg", ".jpg", ".png")
                    ):
                        return _image_from_bytes(zf.read(name), max_size)
        except (zipfile.BadZipFile, OSError):
            return None
        return None
    if suffix in Extractor._AUDIO_VIDEO_EXTENSIONS:
        data = _audio_cover(path)
        return _image_from_bytes(data, max_size) if data else None

    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and (size.width() > max_size.width() or size.height() > max_size.height()):
        reader.setScaledSize(size.scaled(max_size, Qt.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        # Formats Qt cannot read (e.g. HEIC) — try Pillow.
        try:
            from PIL import Image

            with Image.open(path) as im:
                im.thumbnail((max_size.width(), max_size.height()))
                buf = io.BytesIO()
                im.convert("RGB").save(buf, "PNG")
            return _image_from_bytes(buf.getvalue(), max_size)
        except Exception:  # noqa: BLE001
            return None
    return image


class PreviewWidget(QLabel):
    """Shows a thumbnail of the selected file, or a short hint when none is available."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview_label")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(160)
        self.setWordWrap(True)
        self._path: str | None = None
        self.clear_preview()

    def clear_preview(self) -> None:
        self._path = None
        self.setPixmap(QPixmap())
        self.setText(QCoreApplication.translate("Widgets", "No file selected"))

    def set_file(self, path: str | None) -> None:
        if not path or path == self._path:
            if not path:
                self.clear_preview()
            return
        self._path = path
        image = render_preview(path, QSize(320, 240))
        if image is None:
            self.setPixmap(QPixmap())
            self.setText(
                QCoreApplication.translate("Widgets", "No preview for this file type") + f"\n{Path(path).name}"
            )
        else:
            self.setText("")
            self.setPixmap(QPixmap.fromImage(image))
        self.setToolTip(path)


# ---------------------------------------------------------------------------
# Map (OpenStreetMap tiles, opt-in)
# ---------------------------------------------------------------------------

TILE_SIZE = 256
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
MAX_ZOOM = 17


def lonlat_to_pixel(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    """Web-Mercator world pixel coordinates at *zoom*."""
    lat = max(min(lat, 85.05112878), -85.05112878)
    scale = TILE_SIZE * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * scale
    return x, y


def fit_zoom(points: list[tuple[float, float]], width: int, height: int, margin: int = 40) -> int:
    """Largest zoom (≤ 15 for a single point) at which all points fit in the viewport."""
    if len(points) <= 1:
        return 15
    for zoom in range(MAX_ZOOM, -1, -1):
        xs, ys = zip(*(lonlat_to_pixel(lon, lat, zoom) for lat, lon in points), strict=True)
        if max(xs) - min(xs) <= width - 2 * margin and max(ys) - min(ys) <= height - 2 * margin:
            return zoom
    return 0


class MapWidget(QWidget):
    """Tiny slippy map: shows (lat, lon) markers on OpenStreetMap tiles.

    No request is made until :meth:`enable_network` is called — the caller
    decides based on the user's consent (Settings → "Allow map tiles").
    """

    consent_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(240, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._points: list[tuple[float, float]] = []
        self._zoom = 15
        self._center: tuple[float, float] = (0.0, 0.0)  # world pixel coords
        self._tiles: dict[tuple[int, int, int], QPixmap] = {}
        self._pending: set[tuple[int, int, int]] = set()
        self._network: QNetworkAccessManager | None = None
        self._drag_from: QPointF | None = None

        self._consent_btn = QPushButton(
            QCoreApplication.translate("Widgets", "Load map (contacts openstreetmap.org)"), self
        )
        self._consent_btn.setObjectName("secondary_btn")
        self._consent_btn.setCursor(Qt.PointingHandCursor)
        self._consent_btn.clicked.connect(self.consent_requested.emit)

    # -- public API ---------------------------------------------------------

    @property
    def points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def network_enabled(self) -> bool:
        return self._network is not None

    def enable_network(self) -> None:
        if self._network is None:
            self._network = QNetworkAccessManager(self)
        self._consent_btn.hide()
        self.update()

    def set_points(self, points: list[tuple[float, float]]) -> None:
        self._points = list(points)
        if not self._points:
            self.update()
            return
        self._zoom = fit_zoom(self._points, max(self.width(), 240), max(self.height(), 200))
        self._recenter()
        self.update()

    def osm_url(self) -> str | None:
        if not self._points:
            return None
        lat, lon = self._points[0]
        return f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}"

    # -- internals ----------------------------------------------------------

    def _recenter(self) -> None:
        pixels = [lonlat_to_pixel(lon, lat, self._zoom) for lat, lon in self._points]
        xs, ys = zip(*pixels, strict=True)
        self._center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)

    def _set_zoom(self, zoom: int) -> None:
        zoom = max(1, min(MAX_ZOOM, zoom))
        if zoom == self._zoom:
            return
        factor = 2 ** (zoom - self._zoom)
        self._center = (self._center[0] * factor, self._center[1] * factor)
        self._zoom = zoom
        self.update()

    def _request_tile(self, key: tuple[int, int, int]) -> None:
        if self._network is None or key in self._pending:
            return
        self._pending.add(key)
        z, x, y = key
        request = QNetworkRequest(QUrl(TILE_URL.format(z=z, x=x, y=y)))
        # OSM tile usage policy requires an identifying User-Agent.
        request.setHeader(QNetworkRequest.UserAgentHeader, f"EOM/{__version__} (+https://github.com/abogo-nono/eom)")
        reply = self._network.get(request)
        reply.finished.connect(lambda r=reply, k=key: self._on_tile(r, k))

    def _on_tile(self, reply: QNetworkReply, key: tuple[int, int, int]) -> None:
        self._pending.discard(key)
        if reply.error() == QNetworkReply.NoError:
            pixmap = QPixmap()
            if pixmap.loadFromData(reply.readAll()):
                self._tiles[key] = pixmap
                self.update()
        reply.deleteLater()

    def resizeEvent(self, event) -> None:  # noqa: N802 — Qt override
        self._consent_btn.adjustSize()
        self._consent_btn.move(
            (self.width() - self._consent_btn.width()) // 2, (self.height() - self._consent_btn.height()) // 2
        )
        super().resizeEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._network is not None and self._points:
            self._set_zoom(self._zoom + (1 if event.angleDelta().y() > 0 else -1))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag_from = event.position()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_from is not None:
            delta = event.position() - self._drag_from
            self._center = (self._center[0] - delta.x(), self._center[1] - delta.y())
            self._drag_from = event.position()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_from = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        url = self.osm_url()
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(theme.color("input_bg")))
        w, h = self.width(), self.height()

        if not self._points:
            painter.setPen(QColor(theme.color("muted")))
            painter.drawText(
                self.rect(), Qt.AlignCenter, QCoreApplication.translate("Widgets", "No GPS location in this file")
            )
            self._consent_btn.hide()
            return

        if self._network is None:
            self._consent_btn.show()
            painter.setPen(QColor(theme.color("muted")))
            lat, lon = self._points[0]
            text = (
                f"{lat:.5f}, {lon:.5f}"
                if len(self._points) == 1
                else QCoreApplication.translate("Widgets", "%n location(s)").replace("%n", str(len(self._points)))
            )
            painter.drawText(QRectF(0, h / 2 + 24, w, 30), Qt.AlignHCenter | Qt.AlignTop, text)
            return

        cx, cy = self._center
        left, top = cx - w / 2, cy - h / 2
        n = 2**self._zoom
        for tx in range(int(left // TILE_SIZE), int((left + w) // TILE_SIZE) + 1):
            for ty in range(int(top // TILE_SIZE), int((top + h) // TILE_SIZE) + 1):
                if ty < 0 or ty >= n:
                    continue
                key = (self._zoom, tx % n, ty)
                pixmap = self._tiles.get(key)
                if pixmap is None:
                    self._request_tile(key)
                    continue
                painter.drawPixmap(int(tx * TILE_SIZE - left), int(ty * TILE_SIZE - top), pixmap)

        pen = QPen(QColor("#ffffff"), 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(theme.color("high"))))
        for lat, lon in self._points:
            px, py = lonlat_to_pixel(lon, lat, self._zoom)
            painter.drawEllipse(QPointF(px - left, py - top), 7, 7)

        # Attribution is mandatory under the OSM tile usage policy.
        font = QFont(self.font())
        font.setPointSize(7)
        painter.setFont(font)
        label = "© OpenStreetMap contributors"
        metrics = painter.fontMetrics()
        rect = QRectF(
            w - metrics.horizontalAdvance(label) - 10,
            h - metrics.height() - 4,
            metrics.horizontalAdvance(label) + 8,
            metrics.height() + 2,
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        painter.drawRect(rect)
        painter.setPen(QColor("#333333"))
        painter.drawText(rect, Qt.AlignCenter, label)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


class BeforeAfterDialog(QDialog):
    """Side-by-side comparison of a file's metadata before and after cleaning."""

    def __init__(self, name: str, before: dict | None, after: dict | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Before / after — %1").replace("%1", Path(name).name))
        self.resize(820, 520)
        diff = Extractor.diff_metadata(before, after)
        before = {k: v for k, v in (before or {}).items() if not risk.is_file_property(k) and k != "GoogleMapLink"}
        after = {k: v for k, v in (after or {}).items() if not risk.is_file_property(k) and k != "GoogleMapLink"}

        layout = QVBoxLayout(self)
        residual = risk.assess(after)
        summary = QLabel(
            self.tr("%1 tag(s) removed, %2 changed, %3 kept. Remaining risk: %4")
            .replace("%1", str(len(diff["removed"])))
            .replace("%2", str(len(diff["changed"])))
            .replace("%3", str(len(diff["remaining"])))
            .replace("%4", risk_summary(residual))
        )
        summary.setObjectName("risk_banner")
        summary.setProperty("level", residual.level.name.lower())
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([self.tr("Tag"), self.tr("Before"), self.tr("After"), self.tr("Result")])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        keys = list(before) + [k for k in after if k not in before]
        removed, changed = set(diff["removed"]), set(diff["changed"])
        for key in keys:
            row = self.table.rowCount()
            self.table.insertRow(row)
            if key in removed:
                result, color = self.tr("Removed"), theme.color("low")
            elif key in changed:
                result, color = self.tr("Changed"), theme.color("medium")
            elif key in before:
                sev = risk.severity_of(key)
                result = self.tr("Kept")
                color = theme.color("high") if sev >= risk.Severity.HIGH else theme.color("muted")
            else:
                result, color = self.tr("Added"), theme.color("medium")
            for col, text in enumerate((key, str(before.get(key, "—")), str(after.get(key, "—")), result)):
                item = QTableWidgetItem(text)
                if col == 3:
                    item.setForeground(QColor(color))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class EditDialog(QDialog):
    """Edit common fields and/or shift every date of one file or a whole folder."""

    def __init__(self, target_label: str, current: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Edit metadata"))
        self.setMinimumWidth(520)
        current = current or {}

        layout = QVBoxLayout(self)
        intro = QLabel(self.tr("Target: %1").replace("%1", target_label))
        intro.setObjectName("muted_label")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        hint = QLabel(self.tr("Tick a field to change it. A ticked empty field is cleared."))
        hint.setObjectName("muted_label")
        layout.addWidget(hint)

        grid = QGridLayout()
        self._fields: dict[str, tuple[QCheckBox, QLineEdit]] = {}
        labels = {
            "Title": self.tr("Title"),
            "Author": self.tr("Author / artist"),
            "Copyright": self.tr("Copyright"),
            "Description": self.tr("Description"),
            "Date": self.tr("Date (YYYY-MM-DD HH:MM:SS)"),
        }
        for row, name in enumerate(Extractor.EDITABLE_FIELDS):
            check = QCheckBox(labels[name])
            edit = QLineEdit(self._guess(name, current))
            edit.setEnabled(False)
            check.toggled.connect(edit.setEnabled)
            grid.addWidget(check, row, 0)
            grid.addWidget(edit, row, 1)
            self._fields[name] = (check, edit)
        layout.addLayout(grid)

        shift_title = QLabel(self.tr("Shift all dates (fix a wrong camera clock)"))
        shift_title.setObjectName("section_title")
        layout.addWidget(shift_title)
        shift_row = QHBoxLayout()
        self._days, self._hours, self._minutes = (QSpinBox(), QSpinBox(), QSpinBox())
        for spin, rng, suffix in (
            (self._days, 3650, self.tr(" d")),
            (self._hours, 23, self.tr(" h")),
            (self._minutes, 59, self.tr(" min")),
        ):
            spin.setRange(-rng, rng)
            spin.setSuffix(suffix)
            shift_row.addWidget(spin)
        shift_row.addStretch()
        layout.addLayout(shift_row)

        self._error = QLabel()
        self._error.setObjectName("risk_banner")
        self._error.setProperty("level", "high")
        self._error.hide()
        layout.addWidget(self._error)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(self.tr("Apply"))
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _guess(name: str, data: dict) -> str:
        candidates = {
            "Title": ("Title", "XPTitle", "ObjectName"),
            "Author": ("Artist", "Author", "Creator", "By-line"),
            "Copyright": ("Copyright", "Rights"),
            "Description": ("ImageDescription", "Description", "Subject", "Comment"),
            "Date": ("DateTimeOriginal", "CreateDate", "CreationDate", "Created", "DateTime", "Date"),
        }[name]
        for key, value in data.items():
            if risk.split_key(key)[1] in candidates and value:
                return str(value)
        return ""

    def fields(self) -> dict[str, str]:
        return {name: edit.text().strip() for name, (check, edit) in self._fields.items() if check.isChecked()}

    def shift(self) -> timedelta:
        return timedelta(days=self._days.value(), hours=self._hours.value(), minutes=self._minutes.value())

    def _validate(self) -> None:
        fields = self.fields()
        if not fields and not self.shift():
            self._show_error(self.tr("Nothing to change: tick a field or set a date shift."))
            return
        if fields.get("Date"):
            try:
                Extractor._parse_user_date(fields["Date"])
            except ValueError:
                self._show_error(self.tr("The date must look like 2024-05-31 14:30:00."))
                return
        self.accept()

    def _show_error(self, text: str) -> None:
        self._error.setText(text)
        self._error.show()


class CustomSelectionDialog(QDialog):
    """Pick categories (any mode) or individual tags (single file) to remove."""

    def __init__(
        self,
        metadata: dict | None,
        selected_categories: set[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Choose what to remove"))
        self.resize(640, 560)
        self._metadata = {
            k: v for k, v in (metadata or {}).items() if not risk.is_file_property(k) and k != "GoogleMapLink"
        }
        self._updating = False

        layout = QVBoxLayout(self)
        hint = QLabel(
            self.tr("Tick categories or individual tags. Sensitive tags are pre-selected.")
            if self._metadata
            else self.tr("Tick the categories to remove from every file.")
        )
        hint.setObjectName("muted_label")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([self.tr("Category / tag"), self.tr("Value")])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._category_items: dict[str, QTreeWidgetItem] = {}
        by_category: dict[str, list[str]] = {}
        for key in self._metadata:
            by_category.setdefault(risk.categorize(key), []).append(key)

        for category in sorted(risk.CATEGORIES, key=lambda c: -risk.CATEGORY_SEVERITY[c]):
            keys = by_category.get(category, [])
            if self._metadata and not keys:
                continue
            item = QTreeWidgetItem([category_label(category), f"{len(keys)}" if self._metadata else ""])
            item.setData(0, Qt.UserRole, category)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            color = severity_color(risk.CATEGORY_SEVERITY[category])
            if color:
                item.setForeground(0, color)
            checked = category in selected_categories
            item.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
            for key in keys:
                child = QTreeWidgetItem([key, str(self._metadata[key])[:200]])
                child.setData(0, Qt.UserRole, key)
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
                item.addChild(child)
            self.tree.addTopLevelItem(item)
            self._category_items[category] = item
        layout.addWidget(self.tree)

        quick = QHBoxLayout()
        for text, cats in (
            (self.tr("Select sensitive"), {c for c, s in risk.CATEGORY_SEVERITY.items() if s >= risk.Severity.MEDIUM}),
            (self.tr("Select all"), set(risk.CATEGORIES)),
            (self.tr("Select none"), set()),
        ):
            btn = QPushButton(text)
            btn.setObjectName("secondary_btn")
            btn.clicked.connect(lambda _=False, c=cats: self._select(c))
            quick.addWidget(btn)
        quick.addStretch()
        layout.addLayout(quick)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select(self, categories: set[str]) -> None:
        for category, item in self._category_items.items():
            item.setCheckState(0, Qt.Checked if category in categories else Qt.Unchecked)
            for i in range(item.childCount()):
                item.child(i).setCheckState(0, Qt.Checked if category in categories else Qt.Unchecked)

    def categories(self) -> set[str]:
        """Categories fully or partially checked."""
        return {cat for cat, item in self._category_items.items() if item.checkState(0) != Qt.Unchecked}

    def keys(self) -> list[str] | None:
        """Individually checked tags (single-file mode), else None."""
        if not self._metadata:
            return None
        keys = []
        for item in self._category_items.values():
            for i in range(item.childCount()):
                child = item.child(i)
                if child.checkState(0) == Qt.Checked:
                    keys.append(child.data(0, Qt.UserRole))
        return keys
