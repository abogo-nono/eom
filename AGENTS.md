# AGENTS.md — EOM (Eye On Metadata)

PySide6 desktop app for viewing/exporting/removing image metadata. End-user docs live in [README.md](README.md).

## Stack & Run

- **Python ≥3.10 + PySide6** (Qt for Python) + **Pillow** for EXIF.
- **Optional:** [`exiftool`](https://exiftool.org) CLI — install via system package manager
  (`sudo apt install libimage-exiftool-perl` / `brew install exiftool` / download from exiftool.org on Windows).
  When found in PATH, EOM uses it as the primary backend for deeper metadata (XMP, IPTC, MakerNotes, RAW).
  The UI header shows `ExifTool ✓` or `ExifTool ✗` to indicate availability.
  The `exiftool_backend.py` module handles detection and subprocess calls (always `shell=False`).
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
- **Lint / format** (ruff is configured in `pyproject.toml`; generated files excluded):
  ```bash
  ruff check .
  ruff format .
  ```
- **Standalone binary** (PyInstaller, single-file, windowed):
  ```bash
  pyinstaller eom.spec --noconfirm --clean   # → dist/eom (or dist/eom.exe)
  ```
- **CI**: [.github/workflows/ci.yml](.github/workflows/ci.yml) runs ruff + pytest on Linux/Windows/macOS × Python 3.10–3.12. Linux jobs install Qt runtime libs (`libegl1`, `libxkbcommon0`, `libxcb-cursor0`, `libgl1`, `libdbus-1-3`).
- **Releases**: push a `v*` tag → [.github/workflows/release.yml](.github/workflows/release.yml) builds PyInstaller artifacts for all 3 OSes and attaches zips to a GitHub Release.

## Architecture (3 hand-written files)

- [main.py](main.py) — `MainWindow` class. Wires every Qt signal to a handler, manages the frameless window (custom drag + min/max/close buttons in `header_widget`), and switches pages via `ui.stackedWidget.setCurrentIndex(...)`.
- [Extractor.py](Extractor.py) — pure functions that operate on file paths:
  - `single_image_extractor(path)` / `multi_image_extractor(dir, images)` → dict of EXIF tags (adds `GoogleMapLink` when GPS present).
  - `remove_image_metadata(path)` / `multi_remove_image_metadata(...)` → rewrites the file in place by copying pixel data into a new `Image` without EXIF.
  - **Only JPEG/JPG is implemented** despite README claims of video/audio/PDF support. New format support belongs here as new functions, dispatched from the handlers in `main.py`.
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

- **Frameless window** (`Qt.FramelessWindowHint`): there are no OS title-bar controls. Window dragging and min/max/close are custom on `ui.header_widget` — preserve that wiring when refactoring `main.py`.
- **Handler naming**: `on_<widget>_<signal>` (e.g. `on_extract_btn_clicked`). Follow this when adding handlers.
- **File naming is inconsistent** (`Extractor.py` capitalized, `main.py` / `app_ui.py` lowercase). Match the existing case of the file you touch rather than renaming.
- `on_menu_docs_btn_toggled` currently routes to stacked index `0` (same as home) — known quirk, confirm intent before "fixing".
- Directory-mode handlers call `os.listdir(path)` with no extension filter; non-JPEG files will fall through `Extractor` returning `None`. Keep that contract (functions return `None`/falsy on unsupported formats) — [tests/test_extractor.py](tests/test_extractor.py) asserts it.
- Manual smoke test on top of `pytest` = run `python main.py` and exercise Extract / Remove on a sample JPEG with EXIF.
