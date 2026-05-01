"""Shared pytest fixtures for EOM tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

# Make project root importable so `import Extractor`, `import main` work.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import exiftool_backend  # noqa: E402 — must come after sys.path insert


@pytest.fixture(autouse=True)
def _disable_exiftool(request):
    """Disable the ExifTool backend for all tests by default.

    Tests that explicitly need ExifTool should patch exiftool_backend._EXIFTOOL_PATH
    themselves (which overrides this fixture's patch within the test's scope).
    """
    with patch.object(exiftool_backend, "_EXIFTOOL_PATH", None):
        yield


@pytest.fixture
def jpeg_with_exif(tmp_path: Path) -> Path:
    """Create a tiny JPEG with a minimal EXIF block."""
    path = tmp_path / "with_exif.jpg"
    img = Image.new("RGB", (4, 4), color=(255, 0, 0))
    exif = img.getexif()
    # 0x010F = Make, 0x0110 = Model
    exif[0x010F] = "EOM-Test"
    exif[0x0110] = "Synthetic"
    img.save(path, "JPEG", exif=exif)
    return path


@pytest.fixture
def jpeg_without_exif(tmp_path: Path) -> Path:
    path = tmp_path / "no_exif.jpg"
    Image.new("RGB", (4, 4), color=(0, 255, 0)).save(path, "JPEG")
    return path


@pytest.fixture(autouse=True)
def _qt_offscreen(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run Qt headlessly in CI."""
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
