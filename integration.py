"""Optional file-manager integration ("Inspect with EOM" / "Clean with EOM").

* Linux — Nautilus scripts, Nemo actions, Dolphin service menu and an
  ``eom.desktop`` launcher (so EOM also appears under "Open with").
* Windows — per-user Explorer context-menu verbs under ``HKCU\\Software\\Classes``.
* macOS — not supported (Quick Actions must be created in Automator).

Everything is per-user (no admin rights) and fully removed by :func:`uninstall`.
Both entries only *open* EOM with the selection loaded; nothing is modified
until the user clicks Remove.
"""

from __future__ import annotations

import os
import shlex
import stat
import sys
from pathlib import Path

ACTIONS = {
    "extract": "Inspect metadata with EOM",
    "remove": "Clean metadata with EOM",
}
_MARKER = "# Installed by Eye On Metadata"


def launch_command() -> list[str]:
    """Command that starts the EOM GUI (frozen binary or ``python main.py``)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, str(Path(__file__).resolve().parent / "main.py")]


def supported() -> bool:
    return sys.platform.startswith("linux") or sys.platform == "win32"


# ---------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------


def _data_home(home: Path | None) -> Path:
    if home is not None:
        return home / ".local" / "share"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _linux_files(home: Path | None = None) -> dict[Path, str]:
    data = _data_home(home)
    cmd = shlex.join(launch_command())
    files: dict[Path, str] = {}
    for action, label in ACTIONS.items():
        files[data / "nautilus" / "scripts" / label] = f'#!/bin/sh\n{_MARKER}\nexec {cmd} --{action} "$@"\n'
        files[data / "nemo" / "actions" / f"eom-{action}.nemo_action"] = (
            f"[Nemo Action]\n{_MARKER}\nName={label}\nComment={label}\n"
            f"Exec={cmd} --{action} %F\nIcon-Name=document-properties\nSelection=notnone\nExtensions=any;\n"
        )
    files[data / "kio" / "servicemenus" / "eom.desktop"] = (
        f"[Desktop Entry]\n{_MARKER}\nType=Service\nMimeType=all/allfiles;inode/directory;\n"
        "Actions=eomExtract;eomRemove;\nX-KDE-Submenu=Eye On Metadata\n\n"
        f"[Desktop Action eomExtract]\nName={ACTIONS['extract']}\nIcon=document-properties\nExec={cmd} --extract %F\n\n"
        f"[Desktop Action eomRemove]\nName={ACTIONS['remove']}\nIcon=edit-clear\nExec={cmd} --remove %F\n"
    )
    files[data / "applications" / "eom.desktop"] = (
        f"[Desktop Entry]\n{_MARKER}\nType=Application\nName=Eye On Metadata\n"
        "Comment=View, export, clean and edit file metadata\n"
        f"Exec={cmd} %F\nTerminal=false\nCategories=Utility;Graphics;\n"
        "MimeType=image/jpeg;image/png;image/tiff;image/webp;image/gif;image/heic;application/pdf;"
        "audio/mpeg;audio/flac;audio/ogg;video/mp4;video/x-matroska;video/webm;"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document;\n"
    )
    return files


def _ours(path: Path) -> bool:
    try:
        return _MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

_WIN_ROOTS = (r"Software\Classes\*\shell", r"Software\Classes\Directory\shell")


def _win_install() -> list[str]:  # pragma: no cover - Windows only
    import winreg

    exe = launch_command()
    created = []
    for root in _WIN_ROOTS:
        for action, label in ACTIONS.items():
            key_path = rf"{root}\EOM.{action}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, label)
                winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, exe[0])
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\command") as key:
                command = " ".join(f'"{part}"' for part in exe) + f' --{action} "%1"'
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
            created.append("HKCU\\" + key_path)
    return created


def _win_uninstall() -> list[str]:  # pragma: no cover - Windows only
    import winreg

    removed = []
    for root in _WIN_ROOTS:
        for action in ACTIONS:
            key_path = rf"{root}\EOM.{action}"
            for sub in (key_path + r"\command", key_path):
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
                except OSError:
                    continue
            removed.append("HKCU\\" + key_path)
    return removed


def _win_installed() -> bool:  # pragma: no cover - Windows only
    import winreg

    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{_WIN_ROOTS[0]}\EOM.extract").Close()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def is_installed(home: Path | None = None) -> bool:
    if sys.platform == "win32":  # pragma: no cover
        return _win_installed()
    return any(p.exists() and _ours(p) for p in _linux_files(home))


def install(home: Path | None = None) -> list[str]:
    """Create the integration entries; returns what was created."""
    if sys.platform == "win32":  # pragma: no cover
        return _win_install()
    if not sys.platform.startswith("linux"):
        raise OSError("File-manager integration is only available on Linux and Windows.")
    created = []
    for path, content in _linux_files(home).items():
        if path.exists() and not _ours(path):
            continue  # never overwrite a file we did not create
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IRUSR)
        created.append(str(path))
    return created


def uninstall(home: Path | None = None) -> list[str]:
    if sys.platform == "win32":  # pragma: no cover
        return _win_uninstall()
    removed = []
    for path in _linux_files(home):
        if path.exists() and _ours(path):
            path.unlink()
            removed.append(str(path))
    return removed
