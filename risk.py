"""Privacy-risk classification of metadata tags.

Every tag name produced by any backend (ExifTool ``Group:Tag`` keys, Pillow
EXIF names, pypdf ``Author``, mutagen ``Artist``, Office ``creator``…) is mapped
to a *category* and a *severity*.  The categories are also what cleaning
profiles operate on (see :mod:`profiles`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum


def QT_TRANSLATE_NOOP(context: str, text: str) -> str:  # noqa: N802 — name recognised by pyside6-lupdate
    """Mark *text* for translation without importing Qt (the CLI stays Qt-free)."""
    return text


class Severity(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3


# Category ids — stable strings, used by profiles, the CLI and QSettings.
LOCATION = "location"
IDENTITY = "identity"
DEVICE = "device"
DATES = "dates"
SOFTWARE = "software"
THUMBNAIL = "thumbnail"
IDENTIFIERS = "identifiers"
COPYRIGHT = "copyright"
TECHNICAL = "technical"
OTHER = "other"

CATEGORIES: dict[str, str] = {
    LOCATION: QT_TRANSLATE_NOOP("risk", "Location (GPS)"),
    IDENTITY: QT_TRANSLATE_NOOP("risk", "Author / owner"),
    DEVICE: QT_TRANSLATE_NOOP("risk", "Camera / device"),
    DATES: QT_TRANSLATE_NOOP("risk", "Dates & times"),
    SOFTWARE: QT_TRANSLATE_NOOP("risk", "Software / editing history"),
    THUMBNAIL: QT_TRANSLATE_NOOP("risk", "Embedded thumbnails"),
    IDENTIFIERS: QT_TRANSLATE_NOOP("risk", "Unique IDs / serials"),
    COPYRIGHT: QT_TRANSLATE_NOOP("risk", "Copyright & licence"),
    TECHNICAL: QT_TRANSLATE_NOOP("risk", "Technical (size, colour, codec)"),
    OTHER: QT_TRANSLATE_NOOP("risk", "Other"),
}

CATEGORY_SEVERITY: dict[str, Severity] = {
    LOCATION: Severity.HIGH,
    IDENTITY: Severity.HIGH,
    IDENTIFIERS: Severity.HIGH,
    DEVICE: Severity.MEDIUM,
    DATES: Severity.MEDIUM,
    SOFTWARE: Severity.MEDIUM,
    THUMBNAIL: Severity.MEDIUM,
    COPYRIGHT: Severity.LOW,
    TECHNICAL: Severity.NONE,
    OTHER: Severity.LOW,
}

# ExifTool groups that describe the file on disk, not embedded metadata.
# They never count towards the risk score and can't be removed.
NON_METADATA_GROUPS = {"System", "File", "ExifTool", "Composite", "ZIP"}

# Ordered: first match wins.  Patterns are matched case-insensitively against
# the tag name *without* its ExifTool group prefix.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        LOCATION,
        re.compile(
            r"gps|latitude|longitude|altitude|location|city|country|province|state$|sublocation|googlemaplink|geotag"
        ),
    ),
    (
        IDENTIFIERS,
        re.compile(
            r"serial|uniqueid|imageuniqueid|documentid|instanceid|originaldocumentid|internalserial|bodyserial|lensserial|uuid|guid|ownerid"
        ),
    ),
    (THUMBNAIL, re.compile(r"thumbnail|previewimage|jpgfromraw|otherimage")),
    (COPYRIGHT, re.compile(r"copyright|rights|licen[cs]e|usageterms|webstatement")),
    (
        IDENTITY,
        re.compile(
            r"artist|author|creator(?!tool)|by-?line|owner|lastmodifiedby|company|manager|publisher|contact|email|e-mail|phone|address|username|user$|hostname|computer|writer|captionwriter|credit|personinimage|albumartist|composer|performer|encodedby|^xmp$"
        ),
    ),
    (DEVICE, re.compile(r"^make$|model|lens|camera|device|firmware|manufacturer|hardware|androidversion")),
    (DATES, re.compile(r"date|(?<!exposure)time(?!zone)|year$|created|modified|offsettime")),
    (
        SOFTWARE,
        re.compile(
            r"software|creatortool|producer|application|appversion|history|tool|encoder|encodingsettings|template|revision|totaltime|processingsoftware|hostcomputer"
        ),
    ),
    (
        TECHNICAL,
        re.compile(
            r"width|height|resolution|bits|color|colour|compression|orientation|samplerate|bitrate|channels|duration|codec|format|version|profile|exposure|fnumber|aperture|iso|focal|flash|whitebalance|metering|shutter|brightness|contrast|saturation|sharpness|scene|gain|ycbcr|components|page|linearized|encoding|layout|pixel|planar|gamma|chromaticit|interop|primar|matrix|transfer|byteorder|megapixels|imagesize|lightsource|sensing|digitalzoom|subjectdistance"
        ),
    ),
]


def split_key(key: str) -> tuple[str | None, str]:
    """Split an ExifTool ``Group:Tag`` key; plain keys return ``(None, key)``."""
    if ":" in key:
        group, _, name = key.partition(":")
        if group and name and " " not in group:
            return group, name
    return None, key


def is_file_property(key: str) -> bool:
    """True for ExifTool keys that describe the file itself (size, path…)."""
    group, _ = split_key(key)
    return group in NON_METADATA_GROUPS


def categorize(key: str) -> str:
    group, name = split_key(key)
    if group == "GPS":
        return LOCATION
    if group and group.startswith("ICC"):
        return TECHNICAL
    lowered = name.lower()
    for category, pattern in _RULES:
        if pattern.search(lowered):
            return category
    return OTHER


def severity_of(key: str) -> Severity:
    if is_file_property(key):
        # Composite GPS values still reveal a location even though they are derived.
        group, name = split_key(key)
        if group == "Composite" and categorize(name) == LOCATION:
            return Severity.HIGH
        return Severity.NONE
    return CATEGORY_SEVERITY[categorize(key)]


@dataclass
class RiskReport:
    level: Severity = Severity.NONE
    findings: dict[str, list[str]] = field(default_factory=dict)  # category -> keys

    @property
    def label(self) -> str:
        return {
            Severity.NONE: "Clean",
            Severity.LOW: "Low",
            Severity.MEDIUM: "Medium",
            Severity.HIGH: "High",
        }[self.level]

    def summary(self) -> str:
        """Short human summary, e.g. ``High — Location (GPS), Author / owner``."""
        sensitive = [
            CATEGORIES[cat]
            for cat in sorted(self.findings, key=lambda c: -CATEGORY_SEVERITY[c])
            if CATEGORY_SEVERITY[cat] >= Severity.MEDIUM
        ]
        if not sensitive:
            return self.label
        return f"{self.label} — {', '.join(sensitive)}"


def assess(metadata: dict | None) -> RiskReport:
    """Compute the risk report for one file's metadata dict."""
    report = RiskReport()
    if not metadata:
        return report
    for key in metadata:
        sev = severity_of(key)
        if sev == Severity.NONE:
            continue
        cat = LOCATION if split_key(key)[0] == "Composite" else categorize(key)
        report.findings.setdefault(cat, []).append(key)
        report.level = max(report.level, sev)
    return report
