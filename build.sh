#!/bin/bash
# Dollar Bets — Vercel Build Script
# Generates all pages from accumulated board data in data/boards/
# (Daily scanning is handled by GitHub Actions, not the build)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "[build] Starting Dollar Bets build..."

# Install Pillow — must match the Python version running build.sh (3.12),
# not the 3.14 version Vercel pre-installs to .vercel_python_packages
echo "[build] Installing Pillow for $(python3 --version)..."
rm -rf .vercel_python_packages/PIL .vercel_python_packages/Pillow* 2>/dev/null
python3 -m pip install Pillow --target=.vercel_python_packages --no-cache-dir 2>&1 \
  || echo "[build] WARNING: Could not install Pillow"
python3 -c "from PIL import Image; print('[build] Pillow OK:', Image.__version__)" 2>&1 \
  || echo "[build] WARNING: Pillow import check FAILED"

# Download DejaVu fonts if not already present (Vercel has no system fonts)
FONT_DIR="$DIR/.fonts"
if [ ! -f "$FONT_DIR/DejaVuSerif-Bold.ttf" ]; then
  echo "[build] Downloading DejaVu fonts..."
  mkdir -p "$FONT_DIR"
  DEJAVU_URL="https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
  curl -sL "$DEJAVU_URL" -o /tmp/dejavu.zip \
    && unzip -qo /tmp/dejavu.zip -d /tmp/dejavu \
    && cp /tmp/dejavu/dejavu-fonts-ttf-2.37/ttf/DejaVuSerif-Bold.ttf "$FONT_DIR/" \
    && cp /tmp/dejavu/dejavu-fonts-ttf-2.37/ttf/DejaVuSerif-Italic.ttf "$FONT_DIR/" \
    && cp /tmp/dejavu/dejavu-fonts-ttf-2.37/ttf/DejaVuSansMono.ttf "$FONT_DIR/" \
    && cp /tmp/dejavu/dejavu-fonts-ttf-2.37/ttf/DejaVuSansMono-Bold.ttf "$FONT_DIR/" \
    && echo "[build] Fonts downloaded to $FONT_DIR" \
    || echo "[build] WARNING: Could not download fonts, OG images may be skipped"
  rm -rf /tmp/dejavu /tmp/dejavu.zip
fi

# Ensure data directory exists
mkdir -p data/boards

# If no board files exist yet, run scanner to bootstrap
if [ -z "$(ls -A data/boards/ 2>/dev/null)" ]; then
  echo "[build] No board data found, running scanner to bootstrap..."
  TODAY=$(date -u +%Y-%m-%d)
  python3 scanner.py > "data/boards/${TODAY}.json" 2>/dev/null || echo "[build] Scanner failed, will generate with empty data"
fi

# If no sports board exists and ODDS_API_KEY is set, run sports scanner
TODAY=$(date -u +%Y-%m-%d)
if [ ! -f "data/boards/sports-${TODAY}.json" ] && [ -n "$ODDS_API_KEY" ]; then
  echo "[build] No sports board for today, running sports scanner..."
  python3 sports_scanner.py > "data/boards/sports-${TODAY}.json" 2>/dev/null || {
    echo "[build] Sports scanner failed, underdogs page will use latest available"
    rm -f "data/boards/sports-${TODAY}.json"
  }
fi

# Generate all pages
python3 generate.py

# Generate content pages (SEO articles, Hall of Filth, explainers)
python3 generate_content.py

# Copy static source files (admin CMS, etc.)
if [ -d "src" ]; then
  echo "[build] Copying static source files..."
  cp -r src/* public/
fi

echo "[build] Done."
