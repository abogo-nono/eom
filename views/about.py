"""About page: what EOM is, backends, version, links and bug reporting."""

from __future__ import annotations

import platform
import sys

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import exiftool_backend
import icons
from version import __version__
from widgets import set_badge, styled

REPO = "https://github.com/abogo-nono/eom"


def system_info() -> str:
    exiftool_status = exiftool_backend._EXIFTOOL_PATH if exiftool_backend.is_available() else "not found"
    return "\n".join(
        [
            f"EOM version : v{__version__}",
            f"Python      : {sys.version.split()[0]}",
            f"Platform    : {platform.system()} {platform.release()} ({platform.machine()})",
            f"ExifTool    : {exiftool_status}",
        ]
    )


class AboutView(QWidget):
    def __init__(self, logo: QIcon, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        contents = QWidget()
        scroll.setWidget(contents)
        column = QHBoxLayout(contents)
        column.addStretch(1)
        body = QWidget()
        body.setMaximumWidth(760)
        column.addWidget(body, 6)
        column.addStretch(1)

        root = QVBoxLayout(body)
        root.setContentsMargins(8, 28, 8, 28)
        root.setSpacing(14)

        hero = QHBoxLayout()
        hero.setSpacing(16)
        tile = styled(QFrame(), panel="true")
        tile.setFixedSize(64, 64)
        tl = QVBoxLayout(tile)
        tl.setContentsMargins(0, 0, 0, 0)
        logo_label = icons.bind(QLabel(), "eye", "primary", 34)
        logo_label.setAlignment(Qt.AlignCenter)
        tl.addWidget(logo_label)
        hero.addWidget(tile)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(styled(QLabel("Eye On Metadata"), role="hero"))
        titles.addWidget(
            styled(QLabel(self.tr("Version %1 · open source · MIT licence").replace("%1", __version__)), role="muted")
        )
        hero.addLayout(titles, 1)
        root.addLayout(hero)

        desc = QLabel(
            self.tr(
                "EOM shows what your files reveal — location, author, device, serial numbers, editing history — "
                "and removes it. Everything happens on this computer: no upload, no account, no cloud."
            )
        )
        desc.setWordWrap(True)
        root.addWidget(desc)

        # Backends.
        card = styled(QFrame(), panel="true")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(8)
        cl.addWidget(styled(QLabel(self.tr("Metadata engines")), role="h2"))
        row = QHBoxLayout()
        row.addWidget(QLabel("ExifTool"))
        status = QLabel()
        available = exiftool_backend.is_available()
        status.setText(self.tr("Active") if available else self.tr("Not installed"))
        set_badge(status, "low" if available else "medium")
        row.addWidget(status)
        row.addStretch()
        cl.addLayout(row)
        hint = styled(
            QLabel(
                self.tr("ExifTool reads XMP, IPTC, maker notes and RAW files. It is used automatically when installed.")
                if available
                else self.tr(
                    "Install ExifTool for deeper metadata (XMP, IPTC, maker notes, RAW): "
                    "“sudo apt install libimage-exiftool-perl” or “brew install exiftool”."
                )
            ),
            role="muted",
        )
        hint.setWordWrap(True)
        hint.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cl.addWidget(hint)
        cl.addWidget(
            styled(
                QLabel(self.tr("Built-in: Pillow (images) · mutagen (audio/video) · pypdf (PDF) · Office documents")),
                role="caption",
            )
        )
        root.addWidget(card)

        # Bug report.
        card = styled(QFrame(), panel="true")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(10)
        cl.addWidget(styled(QLabel(self.tr("Found a bug or have an idea?")), role="h2"))
        hint = styled(
            QLabel(
                self.tr(
                    "Open an issue on GitHub and paste the system information below — it helps reproduce the problem."
                )
            ),
            role="muted",
        )
        hint.setWordWrap(True)
        cl.addWidget(hint)
        self.info_box = styled(QPlainTextEdit(system_info()), role="mono")
        self.info_box.setReadOnly(True)
        self.info_box.setFixedHeight(92)
        cl.addWidget(self.info_box)
        buttons = QHBoxLayout()
        self.issue_btn = icons.bind(
            styled(QPushButton(self.tr("Open a GitHub issue")), kind="primary"), "external", "on_accent"
        )
        self.issue_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"{REPO}/issues/new")))
        self.copy_btn = icons.bind(QPushButton(self.tr("Copy system info")), "copy")
        self.copy_btn.clicked.connect(self._copy)
        repo_btn = styled(QPushButton(self.tr("Source code")), kind="ghost")
        repo_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO)))
        for b in (self.issue_btn, self.copy_btn, repo_btn):
            b.setCursor(Qt.PointingHandCursor)
            buttons.addWidget(b)
        buttons.addStretch()
        cl.addLayout(buttons)
        root.addWidget(card)

        credit = styled(QLabel(self.tr("Made by Abogo Lincoln and contributors.")), role="caption")
        root.addWidget(credit)
        root.addStretch()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(system_info())
        self.copy_btn.setText(self.tr("Copied!"))
        QTimer.singleShot(2000, lambda: self.copy_btn.setText(self.tr("Copy system info")))
