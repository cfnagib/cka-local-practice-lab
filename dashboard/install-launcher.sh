#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$HOME/.local/share/applications"
TARGET="$TARGET_DIR/CKA-Local-Practice.desktop"

mkdir -p "$TARGET_DIR"
sed "s#REPLACE_WITH_PROJECT_PATH#${ROOT_DIR}#" \
  "$ROOT_DIR/dashboard/CKA-Local-Practice.desktop" > "$TARGET"
chmod +x "$TARGET"
echo "Desktop launcher installed: $TARGET"
