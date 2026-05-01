# 👁️ EOM – Eye On Metadata
**EOM (Eye On Metadata)** is a free and open-source desktop application for **viewing, exporting, and removing metadata** from a wide range of media files — images, audio, video, and PDFs.

Cross-platform by design, EOM runs on **Windows**, **Linux**, and **macOS** with a single pre-built binary — no Python or runtime installation required.

## 🖼️ Gallery

<img src='./screenshots/Screenshot from 2024-03-27 00-27-50.png' alt='EOM Screenshot'>
<img src='./screenshots/Screenshot from 2024-03-20 21-00-06.png' alt='EOM Screenshot'>
<img src='./screenshots/Screenshot from 2024-03-27 00-38-04.png' alt='EOM Screenshot'>
<img src='./screenshots/Screenshot from 2024-03-27 00-43-14.png' alt='EOM Screenshot'>
<img src='./screenshots/Screenshot from 2024-03-27 00-47-08.png' alt='EOM Screenshot'>

## ❓ What is EOM?

Eye On Metadata (EOM) is a lightweight privacy tool that gives you full control over the hidden data embedded in your files. Whether you want to inspect EXIF data before sharing a photo, strip GPS coordinates from images, or clean identifying tags from audio and video files, EOM handles it with a clean, simple interface.

### Supported formats

| Category | Formats |
|----------|---------|
| Images | JPEG, PNG, TIFF |
| Audio | MP3, FLAC, OGG, WAV, AIFF, M4A, WMA |
| Video | MP4, M4V, MKV, WebM |
| Documents | PDF |

### Optional: deeper metadata with ExifTool

If [`exiftool`](https://exiftool.org) is installed on your system, EOM automatically uses it as the primary metadata backend, unlocking XMP, IPTC, MakerNotes, RAW camera tags, and much more. The header bar shows **ExifTool ✓** (green) or **ExifTool ✗** (amber) so you always know which backend is active.

- **Linux / macOS:** `sudo apt install libimage-exiftool-perl` / `brew install exiftool`
- **Windows:** The pre-built `eom.exe` release already includes a bundled `exiftool.exe` — no separate install needed.

## 📥 Download

Pre-built binaries are attached to every [GitHub Release](https://github.com/abogo-nono/eom/releases):

| Platform | File | Requires |
|----------|------|---------|
| Linux x86-64 | `eom-linux-x86_64.zip` | Ubuntu 20.04+ / Debian 11+ |
| Windows x86-64 | `eom-windows-x86_64.zip` | Windows 10+ (includes exiftool.exe) |
| macOS Intel | `eom-macos-x86_64.zip` | macOS 12 Monterey+ |
| macOS Apple Silicon | `eom-macos-arm64.zip` | macOS 14 Sonoma+ |

## 📤 How to Extract / Display Metadata

1. Click **Extract**
2. Choose extraction type — **single file** or **directory**
3. Select the file(s) or folder
4. Click **Extract**

Metadata is displayed in an organized table. Use **Export** to save it to a file.

## 🧹 How to Remove Metadata

1. Click **Remove**
2. Choose remove type — **single file** or **directory**
3. Select the file(s) or folder
4. Click **Remove**

EOM strips metadata safely while keeping your files intact.

## 📁 How to Export Metadata

1. Click **Extract** and run an extraction
2. Click **Export**
3. Set the save path and filename
4. Click **Save**

## 🛠️ Report a Bug / Contribute / Suggest a Feature

1. Visit the GitHub repo: [EOM GitHub Repository](https://github.com/abogo-nono/eom)
2. Open an issue for bugs or feature requests
3. Submit a pull request if you’d like to contribute directly

See [AGENTS.md](AGENTS.md) for the developer guide (architecture, build instructions, conventions).

## 👤 Developed by ABOGO Lincoln

Crafted with care and open-source spirit 💡  
[https://github.com/abogo-nono](https://github.com/abogo-nono)
