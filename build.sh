#!/bin/bash
# Dollar Bets — Vercel Build Script
# Generates all pages from accumulated board data in data/boards/
# (Daily scanning is handled by GitHub Actions, not the build)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "[build] Starting Dollar Bets build..."

# Install fonts + Pillow for OG image generation
echo "[build] Installing fonts and Pillow..."
apt-get update -qq && apt-get install -y -qq fonts-dejavu-core fonts-liberation2 2>&1 \
  || echo "[build] WARNING: Could not install fonts (may already exist)"
uv pip install Pillow --system 2>&1 \
  || python3 -m pip install Pillow --break-system-packages 2>&1 \
  || echo "[build] WARNING: Could not install Pillow, OG images will be skipped"

# Ensure data directory exists
mkdir -p data/boards

# If no board files exist yet, run scanner to bootstrap
if [ -z "$(ls -A data/boards/ 2>/dev/null)" ]; then
  echo "[build] No board data found, running scanner to bootstrap..."
  TODAY=$(date -u +%Y-%m-%d)
  python3 scanner.py > "data/boards/${TODAY}.json" 2>/dev/null || echo "[build] Scanner failed, will generate with empty data"
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
