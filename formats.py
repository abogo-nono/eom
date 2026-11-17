"""Single source of truth for the file formats EOM understands.

Controllers, workers, the CLI and the backends all import from here so a new
format only has to be declared once.
"""

from __future__ import annotations

import os
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".gif", ".heic", ".heif"}
PDF_EXTENSIONS = {".pdf"}
AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".ogg",
    ".oga",
    ".opus",
    ".wav",
    ".aiff",
    ".aif",
    ".m4a",
    ".m4b",
    ".wma",
    ".ape",
    ".wv",
    ".tta",
}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mkv", ".webm", ".mov"}
AUDIO_VIDEO_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
OFFICE_EXTENSIONS = {".docx", ".xlsx", ".pptx"}

SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS | AUDIO_VIDEO_EXTENSIONS | OFFICE_EXTENSIONS

# Extensions ExifTool can *write* (subset of `exiftool -listwf` relevant to EOM).
# Anything else (MP3, FLAC, OGG, Office…) must go through the Python backends
# for removal and editing, even when ExifTool is installed.
# PDF is deliberately excluded: ExifTool edits PDFs as *incremental updates*, so
# the original metadata stays recoverable inside the file.  pypdf rewrites it.
EXIFTOOL_WRITABLE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
    ".gif",
    ".heic",
    ".heif",
    ".mp4",
    ".m4v",
    ".m4a",
    ".m4b",
    ".mov",
}


def _filter_patterns() -> str:
    patterns = []
    for ext in sorted(SUPPORTED_EXTENSIONS):
        patterns.append(f"*{ext}")
        patterns.append(f"*{ext.upper()}")
    return " ".join(patterns)


FILE_DIALOG_FILTER = f"Supported files ({_filter_patterns()});;All files (*)"


def is_supported(path: str | os.PathLike) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def scan_directory(directory: str | os.PathLike, recursive: bool = False) -> dict[str, str]:
    """Return ``{display_name: relative_path}`` for every supported file.

    Relative paths use forward slashes so they are stable across platforms and
    can be fed to ``Extractor._safe_join``.  Hidden directories are skipped when
    recursing.  Results are sorted for deterministic ordering.
    """
    base = Path(directory)
    if not base.is_dir():
        return {}

    found: list[str] = []
    if recursive:
        for root, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in files:
                if is_supported(name):
                    found.append((Path(root) / name).relative_to(base).as_posix())
    else:
        found = [entry.name for entry in base.iterdir() if entry.is_file() and is_supported(entry.name)]

    return {rel: rel for rel in sorted(found)}
