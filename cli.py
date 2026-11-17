"""Command-line interface for EOM.

Usage examples::

    eom extract photo.jpg --format json
    eom extract ~/Pictures -r --format html -o report.html
    eom risk ~/Pictures -r
    eom clean ~/Pictures -r --profile social --output-dir ~/clean
    eom clean doc.pdf --categories location,identity
    eom edit photo.jpg --author "Jane" --copyright "CC-BY" --shift +2h
    eom profiles

``main.py`` forwards to :func:`main` whenever the first argument is one of
:data:`COMMANDS`, so the same binary serves both GUI and CLI.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import timedelta
from pathlib import Path

import exiftool_backend
import exporters
import Extractor
import formats
import profiles
import risk
from version import __version__

COMMANDS = ("extract", "risk", "clean", "edit", "profiles")

_SHIFT_RE = re.compile(r"^([+-])?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")


def parse_shift(text: str) -> timedelta:
    """Parse ``+1d2h30m``, ``-3h``, ``90m``… into a timedelta."""
    match = _SHIFT_RE.match(text.strip().replace(" ", ""))
    if not match or not any(match.groups()[1:]):
        raise argparse.ArgumentTypeError(f"invalid shift '{text}' (examples: +2h, -1d, +1d2h30m)")
    sign, d, h, m, s = match.groups()
    delta = timedelta(days=int(d or 0), hours=int(h or 0), minutes=int(m or 0), seconds=int(s or 0))
    return -delta if sign == "-" else delta


def _collect(path: str, recursive: bool) -> tuple[str, bool, dict]:
    """Return ``(base, is_batch, images)`` for a file or directory argument."""
    p = Path(path).expanduser()
    if p.is_dir():
        return str(p), True, formats.scan_directory(p, recursive)
    if p.is_file():
        return str(p), False, {}
    raise SystemExit(f"eom: no such file or directory: {path}")


def _targets(base: str, is_batch: bool, images: dict):
    if not is_batch:
        yield base, base, Path(base).name
        return
    for name, rel in images.items():
        safe = Extractor._safe_join(base, rel)
        if safe is not None:
            yield name, str(safe), rel


def _extract_all(args) -> dict[str, dict | None]:
    results: dict[str, dict | None] = {}
    for target in args.paths:
        base, is_batch, images = _collect(target, args.recursive)
        for name, path, _rel in _targets(base, is_batch, images):
            label = str(Path(base) / name) if is_batch else name
            results[label] = Extractor.single_image_extractor(path)
    return results


def cmd_extract(args) -> int:
    results = _extract_all(args)
    fmt = args.format or (exporters.format_for_path(args.output) if args.output else "txt")
    if args.output:
        exporters.export(results, args.output, fmt)
        print(f"Saved {len(results)} file(s) to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(exporters.render(results, fmt))
    return 0


def cmd_risk(args) -> int:
    results = _extract_all(args)
    worst = risk.Severity.NONE
    for name, data in results.items():
        report = risk.assess(data)
        worst = max(worst, report.level)
        print(f"{report.label:<7} {name}")
        if args.verbose:
            for category, keys in report.findings.items():
                print(f"          {risk.CATEGORIES[category]}: {', '.join(keys)}")
    # Exit status lets scripts/CI fail on sensitive metadata: 0 clean/low, 1 medium, 2 high.
    return {risk.Severity.HIGH: 2, risk.Severity.MEDIUM: 1}.get(worst, 0)


def _resolve_profile(args) -> profiles.Profile:
    if args.categories:
        cats = {c.strip() for c in args.categories.split(",") if c.strip()}
        try:
            return profiles.custom(cats)
        except ValueError as exc:
            raise SystemExit(f"eom: {exc}. Valid: {', '.join(risk.CATEGORIES)}") from None
    try:
        return profiles.get(args.profile)
    except ValueError as exc:
        raise SystemExit(f"eom: {exc}") from None


def cmd_clean(args) -> int:
    profile = _resolve_profile(args)
    failures = 0
    for target in args.paths:
        base, is_batch, images = _collect(target, args.recursive)
        for name, path, rel in _targets(base, is_batch, images):
            before = Extractor.single_image_extractor(path)
            if args.dry_run:
                keys = (
                    [k for k in (before or {}) if not risk.is_file_property(k)]
                    if profile.remove_all
                    else profiles.keys_to_remove(before, profile)
                )
                print(f"would remove {len(keys):>3} tag(s)  {name}")
                for key in keys if args.verbose else []:
                    print(f"      {key}")
                continue
            dest = Extractor.copy_to_output(path, args.output_dir, rel) if args.output_dir else path
            status = Extractor.remove_metadata(dest, profile)
            if not status:
                failures += 1
                print(f"FAILED   {name}")
                continue
            diff = Extractor.diff_metadata(before, Extractor.single_image_extractor(dest))
            residual = risk.assess({k: "" for k in diff["remaining"]})
            print(f"cleaned  {name}  (-{len(diff['removed'])} tags, remaining risk: {residual.label})")
            if args.output_dir:
                print(f"         -> {dest}")
    return 1 if failures else 0


def cmd_edit(args) -> int:
    fields = {
        name: value
        for name, value in (
            ("Title", args.title),
            ("Author", args.author),
            ("Copyright", args.copyright),
            ("Description", args.description),
            ("Date", args.date),
        )
        if value is not None
    }
    if not fields and not args.shift:
        raise SystemExit("eom edit: nothing to do (give --title/--author/--copyright/--description/--date/--shift)")
    failures = 0
    for target in args.paths:
        base, is_batch, images = _collect(target, args.recursive)
        for name, path, rel in _targets(base, is_batch, images):
            dest = Extractor.copy_to_output(path, args.output_dir, rel) if args.output_dir else path
            try:
                status = Extractor.write_metadata(dest, fields) if fields else True
            except ValueError as exc:
                raise SystemExit(f"eom edit: {exc}") from None
            reason = "" if status else " (could not write fields)"
            if status and args.shift:
                status = Extractor.shift_dates(dest, args.shift)
                reason = "" if status else " (date shift not supported for this format)"
            print(f"{'edited ' if status else 'FAILED '} {name}{reason}")
            failures += 0 if status else 1
    return 1 if failures else 0


def cmd_profiles(_args) -> int:
    for profile in profiles.PROFILES.values():
        print(f"{profile.id:<15} {profile.name} — {profile.description}")
    print("\nCategories for --categories:")
    for cat, label in risk.CATEGORIES.items():
        print(f"  {cat:<12} {label}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eom", description="Eye On Metadata — view, export, clean and edit metadata.")
    parser.add_argument("--version", action="version", version=f"eom {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def _paths(p):
        p.add_argument("paths", nargs="+", metavar="PATH", help="file(s) or folder(s)")
        p.add_argument("-r", "--recursive", action="store_true", help="include sub-folders")

    p = sub.add_parser("extract", help="print or export metadata")
    _paths(p)
    p.add_argument("-f", "--format", choices=list(exporters.FORMATS), help="output format (default: txt)")
    p.add_argument("-o", "--output", help="write to this file instead of stdout")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("risk", help="show the privacy risk of each file (exit 2 = high, 1 = medium)")
    _paths(p)
    p.add_argument("-v", "--verbose", action="store_true", help="list the sensitive tags")
    p.set_defaults(func=cmd_risk)

    p = sub.add_parser("clean", help="remove metadata")
    _paths(p)
    p.add_argument("-p", "--profile", default=profiles.DEFAULT_PROFILE, choices=list(profiles.PROFILES))
    p.add_argument("-c", "--categories", help="comma-separated categories to remove (overrides --profile)")
    p.add_argument("-O", "--output-dir", help="write cleaned copies here instead of modifying originals")
    p.add_argument("-n", "--dry-run", action="store_true", help="show what would be removed")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("edit", help="set fields or shift dates")
    _paths(p)
    p.add_argument("--title")
    p.add_argument("--author")
    p.add_argument("--copyright")
    p.add_argument("--description")
    p.add_argument("--date", help="YYYY-MM-DD HH:MM:SS (sets every date)")
    p.add_argument("--shift", type=parse_shift, help="shift all dates, e.g. +2h, -1d, +1d2h30m")
    p.add_argument("-O", "--output-dir", help="write edited copies here instead of modifying originals")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("profiles", help="list cleaning profiles and categories")
    p.set_defaults(func=cmd_profiles)
    return parser


def _ensure_console() -> None:
    """A windowed PyInstaller build on Windows has no stdout; attach the parent console."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    if sys.platform == "win32":  # pragma: no cover - Windows only
        import ctypes

        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
            sys.stderr = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
            return
    import io as _io

    sys.stdout = sys.stdout or _io.StringIO()
    sys.stderr = sys.stderr or _io.StringIO()


def main(argv: list[str] | None = None) -> int:
    _ensure_console()
    args = build_parser().parse_args(argv)
    if not exiftool_backend.is_available() and args.command != "profiles":
        print("note: ExifTool not found — using built-in backends.", file=sys.stderr)
    try:
        return args.func(args)
    except BrokenPipeError:  # e.g. `eom extract … | head`
        return 0


if __name__ == "__main__":
    sys.exit(main())
