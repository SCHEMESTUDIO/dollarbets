#!/bin/bash
# Dollar Bets — Build Script
# Runs the scanner, pipes to generator, outputs public/index.html
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "[build] Starting Dollar Bets build..."

# Run scanner → pipe to generator
python3 scanner.py | python3 generate.py

echo "[build] Done. Output: public/index.html"
