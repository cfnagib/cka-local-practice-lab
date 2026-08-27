#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
URL="http://127.0.0.1:8790"
LOG_FILE="/tmp/cka-local-dashboard.log"
UNIT="cka-local-dashboard"
TAILSCALE_IP=""

if command -v tailscale >/dev/null 2>&1; then
  TAILSCALE_IP="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
fi

# Restart only this dashboard so the launcher always serves the latest files.
# Do not use setsid here: libvirt snapshot restores started from that session
# can later destroy the guest domains. A user service keeps the dashboard alive
# while its reset subprocesses use `sg libvirt` for the required access.
systemctl --user stop "$UNIT.service" 2>/dev/null || true
systemctl --user reset-failed "$UNIT.service" 2>/dev/null || true
RUN_ENV=()
for variable in DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS; do
  if [[ -n "${!variable:-}" ]]; then
    RUN_ENV+=("--setenv=$variable=${!variable}")
  fi
done
if [[ -n "$TAILSCALE_IP" ]]; then
  RUN_ENV+=("--setenv=CKA_TAILSCALE_IP=$TAILSCALE_IP")
fi
systemd-run --user --unit="$UNIT" --collect "${RUN_ENV[@]}" \
  --property="WorkingDirectory=$ROOT_DIR" \
  --property="StandardOutput=append:$LOG_FILE" \
  --property="StandardError=append:$LOG_FILE" \
  /usr/bin/python3 "$ROOT_DIR/dashboard/server.py" >/dev/null
for _ in {1..20}; do
  ss -ltn "sport = :8790" | grep -q LISTEN && break
  sleep 0.25
done

xdg-open "$URL" >/dev/null 2>&1 &
if [[ -n "$TAILSCALE_IP" ]]; then
  echo "Tailscale access: http://$TAILSCALE_IP:8790"
fi
