"""Tests for formats, risk, profiles, selective removal, editing, exporters and the CLI."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import zipfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

import cli
import exiftool_backend
import exporters
import Extractor
import formats
import profiles
import risk

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _rich_jpeg(path: Path) -> Path:
    img = Image.new("RGB", (16, 16), (10, 20, 30))
    exif = img.getexif()
    exif[0x010F] = "Canon"  # Make
    exif[0x0110] = "EOS"  # Model
    exif[0x013B] = "Bob"  # Artist
    exif[0x8298] = "(c) Bob"  # Copyright
    exif[0x0132] = "2020:01:01 10:00:00"  # DateTime
    exif.get_ifd(0x8769)[0xA431] = "SER123"  # BodySerialNumber
    exif.get_ifd(0x8769)[0x9003] = "2020:01:01 10:00:00"  # DateTimeOriginal
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (48.0, 51.0, 30.0), "E", (2.0, 21.0, 0.0)
    img.save(path, "JPEG", exif=exif)
    return path


@pytest.fixture
def rich_jpeg(tmp_path: Path) -> Path:
    return _rich_jpeg(tmp_path / "rich.jpg")


def _mp3(path: Path, **frames) -> Path:
    from mutagen.id3 import ID3, TIT2, TPE1

    path.write_bytes((bytes([0xFF, 0xFB, 0x90, 0xC0]) + bytes(413)) * 4)
    tags = ID3()
    tags.add(TIT2(encoding=3, text=frames.get("title", "Song")))
    tags.add(TPE1(encoding=3, text=frames.get("artist", "Bob")))
    tags.save(str(path))
    return path


def _pdf(path: Path) -> Path:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Author": "Bob", "/Title": "Doc", "/Producer": "Word"})
    with open(path, "wb") as f:
        writer.write(f)
    return path


_CORE = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    b'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
    b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    b"<dc:title>Secret plan</dc:title><dc:creator>Bob Smith</dc:creator>"
    b"<cp:lastModifiedBy>Alice</cp:lastModifiedBy>"
    b'<dcterms:created xsi:type="dcterms:W3CDTF">2020-01-01T00:00:00Z</dcterms:created>'
    b"</cp:coreProperties>"
)
_APP = (
    b'<?xml version="1.0"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
    b"<Application>Microsoft Office Word</Application><Company>ACME</Company><Pages>3</Pages></Properties>"
)


@pytest.fixture
def docx(tmp_path: Path) -> Path:
    path = tmp_path / "plan.docx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("docProps/core.xml", _CORE)
        zf.writestr("docProps/app.xml", _APP)
        zf.writestr("word/document.xml", b'<w:document xmlns:w="w"><w:ins w:author="Carol"/></w:document>')
    return path


# ---------------------------------------------------------------------------
# formats
# ---------------------------------------------------------------------------


def test_scan_directory_recursive_and_flat(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / ".hidden").mkdir()
    for rel in ("a.jpg", "b.txt", "sub/c.PDF", ".hidden/d.jpg", "sub/e.docx"):
        (tmp_path / rel).write_bytes(b"x")

    assert formats.scan_directory(tmp_path) == {"a.jpg": "a.jpg"}
    assert list(formats.scan_directory(tmp_path, recursive=True)) == ["a.jpg", "sub/c.PDF", "sub/e.docx"]
    assert formats.scan_directory(tmp_path / "missing") == {}


def test_new_formats_are_supported() -> None:
    for ext in (".webp", ".heic", ".gif", ".docx", ".xlsx", ".pptx", ".mov"):
        assert formats.is_supported(f"x{ext}")
    assert ".mp3" not in formats.EXIFTOOL_WRITABLE_EXTENSIONS
    assert ".pdf" not in formats.EXIFTOOL_WRITABLE_EXTENSIONS


# ---------------------------------------------------------------------------
# risk & profiles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "category"),
    [
        ("GPS:GPSLatitude", risk.LOCATION),
        ("GPSLongitude", risk.LOCATION),
        ("IFD0:Artist", risk.IDENTITY),
        ("Author", risk.IDENTITY),
        ("XML:LastModifiedBy", risk.IDENTITY),
        ("ExifIFD:SerialNumber", risk.IDENTIFIERS),
        ("IFD0:Make", risk.DEVICE),
        ("LensModel", risk.DEVICE),
        ("ExifIFD:DateTimeOriginal", risk.DATES),
        ("ExposureTime", risk.TECHNICAL),
        ("IFD0:Software", risk.SOFTWARE),
        ("IFD1:ThumbnailImage", risk.THUMBNAIL),
        ("IFD0:Copyright", risk.COPYRIGHT),
        ("ICC_Profile:ProfileCreator", risk.TECHNICAL),
    ],
)
def test_categorize(key: str, category: str) -> None:
    assert risk.categorize(key) == category


def test_assess_levels() -> None:
    assert risk.assess(None).level == risk.Severity.NONE
    assert risk.assess({"System:FileSize": "1 kB", "File:ImageWidth": "4"}).level == risk.Severity.NONE
    assert risk.assess({"IFD0:Make": "Canon"}).level == risk.Severity.MEDIUM
    report = risk.assess({"IFD0:Make": "Canon", "Composite:GPSPosition": "1, 2"})
    assert report.level == risk.Severity.HIGH
    assert report.summary().startswith("High — Location (GPS)")


def test_profile_keys_to_remove() -> None:
    data = {"IFD0:Artist": "a", "IFD0:Copyright": "c", "ExifIFD:DateTimeOriginal": "d", "System:FileName": "f"}
    assert profiles.keys_to_remove(data, profiles.get("social")) == ["IFD0:Artist"]
    assert set(profiles.keys_to_remove(data, profiles.get("keep_copyright"))) == {
        "IFD0:Artist",
        "ExifIFD:DateTimeOriginal",
    }
    with pytest.raises(ValueError):
        profiles.get("nope")
    with pytest.raises(ValueError):
        profiles.custom({"bogus"})


# ---------------------------------------------------------------------------
# Pillow backend: extraction, selective removal, editing
# ---------------------------------------------------------------------------


def test_pillow_reads_exif_ifd_and_gps(rich_jpeg: Path) -> None:
    data = Extractor.single_image_extractor(str(rich_jpeg))
    assert data["BodySerialNumber"] == "SER123"
    assert data["DateTimeOriginal"] == "2020:01:01 10:00:00"
    lat, lon = Extractor.gps_coordinates(data)
    assert lat == pytest.approx(48.858333, abs=1e-5)
    assert lon == pytest.approx(2.35)


def test_gps_coordinates_parses_exiftool_dms() -> None:
    data = {"Composite:GPSLatitude": "33 deg 52' 10.00\" S", "Composite:GPSLongitude": "151 deg 12' 30.00\" E"}
    lat, lon = Extractor.gps_coordinates(data)
    assert lat == pytest.approx(-33.869444, abs=1e-5)
    assert lon == pytest.approx(151.208333, abs=1e-5)
    assert Extractor.gps_coordinates({"IFD0:Make": "x"}) is None


def test_selective_removal_social_profile(rich_jpeg: Path) -> None:
    os.chmod(rich_jpeg, 0o644)
    assert Extractor.remove_metadata(str(rich_jpeg), profiles.get("social")) is True
    data = Extractor.single_image_extractor(str(rich_jpeg))
    assert "Artist" not in data and "Make" not in data and "BodySerialNumber" not in data
    assert Extractor.gps_coordinates(data) is None
    assert data["Copyright"] == "(c) Bob"
    assert data["DateTimeOriginal"] == "2020:01:01 10:00:00"
    # Atomic write must keep the original permissions (mkstemp creates 0600 files).
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(rich_jpeg).st_mode) == 0o644


def test_remove_explicit_keys(rich_jpeg: Path) -> None:
    assert Extractor.remove_metadata(str(rich_jpeg), keys=["Copyright"]) is True
    data = Extractor.single_image_extractor(str(rich_jpeg))
    assert "Copyright" not in data and data["Artist"] == "Bob"


def test_write_metadata_and_shift_dates(rich_jpeg: Path) -> None:
    assert Extractor.write_metadata(str(rich_jpeg), {"Author": "Alice", "Title": "Hello"}) is True
    assert Extractor.shift_dates(str(rich_jpeg), timedelta(hours=-2)) is True
    data = Extractor.single_image_extractor(str(rich_jpeg))
    assert data["Artist"] == "Alice"
    assert data["XPTitle"] == "Hello"
    assert data["DateTimeOriginal"] == "2020:01:01 08:00:00"
    with pytest.raises(ValueError):
        Extractor.write_metadata(str(rich_jpeg), {"Nope": "x"})
    with pytest.raises(ValueError):
        Extractor.write_metadata(str(rich_jpeg), {"Date": "yesterday"})


def test_png_text_chunks_are_metadata(tmp_path: Path) -> None:
    from PIL import PngImagePlugin

    path = tmp_path / "t.png"
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "Bob")
    info.add_text("Comment", "keep me")
    Image.new("RGB", (4, 4)).save(path, pnginfo=info)
    assert Extractor.single_image_extractor(str(path)) == {"Author": "Bob", "Comment": "keep me"}
    assert Extractor.remove_metadata(str(path), profiles.get("social")) is True
    assert Extractor.single_image_extractor(str(path)) == {"Comment": "keep me"}


def test_webp_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "x.webp"
    img = Image.new("RGB", (4, 4))
    exif = img.getexif()
    exif[0x013B] = "Bob"
    img.save(path, "WEBP", exif=exif)
    assert Extractor.single_image_extractor(str(path))["Artist"] == "Bob"
    assert Extractor.remove_image_metadata(str(path)) is True
    assert Extractor.single_image_extractor(str(path)) is None


# ---------------------------------------------------------------------------
# PDF / audio / Office
# ---------------------------------------------------------------------------


def test_pdf_selective_and_write(tmp_path: Path) -> None:
    path = _pdf(tmp_path / "d.pdf")
    assert Extractor.remove_metadata(str(path), profiles.get("social")) is True
    data = Extractor.single_image_extractor(str(path))
    assert "Author" not in data and data["Title"] == "Doc"
    assert Extractor.write_metadata(str(path), {"Author": "Zed", "Date": "2021-02-03"}) is True
    data = Extractor.single_image_extractor(str(path))
    assert data["Author"] == "Zed" and data["CreationDate"].startswith("D:20210203")


def test_mp3_selective_removal_and_write(tmp_path: Path) -> None:
    path = _mp3(tmp_path / "s.mp3")
    assert Extractor.remove_metadata(str(path), profiles.get("social")) is True
    data = Extractor.single_image_extractor(str(path))
    assert "Artist" not in data and data["Title"] == "Song"
    assert Extractor.write_metadata(str(path), {"Author": "New"}) is True
    assert Extractor.single_image_extractor(str(path))["Artist"] == "New"


def test_office_extract_remove_write(docx: Path) -> None:
    data = Extractor.single_image_extractor(str(docx))
    assert data["Creator"] == "Bob Smith"
    assert data["Company"] == "ACME"
    assert data["RevisionAuthors"] == "Carol"
    assert "Pages" not in data
    assert risk.assess(data).level == risk.Severity.HIGH

    assert Extractor.write_metadata(str(docx), {"Author": "Zed"}) is True
    assert Extractor.single_image_extractor(str(docx))["Creator"] == "Zed"

    assert Extractor.remove_image_metadata(str(docx)) is True
    assert Extractor.single_image_extractor(str(docx)) is None
    with zipfile.ZipFile(docx) as zf:
        assert b"Carol" not in zf.read("word/document.xml")
        assert b"<Pages>3</Pages>" in zf.read("docProps/app.xml")  # statistics untouched


def test_office_bad_zip_returns_none(tmp_path: Path) -> None:
    bad = tmp_path / "bad.docx"
    bad.write_text("not a zip")
    assert Extractor.single_image_extractor(str(bad)) is None
    assert Extractor.remove_image_metadata(str(bad)) is None


# ---------------------------------------------------------------------------
# Output copies & diff
# ---------------------------------------------------------------------------


def test_copy_to_output_never_overwrites(tmp_path: Path, rich_jpeg: Path) -> None:
    out = tmp_path / "out"
    first = Extractor.copy_to_output(str(rich_jpeg), str(out), "sub/rich.jpg")
    second = Extractor.copy_to_output(str(rich_jpeg), str(out), "sub/rich.jpg")
    assert Path(first) == out / "sub" / "rich.jpg"
    assert Path(second).name == "rich (1).jpg"
    # Output dir == source dir must not clobber the original.
    third = Extractor.copy_to_output(str(rich_jpeg), str(rich_jpeg.parent))
    assert Path(third) != rich_jpeg


def test_diff_metadata_ignores_file_properties() -> None:
    before = {"System:FileSize": "1", "IFD0:Artist": "a", "IFD0:Make": "m", "IFD0:Software": "x"}
    after = {"System:FileSize": "2", "IFD0:Make": "m", "IFD0:Software": "y"}
    assert Extractor.diff_metadata(before, after) == {
        "removed": ["IFD0:Artist"],
        "changed": ["IFD0:Software"],
        "remaining": ["IFD0:Make", "IFD0:Software"],
    }


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------

_RESULTS = {"a.jpg": {"IFD0:Artist": "Bob", "File:Size": "1"}, "b.pdf": None}


def test_export_formats(tmp_path: Path) -> None:
    payload = json.loads(exporters.render(_RESULTS, "json"))
    assert payload["a.jpg"]["risk"] == "High"
    assert payload["b.pdf"]["metadata"] == {}

    csv_text = exporters.render(_RESULTS, "csv")
    assert csv_text.splitlines()[1] == "a.jpg,IFD0:Artist,Bob,identity,high"

    html_text = exporters.render({"<x>": {"k": "<script>"}}, "html")
    assert "&lt;script&gt;" in html_text and "<script>" not in html_text

    assert "== a.jpg ==" in exporters.render(_RESULTS, "txt")

    out = tmp_path / "r.HTML"
    assert exporters.export(_RESULTS, str(out)) == "html"
    assert out.read_text().startswith("<!doctype html>")
    with pytest.raises(ValueError):
        exporters.render(_RESULTS, "xml")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_parse_shift() -> None:
    assert cli.parse_shift("+1d2h30m") == timedelta(days=1, hours=2, minutes=30)
    assert cli.parse_shift("-3h") == timedelta(hours=-3)
    with pytest.raises(Exception):  # noqa: B017
        cli.parse_shift("tomorrow")


def test_cli_extract_json(rich_jpeg: Path, capsys) -> None:
    assert cli.main(["extract", str(rich_jpeg), "-f", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[str(rich_jpeg)]["metadata"]["Artist"] == "Bob"


def test_cli_risk_exit_code(rich_jpeg: Path, jpeg_without_exif: Path, capsys) -> None:
    assert cli.main(["risk", str(rich_jpeg)]) == 2
    assert cli.main(["risk", str(jpeg_without_exif)]) == 0


def test_cli_clean_to_output_dir(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    _rich_jpeg(src / "sub" / "p.jpg")
    out = tmp_path / "out"
    assert cli.main(["clean", str(src), "-r", "-p", "location", "-O", str(out)]) == 0
    cleaned = Extractor.single_image_extractor(str(out / "sub" / "p.jpg"))
    assert Extractor.gps_coordinates(cleaned) is None and cleaned["Artist"] == "Bob"
    # Original untouched.
    assert Extractor.gps_coordinates(Extractor.single_image_extractor(str(src / "sub" / "p.jpg")))


def test_cli_dry_run_changes_nothing(rich_jpeg: Path, capsys) -> None:
    before = rich_jpeg.read_bytes()
    assert cli.main(["clean", str(rich_jpeg), "-n"]) == 0
    assert "would remove" in capsys.readouterr().out
    assert rich_jpeg.read_bytes() == before


def test_cli_edit(rich_jpeg: Path, capsys) -> None:
    assert cli.main(["edit", str(rich_jpeg), "--copyright", "CC-BY", "--shift", "+1d"]) == 0
    data = Extractor.single_image_extractor(str(rich_jpeg))
    assert data["Copyright"] == "CC-BY" and data["DateTimeOriginal"] == "2020:01:02 10:00:00"


def test_cli_missing_path() -> None:
    with pytest.raises(SystemExit):
        cli.main(["extract", "/definitely/not/here.jpg"])


# ---------------------------------------------------------------------------
# Real ExifTool integration (skipped when not installed)
# ---------------------------------------------------------------------------

_REAL_EXIFTOOL = shutil.which("exiftool")
needs_exiftool = pytest.mark.skipif(not _REAL_EXIFTOOL or sys.platform == "win32", reason="exiftool not installed")


@needs_exiftool
def test_exiftool_selective_removal(rich_jpeg: Path) -> None:
    with patch.object(exiftool_backend, "_EXIFTOOL_PATH", _REAL_EXIFTOOL):
        data = Extractor.single_image_extractor(str(rich_jpeg))
        assert "GoogleMapLink" in data
        assert Extractor.remove_metadata(str(rich_jpeg), profiles.get("social")) is True
        after = Extractor.single_image_extractor(str(rich_jpeg))
    assert "IFD0:Artist" not in after and "GPS:GPSLatitude" not in after
    assert after["IFD0:Copyright"] == "(c) Bob"


@needs_exiftool
def test_exiftool_present_still_cleans_mp3(tmp_path: Path) -> None:
    """ExifTool cannot write MP3 — removal must fall back to mutagen."""
    path = _mp3(tmp_path / "s.mp3")
    with patch.object(exiftool_backend, "_EXIFTOOL_PATH", _REAL_EXIFTOOL):
        assert Extractor.remove_image_metadata(str(path)) is True
        assert Extractor.remove_metadata(str(_mp3(tmp_path / "t.mp3")), profiles.get("social")) is True
    assert "Title" not in (Extractor.audio_video_extractor(str(path)) or {})
    assert "Artist" not in Extractor.audio_video_extractor(str(tmp_path / "t.mp3"))
