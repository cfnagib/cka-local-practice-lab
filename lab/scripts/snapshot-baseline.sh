#!/usr/bin/env bash
set -euo pipefail

SNAPSHOT="${1:-cka-baseline}"
# Baselines must be captured while every VM is powered off.  Otherwise
# libvirt can restore stale RAM/device state along with the disk snapshot.
for name in cka-base cka-controlplane cka-worker1 cka-worker2; do
  virsh -c qemu:///system destroy "$name" 2>/dev/null || true
done
sleep 2
for name in cka-base cka-controlplane cka-worker1 cka-worker2; do
  if virsh -c qemu:///system snapshot-list "$name" --name | grep -qx "$SNAPSHOT"; then
    echo "$name: snapshot $SNAPSHOT already exists"
  else
    virsh -c qemu:///system snapshot-create-as "$name" "$SNAPSHOT" "CKA lab baseline" --atomic
    echo "$name: created $SNAPSHOT"
  fi
done
for name in cka-base cka-controlplane cka-worker1 cka-worker2; do
  virsh -c qemu:///system start "$name" >/dev/null
done
