# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Image Vault.

Freezes the pywebview desktop shell (desktop.py) into a standalone app that
needs no Python/uv installed on the target machine.

  pyinstaller image-vault.spec

On macOS this produces dist/Image Vault.app. The bundled templates/ and
static/ are placed at the bundle root, which app.py's get_app_dir() finds via
sys._MEIPASS when frozen. User state (config.json, tokens.db, thumbnails/)
still lives under platformdirs' user_data_dir, written at runtime.
"""
import sys

block_cipher = None

# Bundled assets, copied to the frozen app's root (sys._MEIPASS at runtime).
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# pywebview lazily imports its platform backend, and PyMuPDF ships as the
# `fitz` package - pull both in explicitly so PyInstaller's static analysis
# doesn't drop them.
hiddenimports = [
    'fitz',
]
if sys.platform == 'darwin':
    hiddenimports += ['webview.platforms.cocoa']
elif sys.platform == 'win32':
    hiddenimports += ['webview.platforms.edgechromium', 'webview.platforms.winforms']
else:
    hiddenimports += ['webview.platforms.gtk', 'webview.platforms.qt']

a = Analysis(
    ['desktop.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Image Vault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Image Vault',
)

# macOS .app bundle wrapper.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Image Vault.app',
        icon=None,
        bundle_identifier='com.toddgerdy.imagevault',
        info_plist={
            'CFBundleShortVersionString': '2.1.0',
            'CFBundleVersion': '2.1.0',
            'NSHighResolutionCapable': True,
        },
    )
