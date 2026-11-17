"""Dark / light theming.

``style.qss`` is a template whose colours are ``@token`` placeholders.  This
module substitutes the active palette, sets the Fusion style and a matching
QPalette (so dialogs, menus and message boxes follow the theme too).
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

PALETTES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#070c0e",
        "sidebar": "#0a1418",
        "surface": "#0e1a1f",
        "surface_alt": "#132329",
        "input_bg": "#0b1519",
        "line": "#1d3139",
        "accent": "#1e7085",
        "accent_hover": "#268aa3",
        "accent_soft": "rgba(51, 198, 203, 0.14)",
        "on_accent": "#ffffff",
        "primary": "#33c6cb",
        "text": "#e3eaec",
        "muted": "#82929b",
        "high": "#ef5f5a",
        "high_soft": "rgba(239, 95, 90, 0.14)",
        "medium": "#f2a94a",
        "medium_soft": "rgba(242, 169, 74, 0.14)",
        "low": "#6cc28a",
        "low_soft": "rgba(108, 194, 138, 0.14)",
        "scrim": "rgba(0, 0, 0, 0.35)",
    },
    "light": {
        "bg": "#f3f6f7",
        "sidebar": "#e8eff1",
        "surface": "#ffffff",
        "surface_alt": "#eef4f6",
        "input_bg": "#f7fafb",
        "line": "#d4dfe3",
        "accent": "#1e7085",
        "accent_hover": "#175b6c",
        "accent_soft": "rgba(30, 112, 133, 0.10)",
        "on_accent": "#ffffff",
        "primary": "#0f6b78",
        "text": "#14232a",
        "muted": "#5a6a73",
        "high": "#c62828",
        "high_soft": "rgba(198, 40, 40, 0.09)",
        "medium": "#a35f00",
        "medium_soft": "rgba(163, 95, 0, 0.10)",
        "low": "#2e7d32",
        "low_soft": "rgba(46, 125, 50, 0.10)",
        "scrim": "rgba(0, 0, 0, 0.08)",
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


_ASSETS = {
    # QSS cannot draw arrows or check marks from CSS borders: ship tiny SVGs.
    "chevron": '<polyline points="6 9 12 15 18 9" stroke="{c}"/>',
    "check": '<polyline points="20 6 9 17 4 12" stroke="{c}"/>',
}
_asset_dir: Path | None = None


def _asset_urls(palette: dict[str, str], name: str) -> dict[str, str]:
    """Write the theme's SVG assets to a temp folder; return ``{token: path}``."""
    global _asset_dir
    if _asset_dir is None:
        _asset_dir = Path(tempfile.mkdtemp(prefix="eom-theme-"))
    colours = {"chevron": palette["muted"], "check": palette["on_accent"]}
    urls = {}
    for token, body in _ASSETS.items():
        path = _asset_dir / f"{token}-{name}.svg"
        if not path.exists():
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="3" '
                f'stroke-linecap="round" stroke-linejoin="round">{body.format(c=colours[token])}</svg>',
                encoding="utf-8",
            )
        urls[token] = path.as_posix()
    return urls


def render_stylesheet(name: str, template: str | None = None) -> str:
    resolved = resolve(name)
    palette = dict(PALETTES[resolved])
    palette.update(_asset_urls(palette, resolved))
    if template is None:
        template = (_base_dir() / "style.qss").read_text(encoding="utf-8")
    return _TOKEN_RE.sub(lambda m: palette.get(m.group(1), m.group(0)), template)


def _qpalette(p: dict[str, str]) -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(p["bg"]))
    pal.setColor(QPalette.WindowText, QColor(p["text"]))
    pal.setColor(QPalette.Base, QColor(p["input_bg"]))
    pal.setColor(QPalette.AlternateBase, QColor(p["surface_alt"]))
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
