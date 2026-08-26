#!/usr/bin/env bash
set -euo pipefail

for name in cka-controlplane cka-worker1 cka-worker2; do
  virsh -c qemu:///system shutdown "$name" 2>/dev/null || true
done
