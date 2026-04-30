# AGENTS.md — EOM (Eye On Metadata)

PySide6 desktop app for viewing/exporting/removing image metadata. End-user docs live in [README.md](README.md).

## Stack & Run

- **Python + PySide6** (Qt for Python) + **Pillow** for EXIF.
- No `requirements.txt`. Install deps manually:
  ```bash
  pip install PySide6 Pillow
  ```
- Run from the project root (paths to `style.qss` are relative):
  ```bash
  python main.py
  ```
- A `.venv/` already exists in the repo root — activate it before running.

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
- Directory-mode handlers call `os.listdir(path)` with no extension filter; non-JPEG files will fall through `Extractor` returning `None`. Keep that contract (functions return `None`/falsy on unsupported formats).
- No tests, no linter config, no CI. Manual smoke test = run `python main.py` and exercise Extract / Remove on a sample JPEG with EXIF.
