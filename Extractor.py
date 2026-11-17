"""Format-dispatch functions for reading, stripping and editing metadata.

Backends, in dispatch order:

* ExifTool (optional CLI) — richest reader; writer only for the formats in
  :data:`formats.EXIFTOOL_WRITABLE_EXTENSIONS`.
* Pillow — JPEG / PNG / TIFF / WebP / GIF (+ HEIC when ``pillow-heif`` is installed).
* mutagen — audio and video tags.
* pypdf — PDF document info.
* zipfile — Office Open XML (DOCX / XLSX / PPTX) document properties.

Contract relied on by controllers, workers and tests: readers return a dict or
``None`` (unsupported / nothing found); writers return ``True`` or ``None``.
Every fallback writer is atomic (temp file in the same directory + ``os.replace``).
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

from mutagen import File as MutagenFile
from PIL import Image, PngImagePlugin
from PIL.ExifTags import GPSTAGS, TAGS
from pypdf import PdfReader, PdfWriter

import exiftool_backend
import formats
import profiles
import risk

try:  # Optional HEIC/HEIF support for the Pillow fallback.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover - optional dependency
    pass

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Image formats handled via Pillow EXIF API.
_IMAGE_FORMATS = ("JPEG", "JPG", "PNG", "TIFF", "TIF", "WEBP", "GIF", "HEIF", "MPO")
# Kept as module attributes for backward compatibility.
_PDF_EXTENSIONS = formats.PDF_EXTENSIONS
_AUDIO_EXTENSIONS = formats.AUDIO_EXTENSIONS
_VIDEO_EXTENSIONS = formats.VIDEO_EXTENSIONS
_AUDIO_VIDEO_EXTENSIONS = formats.AUDIO_VIDEO_EXTENSIONS
_OFFICE_EXTENSIONS = formats.OFFICE_EXTENSIONS

_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
_POINTER_TAGS = {_EXIF_IFD, _GPS_IFD, 0xA005}  # Exif, GPS, Interop pointers
_TAG_IDS = {name: tag for tag, name in TAGS.items()}
_XP_TAGS = range(0x9C9B, 0x9CA0)  # Windows XPTitle/XPComment/XPAuthor/XPKeywords/XPSubject (UTF-16LE)

# The "fields" EOM can edit, with their per-backend mapping.
EDITABLE_FIELDS = ("Title", "Author", "Copyright", "Description", "Date")


def _convert_decimal_degrees(degree: float, minutes: float, seconds: float, direction: str) -> float:
    """Convert DMS coordinates to decimal degrees."""
    decimal_degrees = float(degree) + float(minutes) / 60 + float(seconds) / 3600
    if direction in ("S", "W"):
        decimal_degrees *= -1
    return decimal_degrees


def _create_google_maps_url(gps_coords: dict) -> str | None:
    """Return a Google Maps URL from a GPS coordinate dict, or None on any error."""
    try:
        lat = gps_coords["lat"]
        lon = gps_coords["lon"]
        dec_deg_lat = _convert_decimal_degrees(float(lat[0]), float(lat[1]), float(lat[2]), gps_coords["lat_ref"])
        dec_deg_lon = _convert_decimal_degrees(float(lon[0]), float(lon[1]), float(lon[2]), gps_coords["lon_ref"])
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return f"https://maps.google.com/?q={dec_deg_lat},{dec_deg_lon}"


def _safe_join(base: str, name: str) -> Path | None:
    """Return the resolved path for *base/name* only if it stays inside *base*.

    Prevents path-traversal attacks (e.g. name='../../etc/passwd').
    """
    base_path = Path(base).resolve()
    candidate = (base_path / name).resolve()
    try:
        candidate.relative_to(base_path)
        return candidate
    except ValueError:
        return None


def _suffix(path: str) -> str:
    return Path(path).suffix.lower()


def _exiftool_can_write(path: str) -> bool:
    return exiftool_backend.is_available() and _suffix(path) in formats.EXIFTOOL_WRITABLE_EXTENSIONS


def _atomic_write(target: str, writer: Callable[[str], None]) -> bool | None:
    """Call ``writer(tmp_path)`` then atomically move tmp over *target*."""
    file_path = Path(target)
    tmp_name: str | None = None
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp")
        os.close(tmp_fd)
        writer(tmp_name)
        shutil.copymode(target, tmp_name)
        os.replace(tmp_name, target)
    except Exception:  # noqa: BLE001 — any backend failure must leave the original intact
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        return None
    return True


def _format_value(value) -> str | None:
    """Render a raw tag value for display; None for values not worth showing."""
    if isinstance(value, bytes):
        stripped = value.rstrip(b"\x00")
        if not stripped:
            return None
        try:
            text = stripped.decode("ascii")
            if text.isprintable():
                return text
        except UnicodeDecodeError:
            pass
        return f"<binary data, {len(value)} bytes>"
    if isinstance(value, str):
        value = value.rstrip("\x00")
        return value or None
    return value


# ---------------------------------------------------------------------------
# GPS helpers (shared by every backend and the map widget)
# ---------------------------------------------------------------------------

_DMS_RE = re.compile(r"(-?[\d.]+)\s*deg\s*(?:([\d.]+)'\s*)?(?:([\d.]+)\"\s*)?([NSEW])?", re.IGNORECASE)
_MAPLINK_RE = re.compile(r"[?&]q=(-?[\d.]+),(-?[\d.]+)")


def _parse_coordinate(text: str) -> float | None:
    text = str(text).strip()
    try:
        return float(text)
    except ValueError:
        pass
    match = _DMS_RE.search(text)
    if not match:
        return None
    deg, minutes, seconds, ref = match.groups()
    return _convert_decimal_degrees(float(deg), float(minutes or 0), float(seconds or 0), (ref or "").upper())


def gps_coordinates(metadata: dict | None) -> tuple[float, float] | None:
    """Return ``(lat, lon)`` in decimal degrees from any backend's output, or None."""
    if not metadata:
        return None
    link = metadata.get("GoogleMapLink")
    if link:
        match = _MAPLINK_RE.search(str(link))
        if match:
            return float(match.group(1)), float(match.group(2))
    lat = metadata.get("Composite:GPSLatitude")
    lon = metadata.get("Composite:GPSLongitude")
    if lat is not None and lon is not None:
        lat_f, lon_f = _parse_coordinate(lat), _parse_coordinate(lon)
        if lat_f is not None and lon_f is not None:
            return lat_f, lon_f
    return None


def _maps_link(lat: float, lon: float) -> str:
    return f"https://maps.google.com/?q={lat},{lon}"


# ---------------------------------------------------------------------------
# Public API — extraction
# ---------------------------------------------------------------------------


def single_image_extractor(image_path: str) -> dict | None:
    """Extract metadata from a single image, audio, video, PDF or Office file.

    When ExifTool is available it is used as the primary backend (richer
    XMP/IPTC/MakerNotes support).  Otherwise falls back to Pillow, mutagen,
    pypdf or zipfile depending on the file extension.

    :param image_path: absolute path to the file
    :return: dict of tag->value, or None when no metadata is found.
    """
    if exiftool_backend.is_available():
        data = exiftool_backend.extract(image_path)
        if data:
            coords = gps_coordinates(data)
            if coords:
                data["GoogleMapLink"] = _maps_link(*coords)
        return data

    return fallback_extractor(image_path)


def fallback_extractor(path: str) -> dict | None:
    """Extract with the built-in Python backends only (never ExifTool)."""
    suffix = _suffix(path)
    if suffix in _PDF_EXTENSIONS:
        return pdf_extractor(path)
    if suffix in _AUDIO_VIDEO_EXTENSIONS:
        return audio_video_extractor(path)
    if suffix in _OFFICE_EXTENSIONS:
        return office_extractor(path)
    return pillow_extractor(path)


def pillow_extractor(image_path: str) -> dict | None:
    """Read EXIF (IFD0 + Exif IFD + GPS IFD), PNG text chunks and XMP via Pillow."""
    try:
        image = Image.open(image_path)
    except OSError:
        return None

    with image:
        if image.format not in _IMAGE_FORMATS:
            return None

        exif = image.getexif()  # public Pillow API (>=9.2); never returns None
        extracted_data: dict = {}

        for tag, value in exif.items():
            tag_name = TAGS.get(tag)
            if not tag_name or tag in _POINTER_TAGS:
                continue
            if tag in _XP_TAGS and isinstance(value, (bytes, tuple)):
                value = bytes(value).decode("utf-16-le", "replace").rstrip("\x00")
            shown = _format_value(value)
            if shown is not None:
                extracted_data[tag_name] = shown

        for tag, value in exif.get_ifd(_EXIF_IFD).items():
            tag_name = TAGS.get(tag)
            if not tag_name or tag in _POINTER_TAGS:
                continue
            shown = _format_value(value)
            if shown is not None:
                extracted_data[tag_name] = shown

        gps_coords: dict = {}
        for key, val in exif.get_ifd(_GPS_IFD).items():
            gps_tag = GPSTAGS.get(key, f"GPSTag{key}")
            shown = _format_value(val)
            if shown is not None:
                extracted_data[gps_tag] = shown
            if gps_tag == "GPSLatitude":
                gps_coords["lat"] = val
            elif gps_tag == "GPSLongitude":
                gps_coords["lon"] = val
            elif gps_tag == "GPSLatitudeRef":
                gps_coords["lat_ref"] = val
            elif gps_tag == "GPSLongitudeRef":
                gps_coords["lon_ref"] = val

        if gps_coords:
            google_map_link = _create_google_maps_url(gps_coords)
            if google_map_link:
                extracted_data["GoogleMapLink"] = google_map_link

        # PNG tEXt/iTXt chunks (Author, Comment, Software…) and XMP packets.
        if image.format == "PNG":
            for key, value in image.info.items():
                if isinstance(value, str) and key not in ("exif", "XML:com.adobe.xmp") and value.strip():
                    extracted_data[key] = value
        xmp = image.info.get("xmp") or image.info.get("XML:com.adobe.xmp")
        if xmp:
            extracted_data["XMP"] = f"<XMP packet, {len(xmp)} bytes>"

    return extracted_data or None


def multi_image_extractor(path: str, images: dict) -> dict:
    """Extract metadata from multiple files in a directory.

    :param path:   directory containing the files
    :param images: mapping of {name: relative_path}
    :return:       mapping of {name: metadata_dict_or_None}
    """
    extracted_data: dict = {}
    for key, value in images.items():
        safe_path = _safe_join(path, value)
        if safe_path is None:
            extracted_data[key] = None
            continue
        extracted_data[key] = single_image_extractor(str(safe_path))
    return extracted_data


# ---------------------------------------------------------------------------
# Public API — removal
# ---------------------------------------------------------------------------


def remove_image_metadata(file: str) -> bool | None:
    """Strip all metadata from a file in place (``Remove everything`` profile).

    :return: True on success, None on unsupported format or I/O error.
    """
    if _exiftool_can_write(file):
        return exiftool_backend.remove(file)

    suffix = _suffix(file)
    if suffix in _PDF_EXTENSIONS:
        return remove_pdf_metadata(file)
    if suffix in _AUDIO_VIDEO_EXTENSIONS:
        return remove_audio_video_metadata(file)
    if suffix in _OFFICE_EXTENSIONS:
        return remove_office_metadata(file)
    return _pillow_remove(file, None)


def remove_metadata(
    file: str,
    profile: profiles.Profile | None = None,
    keys: list[str] | None = None,
) -> bool | None:
    """Strip metadata according to a *profile* or an explicit list of *keys*.

    * ``profile=None`` and ``keys=None`` → remove everything.
    * ``keys`` → remove exactly these keys (as returned by :func:`single_image_extractor`).
    * ``profile`` → remove every key whose risk category the profile targets.

    :return: True on success (including "nothing to remove"), None on error.
    """
    if keys is None and (profile is None or profile.remove_all):
        return remove_image_metadata(file)

    use_exiftool = _exiftool_can_write(file)
    if keys is None:
        metadata = single_image_extractor(file) if use_exiftool else fallback_extractor(file)
        keys = profiles.keys_to_remove(metadata, profile)
    keys = [k for k in keys if k != "GoogleMapLink" and not risk.is_file_property(k)]
    if not keys:
        return True

    if use_exiftool:
        categories = {risk.categorize(k) for k in keys}
        extra: list[str] = []
        if categories & {risk.DEVICE, risk.IDENTIFIERS}:
            extra.append("-MakerNotes:all=")  # maker notes hold serials & device info
        if risk.THUMBNAIL in categories:
            extra.append("-IFD1:all=")
        if risk.LOCATION in categories:
            extra.append("-GPS:all=")
        return exiftool_backend.remove_tags(file, keys, extra)

    # Keys may come from an ExifTool extraction ("ID3v2_3:Title"); the Python
    # backends only know the bare tag name.
    keys = [risk.split_key(k)[1] for k in keys]
    suffix = _suffix(file)
    if suffix in _PDF_EXTENSIONS:
        return remove_pdf_metadata(file, keys)
    if suffix in _AUDIO_VIDEO_EXTENSIONS:
        return remove_audio_video_metadata(file, keys)
    if suffix in _OFFICE_EXTENSIONS:
        return remove_office_metadata(file, keys)
    return _pillow_remove(file, set(keys))


def multi_remove_image_metadata(path: str, images: dict) -> dict:
    """Remove metadata from multiple files in a directory.

    :param path:   directory containing the files
    :param images: mapping of {name: relative_path}
    :return:       mapping of {name: True_or_None}
    """
    removed_list: dict = {}
    for key, value in images.items():
        safe_path = _safe_join(path, value)
        if safe_path is None:
            removed_list[key] = None
            continue
        removed_list[key] = remove_image_metadata(str(safe_path))
    return removed_list


def _pillow_save_kwargs(image: Image.Image) -> dict:
    kwargs: dict = {}
    if image.format == "JPEG":
        kwargs["quality"] = "keep"  # reuse original quantisation tables — no extra quality loss
    if getattr(image, "n_frames", 1) > 1 and image.format in ("GIF", "WEBP", "TIFF", "PNG"):
        kwargs["save_all"] = True
    if image.format == "WEBP":
        kwargs["lossless"] = image.info.get("lossless", False)
    return kwargs


def _pillow_remove(file: str, keys: set[str] | None) -> bool | None:
    """Pillow fallback. ``keys=None`` wipes everything; otherwise strips *keys* only."""
    try:
        image = Image.open(file)
        image.load()
    except OSError:
        return None

    if image.format not in _IMAGE_FORMATS:
        return None

    save_format = image.format
    kwargs = _pillow_save_kwargs(image)

    if keys is not None:
        exif = image.getexif()
        exif_ifd = exif.get_ifd(_EXIF_IFD)
        for name in keys:
            tag = _TAG_IDS.get(name)
            if tag is None or tag in _POINTER_TAGS:
                continue
            exif.pop(tag, None)
            exif_ifd.pop(tag, None)
        if any(k.startswith("GPS") or k == "GoogleMapLink" for k in keys):
            exif.get_ifd(_GPS_IFD).clear()
            exif.pop(_GPS_IFD, None)
        kwargs["exif"] = exif
        if image.info.get("icc_profile"):
            kwargs["icc_profile"] = image.info["icc_profile"]
        xmp = image.info.get("xmp")
        if xmp and "XMP" not in keys and save_format in ("JPEG", "PNG", "WEBP", "TIFF"):
            kwargs["xmp"] = xmp
        if save_format == "PNG":
            info = PngImagePlugin.PngInfo()
            for key, value in image.info.items():
                if isinstance(value, str) and key not in keys and key != "XML:com.adobe.xmp":
                    info.add_text(key, value)
            kwargs["pnginfo"] = info

    def _write(tmp: str) -> None:
        image.save(tmp, format=save_format, **kwargs)

    try:
        return _atomic_write(file, _write)
    finally:
        image.close()


# ---------------------------------------------------------------------------
# Public API — editing
# ---------------------------------------------------------------------------


def _parse_user_date(value: str) -> datetime:
    value = value.strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date '{value}'. Use YYYY-MM-DD HH:MM:SS.")


def write_metadata(file: str, fields: dict[str, str]) -> bool | None:
    """Set editable fields (see :data:`EDITABLE_FIELDS`). Empty string clears a field.

    :raises ValueError: for an unknown field or an unparsable Date.
    :return: True on success, None on unsupported format or I/O error.
    """
    unknown = set(fields) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValueError(f"Unknown field(s): {', '.join(sorted(unknown))}")
    date = _parse_user_date(fields["Date"]) if fields.get("Date") else None
    if not fields:
        return True

    if _exiftool_can_write(file):
        tag_map = {
            "Title": ["Title", "XPTitle"],
            "Author": ["Artist", "Creator", "Author", "XPAuthor"],
            "Copyright": ["Copyright", "Rights"],
            "Description": ["ImageDescription", "Description", "Subject"],
            "Date": ["AllDates"],
        }
        assignments = []
        for name, value in fields.items():
            text = date.strftime("%Y:%m:%d %H:%M:%S") if name == "Date" and date else value
            assignments += [f"-{tag}={text}" for tag in tag_map[name]]
        return exiftool_backend.write(file, assignments)

    suffix = _suffix(file)
    if suffix in _PDF_EXTENSIONS:
        return _pdf_write(file, fields, date)
    if suffix in _AUDIO_VIDEO_EXTENSIONS:
        return _audio_write(file, fields, date)
    if suffix in _OFFICE_EXTENSIONS:
        return _office_write(file, fields, date)
    return _pillow_write(file, fields, date)


def _pillow_write(file: str, fields: dict[str, str], date: datetime | None) -> bool | None:
    try:
        image = Image.open(file)
        image.load()
    except OSError:
        return None
    if image.format not in _IMAGE_FORMATS or image.format == "GIF":
        image.close()
        return None

    exif = image.getexif()
    exif_ifd = exif.get_ifd(_EXIF_IFD)

    def _set(ifd, tag: int, value: str | None) -> None:
        if value:
            ifd[tag] = value
        else:
            ifd.pop(tag, None)

    if "Title" in fields:
        _set(exif, 0x9C9B, fields["Title"].encode("utf-16-le") + b"\x00\x00" if fields["Title"] else None)
    if "Author" in fields:
        _set(exif, 0x013B, fields["Author"])
    if "Copyright" in fields:
        _set(exif, 0x8298, fields["Copyright"])
    if "Description" in fields:
        _set(exif, 0x010E, fields["Description"])
    if "Date" in fields:
        stamp = date.strftime("%Y:%m:%d %H:%M:%S") if date else None
        _set(exif, 0x0132, stamp)
        _set(exif_ifd, 0x9003, stamp)
        _set(exif_ifd, 0x9004, stamp)

    kwargs = _pillow_save_kwargs(image)
    kwargs["exif"] = exif
    for key in ("icc_profile", "xmp"):
        if image.info.get(key):
            kwargs[key] = image.info[key]
    fmt = image.format
    try:
        return _atomic_write(file, lambda tmp: image.save(tmp, format=fmt, **kwargs))
    finally:
        image.close()


def shift_dates(file: str, delta: timedelta) -> bool | None:
    """Shift every date/time tag by *delta* (e.g. to fix a camera clock).

    :return: True on success, None on unsupported format or error.
    """
    if not delta:
        return True
    if _exiftool_can_write(file):
        sign = "+" if delta > timedelta(0) else "-"
        total = abs(delta)
        hours, rem = divmod(total.seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        shift = f"0:0:{total.days} {hours}:{minutes}:{seconds}"
        return exiftool_backend.write(file, [f"-AllDates{sign}={shift}"])

    try:
        image = Image.open(file)
        image.load()
    except OSError:
        return None
    if image.format not in _IMAGE_FORMATS or image.format == "GIF":
        image.close()
        return None

    exif = image.getexif()
    exif_ifd = exif.get_ifd(_EXIF_IFD)
    changed = False
    for ifd, tag in ((exif, 0x0132), (exif_ifd, 0x9003), (exif_ifd, 0x9004)):
        raw = ifd.get(tag)
        if not raw:
            continue
        try:
            ifd[tag] = (datetime.strptime(str(raw).strip("\x00"), "%Y:%m:%d %H:%M:%S") + delta).strftime(
                "%Y:%m:%d %H:%M:%S"
            )
            changed = True
        except ValueError:
            continue
    if not changed:
        image.close()
        return None

    kwargs = _pillow_save_kwargs(image)
    kwargs["exif"] = exif
    for key in ("icc_profile", "xmp"):
        if image.info.get(key):
            kwargs[key] = image.info[key]
    fmt = image.format
    try:
        return _atomic_write(file, lambda tmp: image.save(tmp, format=fmt, **kwargs))
    finally:
        image.close()


# ---------------------------------------------------------------------------
# Output-copy and verification helpers
# ---------------------------------------------------------------------------


def copy_to_output(source: str, output_dir: str, relative_name: str | None = None) -> str:
    """Copy *source* into *output_dir* (keeping *relative_name* sub-folders).

    Never overwrites the source itself and never overwrites an existing file:
    a numeric suffix is appended instead (``photo (1).jpg``).

    :return: path of the copy.
    """
    rel = Path(relative_name or Path(source).name)
    dest = Path(output_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    candidate, counter = dest, 1
    src_resolved = Path(source).resolve()
    while candidate.exists() or candidate.resolve() == src_resolved:
        candidate = dest.with_name(f"{dest.stem} ({counter}){dest.suffix}")
        counter += 1
    shutil.copy2(source, candidate)
    return str(candidate)


def diff_metadata(before: dict | None, after: dict | None) -> dict[str, list[str]]:
    """Compare two extractions. File-system properties are ignored.

    :return: ``{"removed": [...], "changed": [...], "remaining": [...]}``
    """
    before = {k: v for k, v in (before or {}).items() if not risk.is_file_property(k) and k != "GoogleMapLink"}
    after = {k: v for k, v in (after or {}).items() if not risk.is_file_property(k) and k != "GoogleMapLink"}
    return {
        "removed": [k for k in before if k not in after],
        "changed": [k for k in before if k in after and str(before[k]) != str(after[k])],
        "remaining": list(after),
    }


# ---------------------------------------------------------------------------
# PDF support
# ---------------------------------------------------------------------------


def pdf_extractor(pdf_path: str) -> dict | None:
    """Extract document metadata from a PDF file.

    :param pdf_path: absolute path to the PDF file
    :return: dict of metadata fields, or None on error / no metadata.
    """
    try:
        reader = PdfReader(pdf_path)
        meta = reader.metadata
        xmp = reader.xmp_metadata
    except Exception:  # noqa: BLE001  — pypdf can raise various exceptions
        return None

    data = {k.lstrip("/"): str(v) for k, v in meta.items() if v} if meta else {}
    if xmp is not None:
        data["XMP"] = "<XMP metadata stream>"
    return data or None


def remove_pdf_metadata(pdf_path: str, keys: list[str] | None = None) -> bool | None:
    """Remove document metadata from a PDF file in place.

    ``keys=None`` removes everything (info dictionary and XMP stream); otherwise
    only the named info entries are dropped.

    :return: True on success, None on error.
    """
    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter(clone_from=reader)
        if keys is None:
            writer.metadata = None  # drops the /Info dictionary entirely
            if "/Metadata" in writer._root_object:
                del writer._root_object["/Metadata"]
        else:
            meta = {k: v for k, v in (reader.metadata or {}).items() if k.lstrip("/") not in keys}
            # The setter replaces the whole /Info dictionary (pypdf >= 5).
            writer.metadata = meta or None
            if "XMP" in keys and "/Metadata" in writer._root_object:
                del writer._root_object["/Metadata"]
    except Exception:  # noqa: BLE001
        return None

    def _write(tmp: str) -> None:
        with open(tmp, "wb") as f:
            writer.write(f)

    return _atomic_write(pdf_path, _write)


def _pdf_write(pdf_path: str, fields: dict[str, str], date: datetime | None) -> bool | None:
    mapping = {"Title": "/Title", "Author": "/Author", "Description": "/Subject", "Copyright": "/Copyright"}
    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter(clone_from=reader)
        meta = dict(reader.metadata or {})
        for name, value in fields.items():
            if name == "Date":
                keys = ("/CreationDate", "/ModDate")
                value = date.strftime("D:%Y%m%d%H%M%S") if date else ""
            else:
                keys = (mapping[name],)
            for key in keys:
                if value:
                    meta[key] = value
                else:
                    meta.pop(key, None)
        writer.metadata = meta or None
    except Exception:  # noqa: BLE001
        return None

    def _write(tmp: str) -> None:
        with open(tmp, "wb") as f:
            writer.write(f)

    return _atomic_write(pdf_path, _write)


# ---------------------------------------------------------------------------
# Audio / Video support  (mutagen)
# ---------------------------------------------------------------------------


def audio_video_extractor(path: str) -> dict | None:
    """Extract tags and stream info from an audio or video file.

    Uses mutagen with easy=True so tag keys are normalised to lowercase common
    names (e.g. 'title', 'artist').  Technical stream properties (duration,
    bitrate, sample rate, channels) are appended when available.

    :param path: absolute path to the file
    :return: dict of field->value, or None when the format is unsupported or
             the file contains no metadata at all.
    """
    try:
        f = MutagenFile(path, easy=True)
    except Exception:  # noqa: BLE001
        return None

    if f is None:
        return None

    data: dict = {}

    if f.tags:
        for key, value in f.tags.items():
            data[key.title()] = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)

    info = f.info
    if hasattr(info, "length"):
        data["Duration"] = f"{info.length:.2f}s"
    if hasattr(info, "bitrate") and info.bitrate:
        data["Bitrate"] = f"{info.bitrate} bps"
    if hasattr(info, "sample_rate") and info.sample_rate:
        data["SampleRate"] = f"{info.sample_rate} Hz"
    if hasattr(info, "channels") and info.channels:
        data["Channels"] = str(info.channels)

    return data or None


def _mutagen_edit(path: str, edit: Callable) -> bool | None:
    """Copy to temp, apply ``edit(mutagen_file)`` there, then atomically replace."""

    def _write(tmp: str) -> None:
        shutil.copy2(path, tmp)
        tmp_f = MutagenFile(tmp, easy=True)
        if tmp_f is None:
            raise ValueError("unsupported")
        edit(tmp_f)

    try:
        if MutagenFile(path, easy=True) is None:
            return None
    except Exception:  # noqa: BLE001
        return None
    return _atomic_write(path, _write)


def remove_audio_video_metadata(path: str, keys: list[str] | None = None) -> bool | None:
    """Strip tags from an audio or video file in place (all, or only *keys*).

    :return: True on success, None on unsupported format or I/O error.
    """

    def _edit(f) -> None:
        if keys is None:
            f.delete()
            # Some formats (e.g. FLAC) also carry embedded pictures.
            if hasattr(f, "clear_pictures"):
                f.clear_pictures()
            f.save()
            return
        if f.tags:
            wanted = {k.lower() for k in keys}
            for tag in list(f.tags.keys()):
                if tag.lower() in wanted:
                    del f.tags[tag]
        f.save()

    return _mutagen_edit(path, _edit)


def _audio_write(path: str, fields: dict[str, str], date: datetime | None) -> bool | None:
    mapping = {"Title": "title", "Author": "artist", "Copyright": "copyright", "Description": "comment", "Date": "date"}

    def _edit(f) -> None:
        if f.tags is None:
            f.add_tags()
        for name, value in fields.items():
            key = mapping[name]
            text = date.strftime("%Y-%m-%d") if name == "Date" and date else value
            try:
                if text:
                    f.tags[key] = text
                elif key in f.tags:
                    del f.tags[key]
            except (KeyError, ValueError):
                continue  # this container has no such tag (e.g. 'comment' in EasyID3)
        f.save()

    return _mutagen_edit(path, _edit)


# ---------------------------------------------------------------------------
# Office Open XML support (DOCX / XLSX / PPTX)
# ---------------------------------------------------------------------------

_NS = {
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
}
_CORE = "docProps/core.xml"
_APP = "docProps/app.xml"
# Interesting app.xml entries (the rest are statistics like word counts).
_APP_FIELDS = {"Application", "AppVersion", "Company", "Manager", "Template", "TotalTime", "HyperlinkBase"}
# Author attributes on comments / tracked changes inside Word documents.
_WORD_AUTHOR_RE = re.compile(rb'(w:author|w:initials)="[^"]*"')
_ANON_AUTHOR = "Author"


def _register_office_namespaces() -> None:
    """Make ElementTree serialise with the prefixes Office itself uses."""
    for prefix, uri in _NS.items():
        # app.xml uses the extended-properties namespace as its *default* namespace.
        ET.register_namespace("" if prefix == "ep" else prefix, uri)
    ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
    ET.register_namespace("vt", "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def office_extractor(path: str) -> dict | None:
    """Read core (author, dates…) and app (company, software…) properties."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            data: dict = {}
            if _CORE in names:
                for el in ET.fromstring(zf.read(_CORE)):
                    if el.text and el.text.strip():
                        name = _local(el.tag)
                        data[name[0].upper() + name[1:]] = el.text.strip()
            if _APP in names:
                for el in ET.fromstring(zf.read(_APP)):
                    name = _local(el.tag)
                    if name in _APP_FIELDS and el.text and el.text.strip():
                        data[name] = el.text.strip()
            authors = set()
            for name in names:
                if name.startswith("word/") and name.endswith(".xml"):
                    for match in re.finditer(rb'w:author="([^"]*)"', zf.read(name)):
                        author = match.group(1).decode("utf-8", "replace")
                        if author and author != _ANON_AUTHOR:
                            authors.add(author)
            if authors:
                data["RevisionAuthors"] = ", ".join(sorted(authors))
    except (zipfile.BadZipFile, ET.ParseError, OSError, KeyError):
        return None
    return data or None


def _rewrite_zip(path: str, transform: Callable[[str, bytes], bytes]) -> bool | None:
    """Rewrite every member of the zip through ``transform(name, data)``."""

    def _write(tmp: str) -> None:
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                dst.writestr(item, transform(item.filename, src.read(item.filename)))

    try:
        zipfile.ZipFile(path).close()
    except (zipfile.BadZipFile, OSError):
        return None
    return _atomic_write(path, _write)


def _strip_xml(data: bytes, drop: Callable[[str], bool]) -> bytes:
    root = ET.fromstring(data)
    for el in list(root):
        if drop(_local(el.tag)):
            root.remove(el)
    _register_office_namespaces()
    return ET.tostring(root, xml_declaration=True, encoding="UTF-8")


def remove_office_metadata(path: str, keys: list[str] | None = None) -> bool | None:
    """Strip document properties (all, or only *keys*) from a DOCX/XLSX/PPTX file."""
    wanted = None if keys is None else {k[0].lower() + k[1:] for k in keys} | set(keys)

    def _transform(name: str, data: bytes) -> bytes:
        if name == _CORE:
            return _strip_xml(data, lambda tag: wanted is None or tag in wanted)
        if name == _APP:
            return _strip_xml(data, lambda tag: tag in _APP_FIELDS and (wanted is None or tag in wanted))
        if name.startswith("word/") and name.endswith(".xml") and (wanted is None or "RevisionAuthors" in wanted):
            return _WORD_AUTHOR_RE.sub(lambda m: m.group(1) + b'="Author"', data)
        return data

    return _rewrite_zip(path, _transform)


def _office_write(path: str, fields: dict[str, str], date: datetime | None) -> bool | None:
    targets = {
        "Title": f"{{{_NS['dc']}}}title",
        "Author": f"{{{_NS['dc']}}}creator",
        "Description": f"{{{_NS['dc']}}}description",
        "Copyright": f"{{{_NS['dc']}}}rights",
        "Date": f"{{{_NS['dcterms']}}}created",
    }

    def _transform(name: str, data: bytes) -> bytes:
        if name != _CORE:
            return data
        _register_office_namespaces()
        root = ET.fromstring(data)
        for field_name, value in fields.items():
            tag = targets[field_name]
            el = root.find(tag)
            text = date.strftime("%Y-%m-%dT%H:%M:%SZ") if field_name == "Date" and date else value
            if not text:
                if el is not None:
                    root.remove(el)
                continue
            if el is None:
                el = ET.SubElement(root, tag)
                if field_name == "Date":
                    el.set("{http://www.w3.org/2001/XMLSchema-instance}type", "dcterms:W3CDTF")
            el.text = text
        return ET.tostring(root, xml_declaration=True, encoding="UTF-8")

    try:
        with zipfile.ZipFile(path) as zf:
            if _CORE not in zf.namelist():
                return None
    except (zipfile.BadZipFile, OSError):
        return None
    return _rewrite_zip(path, _transform)
