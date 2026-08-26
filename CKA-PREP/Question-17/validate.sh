#!/bin/bash
set -e

URL="https://ckaquestion.k8s.local"

echo "Starting TLS validation..."

# -------------------------------------------------
# 1. TLS 1.2 must FAIL
# -------------------------------------------------
echo "Checking TLS 1.2 (should fail)..."

if curl -sk --tls-max 1.2 "$URL" >/dev/null 2>&1; then
  echo "FAIL: TLS 1.2 connection succeeded (should be blocked)"
  exit 1
else
  echo "✓ TLS 1.2 correctly rejected"
fi

# -------------------------------------------------
# 2. TLS 1.3 must SUCCEED
# -------------------------------------------------
echo "Checking TLS 1.3 (should succeed)..."

if curl -sk --tlsv1.3 "$URL" >/dev/null 2>&1; then
  echo "✓ TLS 1.3 connection succeeded"
else
  echo "FAIL: TLS 1.3 connection failed"
  exit 1
fi

echo
echo "SUCCESS: TLS configuration is valid"
