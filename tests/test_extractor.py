"""Smoke tests for Extractor pure functions."""

from __future__ import annotations

from pathlib import Path

import pytest
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
    # After removal, getexif() should return an empty Exif object.
    with Image.open(jpeg_with_exif) as img:
        assert not img.getexif()


def test_multi_image_extractor(tmp_path: Path, jpeg_with_exif: Path) -> None:
    # Place the fixture image in a directory and dispatch.
    images = {jpeg_with_exif.name: jpeg_with_exif.name}
    result = Extractor.multi_image_extractor(str(jpeg_with_exif.parent), images)
    assert jpeg_with_exif.name in result
    assert result[jpeg_with_exif.name]["Make"] == "EOM-Test"


# ---------------------------------------------------------------------------
# PNG support
# ---------------------------------------------------------------------------


def test_single_image_extractor_png_returns_exif(tmp_path: Path) -> None:
    path = tmp_path / "with_exif.png"
    img = Image.new("RGB", (4, 4), color=(0, 0, 255))
    exif = img.getexif()
    exif[0x010F] = "PNG-Make"
    img.save(path, "PNG", exif=exif)
    data = Extractor.single_image_extractor(str(path))
    assert data is not None
    assert data.get("Make") == "PNG-Make"


def test_remove_image_metadata_strips_exif_png(tmp_path: Path) -> None:
    path = tmp_path / "with_exif.png"
    img = Image.new("RGB", (4, 4), color=(0, 0, 255))
    exif = img.getexif()
    exif[0x010F] = "PNG-Make"
    img.save(path, "PNG", exif=exif)
    assert Extractor.remove_image_metadata(str(path)) is True
    with Image.open(path) as img2:
        assert not img2.getexif()


# ---------------------------------------------------------------------------
# PDF support
# ---------------------------------------------------------------------------


def test_pdf_extractor_returns_metadata(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    PdfWriter = pypdf.PdfWriter

    path = tmp_path / "meta.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Author": "TestAuthor", "/Title": "TestTitle"})
    with open(path, "wb") as f:
        writer.write(f)

    data = Extractor.pdf_extractor(str(path))
    assert data is not None
    assert data.get("Author") == "TestAuthor"


def test_remove_pdf_metadata_strips(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    PdfWriter = pypdf.PdfWriter

    path = tmp_path / "meta.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Author": "ToBeRemoved"})
    with open(path, "wb") as f:
        writer.write(f)

    assert Extractor.remove_pdf_metadata(str(path)) is True
    data = Extractor.pdf_extractor(str(path))
    # After removal, no Author should be present.
    assert data is None or "Author" not in data


# ---------------------------------------------------------------------------
# GPS edge cases
# ---------------------------------------------------------------------------


def test_gps_malformed_data_does_not_crash(jpeg_with_exif: Path) -> None:
    """_create_google_maps_url with missing keys should not raise."""
    # Call the internal helper directly with deliberately incomplete GPS dicts.
    assert Extractor._create_google_maps_url({}) is None
    assert Extractor._create_google_maps_url({"lat": None, "lon": None}) is None
    assert Extractor._create_google_maps_url({"lat": "bad", "lon": "data", "lat_ref": "N", "lon_ref": "E"}) is None


# ---------------------------------------------------------------------------
# Path-traversal safety
# ---------------------------------------------------------------------------


def test_safe_join_blocks_traversal(tmp_path: Path) -> None:
    result = Extractor._safe_join(str(tmp_path), "../../etc/passwd")
    assert result is None


def test_multi_image_extractor_blocks_traversal(tmp_path: Path) -> None:
    images = {"evil": "../../etc/passwd"}
    result = Extractor.multi_image_extractor(str(tmp_path), images)
    assert result["evil"] is None


# ---------------------------------------------------------------------------
# Atomic write safety
# ---------------------------------------------------------------------------


def test_remove_image_metadata_no_temp_files_left(jpeg_with_exif: Path) -> None:
    parent = jpeg_with_exif.parent
    before = set(parent.iterdir())
    Extractor.remove_image_metadata(str(jpeg_with_exif))
    after = set(parent.iterdir())
    new_files = after - before
    assert not any(f.suffix == ".tmp" for f in new_files)


# ---------------------------------------------------------------------------
# Audio / Video support
# ---------------------------------------------------------------------------


def test_audio_video_extractor_returns_tags(tmp_path: Path) -> None:
    pytest.importorskip("mutagen")
    from mutagen.id3 import ID3, TIT2, TPE1

    path = tmp_path / "sample.mp3"
    # MPEG1 Layer3 128kbps 44100Hz joint-stereo, no emphasis = valid silent frame.
    # Frame size: 144 * 128000 / 44100 = 417 bytes.
    mp3_frame = bytes([0xFF, 0xFB, 0x90, 0xC0]) + bytes(413)
    path.write_bytes(mp3_frame * 4)

    tags = ID3()
    tags.add(TIT2(encoding=3, text="Test Title"))
    tags.add(TPE1(encoding=3, text="Test Artist"))
    tags.save(str(path))

    data = Extractor.audio_video_extractor(str(path))
    assert data is not None
    assert data.get("Title") == "Test Title"
    assert data.get("Artist") == "Test Artist"


def test_remove_audio_video_metadata_strips_tags(tmp_path: Path) -> None:
    pytest.importorskip("mutagen")
    from mutagen.id3 import ID3, TIT2

    path = tmp_path / "tagged.mp3"
    mp3_frame = bytes([0xFF, 0xFB, 0x90, 0xC0]) + bytes(413)
    path.write_bytes(mp3_frame * 4)

    tags = ID3()
    tags.add(TIT2(encoding=3, text="RemoveMe"))
    tags.save(str(path))

    assert Extractor.remove_audio_video_metadata(str(path)) is True
    data = Extractor.audio_video_extractor(str(path))
    assert data is None or "Title" not in data


def test_single_image_extractor_dispatches_audio(tmp_path: Path) -> None:
    """single_image_extractor routes .mp3 files to audio_video_extractor."""
    pytest.importorskip("mutagen")
    from mutagen.id3 import ID3, TIT2

    path = tmp_path / "dispatch.mp3"
    mp3_frame = bytes([0xFF, 0xFB, 0x90, 0xC0]) + bytes(413)
    path.write_bytes(mp3_frame * 4)
    tags = ID3()
    tags.add(TIT2(encoding=3, text="Dispatched"))
    tags.save(str(path))

    data = Extractor.single_image_extractor(str(path))
    assert data is not None
    assert data.get("Title") == "Dispatched"
