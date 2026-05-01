"""Smoke tests for Extractor pure functions."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import Extractor


def test_single_image_extractor_returns_exif(jpeg_with_exif: Path) -> None:
    data = Extractor.single_image_extractor(str(jpeg_with_exif))
    assert data is not None
    assert data.get("Make") == "EOM-Test"
    assert data.get("Model") == "Synthetic"


def test_single_image_extractor_no_exif_returns_none(jpeg_without_exif: Path) -> None:
    assert Extractor.single_image_extractor(str(jpeg_without_exif)) is None


def test_single_image_extractor_unsupported_format_returns_none(tmp_path: Path) -> None:
    bogus = tmp_path / "not_an_image.txt"
    bogus.write_text("hello")
    assert Extractor.single_image_extractor(str(bogus)) is None


def test_remove_image_metadata_strips_exif(jpeg_with_exif: Path) -> None:
    assert Extractor.remove_image_metadata(str(jpeg_with_exif)) is True
    # After removal, no EXIF should be readable.
    with Image.open(jpeg_with_exif) as img:
        assert img._getexif() is None  # type: ignore[attr-defined]


def test_multi_image_extractor(tmp_path: Path, jpeg_with_exif: Path) -> None:
    # Place the fixture image in a directory and dispatch.
    images = {jpeg_with_exif.name: jpeg_with_exif.name}
    result = Extractor.multi_image_extractor(str(jpeg_with_exif.parent), images)
    assert jpeg_with_exif.name in result
    assert result[jpeg_with_exif.name]["Make"] == "EOM-Test"
