"""The workspace: one screen to add files, inspect their metadata and clean them.

Layout::

    ┌ drop zone (empty session) ─────────────────────────────────────┐
    or
    ┌ file list ─────┬ detail: header · tag tree (by category) · preview/map ┐
    │                │                                                      │
    ├────────────────┴──────────────────────────────────────────────────────┤
    │ profile ▾  ☐ copies → folder        summary        Export ▾   Clean N │
    └───────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QModelIndex, QRect, QSize, Qt, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import exporters
import Extractor
import formats
import icons
import profiles
import risk
import settings
import theme
from session import CLEANED, FAILED, PENDING, CleaningPlan, FileEntry, Session, expand
from views.common import EXPORT_FORMATS, ask_export_path, confirm_in_place
from widgets import (
    BeforeAfterDialog,
    CustomSelectionDialog,
    EditDialog,
    MapWidget,
    PreviewWidget,
    category_label,
    set_badge,
    severity_label,
    styled,
)
from workers import CleanTask, EditWorker, ExtractionWorker, RemovalWorker

PATH_ROLE = Qt.UserRole
KEY_ROLE = Qt.UserRole + 1
CATEGORY_ROLE = Qt.UserRole + 2
FILE_GROUP = "__file__"


def _level_name(level: risk.Severity) -> str:
    return level.name.lower()


def _rgba(token: str, alpha: int) -> QColor:
    color = QColor(theme.color(token))
    color.setAlpha(alpha)
    return color


# ---------------------------------------------------------------------------
# Drop zone (empty state)
# ---------------------------------------------------------------------------


class DropZone(QWidget):
    """Shown when the session is empty: a big target plus recent items."""

    add_files = Signal()
    add_folder = Signal()
    open_recent = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.addStretch(1)

        self.frame = QFrame()
        self.frame.setObjectName("DropZone")
        self.frame.setMinimumHeight(300)
        self.frame.setMaximumWidth(760)
        box = QVBoxLayout(self.frame)
        box.setContentsMargins(40, 40, 40, 36)
        box.setSpacing(10)
        box.setAlignment(Qt.AlignCenter)

        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignCenter)
        box.addWidget(self.icon)

        title = styled(QLabel(self.tr("Drop files or folders here")), role="hero")
        title.setAlignment(Qt.AlignCenter)
        box.addWidget(title)
        sub = styled(
            QLabel(self.tr("See what your photos, documents and media reveal about you — then clean them.")),
            role="muted",
        )
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        box.addWidget(sub)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch()
        self.files_btn = styled(QPushButton(self.tr("Add files")), kind="primary")
        self.files_btn.setCursor(Qt.PointingHandCursor)
        self.files_btn.clicked.connect(self.add_files)
        self.folder_btn = QPushButton(self.tr("Add a folder"))
        self.folder_btn.setCursor(Qt.PointingHandCursor)
        self.folder_btn.clicked.connect(self.add_folder)
        buttons.addWidget(self.files_btn)
        buttons.addWidget(self.folder_btn)
        buttons.addStretch()
        box.addSpacing(8)
        box.addLayout(buttons)

        privacy = styled(QLabel(self.tr("🔒 Everything stays on this computer — nothing is uploaded.")), role="caption")
        privacy.setAlignment(Qt.AlignCenter)
        box.addSpacing(6)
        box.addWidget(privacy)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.frame, 10)
        row.addStretch()
        outer.addLayout(row)

        self.recent_box = QWidget()
        self.recent_box.setMaximumWidth(760)
        self.recent_layout = QVBoxLayout(self.recent_box)
        self.recent_layout.setContentsMargins(4, 18, 4, 0)
        self.recent_layout.setSpacing(2)
        rrow = QHBoxLayout()
        rrow.addStretch()
        rrow.addWidget(self.recent_box, 10)
        rrow.addStretch()
        outer.addLayout(rrow)
        outer.addStretch(2)
        self.refresh()

    def set_active(self, active: bool) -> None:
        self.frame.setProperty("active", active)
        self.frame.style().unpolish(self.frame)
        self.frame.style().polish(self.frame)

    def refresh(self) -> None:
        self.icon.setPixmap(icons.pixmap("inbox", 56, "primary"))
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        items = [p for p in settings.recent() if Path(p).exists()][:5]
        if not items:
            return
        self.recent_layout.addWidget(styled(QLabel(self.tr("RECENT")), role="section"))
        for path in items:
            btn = styled(
                QPushButton(icons.icon("folder" if Path(path).is_dir() else icons.for_file(path), "muted"), path),
                kind="ghost",
            )
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("text-align: left;")
            btn.clicked.connect(lambda _=False, p=path: self.open_recent.emit(p))
            self.recent_layout.addWidget(btn)


# ---------------------------------------------------------------------------
# File list
# ---------------------------------------------------------------------------


class FileDelegate(QStyledItemDelegate):
    """Two-line row: type icon · name / status · risk pill."""

    def __init__(self, session: Session, plan_getter, parent=None) -> None:
        super().__init__(parent)
        self._session = session
        self._plan = plan_getter

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), 52)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        entry = self._session.get(index.data(PATH_ROLE))
        if entry is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        rect = option.rect.adjusted(6, 2, -6, -2)
        if option.state & QStyle.State_Selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(_rgba("primary", 38))
            painter.drawRoundedRect(rect, 8, 8)
        elif option.state & QStyle.State_MouseOver:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.color("surface_alt")))
            painter.drawRoundedRect(rect, 8, 8)

        icon_rect = QRect(rect.left() + 10, rect.center().y() - 10, 20, 20)
        painter.drawPixmap(icon_rect, icons.pixmap(icons.for_file(entry.path), 20, "muted"))

        # Right-hand pill.
        pill_text, pill_token = self._pill(entry)
        small = QFont(option.font)
        small.setPointSizeF(max(7.5, option.font.pointSizeF() - 1.5))
        small.setBold(True)
        fm_small = QFontMetrics(small)
        pill_w = fm_small.horizontalAdvance(pill_text) + 16 if pill_text else 0
        pill_rect = QRect(rect.right() - pill_w - 8, rect.center().y() - 10, pill_w, 20)
        if pill_text:
            painter.setPen(Qt.NoPen)
            painter.setBrush(_rgba(pill_token, 36))
            painter.drawRoundedRect(pill_rect, 10, 10)
            painter.setPen(QColor(theme.color(pill_token)))
            painter.setFont(small)
            painter.drawText(pill_rect, Qt.AlignCenter, pill_text)

        text_left = icon_rect.right() + 12
        text_w = max(10, pill_rect.left() - text_left - 8)
        name_font = QFont(option.font)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor(theme.color("text")))
        fm = QFontMetrics(name_font)
        painter.drawText(
            QRect(text_left, rect.top() + 7, text_w, fm.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            fm.elidedText(entry.name, Qt.ElideMiddle, text_w),
        )
        sub_font = QFont(option.font)
        sub_font.setPointSizeF(max(7.5, option.font.pointSizeF() - 1))
        painter.setFont(sub_font)
        painter.setPen(QColor(theme.color("muted")))
        fm2 = QFontMetrics(sub_font)
        painter.drawText(
            QRect(text_left, rect.bottom() - fm2.height() - 6, text_w, fm2.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            fm2.elidedText(self._subtitle(entry), Qt.ElideRight, text_w),
        )
        painter.restore()

    def _pill(self, entry: FileEntry) -> tuple[str, str]:
        if entry.state == PENDING:
            return "", "muted"
        if entry.state == FAILED:
            return self.tr("Error"), "high"
        level = entry.risk.level
        token = {risk.Severity.HIGH: "high", risk.Severity.MEDIUM: "medium"}.get(level, "low")
        return severity_label(level), token

    def _subtitle(self, entry: FileEntry) -> str:
        if entry.state == PENDING:
            return self.tr("Reading…")
        if entry.state == FAILED:
            return self.tr("Could not be cleaned")
        if entry.state == CLEANED and entry.report:
            removed = len((entry.report.get("diff") or {}).get("removed", []))
            text = self.tr("✓ Cleaned · %1 tag(s) removed").replace("%1", str(removed))
            if entry.report.get("target") != entry.path:
                text += " · " + self.tr("copy saved")
            return text
        keys = entry.embedded_keys
        if not keys:
            return self.tr("No metadata")
        sensitive = sum(1 for k in keys if risk.severity_of(k) >= risk.Severity.MEDIUM)
        return self.tr("%1 tag(s) · %2 sensitive").replace("%1", str(len(keys))).replace("%2", str(sensitive))


# ---------------------------------------------------------------------------
# Tag tree
# ---------------------------------------------------------------------------


class TagTree(QTreeWidget):
    """Metadata of one file grouped by risk category, with the cleaning preview."""

    custom_keys_changed = Signal(set)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHeaderLabels([self.tr("Tag"), self.tr("Value"), self.tr("When cleaned")])
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        self.setColumnWidth(0, 210)
        self.setUniformRowHeights(True)
        self.setAnimated(True)
        self.setIndentation(18)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemDoubleClicked.connect(self._open_link)
        self.itemChanged.connect(self._on_item_changed)
        self._custom = False
        self._filling = False
        self._filter = ""
        # Categories the user opened/closed by hand — remembered across files.
        self._user_open: set[str] = set()
        self._user_closed: set[str] = set()
        self.itemExpanded.connect(lambda item: self._remember(item, True))
        self.itemCollapsed.connect(lambda item: self._remember(item, False))

    def _remember(self, item: QTreeWidgetItem, opened: bool) -> None:
        if self._filling or self._filter:
            return
        group = item.data(0, CATEGORY_ROLE)
        (self._user_open if opened else self._user_closed).add(group)
        (self._user_closed if opened else self._user_open).discard(group)

    def show_entry(self, entry: FileEntry | None, removed: set[str], custom: bool) -> None:
        self._filling = True
        self._custom = custom
        self.clear()
        if entry is None or not entry.metadata:
            self._filling = False
            return

        groups: dict[str, list[str]] = {}
        for key in entry.metadata:
            if key == "GoogleMapLink":
                continue
            group = FILE_GROUP if risk.is_file_property(key) else risk.categorize(key)
            groups.setdefault(group, []).append(key)

        order = sorted((g for g in groups if g != FILE_GROUP), key=lambda c: -risk.CATEGORY_SEVERITY[c])
        if FILE_GROUP in groups:
            order.append(FILE_GROUP)

        bold = QFont(self.font())
        bold.setBold(True)
        strike = QFont(self.font())
        strike.setStrikeOut(True)
        high = QColor(theme.color("high"))
        muted = QColor(theme.color("muted"))
        low = QColor(theme.color("low"))

        for group in order:
            keys = groups[group]
            is_file = group == FILE_GROUP
            severity = risk.Severity.NONE if is_file else risk.CATEGORY_SEVERITY[group]
            token = {risk.Severity.HIGH: "high", risk.Severity.MEDIUM: "medium"}.get(severity, "muted")
            label = self.tr("File properties (not embedded)") if is_file else category_label(group)
            n_removed = sum(1 for k in keys if k in removed)
            parent = QTreeWidgetItem([label, self.tr("%n tag(s)").replace("%n", str(len(keys))), ""])
            parent.setData(0, CATEGORY_ROLE, group)
            parent.setIcon(0, icons.icon("file" if is_file else icons.CATEGORY_ICONS[group], token))
            parent.setFont(0, bold)
            parent.setForeground(1, muted)
            parent.setFirstColumnSpanned(False)
            if n_removed and not custom:
                parent.setText(2, self.tr("%1 removed").replace("%1", str(n_removed)))
                parent.setForeground(2, high)
            if custom and not is_file:
                parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            for key in keys:
                group_name, name = risk.split_key(key)
                value = str(entry.metadata[key])
                shown = value if len(value) <= 300 else value[:300] + "…"
                child = QTreeWidgetItem([name, shown, ""])
                child.setData(0, KEY_ROLE, key)
                child.setToolTip(0, key)
                child.setToolTip(1, value[:2000])
                if is_file:
                    child.setForeground(0, muted)
                    child.setForeground(1, muted)
                elif custom:
                    child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                    child.setCheckState(0, Qt.Checked if key in removed else Qt.Unchecked)
                if not is_file and not custom:
                    if key in removed:
                        child.setText(2, self.tr("Remove"))
                        child.setForeground(2, high)
                        child.setFont(1, strike)
                        child.setForeground(1, muted)
                    else:
                        child.setText(2, self.tr("Keep"))
                        child.setForeground(2, low if severity < risk.Severity.MEDIUM else muted)
                parent.addChild(child)
            self.addTopLevelItem(parent)
            default_open = not is_file and severity >= risk.Severity.MEDIUM
            parent.setExpanded((default_open or group in self._user_open) and group not in self._user_closed)
        self._filling = False
        self.apply_filter(self._filter)

    def apply_filter(self, text: str) -> None:
        self._filter = needle = text.strip().lower()
        for i in range(self.topLevelItemCount()):
            parent = self.topLevelItem(i)
            any_visible = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                hay = f"{child.data(0, KEY_ROLE)} {child.text(1)}".lower()
                visible = not needle or needle in hay
                child.setHidden(not visible)
                any_visible |= visible
            parent.setHidden(not any_visible)
            if needle and any_visible:
                parent.setExpanded(True)

    def checked_keys(self) -> set[str]:
        keys = set()
        for i in range(self.topLevelItemCount()):
            parent = self.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.flags() & Qt.ItemIsUserCheckable and child.checkState(0) == Qt.Checked:
                    keys.add(child.data(0, KEY_ROLE))
        return keys

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._filling or not self._custom or column != 0:
            return
        self.custom_keys_changed.emit(self.checked_keys())

    def _open_link(self, item: QTreeWidgetItem, _column: int) -> None:
        if item.text(1).startswith(("http://", "https://")):
            QDesktopServices.openUrl(QUrl(item.text(1)))

    def _context_menu(self, pos) -> None:
        items = [i for i in self.selectedItems() if i.data(0, KEY_ROLE)]
        if not items:
            return
        menu = QMenu(self)
        copy_value = menu.addAction(self.tr("Copy value"))
        copy_row = menu.addAction(self.tr("Copy tag and value"))
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is copy_value:
            QGuiApplication.clipboard().setText("\n".join(i.toolTip(1) for i in items))
        elif chosen is copy_row:
            QGuiApplication.clipboard().setText("\n".join(f"{i.data(0, KEY_ROLE)}: {i.toolTip(1)}" for i in items))


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------


class DetailPanel(QWidget):
    compare_requested = Signal()
    edit_requested = Signal()
    remove_requested = Signal()
    map_consent_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        self.type_icon = QLabel()
        head.addWidget(self.type_icon)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        self.name = styled(QLabel(), role="h2")
        self.name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.badge = QLabel()
        name_row.addWidget(self.name)
        name_row.addWidget(self.badge)
        name_row.addStretch()
        titles.addLayout(name_row)
        self.path_btn = styled(QPushButton(), kind="link")
        self.path_btn.setCursor(Qt.PointingHandCursor)
        self.path_btn.setToolTip(self.tr("Open the containing folder"))
        self.path_btn.clicked.connect(self._open_folder)
        titles.addWidget(self.path_btn)
        head.addLayout(titles, 1)

        self.compare_btn = icons.bind(QPushButton(self.tr("Before / after")), "columns")
        self.compare_btn.clicked.connect(self.compare_requested)
        self.edit_btn = icons.bind(QPushButton(self.tr("Edit…")), "edit")
        self.edit_btn.setToolTip(self.tr("Change author, title, copyright, dates…"))
        self.edit_btn.clicked.connect(self.edit_requested)
        self.more_btn = styled(QToolButton(), kind="ghost")
        icons.bind(self.more_btn, "more")
        self.more_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.more_btn)
        menu.addAction(self.tr("Open containing folder"), self._open_folder)
        menu.addAction(self.tr("Copy path"), lambda: QGuiApplication.clipboard().setText(self._path or ""))
        menu.addSeparator()
        menu.addAction(self.tr("Remove from list"), self.remove_requested)
        self.more_btn.setMenu(menu)
        for btn in (self.compare_btn, self.edit_btn, self.more_btn):
            btn.setCursor(Qt.PointingHandCursor)
            head.addWidget(btn)
        layout.addLayout(head)

        self.summary = styled(QLabel(), role="muted")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tr("Search tags and values…"))
        self.search.setClearButtonEnabled(True)
        icons.bind(self.search.addAction(icons.icon("search", "muted"), QLineEdit.LeadingPosition), "search", "muted")
        layout.addWidget(self.search)

        self.splitter = QSplitter(Qt.Horizontal)
        self.tree = TagTree()
        self.search.textChanged.connect(self.tree.apply_filter)
        self.splitter.addWidget(self.tree)

        side = QWidget()
        side.setMinimumWidth(240)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(12, 0, 0, 0)
        side_layout.setSpacing(8)
        side_layout.addWidget(styled(QLabel(self.tr("PREVIEW")), role="section"))
        preview_frame = styled(QFrame(), panel="true")
        pf = QVBoxLayout(preview_frame)
        pf.setContentsMargins(8, 8, 8, 8)
        self.preview = PreviewWidget()
        pf.addWidget(self.preview)
        side_layout.addWidget(preview_frame, 3)
        side_layout.addWidget(styled(QLabel(self.tr("LOCATION")), role="section"))
        self.location = styled(QLabel(), role="caption")
        self.location.setOpenExternalLinks(True)
        self.location.setWordWrap(True)
        side_layout.addWidget(self.location)
        self.map = MapWidget()
        self.map.consent_requested.connect(self.map_consent_requested)
        side_layout.addWidget(self.map, 3)
        self.side = side
        self.splitter.addWidget(side)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([640, 320])
        layout.addWidget(self.splitter, 1)
        self._path: str | None = None

    def resizeEvent(self, event) -> None:  # noqa: N802
        # Below ~760 px the tag table needs the room more than the preview.
        self.side.setVisible(self.width() >= 760)
        super().resizeEvent(event)

    def _open_folder(self) -> None:
        if self._path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._path).parent)))

    def show_entry(self, entry: FileEntry | None, plan: CleaningPlan, profile_name: str) -> None:
        self._path = entry.path if entry else None
        if entry is None:
            self.name.setText("")
            self.badge.hide()
            self.path_btn.setText("")
            self.summary.setText("")
            self.tree.show_entry(None, set(), False)
            self.preview.clear_preview()
            self.map.set_points([])
            self.location.setText("")
            self.compare_btn.setEnabled(False)
            self.edit_btn.setEnabled(False)
            return

        self.type_icon.setPixmap(icons.pixmap(icons.for_file(entry.path), 28, "primary"))
        self.name.setText(entry.name)
        width = max(160, self.width() - 520)
        self.path_btn.setText(QFontMetrics(self.path_btn.font()).elidedText(entry.folder, Qt.ElideMiddle, width))
        self.path_btn.setToolTip(entry.folder)
        if entry.state == PENDING:
            self.badge.hide()
        else:
            report = entry.risk
            self.badge.setText(severity_label(report.level))
            set_badge(self.badge, _level_name(report.level) if report.level else "none")
            self.badge.show()

        removed = plan.keys_removed(entry) if entry.state != PENDING else set()
        keys = entry.embedded_keys
        sensitive = sum(1 for k in keys if risk.severity_of(k) >= risk.Severity.MEDIUM)
        if entry.state == PENDING:
            text = self.tr("Reading metadata…")
        elif not keys:
            text = self.tr("No embedded metadata found.")
        else:
            text = (
                self.tr("%1 tag(s), %2 sensitive. “%3” would remove %4 and keep %5.")
                .replace("%1", str(len(keys)))
                .replace("%2", str(sensitive))
                .replace("%3", profile_name)
                .replace("%4", str(len(removed)))
                .replace("%5", str(len(keys) - len(removed)))
            )
        if entry.state == CLEANED and entry.report and entry.report.get("target") != entry.path:
            text += "  " + self.tr("Cleaned copy: %1").replace("%1", Path(entry.report["target"]).name)
        self.summary.setText(text)

        self.tree.show_entry(entry, removed, plan.profile_id == "custom")
        self.compare_btn.setEnabled(bool(entry.report and entry.report.get("before") is not None))
        self.edit_btn.setEnabled(entry.state != PENDING)
        self.preview.set_file(entry.path)
        coords = Extractor.gps_coordinates(entry.metadata)
        self.map.set_points([coords] if coords else [])
        if coords:
            lat, lon = coords
            url = f"https://www.openstreetmap.org/?mlat={lat:.6f}&mlon={lon:.6f}#map=16/{lat:.6f}/{lon:.6f}"
            self.location.setText(
                self.tr("%1, %2 — <a href='%3'>open in browser</a>")
                .replace("%1", f"{lat:.5f}")
                .replace("%2", f"{lon:.5f}")
                .replace("%3", url)
            )
        else:
            self.location.setText(self.tr("No GPS position in this file."))


# ---------------------------------------------------------------------------
# Action bar
# ---------------------------------------------------------------------------


class ActionBar(QFrame):
    clean_requested = Signal()
    export_requested = Signal(str, bool)  # format, then clean
    profile_changed = Signal(str)
    customize_requested = Signal()
    copies_toggled = Signal(bool)
    output_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActionBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        layout.addWidget(styled(QLabel(self.tr("Clean with")), role="muted"))
        self.profile = QComboBox()
        for profile in profiles.PROFILES.values():
            self.profile.addItem(QCoreApplication.translate("profiles", profile.name), profile.id)
            self.profile.setItemData(
                self.profile.count() - 1,
                QCoreApplication.translate("profiles", profile.description),
                Qt.ToolTipRole,
            )
        self.profile.addItem(self.tr("Custom…"), "custom")
        self.profile.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.profile.setMinimumWidth(self.profile.sizeHint().width())
        self.profile.activated.connect(lambda _i: self.profile_changed.emit(self.profile.currentData()))
        layout.addWidget(self.profile)
        self.customize = styled(QPushButton(self.tr("Categories…")), kind="ghost")
        self.customize.setToolTip(
            self.tr(
                "Choose the categories removed from every file. Tick individual tags in the list for the current file."
            )
        )
        self.customize.clicked.connect(self.customize_requested)
        layout.addWidget(self.customize)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        layout.addWidget(sep)

        self.copies = QCheckBox(self.tr("Copies in"))
        self.copies.setToolTip(self.tr("Keep originals untouched and write cleaned copies to another folder"))
        self.copies.toggled.connect(self.copies_toggled)
        layout.addWidget(self.copies)
        self.output = styled(QPushButton(), kind="ghost")
        icons.bind(self.output, "folder", "muted")
        self.output.setCursor(Qt.PointingHandCursor)
        self.output.clicked.connect(self.output_requested)
        layout.addWidget(self.output)

        layout.addStretch()
        self.summary = styled(QLabel(), role="muted")
        layout.addWidget(self.summary)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(180)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.export_btn = icons.bind(QPushButton(self.tr("Export")), "download")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        menu = QMenu(self.export_btn)
        names = {"json": "JSON", "csv": "CSV", "html": self.tr("HTML report"), "txt": self.tr("Text")}
        for fmt in EXPORT_FORMATS:
            menu.addAction(names[fmt], lambda f=fmt: self.export_requested.emit(f, False))
        menu.addSeparator()
        menu.addAction(self.tr("Export, then clean…"), lambda: self.export_requested.emit("json", True))
        self.export_btn.setMenu(menu)
        layout.addWidget(self.export_btn)

        self.clean_btn = icons.bind(styled(QPushButton(self.tr("Clean")), kind="primary"), "shield-check", "on_accent")
        self.clean_btn.setCursor(Qt.PointingHandCursor)
        self.clean_btn.setMinimumWidth(170)
        self.clean_btn.setShortcut(QKeySequence("Ctrl+Return"))
        self.clean_btn.clicked.connect(self.clean_requested)
        layout.addWidget(self.clean_btn)

    def resizeEvent(self, event) -> None:  # noqa: N802
        # The summary is also the Clean button's tooltip, so it can go when space runs out.
        self.summary.setVisible(self.width() >= 1100 or self.progress.isVisible())
        super().resizeEvent(event)

    def set_summary(self, text: str) -> None:
        self.summary.setText(text)
        self.clean_btn.setToolTip(text)

    def set_busy(self, busy: bool, text: str = "") -> None:
        self.progress.setVisible(busy)
        self.summary.setText(text if busy else self.summary.text())
        for w in (self.clean_btn, self.export_btn, self.profile, self.customize, self.copies, self.output):
            w.setEnabled(not busy)


# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------


class WorkspaceView(QWidget):
    """Owns the session, the workers and every workspace widget.

    Signals
    -------
    message(str)   short status text for the window's status bar
    """

    message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.session = Session(self)
        self.plan = CleaningPlan()
        self._scan_worker: ExtractionWorker | None = None
        self._scan_queue: list[str] = []
        self._clean_worker: RemovalWorker | None = None
        self._edit_worker: EditWorker | None = None
        self._export_after_clean: tuple[str, str] | None = None
        self._map_allowed_once = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # Empty state.
        self.drop_zone = DropZone()
        self.drop_zone.add_files.connect(self.choose_files)
        self.drop_zone.add_folder.connect(self.choose_folder)
        self.drop_zone.open_recent.connect(lambda p: self.add_paths([p]))
        self.stack.addWidget(self.drop_zone)

        # Content.
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        left = QWidget()
        left.setMinimumWidth(290)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 14, 6, 10)
        ll.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(styled(QLabel(self.tr("Files")), role="h2"))
        self.count_label = QLabel()
        set_badge(self.count_label, "info")
        head.addWidget(self.count_label)
        head.addStretch()
        self.add_btn = styled(QToolButton(), kind="ghost")
        icons.bind(self.add_btn, "file-plus")
        self.add_btn.setToolTip(self.tr("Add files (Ctrl+O)"))
        self.add_btn.clicked.connect(self.choose_files)
        self.add_folder_btn = styled(QToolButton(), kind="ghost")
        icons.bind(self.add_folder_btn, "folder-plus")
        self.add_folder_btn.setToolTip(self.tr("Add a folder (Ctrl+Shift+O)"))
        self.add_folder_btn.clicked.connect(self.choose_folder)
        self.list_menu_btn = styled(QToolButton(), kind="ghost")
        icons.bind(self.list_menu_btn, "more")
        self.list_menu_btn.setPopupMode(QToolButton.InstantPopup)
        list_menu = QMenu(self.list_menu_btn)
        self.recursive_action = QAction(self.tr("Include sub-folders"), list_menu, checkable=True)
        self.recursive_action.setChecked(settings.get("recursive"))
        self.recursive_action.toggled.connect(lambda v: settings.set("recursive", v))
        list_menu.addAction(self.recursive_action)
        list_menu.addSeparator()
        list_menu.addAction(self.tr("Re-read metadata"), self.rescan)
        list_menu.addAction(self.tr("Remove selected from list"), self.remove_selected)
        list_menu.addAction(self.tr("Clear list"), self.clear)
        self.list_menu_btn.setMenu(list_menu)
        for b in (self.add_btn, self.add_folder_btn, self.list_menu_btn):
            b.setCursor(Qt.PointingHandCursor)
            head.addWidget(b)
        ll.addLayout(head)

        self.risk_filter = QComboBox()
        self.risk_filter.addItem(self.tr("All files"), "all")
        self.risk_filter.addItem(self.tr("High risk"), "high")
        self.risk_filter.addItem(self.tr("Medium risk"), "medium")
        self.risk_filter.addItem(self.tr("Low risk / clean"), "low")
        self.risk_filter.addItem(self.tr("Cleaned"), "cleaned")
        self.risk_filter.currentIndexChanged.connect(self._apply_list_filter)
        ll.addWidget(self.risk_filter)

        self.file_list = QListWidget()
        self.file_list.setObjectName("FileList")
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setMouseTracking(True)
        self.file_list.setItemDelegate(FileDelegate(self.session, lambda: self.plan, self.file_list))
        self.file_list.itemSelectionChanged.connect(self._on_selection)
        self.file_list.installEventFilter(self)
        ll.addWidget(self.file_list, 1)
        self.list_summary = styled(QLabel(), role="caption")
        self.list_summary.setWordWrap(True)
        ll.addWidget(self.list_summary)
        self.splitter.addWidget(left)

        self.detail = DetailPanel()
        self.detail.compare_requested.connect(self.compare_current)
        self.detail.edit_requested.connect(self.edit_targets)
        self.detail.remove_requested.connect(self.remove_selected)
        self.detail.map_consent_requested.connect(self._ask_map_consent)
        self.detail.tree.custom_keys_changed.connect(self._on_custom_keys)
        self.splitter.addWidget(self.detail)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([300, 900])
        cl.addWidget(self.splitter, 1)

        self.action_bar = ActionBar()
        self.action_bar.clean_requested.connect(self.clean)
        self.action_bar.export_requested.connect(self.export)
        self.action_bar.profile_changed.connect(self._on_profile_changed)
        self.action_bar.customize_requested.connect(self.choose_categories)
        self.action_bar.copies_toggled.connect(self._on_copies_toggled)
        self.action_bar.output_requested.connect(self.choose_output_dir)
        cl.addWidget(self.action_bar)
        self.stack.addWidget(content)

        # Drag-over overlay.
        self.overlay = QFrame(self)
        self.overlay.setObjectName("DropOverlay")
        ol = QVBoxLayout(self.overlay)
        ol.setAlignment(Qt.AlignCenter)
        self.overlay_icon = QLabel()
        self.overlay_icon.setAlignment(Qt.AlignCenter)
        ol.addWidget(self.overlay_icon)
        ot = styled(QLabel(self.tr("Drop to add")), role="hero")
        ot.setAlignment(Qt.AlignCenter)
        ol.addWidget(ot)
        self.overlay.hide()

        self.session.added.connect(self._on_added)
        self.session.updated.connect(self._on_updated)
        self.session.removed.connect(self._on_removed)

        for seq, slot in (
            ("Ctrl+O", self.choose_files),
            ("Ctrl+Shift+O", self.choose_folder),
            ("Ctrl+F", self._focus_search),
        ):
            QShortcut(QKeySequence(seq), self, activated=slot)

        self.reload_settings()
        self._refresh()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def reload_settings(self) -> None:
        self.recursive_action.setChecked(settings.get("recursive"))
        pid = settings.get("profile")
        if pid != "custom" and pid not in profiles.PROFILES:
            pid = profiles.DEFAULT_PROFILE
        self.plan.profile_id = pid
        self.plan.custom_categories = frozenset(c for c in settings.get("custom_categories") if c in risk.CATEGORIES)
        self.action_bar.profile.setCurrentIndex(max(0, self.action_bar.profile.findData(pid)))
        self.action_bar.copies.blockSignals(True)
        self.action_bar.copies.setChecked(settings.get("output_mode") and bool(settings.get("output_dir")))
        self.action_bar.copies.blockSignals(False)
        self.plan.output_dir = settings.get("output_dir") if self.action_bar.copies.isChecked() else None
        if settings.get("allow_map_tiles"):
            self.detail.map.enable_network()
        self._refresh()

    # ------------------------------------------------------------------
    # Adding files
    # ------------------------------------------------------------------

    def choose_files(self) -> None:
        start = settings.get("last_dir") or str(Path.home())
        paths, _ = QFileDialog.getOpenFileNames(self, self.tr("Add files"), start, formats.FILE_DIALOG_FILTER)
        if paths:
            settings.set("last_dir", str(Path(paths[0]).parent))
            self.add_paths(paths)

    def choose_folder(self) -> None:
        start = settings.get("last_dir") or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, self.tr("Add a folder"), start)
        if folder:
            settings.set("last_dir", folder)
            self.add_paths([folder])

    def add_paths(self, paths: list[str]) -> int:
        """Add files and folders (expanded per the sub-folders setting). Returns how many were new."""
        pairs = expand(paths, settings.get("recursive"))
        for raw in paths:
            if Path(raw).exists():
                settings.add_recent(str(Path(raw).expanduser().resolve()))
        if not pairs:
            self.message.emit(self.tr("No supported files found."))
            return 0
        new = self.session.add(pairs)
        if not new:
            self.message.emit(self.tr("These files are already in the list."))
        return len(new)

    def _on_added(self, paths: list[str]) -> None:
        first_new = None
        for path in paths:
            item = QListWidgetItem()
            item.setData(PATH_ROLE, path)
            item.setToolTip(path)
            self.file_list.addItem(item)
            first_new = first_new or item
        if not self.file_list.selectedItems() and first_new is not None:
            self.file_list.setCurrentItem(first_new)
        self._scan(paths)
        self._refresh()

    def _scan(self, paths: list[str]) -> None:
        self._scan_queue.extend(paths)
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        batch, self._scan_queue = self._scan_queue, []
        if not batch:
            return
        self._scan_worker = ExtractionWorker(batch)
        self._scan_worker.result_ready.connect(self.session.set_metadata)
        self._scan_worker.finished_all.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_finished(self) -> None:
        if self._scan_queue:
            self._scan([])
        else:
            self._refresh()
            self.message.emit(self.tr("%1 file(s) read.").replace("%1", str(len(self.session))))

    def rescan(self) -> None:
        for entry in self.session.entries():
            entry.state = PENDING
        self._scan(self.session.paths())
        self._refresh()

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _item_for(self, path: str) -> QListWidgetItem | None:
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.data(PATH_ROLE) == path:
                return item
        return None

    def _on_updated(self, path: str) -> None:
        item = self._item_for(path)
        if item is not None:
            self.file_list.update(self.file_list.indexFromItem(item))
        if path == self.current_path():
            self._show_current()
        self._refresh_summary()

    def _on_removed(self, paths: list[str]) -> None:
        for path in paths:
            item = self._item_for(path)
            if item is not None:
                self.file_list.takeItem(self.file_list.row(item))
        self._refresh()

    def remove_selected(self) -> None:
        self.session.remove(self.selected_paths())

    def clear(self) -> None:
        self.session.clear()

    def selected_paths(self) -> list[str]:
        return [i.data(PATH_ROLE) for i in self.file_list.selectedItems()]

    def current_path(self) -> str | None:
        item = self.file_list.currentItem()
        return item.data(PATH_ROLE) if item is not None else None

    def target_entries(self) -> list[FileEntry]:
        """Several selected files → those; otherwise every file in the list."""
        selected = self.selected_paths()
        paths = selected if len(selected) > 1 else self.session.paths()
        return [e for e in (self.session.get(p) for p in paths) if e is not None and e.state != PENDING]

    def _apply_list_filter(self) -> None:
        mode = self.risk_filter.currentData()
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            entry = self.session.get(item.data(PATH_ROLE))
            if entry is None or mode == "all" or entry.state == PENDING:
                item.setHidden(False)
                continue
            level = entry.risk.level
            visible = {
                "high": level == risk.Severity.HIGH,
                "medium": level == risk.Severity.MEDIUM,
                "low": level <= risk.Severity.LOW,
                "cleaned": entry.state == CLEANED,
            }[mode]
            item.setHidden(not visible)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if (
            obj is self.file_list
            and event.type() == QEvent.KeyPress
            and event.key() in (Qt.Key_Delete, Qt.Key_Backspace)
        ):
            self.remove_selected()
            return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _profile_name(self) -> str:
        return self.action_bar.profile.currentText().rstrip("…")

    def _on_selection(self) -> None:
        self._show_current()
        self._refresh_summary()

    def _show_current(self) -> None:
        path = self.current_path()
        entry = self.session.get(path) if path else None
        self.detail.show_entry(entry, self.plan, self._profile_name())

    def _refresh(self) -> None:
        empty = len(self.session) == 0
        self.stack.setCurrentIndex(0 if empty else 1)
        if empty:
            self.drop_zone.refresh()
        self.count_label.setText(str(len(self.session)))
        self.action_bar.customize.setVisible(self.plan.profile_id == "custom")
        self._refresh_output_button()
        self._apply_list_filter()
        self._show_current()
        self._refresh_summary()

    def _refresh_output_button(self) -> None:
        folder = settings.get("output_dir")
        self.action_bar.output.setText(Path(folder).name if folder else self.tr("Choose folder…"))
        self.action_bar.output.setToolTip(folder or self.tr("Choose where cleaned copies are written"))
        self.action_bar.output.setVisible(self.action_bar.copies.isChecked())

    def _refresh_summary(self) -> None:
        counts = self.session.risk_counts()
        pending = self.session.pending()
        parts = []
        if counts[risk.Severity.HIGH]:
            parts.append(self.tr("%1 high").replace("%1", str(counts[risk.Severity.HIGH])))
        if counts[risk.Severity.MEDIUM]:
            parts.append(self.tr("%1 medium").replace("%1", str(counts[risk.Severity.MEDIUM])))
        low = counts[risk.Severity.LOW] + counts[risk.Severity.NONE]
        if low:
            parts.append(self.tr("%1 low or clean").replace("%1", str(low)))
        if pending:
            parts.append(self.tr("%1 reading…").replace("%1", str(pending)))
        self.list_summary.setText(" · ".join(parts))

        if self._clean_worker is not None and self._clean_worker.isRunning():
            return
        targets = self.target_entries()
        n_tags = sum(len(self.plan.keys_removed(e)) for e in targets)
        selected = len(self.selected_paths()) > 1
        label = (
            self.tr("Clean %1 selected").replace("%1", str(len(targets)))
            if selected
            else self.tr("Clean %1 file(s)").replace("%1", str(len(targets)))
        )
        self.action_bar.clean_btn.setText(label)
        self.action_bar.clean_btn.setEnabled(bool(targets) and n_tags > 0)
        self.action_bar.export_btn.setEnabled(bool(targets))
        where = (
            self.tr("copies → %1").replace("%1", Path(self.plan.output_dir).name)
            if self.plan.output_dir
            else self.tr("originals will be modified")
        )
        self.action_bar.set_summary(
            self.tr("Removes %1 tag(s) · %2").replace("%1", str(n_tags)).replace("%2", where) if targets else ""
        )

    def _focus_search(self) -> None:
        if self.stack.currentIndex() == 1:
            self.detail.search.setFocus()
            self.detail.search.selectAll()

    # ------------------------------------------------------------------
    # Profile / options
    # ------------------------------------------------------------------

    def _on_profile_changed(self, pid: str) -> None:
        self.plan.profile_id = pid
        settings.set("profile", pid)
        if pid == "custom" and not self.plan.custom_categories:
            self.choose_categories()
        self._refresh()

    def choose_categories(self) -> None:
        selected = set(self.plan.custom_categories) or {
            c for c, s in risk.CATEGORY_SEVERITY.items() if s >= risk.Severity.MEDIUM
        }
        dlg = CustomSelectionDialog(None, selected, self)
        if dlg.exec() != QDialog.Accepted:
            return
        self.plan.custom_categories = frozenset(dlg.categories())
        settings.set("custom_categories", sorted(self.plan.custom_categories))
        for entry in self.session.entries():
            entry.custom_keys = None
        self._refresh()

    def _on_custom_keys(self, keys: set) -> None:
        entry = self.session.get(self.current_path() or "")
        if entry is not None:
            entry.custom_keys = set(keys)
            self._refresh_summary()
            self.file_list.viewport().update()

    def _on_copies_toggled(self, checked: bool) -> None:
        if checked and not settings.get("output_dir"):
            self.choose_output_dir()
            if not settings.get("output_dir"):
                self.action_bar.copies.setChecked(False)
                return
        settings.set("output_mode", checked)
        self.plan.output_dir = settings.get("output_dir") if checked else None
        self._refresh_output_button()
        self._refresh_summary()

    def choose_output_dir(self) -> None:
        start = settings.get("output_dir") or settings.get("last_dir") or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, self.tr("Save cleaned copies to"), start)
        if folder:
            settings.set("output_dir", folder)
            if not self.action_bar.copies.isChecked():
                self.action_bar.copies.setChecked(True)
            self.plan.output_dir = folder
        self._refresh_output_button()
        self._refresh_summary()

    def _ask_map_consent(self) -> None:
        box = QMessageBox(self)
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
            self.detail.map.enable_network()
        elif box.clickedButton() is once:
            self.detail.map.enable_network()

    # ------------------------------------------------------------------
    # Clean
    # ------------------------------------------------------------------

    def clean(self) -> None:
        if self._clean_worker is not None and self._clean_worker.isRunning():
            return
        targets = [e for e in self.target_entries() if self.plan.keys_removed(e)]
        if not targets:
            self.message.emit(self.tr("Nothing to remove with this profile."))
            return
        if self.plan.output_dir is None and not confirm_in_place(self, len(targets)):
            return
        tasks = []
        for entry in targets:
            profile, keys = self.plan.for_entry(entry)
            tasks.append(CleanTask(entry.path, entry.rel, profile, keys))
        self._clean_worker = RemovalWorker(tasks, output_dir=self.plan.output_dir, verify=True)
        self._clean_worker.report_ready.connect(self._on_clean_report)
        self._clean_worker.progress.connect(self._on_progress)
        self._clean_worker.error.connect(lambda m: QMessageBox.warning(self, self.tr("Cleaning failed"), m))
        self._clean_worker.finished_all.connect(self._on_clean_finished)
        self._clean_reports: dict[str, dict] = {}
        self.action_bar.progress.setRange(0, len(tasks))
        self.action_bar.progress.setValue(0)
        self.action_bar.set_busy(True, self.tr("Cleaning…"))
        self._clean_worker.start()

    def _on_progress(self, current: int, total: int) -> None:
        self.action_bar.progress.setRange(0, total)
        self.action_bar.progress.setValue(current)
        self.action_bar.summary.setText(self.tr("%1 / %2").replace("%1", str(current)).replace("%2", str(total)))

    def _on_clean_report(self, path: str, report: dict) -> None:
        self._clean_reports[path] = report
        self.session.set_report(path, report)

    def _on_clean_finished(self) -> None:
        self.action_bar.set_busy(False)
        reports = self._clean_reports
        if self._export_after_clean and reports:
            out, fmt = self._export_after_clean
            try:
                exporters.export({p: r.get("before") for p, r in reports.items()}, out, fmt)
            except OSError as exc:
                QMessageBox.warning(self, self.tr("Export failed"), str(exc))
        self._export_after_clean = None
        failures = [p for p, r in reports.items() if not r["status"]]
        removed = sum(len((r.get("diff") or {}).get("removed", [])) for r in reports.values())
        ok = len(reports) - len(failures)
        self._refresh()
        if failures:
            QMessageBox.warning(
                self,
                self.tr("Some files were not cleaned"),
                self.tr("%1 file(s) could not be cleaned (unsupported format or read-only):\n%2")
                .replace("%1", str(len(failures)))
                .replace("%2", "\n".join(Path(f).name for f in failures[:20])),
            )
        text = self.tr("Cleaned %1 file(s), %2 tag(s) removed.").replace("%1", str(ok)).replace("%2", str(removed))
        if self.plan.output_dir and ok:
            text += " " + self.tr("Copies saved to %1.").replace("%1", self.plan.output_dir)
        self.message.emit(text)

    def compare_current(self) -> None:
        entry = self.session.get(self.current_path() or "")
        if entry and entry.report:
            BeforeAfterDialog(entry.name, entry.report.get("before"), entry.report.get("after"), self).exec()

    # ------------------------------------------------------------------
    # Export / edit
    # ------------------------------------------------------------------

    def export(self, fmt: str, then_clean: bool = False) -> None:
        targets = self.target_entries()
        if not targets:
            return
        default = Path(targets[0].folder).name if len(targets) > 1 else Path(targets[0].name).stem
        choice = ask_export_path(self, f"{default or 'metadata'}-metadata", fmt)
        if choice is None:
            return
        path, fmt = choice
        if then_clean:
            self._export_after_clean = (path, fmt)
            self.clean()
            if self._clean_worker is None or not self._clean_worker.isRunning():
                self._export_after_clean = None
            return
        try:
            exporters.export({e.path: e.metadata for e in targets}, path, fmt)
        except OSError as exc:
            QMessageBox.warning(
                self, self.tr("Export failed"), self.tr("Could not save the file:\n%1").replace("%1", str(exc))
            )
            return
        self.message.emit(self.tr("Exported %1 file(s) to %2").replace("%1", str(len(targets))).replace("%2", path))

    def edit_targets(self) -> None:
        selected = self.selected_paths()
        entries = [self.session.get(p) for p in (selected or [self.current_path()]) if p]
        entries = [e for e in entries if e is not None and e.state != PENDING]
        if not entries:
            return
        output = self.plan.output_dir
        label = entries[0].path if len(entries) == 1 else self.tr("%1 files").replace("%1", str(len(entries)))
        if output:
            label += "\n" + self.tr("Edited copies will be saved to: %1").replace("%1", output)
        dlg = EditDialog(label, entries[0].metadata if len(entries) == 1 else None, self)
        if dlg.exec() != QDialog.Accepted:
            return
        if output is None and not confirm_in_place(self, len(entries)):
            return
        self._edit_worker = EditWorker(
            [(e.path, e.rel) for e in entries], fields=dlg.fields(), shift=dlg.shift() or None, output_dir=output
        )
        failures: list[str] = []
        self._edit_worker.result_ready.connect(lambda p, ok: None if ok else failures.append(p))
        self._edit_worker.progress.connect(self._on_progress)
        self._edit_worker.finished_all.connect(
            lambda: self._on_edit_finished([e.path for e in entries], failures, output)
        )
        self.action_bar.set_busy(True, self.tr("Editing…"))
        self._edit_worker.start()

    def _on_edit_finished(self, paths: list[str], failures: list[str], output: str | None) -> None:
        self.action_bar.set_busy(False)
        if failures:
            QMessageBox.warning(
                self,
                self.tr("Some files were not edited"),
                self.tr("These files could not be edited (unsupported format or field):\n%1").replace(
                    "%1", "\n".join(Path(f).name for f in failures[:20])
                ),
            )
        if output:
            self.message.emit(self.tr("Edited copies saved to %1.").replace("%1", output))
        else:
            for path in paths:
                entry = self.session.get(path)
                if entry is not None:
                    entry.state = PENDING
            self._scan(paths)
            self.message.emit(self.tr("%1 file(s) edited.").replace("%1", str(len(paths) - len(failures))))
        self._refresh()

    # ------------------------------------------------------------------
    # Drag & drop
    # ------------------------------------------------------------------

    def show_drop_overlay(self, visible: bool) -> None:
        if self.stack.currentIndex() == 0:
            self.drop_zone.set_active(visible)
            return
        if visible:
            self.overlay_icon.setPixmap(icons.pixmap("inbox", 48, "primary"))
            self.overlay.setGeometry(self.rect().adjusted(16, 16, -16, -16))
            self.overlay.raise_()
        self.overlay.setVisible(visible)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
            self.show_drop_overlay(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.show_drop_overlay(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.show_drop_overlay(False)
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.add_paths(paths)

    def resizeEvent(self, event) -> None:  # noqa: N802
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.rect().adjusted(16, 16, -16, -16))
        super().resizeEvent(event)

    def retheme(self) -> None:
        """Re-render custom-painted parts after a theme change."""
        self.drop_zone.refresh()
        self.file_list.viewport().update()
        self._show_current()

    def shutdown(self) -> None:
        """Stop background work before the window closes."""
        for worker in (self._scan_worker, self._clean_worker, self._edit_worker):
            if worker is not None and worker.isRunning():
                worker.requestInterruption()
                worker.wait(5000)
