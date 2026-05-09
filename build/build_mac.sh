#!/bin/bash
# Build FBGroupPosterPro for macOS
# Usage: bash build/build_mac.sh
set -e
cd "$(dirname "$0")/.."

echo "=== FBGroupPosterPro macOS Build ==="

# 1. Build Next.js frontend
echo "[1/4] Building Next.js frontend..."
cd frontend && npm install && npm run build && cd ..
echo "  ✓ Frontend built → frontend/out/"

# 2. Install Python dependencies
echo "[2/4] Installing Python dependencies..."
pip3 install -r requirements.txt
echo "  ✓ Python deps installed"

# 3. Run PyInstaller
echo "[3/4] Running PyInstaller..."
pip3 install pyinstaller
pyinstaller build/build.spec --distpath dist/ --workpath build/work/ --clean
echo "  ✓ App built → dist/FBGroupPosterPro.app"

# 4. Create DMG (optional, requires create-dmg)
if command -v create-dmg &>/dev/null; then
  echo "[4/4] Creating DMG..."
  create-dmg \
    --volname "FBGroupPosterPro" \
    --window-pos 200 120 \
    --window-size 600 300 \
    --icon-size 100 \
    --icon "FBGroupPosterPro.app" 175 120 \
    --hide-extension "FBGroupPosterPro.app" \
    --app-drop-link 425 120 \
    "dist/FBGroupPosterPro.dmg" \
    "dist/FBGroupPosterPro.app"
  echo "  ✓ DMG created → dist/FBGroupPosterPro.dmg"
else
  echo "[4/4] create-dmg not found, skipping DMG. Install with: brew install create-dmg"
  # Fallback: zip the .app
  cd dist && zip -r FBGroupPosterPro-mac.zip FBGroupPosterPro.app && cd ..
  echo "  ✓ Zip created → dist/FBGroupPosterPro-mac.zip"
fi

echo ""
echo "=== Build Complete ==="
ls -lh dist/
