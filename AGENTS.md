# AGENTS.md — EOM (Eye On Metadata)

PySide6 desktop app (and CLI) for viewing, exporting, cleaning and editing image, audio, video, PDF and Office metadata. End-user docs live in [README.md](README.md).

## Stack & Run

- **Python ≥3.10 + PySide6** (Qt for Python) + **Pillow** for image EXIF.
- **pypdf ≥5,<6** — PDF metadata extraction, removal and editing.
- **mutagen ≥1.47** — audio/video tags (MP3, FLAC, OGG, WAV, AIFF, M4A, WMA, MP4, MKV, WebM).
- **Optional:** `pillow-heif` (`pip install .[heif]`) — HEIC/HEIF in the Pillow fallback.
- QtPdf (PDF preview) and QtNetwork (opt-in map tiles / update check) come with PySide6.
- **Optional:** [`exiftool`](https://exiftool.org) CLI — install via system package manager
  (`sudo apt install libimage-exiftool-perl` / `brew install exiftool` / download from exiftool.org on Windows).
  When found in PATH, EOM uses it as the primary backend for deeper metadata (XMP, IPTC, MakerNotes, RAW).
  The UI header shows `ExifTool ✓` or `ExifTool ✗` to indicate availability.
  The `exiftool_backend.py` module handles detection and subprocess calls (always `shell=False`).
  On Windows, the pre-built binary ships with a bundled `exiftool.exe` inside the exe (downloaded during CI).
- Install runtime + dev deps:
  ```bash
  pip install -r requirements-dev.txt   # includes runtime + pytest + ruff + pyinstaller
  ```
- Run from the project root:
  ```bash
  python main.py
  ```
- A `.venv/` already exists in the repo root — activate it before running.

## Test / Lint / Build

- **Tests** (Qt runs headless via `QT_QPA_PLATFORM=offscreen`, set by `tests/conftest.py`):
  ```bash
  pytest                # runs tests/ with coverage config from pyproject.toml
  ```
  `tests/conftest.py` has an `autouse` fixture that patches `exiftool_backend._EXIFTOOL_PATH = None`
  for every test, so tests are isolated from whatever is installed locally. Tests that need ExifTool
  patch it explicitly with `patch.object(exiftool_backend, "_EXIFTOOL_PATH", "exiftool")`.
- **Lint / format** (ruff is configured in `pyproject.toml`; generated files excluded):
  ```bash
  ruff check .
  ruff format .
  ```
- **Standalone binary** (PyInstaller, single-file, windowed):
  ```bash
  pyinstaller eom.spec --noconfirm --clean   # → dist/eom (or dist/eom.exe)
  ```
  The spec conditionally bundles `exiftool.exe` if present in the repo root (place it there before
  building on Windows). On macOS, the CI step generates `images/app-logo.icns` from `app-logo.ico`
  using Pillow before invoking PyInstaller.
- **CI**: [.github/workflows/ci.yml](.github/workflows/ci.yml) runs ruff + pytest on Linux/Windows/macOS × Python 3.10–3.12.
- **Releases**: push a `v*` tag → [.github/workflows/release.yml](.github/workflows/release.yml) builds
  PyInstaller artifacts for 4 targets and attaches zips to a GitHub Release:
  - `eom-linux-x86_64` — built inside `python:3.10-focal` container (glibc 2.31 → Ubuntu 20.04+)
  - `eom-windows-x86_64` — built on `windows-2019`; CI downloads `exiftool_64.zip` and bundles it
  - `eom-macos-x86_64` — built on `macos-13` (Intel); runs on macOS 12+
  - `eom-macos-arm64` — built on `macos-14` (Apple Silicon); runs on macOS 14+

## Architecture

Hand-written source files:

- [main.py](main.py) — thin `MainWindow` shell + `main()` entry point. Wires window chrome signals
  (frameless: custom drag + min/max/close in `header_widget`), page navigation via `PageIndex` enum +
  `stackedWidget` (HOME, EXTRACT, REMOVE, REPORT, SETTINGS), drag & drop (`dropEvent` → `open_paths`),
  instantiates the controllers, adds the ExifTool status label and the opt-in update link.
  `main()` forwards to `cli.main()` when the first argument is a CLI command, otherwise starts the GUI
  (`[--extract|--remove] PATH...` pre-loads files). `_resource_path(rel)` resolves bundled files in
  dev and PyInstaller frozen modes.
- [Extractor.py](Extractor.py) — pure format-dispatch functions (no Qt):
  - `single_image_extractor(path)` — ExifTool first (when available), else `fallback_extractor`:
    Pillow (JPEG/PNG/TIFF/WebP/GIF/HEIC; IFD0 + Exif IFD + GPS IFD + PNG text + XMP), mutagen
    (audio/video), pypdf (PDF), zipfile (DOCX/XLSX/PPTX core/app props + Word revision authors).
    Adds `GoogleMapLink` when GPS is present; `gps_coordinates(data)` parses any backend's GPS.
  - `remove_image_metadata(path)` (wipe all) / `remove_metadata(path, profile=None, keys=None)`
    (selective). `write_metadata(path, fields)` edits `EDITABLE_FIELDS`; `shift_dates(path, delta)`.
  - `copy_to_output()` (never overwrites) and `diff_metadata(before, after)` for verification.
  - Every fallback writer goes through `_atomic_write` (temp file in the same dir + `os.replace`,
    preserving permissions).
- [formats.py](formats.py) — the only list of supported extensions, the file-dialog filter,
  `EXIFTOOL_WRITABLE_EXTENSIONS`, and `scan_directory(dir, recursive)`.
- [risk.py](risk.py) — tag → category (location, identity, identifiers, device, dates, software,
  thumbnail, copyright, technical, other) → severity; `assess(metadata)` → `RiskReport`.
- [profiles.py](profiles.py) — cleaning profiles = sets of risk categories; `keys_to_remove()`.
- [exporters.py](exporters.py) — TXT / JSON / CSV / HTML export of `{file: metadata}`.
- [cli.py](cli.py) — argparse CLI: `extract`, `risk`, `clean`, `edit`, `profiles` (no Qt widgets).
- [exiftool_backend.py](exiftool_backend.py) — optional ExifTool wrapper. Detects the binary via
  `_find_exiftool()` (checks `sys._MEIPASS` first for the bundled Windows exe, then `shutil.which`).
  `extract()` uses `-json -G1 -a -u`; `remove()` uses `-all= -overwrite_original`; `write()` /
  `remove_tags()` apply assignments with `-m`. `shell=False` throughout; 30 s subprocess timeout.
- [workers.py](workers.py) — `ExtractionWorker`, `RemovalWorker` (profile/keys, output dir,
  verification → `report_ready(str, dict)`), `EditWorker`. Common signals: `result_ready(str, object)`,
  `progress(int, int)`, `error(str)`, `finished_all()`.
- [controllers/common.py](controllers/common.py) — `FileSelection` (file/folder mode, Sub-folders
  checkbox, Recent menu, multi-file selections), export-path dialog, "modify originals?" confirmation.
- [controllers/extraction.py](controllers/extraction.py) — `ExtractionController`: Extract page (risk
  banner, filter, preview + map side panel, export from cached results, Edit dialog).
- [controllers/removal.py](controllers/removal.py) — `RemovalController`: Remove page (profile combo,
  custom selection, "Save copies to", before/after dialog, export-and-remove).
- [controllers/settings_page.py](controllers/settings_page.py) — `SettingsController`: Settings page.
- [widgets.py](widgets.py) — `PreviewWidget`, `MapWidget` (OSM tiles, no request without consent),
  `BeforeAfterDialog`, `EditDialog`, `CustomSelectionDialog`, risk label/colour helpers.
- [settings.py](settings.py) — typed `QSettings` wrapper (INI). Tests redirect it via `use_path()`.
- [theme.py](theme.py) — dark/light palettes; renders the [style.qss](style.qss) template.
- [i18n.py](i18n.py) — loads `translations/eom_<lang>.qm` + Qt's own translations.
- [integration.py](integration.py) — right-click menu install/uninstall (Linux file managers, Windows registry).
- [updater.py](updater.py) — opt-in GitHub release check.
- [version.py](version.py) — `__version__`, the single version string.

## Generated files — DO NOT edit by hand

- [app_ui.py](app_ui.py) — regenerate from [app.ui](app.ui) (Qt Designer) with:
  ```bash
  pyside6-uic app.ui -o app_ui.py
  ```
- [resources_rc.py](resources_rc.py) — ~130k lines, regenerate from [resources.qrc](resources.qrc) with:
  ```bash
  pyside6-rcc resources.qrc -o resources_rc.py
  ```
  Resources are referenced as Qt paths like `:/outline/icons/outline/maximize-2.svg`.
- `app - Copy.ui` is a stray duplicate; ignore it.
- [translations/eom_fr.qm](translations) — compiled from `eom_fr.ts`. After changing UI strings:
  ```bash
  pyside6-lupdate app.ui main.py widgets.py risk.py profiles.py controllers/*.py -ts translations/eom_fr.ts
  # translate the new entries (Qt Linguist: pyside6-linguist translations/eom_fr.ts), then:
  pyside6-lrelease translations/eom_fr.ts -qm translations/eom_fr.qm
  ```
  `tests/test_app_modules.py::test_translations_are_complete` fails while any entry is unfinished.

## Project conventions / pitfalls

- **Frameless window** (`Qt.FramelessWindowHint`): no OS title-bar controls. Window dragging uses
  `startSystemMove()` (Wayland + X11 + Windows + macOS). Falls back to manual delta when
  `windowHandle()` is `None` (e.g. offscreen in tests). Min/max/close are custom buttons in
  `ui.header_widget` — preserve that wiring when refactoring `main.py`.
- **Handler naming**: `on_<widget>_<signal>` (e.g. `on_extract_btn_clicked`). Follow this when adding handlers.
- **File naming is inconsistent** (`Extractor.py` capitalized, `main.py` / `app_ui.py` lowercase). Match the existing case of the file you touch rather than renaming.
- **ExifTool dispatch is first for reading**: `single_image_extractor` uses ExifTool whenever it is
  available. **Writing** (remove/edit/shift) uses ExifTool only for `formats.EXIFTOOL_WRITABLE_EXTENSIONS`;
  MP3/FLAC/OGG/Office go through mutagen/zipfile, and **PDF always goes through pypdf** — ExifTool PDF
  edits are incremental updates that leave the old metadata recoverable in the file.
- **Keys differ per backend**: ExifTool returns `Group:Tag` (`IFD0:Artist`), the fallbacks bare names
  (`Artist`). `remove_metadata` strips the group before calling a Python backend; `risk` handles both.
- **`style.qss` is a template**: colours are `@token`s substituted by `theme.py`. Don't load it with
  `app.setStyleSheet` directly, and don't hard-code colours in Python — add an objectName + QSS rule
  (or use `theme.color(token)` when painting by hand).
- **Translatable strings**: use `self.tr("literal")` in QObject subclasses, or
  `QCoreApplication.translate("Context", "literal")` elsewhere — lupdate only extracts literals.
  Dynamic values are inserted with `.replace("%1", value)` after translation. Category/profile labels
  are marked with `QT_TRANSLATE_NOOP` in `risk.py` / `profiles.py` (which must stay Qt-free for the CLI).
- **Privacy**: no network request without consent. Map tiles and update checks are opt-in settings.
- **`app_ui.py` sets a stock-photo window icon** — `main.py` overrides it after `setupUi` using
  `_resource_path("images/app-logo.ico")`. Do not "fix" the generated file.
- `on_menu_docs_btn_toggled` currently routes to stacked index `0` (same as home) — known quirk, confirm intent before "fixing".
- **Extractor returns `None`/falsy on unsupported formats** — controllers and workers depend on this contract. [tests/test_extractor.py](tests/test_extractor.py) asserts it.
- Manual smoke test on top of `pytest` = run `python main.py`, drop a sample JPEG, MP3, PDF and DOCX,
  check the risk banner, clean with the *Social media sharing* profile into a copies folder, and
  double-click the result to review before/after. Also try `python main.py risk <file>`.
