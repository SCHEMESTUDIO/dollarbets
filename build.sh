#!/bin/bash
# Dollar Bets — Vercel Build Script
# Generates all pages from accumulated board data in data/boards/
# (Daily scanning is handled by GitHub Actions, not the build)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "[build] Starting Dollar Bets build..."

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

echo "[build] Done."
