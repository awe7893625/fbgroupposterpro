# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FBGroupPosterPro — Windows
# Build:  pyinstaller build\build_win.spec --distpath dist\ --workpath build\work\
# Output: dist\FBGroupPosterPro\FBGroupPosterPro.exe (one-folder, faster startup
#         and easier to bundle the Next.js static export inside the install dir)

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent

# Force-bundle every backend submodule. The backend uses lazy (function-level) imports
# (e.g. selenium_engine imports fb_graphql inside methods), which PyInstaller's static
# graph can miss — collect_submodules guarantees fb_graphql/scheduler/routes are included.
_BACKEND_MODULES = collect_submodules('backend')

block_cipher = None

# Try to find an .ico — Inno Setup will also use this.
_ico_candidates = [
    ROOT / 'icons' / 'icon.ico',
    ROOT / 'build' / 'icon.ico',
]
ICON_PATH = next((str(p) for p in _ico_candidates if p.exists()), None)

# Frontend static export must already be built (`npm run build` then `npm run export`)
# before invoking PyInstaller.
_frontend_out = ROOT / 'frontend' / 'out'
if not _frontend_out.exists():
    raise SystemExit(
        f"Frontend static export missing: {_frontend_out}\n"
        "Run `npm run build` in frontend/ first."
    )

datas = [
    (str(_frontend_out), 'frontend/out'),
]
if (ROOT / 'icons').exists():
    datas.append((str(ROOT / 'icons'), 'icons'))

a = Analysis(
    [str(ROOT / 'tray_app.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=_BACKEND_MODULES + [
        # SQLAlchemy
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
        # Crypto (pycryptodome)
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
        # asyncio + multiprocessing helpers
        'asyncio',
        'asyncio.events',
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
    upx=False,            # UPX confuses some AV engines on Windows; safer off.
    console=False,        # No console window — tray app.
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FBGroupPosterPro',
)
