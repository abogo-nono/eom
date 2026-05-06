"""Tests for the optional ExifTool backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import exiftool_backend
import Extractor


def test_is_available_returns_bool() -> None:
    assert isinstance(exiftool_backend.is_available(), bool)


def test_extract_returns_none_when_not_available(tmp_path: Path) -> None:
    fake = tmp_path / "img.jpg"
    fake.touch()
    with patch.object(exiftool_backend, "_EXIFTOOL_PATH", None):
        assert exiftool_backend.extract(str(fake)) is None


def test_remove_returns_none_when_not_available(tmp_path: Path) -> None:
    fake = tmp_path / "img.jpg"
    fake.touch()
    with patch.object(exiftool_backend, "_EXIFTOOL_PATH", None):
        assert exiftool_backend.remove(str(fake)) is None


def test_single_image_extractor_prefers_exiftool(jpeg_with_exif: Path) -> None:
    """When ExifTool is available, single_image_extractor uses it."""
    mock_data = {"EXIF:Make": "ExifTool-Backend", "EXIF:Model": "Test"}
    with (
        patch.object(exiftool_backend, "_EXIFTOOL_PATH", "exiftool"),
        patch("exiftool_backend.extract", return_value=mock_data),
    ):
        result = Extractor.single_image_extractor(str(jpeg_with_exif))
    assert result == mock_data


def test_remove_image_metadata_prefers_exiftool(jpeg_with_exif: Path) -> None:
    """When ExifTool is available, remove_image_metadata uses it."""
    with (
        patch.object(exiftool_backend, "_EXIFTOOL_PATH", "exiftool"),
        patch("exiftool_backend.remove", return_value=True),
    ):
        result = Extractor.remove_image_metadata(str(jpeg_with_exif))
    assert result is True


def test_single_image_extractor_falls_back_without_exiftool(jpeg_with_exif: Path) -> None:
    """When ExifTool is absent, Pillow fallback still returns EXIF data."""
    with patch.object(exiftool_backend, "_EXIFTOOL_PATH", None):
        result = Extractor.single_image_extractor(str(jpeg_with_exif))
    assert result is not None
    assert result.get("Make") == "EOM-Test"
