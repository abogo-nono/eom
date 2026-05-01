from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from mutagen import File as MutagenFile
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS
from pypdf import PdfReader, PdfWriter

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Image formats handled via Pillow EXIF API.
_IMAGE_FORMATS = ("JPEG", "JPG", "PNG", "TIFF", "TIF")
# PDF is handled separately via pypdf.
_PDF_EXTENSIONS = {".pdf"}
# Audio/video formats handled via mutagen.
_AUDIO_EXTENSIONS = {
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
_VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mkv", ".webm"}
_AUDIO_VIDEO_EXTENSIONS = _AUDIO_EXTENSIONS | _VIDEO_EXTENSIONS


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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def single_image_extractor(image_path: str) -> dict | None:
    """Extract metadata from a single image, audio, video, or PDF.

    :param image_path: absolute path to the file
    :return: dict of tag->value (includes GoogleMapLink when GPS present),
             or None when the format is unsupported or metadata is absent.
    """
    suffix = Path(image_path).suffix.lower()
    if suffix in _PDF_EXTENSIONS:
        return pdf_extractor(image_path)
    if suffix in _AUDIO_VIDEO_EXTENSIONS:
        return audio_video_extractor(image_path)

    try:
        image = Image.open(image_path)
    except OSError:
        return None

    if image.format not in _IMAGE_FORMATS:
        return None

    exif = image.getexif()  # public Pillow API (>=9.2); never returns None
    if not exif:
        return None

    extracted_data: dict = {}
    gps_coords: dict = {}

    for tag, value in exif.items():
        tag_name = TAGS.get(tag)
        if not tag_name:
            continue

        extracted_data[tag_name] = value

        if tag_name == "GPSInfo":
            for key, val in value.items():
                gps_tag = GPSTAGS.get(key)
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
        extracted_data["GPSInfo"] = list(gps_coords.values())

    return extracted_data


def multi_image_extractor(path: str, images: dict) -> dict:
    """Extract metadata from multiple images in a directory.

    :param path:   directory containing the images
    :param images: mapping of {name: filename}
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


def remove_image_metadata(file: str) -> bool | None:
    """Strip metadata from an image, audio, video, or PDF file in place.

    Uses an atomic write (temp file + os.replace) so the original is never
    corrupted if the process is interrupted mid-write.

    :return: True on success, None on unsupported format or I/O error.
    """
    suffix = Path(file).suffix.lower()
    if suffix in _PDF_EXTENSIONS:
        return remove_pdf_metadata(file)
    if suffix in _AUDIO_VIDEO_EXTENSIONS:
        return remove_audio_video_metadata(file)

    try:
        image = Image.open(file)
    except OSError:
        return None

    if image.format not in _IMAGE_FORMATS:
        return None

    # Determine save format — preserve original type so PNG stays PNG etc.
    save_format = image.format if image.format in _IMAGE_FORMATS else "JPEG"

    # Copy pixel data without EXIF (paste copies pixels only, not metadata).
    img_no_exif = Image.new(image.mode, image.size)
    img_no_exif.paste(image)

    file_path = Path(file)
    tmp_name: str | None = None
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp")
        os.close(tmp_fd)
        img_no_exif.save(tmp_name, format=save_format)
        os.replace(tmp_name, file)
    except OSError:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        return None

    return True


def multi_remove_image_metadata(path: str, images: dict) -> dict:
    """Remove metadata from multiple images in a directory.

    :param path:   directory containing the images
    :param images: mapping of {name: filename}
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
    except Exception:  # noqa: BLE001  — pypdf can raise various exceptions
        return None

    if not meta:
        return None

    return {k.lstrip("/"): str(v) for k, v in meta.items() if v}


def remove_pdf_metadata(pdf_path: str) -> bool | None:
    """Remove all document metadata from a PDF file in place.

    Uses an atomic write so the original is never corrupted on error.

    :return: True on success, None on error.
    """
    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        # PdfWriter starts with empty metadata by default — no explicit clear needed.

        file_path = Path(pdf_path)
        tmp_fd, tmp_name = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp")
        try:
            os.close(tmp_fd)
            with open(tmp_name, "wb") as f:
                writer.write(f)
            os.replace(tmp_name, pdf_path)
        except OSError:
            Path(tmp_name).unlink(missing_ok=True)
            return None
    except Exception:  # noqa: BLE001
        return None

    return True


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


def remove_audio_video_metadata(path: str) -> bool | None:
    """Strip all tags from an audio or video file in place.

    Copies the file to a temp location, strips tags there, then atomically
    replaces the original — so the original is never corrupted on error.

    :return: True on success, None on unsupported format or I/O error.
    """
    try:
        f = MutagenFile(path, easy=True)
    except Exception:  # noqa: BLE001
        return None

    if f is None:
        return None

    file_path = Path(path)
    tmp_name: str | None = None
    try:
        tmp_fd, tmp_name = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp")
        os.close(tmp_fd)
        shutil.copy2(path, tmp_name)
        tmp_f = MutagenFile(tmp_name, easy=True)
        if tmp_f is not None:
            tmp_f.delete()
            tmp_f.save()
        os.replace(tmp_name, path)
    except Exception:  # noqa: BLE001
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)
        return None

    return True
