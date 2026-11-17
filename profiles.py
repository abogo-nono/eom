"""Cleaning profiles: which metadata categories to strip.

A profile is a set of :mod:`risk` categories to remove.  ``remove_all`` means
"wipe everything the backend can wipe" (the historical EOM behaviour).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import risk
from risk import QT_TRANSLATE_NOOP


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    description: str
    remove: frozenset[str] = field(default_factory=frozenset)
    remove_all: bool = False

    def removes(self, category: str) -> bool:
        return self.remove_all or category in self.remove


_ALL_BUT = lambda *keep: frozenset(set(risk.CATEGORIES) - set(keep))  # noqa: E731

PROFILES: dict[str, Profile] = {
    p.id: p
    for p in (
        Profile(
            "all",
            QT_TRANSLATE_NOOP("profiles", "Remove everything"),
            QT_TRANSLATE_NOOP(
                "profiles", "Wipe every writable metadata tag, including orientation and colour profile."
            ),
            remove_all=True,
        ),
        Profile(
            "anonymous",
            QT_TRANSLATE_NOOP("profiles", "Full anonymity"),
            QT_TRANSLATE_NOOP("profiles", "Remove everything that is not needed to display the file correctly."),
            remove=_ALL_BUT(risk.TECHNICAL),
        ),
        Profile(
            "social",
            QT_TRANSLATE_NOOP("profiles", "Social media sharing"),
            QT_TRANSLATE_NOOP(
                "profiles", "Remove location, author, device, serial numbers and thumbnails. Keep dates and copyright."
            ),
            remove=frozenset({risk.LOCATION, risk.IDENTITY, risk.IDENTIFIERS, risk.DEVICE, risk.THUMBNAIL}),
        ),
        Profile(
            "keep_copyright",
            QT_TRANSLATE_NOOP("profiles", "Keep copyright"),
            QT_TRANSLATE_NOOP("profiles", "Remove everything except copyright/licence and technical tags."),
            remove=_ALL_BUT(risk.COPYRIGHT, risk.TECHNICAL),
        ),
        Profile(
            "location",
            QT_TRANSLATE_NOOP("profiles", "Location only"),
            QT_TRANSLATE_NOOP("profiles", "Remove GPS coordinates and place names, keep everything else."),
            remove=frozenset({risk.LOCATION}),
        ),
    )
}

DEFAULT_PROFILE = "all"


def custom(categories: set[str] | frozenset[str]) -> Profile:
    unknown = set(categories) - set(risk.CATEGORIES)
    if unknown:
        raise ValueError(f"Unknown categories: {', '.join(sorted(unknown))}")
    return Profile("custom", "Custom", "User-selected categories.", remove=frozenset(categories))


def get(profile_id: str) -> Profile:
    try:
        return PROFILES[profile_id]
    except KeyError:
        raise ValueError(f"Unknown profile '{profile_id}'. Choose from: {', '.join(PROFILES)}") from None


def keys_to_remove(metadata: dict | None, profile: Profile) -> list[str]:
    """Return the keys of *metadata* that *profile* would strip."""
    if not metadata:
        return []
    return [
        key
        for key in metadata
        if not risk.is_file_property(key) and profile.removes(risk.categorize(key)) and key != "GoogleMapLink"
    ]
