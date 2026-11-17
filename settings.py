"""Persistent user preferences (QSettings wrapper with typed accessors).

Stored as an INI file in the platform's per-user config location
(``~/.config/EOM/EyeOnMetadata.ini`` on Linux).  Tests redirect it to a temp
directory via :func:`use_path`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

ORG = "EOM"
APP = "EyeOnMetadata"
MAX_RECENT = 10

_DEFAULTS: dict[str, object] = {
    "theme": "dark",  # dark | light | system
    "language": "system",  # system | en | fr
    "recursive": False,
    "profile": "all",
    "custom_categories": [],
    "output_mode": False,  # write cleaned copies instead of modifying originals
    "output_dir": "",
    "confirm_in_place": True,
    "allow_map_tiles": False,  # network access to OpenStreetMap — opt-in
    "check_updates": False,  # network access to GitHub — opt-in
    "last_dir": "",
    "recent": [],
}

_path_override: str | None = None


def use_path(directory: str | Path | None) -> None:
    """Store settings under *directory* (tests); ``None`` restores the default."""
    global _path_override
    _path_override = str(directory) if directory else None


def _qsettings() -> QSettings:
    if _path_override:
        return QSettings(str(Path(_path_override) / "eom.ini"), QSettings.IniFormat)
    return QSettings(QSettings.IniFormat, QSettings.UserScope, ORG, APP)


def get(key: str):
    default = _DEFAULTS[key]
    value = _qsettings().value(key, default)
    # INI round-trips lose types: coerce back to the default's type.
    if isinstance(default, bool):
        return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes")
    if isinstance(default, list):
        if value in (None, ""):
            return []
        return [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]
    return "" if value is None else str(value)


def set(key: str, value) -> None:  # noqa: A001 — mirrors QSettings API
    if key not in _DEFAULTS:
        raise KeyError(key)
    s = _qsettings()
    s.setValue(key, value)
    s.sync()


def recent() -> list[str]:
    return [p for p in get("recent") if p]


def add_recent(path: str) -> None:
    items = [p for p in recent() if p != path]
    items.insert(0, path)
    set("recent", items[:MAX_RECENT])
    parent = str(Path(path).parent if Path(path).is_file() else path)
    set("last_dir", parent)


def clear_recent() -> None:
    set("recent", [])
