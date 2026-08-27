#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/config.env"
SNAPSHOT="${1:-cka-baseline}"

network_is_active() {
  local network_info
  network_info="$(virsh -c qemu:///system net-info "$NETWORK" 2>/dev/null)" || return 1
  [[ "$network_info" =~ Active:[[:space:]]+yes ]]
}

for name in cka-base cka-controlplane cka-worker1 cka-worker2; do
  virsh -c qemu:///system destroy "$name" 2>/dev/null || true
done

# Keep an already active persistent bridge. Tearing it down and immediately
# recreating it is asynchronous on some hosts: libvirt can report success
# before dnsmasq and virbr0 are usable by the VM guests.
if ! network_is_active; then
  # A parallel libvirt event can activate it after the check above.
  virsh -c qemu:///system net-start "$NETWORK" 2>/dev/null || true
fi
network_active=false
for attempt in {1..60}; do
  if network_is_active; then
    network_active=true
    break
  fi
  sleep 1
done
[[ "$network_active" == true ]] || {
  echo "Libvirt network $NETWORK did not become active"
  exit 1
}
for name in cka-base cka-controlplane cka-worker1 cka-worker2; do
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
