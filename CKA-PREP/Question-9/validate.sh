#!/bin/bash

set -e

NAMESPACE="backend"
EXPECTED_POLICY="policy-z"
EXPECTED_PORT="80"

echo "Validating NetworkPolicy selection (least permissive)..."

# 1. NetworkPolicy exists
kubectl get networkpolicy "$EXPECTED_POLICY" -n "$NAMESPACE" >/dev/null 2>&1 \
  || { echo "FAIL: NetworkPolicy $EXPECTED_POLICY not found in $NAMESPACE"; exit 1; }

echo "✓ policy-z exists"

# 2. podSelector targets backend pods
BACKEND_SELECTOR=$(kubectl get networkpolicy "$EXPECTED_POLICY" -n "$NAMESPACE" \
  -o jsonpath='{.spec.podSelector.matchLabels.app}')

[ "$BACKEND_SELECTOR" = "backend" ] \
  || { echo "FAIL: podSelector does not target backend pods"; exit 1; }

echo "✓ Targets backend pods only"

# 3. Ingress restricted to frontend namespace
NS_SELECTOR=$(kubectl get networkpolicy "$EXPECTED_POLICY" -n "$NAMESPACE" \
  -o jsonpath='{.spec.ingress[0].from[0].namespaceSelector.matchLabels.kubernetes\.io/metadata\.name}')

[ "$NS_SELECTOR" = "frontend" ] \
  || { echo "FAIL: Ingress not restricted to frontend namespace"; exit 1; }

echo "✓ Restricted to frontend namespace"

# 4. Ingress restricted to frontend pods
POD_SELECTOR=$(kubectl get networkpolicy "$EXPECTED_POLICY" -n "$NAMESPACE" \
  -o jsonpath='{.spec.ingress[0].from[1].podSelector.matchLabels.app}')

[ "$POD_SELECTOR" = "frontend" ] \
  || { echo "FAIL: Ingress not restricted to frontend pods"; exit 1; }

echo "✓ Restricted to frontend pods"

# 5. Port restriction
PORT=$(kubectl get networkpolicy "$EXPECTED_POLICY" -n "$NAMESPACE" \
  -o jsonpath='{.spec.ingress[0].ports[0].port}')

[ "$PORT" = "$EXPECTED_PORT" ] \
  || { echo "FAIL: Port $PORT configured (expected $EXPECTED_PORT)"; exit 1; }

echo "✓ Port 80 restriction enforced"

# 6. Ensure no overly-permissive policies exist
BAD_POLICIES=$(kubectl get networkpolicy -n "$NAMESPACE" \
  --no-headers | awk '{print $1}' | grep -E 'policy-x|policy-y' || true)

[ -z "$BAD_POLICIES" ] \
  || { echo "FAIL: Overly permissive NetworkPolicy detected: $BAD_POLICIES"; exit 1; }

echo "✓ No overly permissive policies present"

echo "SUCCESS: Least-permissive NetworkPolicy (policy-z) is correctly deployed"
