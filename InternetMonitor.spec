# -*- mode: python ; coding: utf-8 -*-
# NetAnalyzer - PyInstaller spec file
# Reproducible builds: always use this file instead of CLI flags.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('monitor', 'monitor')],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtSvg',
        'aiohttp',
        'aiohttp.resolver',
        'aiohttp.connector',
        'qasync',
        'loguru',
        'winreg',
        # proxy_detector uses urllib which is stdlib but ensure it's included
        'urllib.request',
        'urllib.error',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'cv2',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='InternetMonitor',
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
    icon='NONE',
    version='version_info.txt',
)
