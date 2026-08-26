#!/usr/bin/env bash
set -euo pipefail
QUESTION="${1:?Usage: run-question.sh <number>}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/config.env"
SOURCE_DIR="$ROOT_DIR/../CKA-PREP/Question-$QUESTION"
[[ -d "$SOURCE_DIR" ]] || { echo "Question not found: $QUESTION"; exit 1; }
REMOTE_DIR="/tmp/cka-question-$QUESTION"
tar -C "$SOURCE_DIR" -czf - . | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$CONTROL_IP" "rm -rf '$REMOTE_DIR' && mkdir -p '$REMOTE_DIR' && tar -xzf - -C '$REMOTE_DIR' && chmod +x '$REMOTE_DIR/LabSetUp.bash' && '$REMOTE_DIR/LabSetUp.bash'"
echo "Question $QUESTION setup completed on $CONTROL_IP"
