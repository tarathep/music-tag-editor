# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('ffmpeg', '.')],
    datas=[('LICENSE', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Music Tag Editor',
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
    icon=['icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Music Tag Editor',
)
app = BUNDLE(
    coll,
    name='Music Tag Editor.app',
    icon='icon.icns',
    bundle_identifier=None,
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '20260712',
        'CFBundleGetInfoString': 'Music Tag Editor 1.0.0 (Build 20260712)',
        'NSHumanReadableCopyright': 'Copyright © 2026 Bokie Tarathep. All rights reserved.',
    },
)
