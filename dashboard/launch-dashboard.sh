#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="http://127.0.0.1:8790"
LOG_FILE="/tmp/cka-local-dashboard.log"

if ! ss -ltn "sport = :8790" | grep -q LISTEN; then
  nohup sg libvirt -c "cd '$ROOT_DIR' && exec python3 dashboard/server.py" >"$LOG_FILE" 2>&1 &
  for _ in {1..20}; do
    ss -ltn "sport = :8790" | grep -q LISTEN && break
    sleep 0.25
  done
fi

xdg-open "$URL" >/dev/null 2>&1 &
