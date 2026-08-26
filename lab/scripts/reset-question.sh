#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/config.env"
SNAPSHOT="${1:-cka-baseline}"
for name in cka-controlplane cka-worker1 cka-worker2; do
  virsh -c qemu:///system destroy "$name" 2>/dev/null || true
done
# Recreate the bridge only after all tap devices have been detached.
virsh -c qemu:///system net-destroy "$NETWORK" 2>/dev/null || true
virsh -c qemu:///system net-start "$NETWORK" 2>/dev/null || true
for name in cka-controlplane cka-worker1 cka-worker2; do
  virsh -c qemu:///system snapshot-revert "$name" "$SNAPSHOT"
  # The baseline is powered off, so always perform a clean cold boot.
  virsh -c qemu:///system destroy "$name" 2>/dev/null || true
  virsh -c qemu:///system start "$name"
done
echo "Restored the CKA lab to $SNAPSHOT"
echo "Waiting for SSH and Kubernetes API..."
for attempt in {1..60}; do
  if ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$CONTROL_IP" kubectl get nodes 2>/dev/null | grep -q 'Ready'; then
    echo "Kubernetes is ready"
    exit 0
  fi
  sleep 3
done
echo "Kubernetes did not become ready after reset"
exit 1
