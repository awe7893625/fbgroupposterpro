# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FBGroupPosterPro
# Build: pyinstaller build/build.spec --distpath dist/ --workpath build/work/
# Mac:   produces FBGroupPosterPro.app in dist/
# Win:   produces FBGroupPosterPro.exe in dist/

import os
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

block_cipher = None

a = Analysis(
    [str(ROOT / 'tray_app.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Frontend static files (Next.js export output)
        (str(ROOT / 'frontend' / 'out'), 'frontend/out'),
        # Icons
        (str(ROOT / 'icons'), 'icons') if (ROOT / 'icons').exists() else ('', ''),
    ],
    hiddenimports=[
        # SQLAlchemy dialects
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.pysqlite',
        'sqlalchemy.orm',
        'sqlalchemy.sql',
        # aiohttp
        'aiohttp',
        'aiohttp.web',
        'aiohttp_cors',
        # Selenium / undetected-chromedriver
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.common.action_chains',
        'undetected_chromedriver',
        # APScheduler
        'apscheduler',
        'apscheduler.schedulers.asyncio',
        'apscheduler.triggers.cron',
        'apscheduler.triggers.date',
        # Crypto
        'Crypto',
        'Crypto.Cipher',
        'Crypto.Cipher.AES',
        'Crypto.Util',
        'Crypto.Util.Padding',
        # PyQt5
        'PyQt5',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'PyQt5.QtCore',
        # Standard library async
        'asyncio',
        'asyncio.events',
        # Multiprocessing
        'multiprocessing',
        'multiprocessing.pool',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
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
    name='FBGroupPosterPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal window on Windows
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'icons' / 'icon.icns') if (ROOT / 'icons' / 'icon.icns').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FBGroupPosterPro',
)

# macOS .app bundle
app = BUNDLE(
    coll,
    name='FBGroupPosterPro.app',
    icon=str(ROOT / 'icons' / 'icon.icns') if (ROOT / 'icons' / 'icon.icns').exists() else None,
    bundle_identifier='ai.rain.fbgroupposterpro',
    info_plist={
        'NSHighResolutionCapable': True,
        'LSUIElement': True,  # Hide from Dock (tray-only app)
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSAppleEventsUsageDescription': 'FBGroupPosterPro needs to control Chrome for Facebook automation.',
    },
)
