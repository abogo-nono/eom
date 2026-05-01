# PyInstaller spec for EOM. Build with:
#   pyinstaller eom.spec --noconfirm --clean
#
# style.qss is loaded at runtime; app-logo.ico is used as the window icon and
# for the taskbar/dock icon on all platforms.  On macOS the CI step converts
# it to app-logo.icns before invoking PyInstaller.

# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Bundle the standalone exiftool.exe when present (downloaded during Windows CI).
ET_BIN = [("exiftool.exe", ".")] if os.path.isfile("exiftool.exe") else []

# macOS prefers .icns; everywhere else .ico works fine.
if sys.platform == "darwin":
    _icns = "images/app-logo.icns"
    ICON = _icns if os.path.isfile(_icns) else "images/app-logo.ico"
else:
    ICON = "images/app-logo.ico"

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=ET_BIN,
    datas=[("style.qss", "."), ("images/app-logo.ico", "images")],
    hiddenimports=collect_submodules("PySide6"),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="eom",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
