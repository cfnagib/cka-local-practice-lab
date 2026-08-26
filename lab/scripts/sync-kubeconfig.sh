#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/config.env"
mkdir -p "$ROOT_DIR/runtime"
scp -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  "$SSH_USER@$CONTROL_IP:/home/$SSH_USER/.kube/config" "$ROOT_DIR/runtime/kubeconfig"
sed -i "s/127.0.0.1/$CONTROL_IP/g" "$ROOT_DIR/runtime/kubeconfig"
chmod 600 "$ROOT_DIR/runtime/kubeconfig"
echo "Kubeconfig saved to $ROOT_DIR/runtime/kubeconfig"
