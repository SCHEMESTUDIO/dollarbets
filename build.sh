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

# Site typefaces for the 1080×1080 social cards (share_card.py): Archivo
# (variable font, one file covers 700/900) + IBM Plex Mono. Pulled from the
# google/fonts repo, pinned to main. share_card.py falls back to DejaVu if
# any of these are missing, so a failed download costs the look, not the build.
GF="https://github.com/google/fonts/raw/main/ofl"
if [ ! -f "$FONT_DIR/Archivo-VF.ttf" ]; then
  echo "[build] Downloading Archivo + IBM Plex Mono for share cards..."
  mkdir -p "$FONT_DIR"
  curl -sL "$GF/archivo/Archivo%5Bwdth%2Cwght%5D.ttf" -o "$FONT_DIR/Archivo-VF.ttf" \
    && curl -sL "$GF/ibmplexmono/IBMPlexMono-Regular.ttf" -o "$FONT_DIR/IBMPlexMono-Regular.ttf" \
    && curl -sL "$GF/ibmplexmono/IBMPlexMono-SemiBold.ttf" -o "$FONT_DIR/IBMPlexMono-SemiBold.ttf" \
    && echo "[build] Card fonts downloaded" \
    || echo "[build] WARNING: Could not download card fonts, cards fall back to DejaVu"
  # A GitHub error page is not a font — drop anything under 50KB
  for f in Archivo-VF IBMPlexMono-Regular IBMPlexMono-SemiBold; do
    if [ -f "$FONT_DIR/$f.ttf" ] && [ "$(wc -c < "$FONT_DIR/$f.ttf")" -lt 50000 ]; then
      echo "[build] WARNING: $f.ttf looks wrong (too small), removing"
      rm -f "$FONT_DIR/$f.ttf"
    fi
  done
fi

# Ensure data directory exists
mkdir -p data/boards

# If no board files exist yet, run scanner to bootstrap
if [ -z "$(ls -A data/boards/ 2>/dev/null)" ]; then
  echo "[build] No board data found, running scanner to bootstrap..."
  TODAY=$(date -u +%Y-%m-%d)
  python3 scanner.py > "data/boards/${TODAY}.json" 2>/dev/null || echo "[build] Scanner failed, will generate with empty data"
fi

# If sports boards don't exist and ODDS_API_KEY is set, run all sports scanners
# Skip on Vercel builds — scanning is GitHub Actions' job, Vercel just builds HTML
TODAY=$(date -u +%Y-%m-%d)
if [ -n "$ODDS_API_KEY" ] && [ -z "$VERCEL" ]; then
  for MODE in lineup underdogs ocho chalk; do
    case $MODE in
      lineup) PREFIX="sports" ;;
      *) PREFIX="$MODE" ;;
    esac
    OUTFILE="data/boards/${PREFIX}-${TODAY}.json"
    if [ ! -f "$OUTFILE" ]; then
      echo "[build] No ${MODE} board for today, running scanner..."
      python3 sports_scanner.py --board=${MODE} > "$OUTFILE" 2>/dev/null || {
        echo "[build] ${MODE} scanner failed, page will use latest available"
        rm -f "$OUTFILE"
      }
    fi
  done
  # Combo meal (parlays)
  if [ ! -f "data/boards/combo-${TODAY}.json" ]; then
    echo "[build] No combo meal board for today, running parlay scanner..."
    python3 parlay_scanner.py > "data/boards/combo-${TODAY}.json" 2>/dev/null || {
      echo "[build] Parlay scanner failed, combo meal will use latest available"
      rm -f "data/boards/combo-${TODAY}.json"
    }
  fi
fi

# Generate all pages
python3 generate.py

# Generate content pages (SEO articles, Hall of Filth, explainers)
python3 generate_content.py

# /trending/ — live-volume page (Polymarket 24h volume + today's board). Non-fatal.
python3 generate_trending.py || echo "[build] WARNING: trending page failed (non-fatal)"

# Copy static source files (admin CMS, etc.)
if [ -d "src" ]; then
  echo "[build] Copying static source files..."
  cp -r src/* public/
fi

# ── Indexing automation ──────────────────────────────────────
# Notify search engines of changed URLs after each build.

SITE_URL="https://www.dollarbets.lol"
INDEXNOW_KEY="d0b1e5f7a3c94e8b"

# NOTE: The Google and Bing sitemap "ping" endpoints
# (google.com/ping?sitemap= and bing.com/ping?sitemap=) were deprecated and
# now return 404 — they have done nothing since late 2023, so the old curls
# were removed. Google discovers the sitemap via robots.txt + Search Console;
# Bing/Yandex/DuckDuckGo are covered by IndexNow below. There is no
# programmatic "submit to Google" — that must come from earned crawl demand.

# IndexNow — notify Bing/Yandex/DuckDuckGo of CHANGED URLs (NOT Google)
#
# This used to POST an arbitrary `head -100` slice of every generated page on
# every single build — ~3x/day forever, whether or not anything had changed.
# It is now gated on content hashes: scripts/indexnow_submit.py diffs this
# build's pages against the manifest published by the previous deploy and
# submits only what actually changed. If it can't fetch that baseline it
# submits nothing rather than falling back to spraying the whole site.
echo "[build] Submitting changed URLs via IndexNow..."
INDEXNOW_SITE_URL="$SITE_URL" INDEXNOW_KEY="$INDEXNOW_KEY" \
  python3 scripts/indexnow_submit.py --public-dir public \
  || echo "[build] WARNING: IndexNow step failed (non-fatal)"

echo "[build] Done."
