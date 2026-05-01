# AGENTS.md — EOM (Eye On Metadata)

PySide6 desktop app for viewing/exporting/removing image, audio, video, and PDF metadata. End-user docs live in [README.md](README.md).

## Stack & Run

- **Python ≥3.10 + PySide6** (Qt for Python) + **Pillow** for image EXIF.
- **pypdf ≥4,<6** — PDF metadata extraction and removal.
- **mutagen ≥1.47** — audio/video tags (MP3, FLAC, OGG, WAV, AIFF, M4A, WMA, MP4, MKV, WebM).
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
- Run from the project root (paths to `style.qss` are relative):
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

- [main.py](main.py) — thin `MainWindow` shell. Wires window chrome signals (frameless: custom drag +
  min/max/close in `header_widget`), page navigation via `PageIndex` enum + `stackedWidget`,
  instantiates the two feature controllers, and adds the ExifTool status label to the header.
  Contains `_resource_path(rel)` helper that resolves `images/app-logo.ico` in both dev and
  PyInstaller frozen modes.
- [Extractor.py](Extractor.py) — pure format-dispatch functions:
  - `single_image_extractor(path)` / `multi_image_extractor(dir, images)` — dispatches to
    `exiftool_backend` first (when available), then Pillow (JPEG/PNG/TIFF), mutagen (audio/video),
    or pypdf (PDF). Adds `GoogleMapLink` when GPS data is present.
  - `remove_image_metadata(path)` / `multi_remove_image_metadata(...)` — same dispatch order.
    Fallback backends use atomic write (temp file + `os.replace`) to avoid corruption on interrupt.
- [exiftool_backend.py](exiftool_backend.py) — optional ExifTool wrapper. Detects the binary via
  `_find_exiftool()` (checks `sys._MEIPASS` first for the bundled Windows exe, then `shutil.which`).
  `extract()` uses `-json -G1 -a -u`; `remove()` uses `-all= -overwrite_original`. `shell=False`
  throughout; 30 s subprocess timeout.
- [workers.py](workers.py) — `ExtractionWorker` + `RemovalWorker` QThread subclasses. Signals:
  `result_ready(str, object)`, `progress(int, int)`, `error(str)`, `finished_all()`.
- [controllers/extraction.py](controllers/extraction.py) — `ExtractionController`: owns the Extract
  page signals, starts `ExtractionWorker`, handles results and export.
- [controllers/removal.py](controllers/removal.py) — `RemovalController`: owns the Remove page signals,
  starts `RemovalWorker`, handles results.
- [style.qss](style.qss) — Qt stylesheet loaded in `main.py`'s `__main__` block.

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

## Project conventions / pitfalls

- **Frameless window** (`Qt.FramelessWindowHint`): no OS title-bar controls. Window dragging uses
  `startSystemMove()` (Wayland + X11 + Windows + macOS). Falls back to manual delta when
  `windowHandle()` is `None` (e.g. offscreen in tests). Min/max/close are custom buttons in
  `ui.header_widget` — preserve that wiring when refactoring `main.py`.
- **Handler naming**: `on_<widget>_<signal>` (e.g. `on_extract_btn_clicked`). Follow this when adding handlers.
- **File naming is inconsistent** (`Extractor.py` capitalized, `main.py` / `app_ui.py` lowercase). Match the existing case of the file you touch rather than renaming.
- **ExifTool dispatch is first**: `single_image_extractor` and `remove_image_metadata` call
  `exiftool_backend.is_available()` before any format check. If ExifTool handles it, the Pillow/
  mutagen/pypdf paths are skipped entirely.
- **`app_ui.py` sets a stock-photo window icon** — `main.py` overrides it after `setupUi` using
  `_resource_path("images/app-logo.ico")`. Do not "fix" the generated file.
- `on_menu_docs_btn_toggled` currently routes to stacked index `0` (same as home) — known quirk, confirm intent before "fixing".
- **Extractor returns `None`/falsy on unsupported formats** — controllers and workers depend on this contract. [tests/test_extractor.py](tests/test_extractor.py) asserts it.
- Manual smoke test on top of `pytest` = run `python main.py` and exercise Extract / Remove on a sample JPEG, MP3, and PDF.
