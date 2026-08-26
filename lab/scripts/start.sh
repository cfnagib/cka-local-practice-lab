#!/usr/bin/env bash
set -euo pipefail

for name in cka-controlplane cka-worker1 cka-worker2; do
  state="$(virsh -c qemu:///system domstate "$name" 2>/dev/null || true)"
  if [[ "$state" != "running" ]]; then
    virsh -c qemu:///system start "$name"
  fi
done
