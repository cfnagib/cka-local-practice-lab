#!/usr/bin/env bash
set -euo pipefail

SNAPSHOT="${1:-cka-baseline}"
for name in cka-controlplane cka-worker1 cka-worker2; do
  virsh -c qemu:///system snapshot-revert "$name" "$SNAPSHOT" --running
  echo "$name: restored $SNAPSHOT"
done
