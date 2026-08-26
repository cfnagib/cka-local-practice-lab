#!/usr/bin/env bash
set -euo pipefail
QUESTION="${1:?Usage: validate-question.sh <number>}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/config.env"
REMOTE_DIR="/tmp/cka-question-$QUESTION"
ssh -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$CONTROL_IP" "cd '$REMOTE_DIR' && chmod +x validate.sh && ./validate.sh"
