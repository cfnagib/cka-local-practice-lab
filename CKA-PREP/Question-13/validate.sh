#!/bin/bash

set -e

PACKAGE="cri-dockerd"
SERVICE="cri-docker"

echo "Validating cri-dockerd setup..."

# 1. Package installed
dpkg -l | grep -qw "$PACKAGE" \
  || { echo "FAIL: Package $PACKAGE is not installed"; exit 1; }

echo "✓ cri-dockerd package installed"

# 2. Service exists
systemctl list-unit-files | grep -qw "$SERVICE.service" \
  || { echo "FAIL: Service $SERVICE.service not found"; exit 1; }

echo "✓ cri-docker service exists"

# 3. Service enabled
systemctl is-enabled "$SERVICE" >/dev/null 2>&1 \
  || { echo "FAIL: cri-docker service is not enabled"; exit 1; }

echo "✓ cri-docker service enabled"

# 4. Service running
systemctl is-active "$SERVICE" >/dev/null 2>&1 \
  || { echo "FAIL: cri-docker service is not running"; exit 1; }

echo "✓ cri-docker service running"

# 5. br_netfilter module loaded
lsmod | grep -qw br_netfilter \
  || { echo "FAIL: br_netfilter kernel module not loaded"; exit 1; }

echo "✓ br_netfilter module loaded"

# 6. sysctl validations
declare -A SYSCTLS=(
  ["net.bridge.bridge-nf-call-iptables"]="1"
  ["net.ipv6.conf.all.forwarding"]="1"
  ["net.ipv4.ip_forward"]="1"
  ["net.netfilter.nf_conntrack_max"]="131072"
)

for key in "${!SYSCTLS[@]}"; do
  value=$(sysctl -n "$key" 2>/dev/null)
  expected="${SYSCTLS[$key]}"

  [ "$value" = "$expected" ] \
    || { echo "FAIL: $key=$value (expected $expected)"; exit 1; }

  echo "✓ $key correctly set to $expected"
done

echo "SUCCESS: cri-dockerd setup validated successfully"
