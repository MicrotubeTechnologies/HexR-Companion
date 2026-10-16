# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the HEXR Companion app.
#
#     pyinstaller --noconfirm HexR-Companion.spec
#
# Produces a FOLDER build at dist\HexR-Companion\, with a no-console
# HexR-Companion.exe inside it. That folder is what the Inno Setup script in
# packaging\ turns into the single installer .exe, and what BUILD-INSTALLER.bat
# also zips as the portable download.
#
# On macOS the same spec produces dist/HEXR Companion.app (a universal2
# bundle when built with the python.org Python); tools/build_mac.sh signs,
# notarizes and wraps it in a DMG.
#
# Deliberately not --onefile: a onefile build unpacks its whole ~15 MB payload
# into a temp directory on EVERY launch, which is a visible startup delay and
# pointless when an installer is laying the files down once anyway.

import os
import sys

from PyInstaller.utils.hooks import collect_all

MAC = sys.platform == "darwin"

datas, binaries, hiddenimports = [], [], []
# PyAV, for the Headsets screen's live view, ships FFmpeg as DLLs beside its
# extension modules; collect_all brings them along. Windows only, as in
# requirements.txt.
for pkg in ("bleak",) + (() if MAC else ("av",)):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# Bundle the IBM Plex faces so the app renders correctly on a machine that has
# never had them installed. hexr/theme.py loads them per-process at startup.
if os.path.isdir("assets/fonts"):
    datas += [("assets/fonts", "assets/fonts")]

# The icon files the RUNNING app reads, as opposed to the one baked into the
# exe's own resources below. icon.ico is the taskbar/Alt-Tab icon Tk sets at
# startup; icon-16.png is the mark drawn in the title bar. Without these in
# datas both lookups miss inside the bundle, and the packaged app quietly falls
# back to Tk's feather and a plain orange square - which is exactly what it did
# before they were added here.
for _icon in ("assets/icon.ico", "assets/icon-16.png"):
    if os.path.exists(_icon):
        datas += [(_icon, "assets")]

# The glove the Headsets view draws over the wearer's view, and its fonts (SIL OFL).
if os.path.isdir("assets/overlay"):
    datas += [("assets/overlay", "assets/overlay")]

if MAC:
    # tools/build_mac.sh generates icon.icns from icon.png before building.
    icon = "assets/icon.icns" if os.path.exists("assets/icon.icns") else None
else:
    icon = "assets/icon.ico" if os.path.exists("assets/icon.ico") else None

# The Windows version resource is built here from the VERSION file rather than
# kept in a checked-in .txt that something has to rewrite. A build step that
# patched that file with regexes was one shell-quoting mistake away from
# emitting invalid Python and breaking the build; generating it is not.
with open("VERSION", encoding="utf-8") as _f:
    APP_VERSION = _f.read().strip() or "0.0.0"
_parts = (APP_VERSION.split(".") + ["0", "0", "0", "0"])[:4]
_quad = tuple(int(p) if p.isdigit() else 0 for p in _parts)

if MAC:
    version_res = None
else:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
        VarStruct, VSVersionInfo)
    version_res = VSVersionInfo(
        ffi=FixedFileInfo(filevers=_quad, prodvers=_quad, mask=0x3F, flags=0x0,
                          OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
        kids=[
            StringFileInfo([StringTable('040904B0', [
                StringStruct('CompanyName', 'Microtube Technologies'),
                StringStruct('FileDescription', 'HEXR Companion'),
                StringStruct('FileVersion', '.'.join(str(n) for n in _quad)),
                StringStruct('InternalName', 'HexR-Companion'),
                StringStruct('LegalCopyright', '© Microtube Technologies'),
                StringStruct('OriginalFilename', 'HexR-Companion.exe'),
                StringStruct('ProductName', 'HEXR Companion'),
                StringStruct('ProductVersion', '.'.join(str(n) for n in _quad)),
            ])]),
            VarFileInfo([VarStruct('Translation', [1033, 1200])]),
        ])

# ship VERSION inside the bundle so the running app can report it too
datas += [("VERSION", ".")]

a = Analysis(
    ['hexr_tester.py'],           # three-step desktop app (Tkinter)
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        'hexr', 'hexr.theme', 'hexr.widgets', 'hexr.shell',
        'hexr.state', 'hexr.engine', 'hexr.protocol',
        'hexr.screens', 'hexr.screens.base', 'hexr.screens.connect',
        'hexr.screens.test', 'hexr.screens.quicktest',
        'hexr.screens.headsets', 'hexr.screens.fullview', 'hexr.haptics',
        'hexr.overlay', 'hexr.viewer', 'hexr.recorder', 'PIL.ImageTk',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,        # folder build: binaries go in COLLECT
    name='HexR-Companion',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=not MAC,                  # UPX corrupts macOS code signatures
    console=False,                # <-- no terminal window
    icon=icon,
    version=version_res,
    target_arch="universal2" if MAC else None,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=not MAC,
    upx_exclude=[],
    name='HexR-Companion',
)

if MAC:
    app = BUNDLE(
        coll,
        name='HEXR Companion.app',
        icon=icon,
        # Kept from when the app was HEXR Window Tester: a new id would make macOS
        # treat it as another app and ask for Bluetooth all over again.
        bundle_identifier='tech.microtube.hexr-window-tester',
        version=APP_VERSION,
        info_plist={
            'CFBundleName': 'HEXR Companion',
            'CFBundleDisplayName': 'HEXR Companion',
            'CFBundleShortVersionString': APP_VERSION,
            'CFBundleVersion': APP_VERSION,
            'LSMinimumSystemVersion': '10.13',
            'LSApplicationCategoryType': 'public.app-category.utilities',
            'NSHighResolutionCapable': True,
            'NSHumanReadableCopyright': '© Microtube Technologies',
            # Without this macOS kills the app the moment bleak touches
            # CoreBluetooth.
            'NSBluetoothAlwaysUsageDescription':
                'HEXR Companion uses Bluetooth to connect to your HEXR gloves.',
            # macOS asks before an app may reach devices on the local network,
            # and shows this when it does: the Headsets screen finds and talks
            # to HEXR headsets on the same Wi-Fi.
            'NSLocalNetworkUsageDescription':
                'HEXR Companion finds and controls HEXR headsets on your local network.',
            # Bundled IBM Plex faces, if present, are registered by macOS itself.
            'ATSApplicationFontsPath': 'assets/fonts/',
        },
    )
