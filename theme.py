"""Dark / light theming.

``style.qss`` is a template whose colours are ``@token`` placeholders.  This
module substitutes the active palette, sets the Fusion style and a matching
QPalette (so dialogs, menus and message boxes follow the theme too).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#050809",
        "header": "#0a1a24",
        "menu": "#061016",
        "surface": "#0a1a24",
        "input_bg": "#131a1a",
        "accent": "#1e7085",
        "accent_hover": "#33c6cb",
        "accent_soft": "rgba(51, 198, 203, 0.15)",
        "on_accent": "#f5f5f5",
        "primary": "#33c6cb",
        "title": "#f0f8ff",
        "text": "#e0e6e8",
        "muted": "#788596",
        "line": "#123a45",
        "menu_checked": "#f5f5f5",
        "high": "#ef5350",
        "medium": "#ffb74d",
        "low": "#81c784",
    },
    "light": {
        "bg": "#f3f6f7",
        "header": "#ffffff",
        "menu": "#e3edef",
        "surface": "#ffffff",
        "input_bg": "#eef3f4",
        "accent": "#1e7085",
        "accent_hover": "#2a93a8",
        "accent_soft": "rgba(30, 112, 133, 0.12)",
        "on_accent": "#ffffff",
        "primary": "#0d5f6b",
        "title": "#10262e",
        "text": "#1b2a30",
        "muted": "#55626d",
        "line": "#c5d5da",
        "menu_checked": "#0d5f6b",
        "high": "#c62828",
        "medium": "#a35f00",
        "low": "#2e7d32",
    },
}

THEMES = ("dark", "light", "system")
_TOKEN_RE = re.compile(r"@([a-z_]+)")
_current = "dark"


def _base_dir() -> Path:
    return Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent


def resolve(name: str) -> str:
    """Map ``system`` to ``dark``/``light`` using the OS colour scheme."""
    if name == "system":
        hints = QGuiApplication.styleHints() if QGuiApplication.instance() else None
        scheme = hints.colorScheme() if hints is not None and hasattr(hints, "colorScheme") else None
        return "light" if scheme == Qt.ColorScheme.Light else "dark"
    return name if name in PALETTES else "dark"


def current() -> str:
    return _current


def color(token: str) -> str:
    """Colour of *token* in the active palette (for code that paints by hand)."""
    return PALETTES[_current][token]


def render_stylesheet(name: str, template: str | None = None) -> str:
    palette = PALETTES[resolve(name)]
    if template is None:
        template = (_base_dir() / "style.qss").read_text(encoding="utf-8")
    return _TOKEN_RE.sub(lambda m: palette.get(m.group(1), m.group(0)), template)


def _qpalette(p: dict[str, str]) -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(p["bg"]))
    pal.setColor(QPalette.WindowText, QColor(p["text"]))
    pal.setColor(QPalette.Base, QColor(p["input_bg"]))
    pal.setColor(QPalette.AlternateBase, QColor(p["surface"]))
    pal.setColor(QPalette.Text, QColor(p["text"]))
    pal.setColor(QPalette.Button, QColor(p["surface"]))
    pal.setColor(QPalette.ButtonText, QColor(p["text"]))
    pal.setColor(QPalette.Highlight, QColor(p["accent"]))
    pal.setColor(QPalette.HighlightedText, QColor(p["on_accent"]))
    pal.setColor(QPalette.ToolTipBase, QColor(p["surface"]))
    pal.setColor(QPalette.ToolTipText, QColor(p["text"]))
    pal.setColor(QPalette.PlaceholderText, QColor(p["muted"]))
    pal.setColor(QPalette.Link, QColor(p["primary"]))
    return pal


def apply(app: QApplication, name: str) -> str:
    """Apply theme *name* (dark | light | system) to *app*; returns the resolved name."""
    global _current
    _current = resolve(name)
    app.setStyle("Fusion")
    app.setPalette(_qpalette(PALETTES[_current]))
    app.setStyleSheet(render_stylesheet(_current))
    return _current
