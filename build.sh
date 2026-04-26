#!/bin/bash
# Dollar Bets — Build Script (v2: multi-page)
# 1. Run scanner → save daily board JSON
# 2. Run generator → build all pages from accumulated data
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "[build] Starting Dollar Bets build..."

# Ensure data directory exists
mkdir -p data/boards

# Today's date
TODAY=$(date -u +%Y-%m-%d)
BOARD_FILE="data/boards/${TODAY}.json"

# Run scanner → save today's board
echo "[build] Scanning markets..."
python3 scanner.py > "$BOARD_FILE"
echo "[build] Saved board to ${BOARD_FILE}"

# Generate all pages from accumulated board data
echo "[build] Generating all pages..."
python3 generate.py

echo "[build] Done."
