"""Optional ExifTool backend for EOM.

Wraps the ``exiftool`` CLI when it is present in PATH.  All callers should
check :func:`is_available` before calling :func:`extract` or :func:`remove`.

Security notes
--------------
* ``shell=False`` throughout — the file path is passed as a positional
  argument, never interpolated into a shell command string.
* The subprocess timeout (30 s) guards against hanging on very large files.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


def _find_exiftool() -> str | None:
    """Locate the exiftool binary.

    When running as a PyInstaller bundle, the Windows standalone
    ``exiftool.exe`` may have been packaged inside ``sys._MEIPASS``.
    We check there first before falling back to PATH.
    """
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, "exiftool.exe")
        if os.path.isfile(bundled):
            return bundled
    return shutil.which("exiftool")


# Resolved once at import time.  None means ExifTool is not available.
_EXIFTOOL_PATH: str | None = _find_exiftool()

_TIMEOUT = 30  # seconds


def is_available() -> bool:
    """Return True if the ``exiftool`` binary was found in PATH."""
    return _EXIFTOOL_PATH is not None


def extract(path: str) -> dict | None:
    """Extract all metadata from *path* using ExifTool.

    Uses ``-json -G1 -a -u`` so output includes group-prefixed keys
    (e.g. ``EXIF:Make``, ``XMP:Creator``) and unknown/duplicate tags.

    :return: flat dict of ``{GroupName:TagName: value}``, or ``None`` on error.
    """
    if not _EXIFTOOL_PATH:
        return None
    try:
        result = subprocess.run(
            [_EXIFTOOL_PATH, "-json", "-G1", "-a", "-u", path],
            capture_output=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    try:
        records = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None

    if not records:
        return None

    # ExifTool returns a list; we always pass one file so take index 0.
    raw: dict = records[0]

    # Drop the SourceFile entry (it's the input path, not metadata).
    raw.pop("SourceFile", None)

    return {str(k): str(v) for k, v in raw.items()} if raw else None


def remove(path: str) -> bool | None:
    """Strip all writable metadata from *path* using ExifTool in-place.

    Uses ``-all= -overwrite_original`` so no ``*_original`` backup file is
    left behind in the user's directory.

    :return: ``True`` on success, ``None`` on error or ExifTool not found.
    """
    if not _EXIFTOOL_PATH:
        return None
    try:
        result = subprocess.run(
            [_EXIFTOOL_PATH, "-all=", "-overwrite_original", path],
            capture_output=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    return True if result.returncode == 0 else None
