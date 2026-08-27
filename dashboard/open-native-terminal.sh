#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/lab/config.env"

if [[ -f "$CONFIG" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG"
fi

SSH_USER="${SSH_USER:-cfnagib}"
BASE_IP="${BASE_IP:-192.168.122.40}"

exec /usr/bin/konsole \
  --title "CKA Practice Terminal" \
  --hold \
  -e ssh -tt \
    -o LogLevel=ERROR \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    "${SSH_USER}@${BASE_IP}" bash -i
