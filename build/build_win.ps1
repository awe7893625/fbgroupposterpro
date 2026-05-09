# FBGroupPosterPro — Windows build script
# Run from project root: powershell -ExecutionPolicy Bypass -File build\build_win.ps1
# Requires:
#   - Python 3.11+ on PATH
#   - Node 18+ on PATH
#   - Inno Setup 6 installed (default location accepted; override via -InnoSetup)

param(
    [string]$InnoSetup = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    [switch]$SkipFrontend = $false,
    [switch]$SkipInstaller = $false
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> FBGroupPosterPro Windows build" -ForegroundColor Cyan
Write-Host "Root: $Root"

# ── 1. Python venv + deps ──────────────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating venv" -ForegroundColor Yellow
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel | Out-Null
pip install -r requirements.txt
pip install pyinstaller pillow

# ── 2. Generate .ico from PNG if missing ───────────────────────────────────────
$IcoPath = "icons\icon.ico"
if (-not (Test-Path $IcoPath)) {
    Write-Host "==> Generating icon.ico from icon128.png" -ForegroundColor Yellow
    python - <<'PY'
from PIL import Image
import os
src = "icons/icon128.png"
out = "icons/icon.ico"
if not os.path.exists(src):
    raise SystemExit("missing icons/icon128.png")
img = Image.open(src).convert("RGBA")
sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
img.save(out, format="ICO", sizes=sizes)
print("wrote", out)
PY
}

# ── 3. Frontend export (Next.js static) ────────────────────────────────────────
if (-not $SkipFrontend) {
    Write-Host "==> Building frontend" -ForegroundColor Yellow
    Push-Location frontend
    if (-not (Test-Path "node_modules")) { npm ci }
    npm run build
    Pop-Location
    if (-not (Test-Path "frontend\out")) {
        throw "frontend\out missing — does next.config.js have output: 'export'?"
    }
}

# ── 4. PyInstaller ─────────────────────────────────────────────────────────────
Write-Host "==> Cleaning previous build" -ForegroundColor Yellow
if (Test-Path "dist\FBGroupPosterPro") { Remove-Item -Recurse -Force "dist\FBGroupPosterPro" }
if (Test-Path "build\work") { Remove-Item -Recurse -Force "build\work" }

Write-Host "==> Running PyInstaller" -ForegroundColor Yellow
pyinstaller build\build_win.spec --distpath dist\ --workpath build\work\ --noconfirm

if (-not (Test-Path "dist\FBGroupPosterPro\FBGroupPosterPro.exe")) {
    throw "PyInstaller did not produce dist\FBGroupPosterPro\FBGroupPosterPro.exe"
}

# ── 5. Inno Setup installer ────────────────────────────────────────────────────
if (-not $SkipInstaller) {
    if (-not (Test-Path $InnoSetup)) {
        Write-Warning "Inno Setup not found at $InnoSetup — skipping installer build."
        Write-Warning "Install it from https://jrsoftware.org/isdl.php and re-run, or pass -InnoSetup <path>."
    } else {
        Write-Host "==> Building installer" -ForegroundColor Yellow
        & $InnoSetup "build\installer.iss"
    }
}

Write-Host ""
Write-Host "==> Done" -ForegroundColor Green
Write-Host "Portable folder:  dist\FBGroupPosterPro\"
Write-Host "Installer:        dist\FBGroupPosterPro-Setup-*.exe"
