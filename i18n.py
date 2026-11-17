"""Interface translations (Qt Linguist).

Source strings are English.  Translations live in ``translations/eom_<lang>.ts``
and are compiled to ``.qm`` with ``pyside6-lrelease`` (see AGENTS.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

AVAILABLE = ("en", "fr")
_installed: list[QTranslator] = []


def _translations_dir() -> Path:
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
    return base / "translations"


def resolve(code: str) -> str:
    if code in AVAILABLE:
        return code
    system = QLocale.system().name().split("_")[0]
    return system if system in AVAILABLE else "en"


def install(app: QApplication, code: str) -> str:
    """Load the EOM and Qt translations for *code* (``system`` → OS language)."""
    for translator in _installed:
        app.removeTranslator(translator)
    _installed.clear()

    lang = resolve(code)
    if lang == "en":
        return lang

    ours = QTranslator(app)
    if ours.load(str(_translations_dir() / f"eom_{lang}.qm")):
        app.installTranslator(ours)
        _installed.append(ours)

    # Qt's own strings (standard dialog buttons, file dialogs…).
    qt = QTranslator(app)
    if qt.load(f"qtbase_{lang}", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(qt)
        _installed.append(qt)
    return lang
