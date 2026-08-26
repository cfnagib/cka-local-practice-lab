#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="http://127.0.0.1:8790"
LOG_FILE="/tmp/cka-local-dashboard.log"

# Restart only this dashboard so the launcher always serves the latest files.
pkill -f '[p]ython3 dashboard/server.py' 2>/dev/null || true
nohup sg libvirt -c "cd '$ROOT_DIR' && exec python3 dashboard/server.py" >"$LOG_FILE" 2>&1 &
for _ in {1..20}; do
  ss -ltn "sport = :8790" | grep -q LISTEN && break
  sleep 0.25
done

xdg-open "$URL" >/dev/null 2>&1 &
