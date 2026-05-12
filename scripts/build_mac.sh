#!/usr/bin/env bash
# Build a distributable folder: dist/HeartBeatDevil/
# Run on macOS only. Zip that folder → upload as GitHub Release asset (e.g. HeartBeatDevil-mac.zip).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m pip install -r requirements-build.txt
pyinstaller --noconfirm --clean HeartBeatDevil.spec

echo ""
echo "Built: $ROOT/dist/HeartBeatDevil/"
echo "Zip for upload: (cd dist && zip -r HeartBeatDevil-mac.zip HeartBeatDevil)"
