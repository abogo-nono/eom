"""The workspace session: the files the user added and what EOM knows about them.

Pure data + Qt signals, no widgets — the workspace view observes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, Signal

import formats
import profiles
import risk

PENDING, READY, CLEANED, FAILED = "pending", "ready", "cleaned", "failed"


@dataclass
class FileEntry:
    path: str  # absolute
    rel: str  # name used for output copies (keeps the dropped folder's structure)
    metadata: dict | None = None
    state: str = PENDING
    report: dict | None = None  # last clean report (before/after/diff)
    custom_keys: set[str] | None = None  # per-file hand-picked tags (Custom profile)

    @property
    def name(self) -> str:
        return Path(self.path).name

    @property
    def folder(self) -> str:
        return str(Path(self.path).parent)

    @property
    def risk(self) -> risk.RiskReport:
        return risk.assess(self.metadata)

    @property
    def embedded_keys(self) -> list[str]:
        """Metadata keys that are actually embedded in the file (not file-system properties)."""
        return [k for k in (self.metadata or {}) if not risk.is_file_property(k) and k != "GoogleMapLink"]


@dataclass
class CleaningPlan:
    """What the action bar will do: profile id, custom categories, output folder."""

    profile_id: str = profiles.DEFAULT_PROFILE
    custom_categories: frozenset[str] = field(default_factory=frozenset)
    output_dir: str | None = None

    def for_entry(self, entry: FileEntry) -> tuple[profiles.Profile | None, list[str] | None]:
        """``(profile, keys)`` to pass to :func:`Extractor.remove_metadata` for *entry*."""
        if self.profile_id != "custom":
            return profiles.get(self.profile_id), None
        if entry.custom_keys is not None:
            return None, sorted(entry.custom_keys)
        return profiles.custom(set(self.custom_categories)), None

    def keys_removed(self, entry: FileEntry) -> set[str]:
        """Keys of *entry* that cleaning would remove (for the live preview)."""
        profile, keys = self.for_entry(entry)
        if keys is not None:
            return set(keys)
        if profile is None:
            return set()
        if profile.remove_all:
            return set(entry.embedded_keys)
        return set(profiles.keys_to_remove(entry.metadata, profile))


def expand(paths: list[str], recursive: bool) -> list[tuple[str, str]]:
    """Turn dropped/selected paths into ``(absolute_path, rel)`` file pairs.

    A folder contributes its supported files with ``rel = "<folder>/<sub path>"``
    so cleaned copies mirror the structure; a single file uses its own name.
    """
    out: list[tuple[str, str]] = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            for rel in formats.scan_directory(p, recursive):
                out.append((str(p / rel), f"{p.name}/{rel}"))
        elif p.is_file() and formats.is_supported(p):
            out.append((str(p), p.name))
    return out


class Session(QObject):
    """Ordered collection of :class:`FileEntry`, keyed by absolute path.

    Signals
    -------
    added(list[str])     new paths were added (metadata still pending)
    updated(str)         an entry changed (metadata read, cleaned…)
    removed(list[str])   entries were removed from the list
    """

    added = Signal(list)
    updated = Signal(str)
    removed = Signal(list)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: dict[str, FileEntry] = {}

    # -- access -------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, path: str) -> bool:
        return path in self._entries

    def get(self, path: str) -> FileEntry | None:
        return self._entries.get(path)

    def entries(self) -> list[FileEntry]:
        return list(self._entries.values())

    def paths(self) -> list[str]:
        return list(self._entries)

    # -- mutation -----------------------------------------------------------

    def add(self, pairs: list[tuple[str, str]]) -> list[str]:
        """Add ``(path, rel)`` pairs; already-present paths are skipped. Returns the new paths."""
        new = []
        for path, rel in pairs:
            if path not in self._entries:
                self._entries[path] = FileEntry(path, rel)
                new.append(path)
        if new:
            self.added.emit(new)
        return new

    def set_metadata(self, path: str, metadata: dict | None) -> None:
        entry = self._entries.get(path)
        if entry is None:
            return
        entry.metadata = metadata
        if entry.state == PENDING:
            entry.state = READY
        self.updated.emit(path)

    def set_report(self, path: str, report: dict) -> None:
        entry = self._entries.get(path)
        if entry is None:
            return
        entry.report = report
        entry.state = CLEANED if report.get("status") else FAILED
        # Show the file's *current* metadata: after an in-place clean that is the
        # "after" read; with copies, the original is unchanged.
        if report.get("status") and report.get("target") == path and report.get("after") is not None:
            entry.metadata = report["after"]
        elif report.get("status") and report.get("target") == path:
            entry.metadata = None
        entry.custom_keys = None
        self.updated.emit(path)

    def remove(self, paths: list[str]) -> None:
        gone = [p for p in paths if self._entries.pop(p, None) is not None]
        if gone:
            self.removed.emit(gone)

    def clear(self) -> None:
        self.remove(self.paths())

    # -- summaries ----------------------------------------------------------

    def risk_counts(self) -> dict[risk.Severity, int]:
        counts = {level: 0 for level in risk.Severity}
        for entry in self._entries.values():
            if entry.state != PENDING:
                counts[entry.risk.level] += 1
        return counts

    def pending(self) -> int:
        return sum(1 for e in self._entries.values() if e.state == PENDING)
