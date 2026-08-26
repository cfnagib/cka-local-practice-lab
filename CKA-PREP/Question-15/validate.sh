#!/bin/bash

set -e

NODE="node01"
TAINT_KEY="PERMISSION"
TAINT_VALUE="granted"
TAINT_EFFECT="NoSchedule"

echo "Validating taints and tolerations..."

# 1. Node exists
kubectl get node "$NODE" >/dev/null 2>&1 \
  || { echo "FAIL: Node $NODE not found"; exit 1; }

echo "✓ Node exists"

# 2. Validate taint on node
TAINT_FOUND=$(kubectl get node "$NODE" -o jsonpath='{.spec.taints[*].key}')

echo "$TAINT_FOUND" | grep -qw "$TAINT_KEY" \
  || { echo "FAIL: Taint key $TAINT_KEY not found on $NODE"; exit 1; }

VALUE=$(kubectl get node "$NODE" \
  -o jsonpath='{.spec.taints[?(@.key=="'"$TAINT_KEY"'")].value}')

EFFECT=$(kubectl get node "$NODE" \
  -o jsonpath='{.spec.taints[?(@.key=="'"$TAINT_KEY"'")].effect}')

[ "$VALUE" = "$TAINT_VALUE" ] \
  || { echo "FAIL: Taint value=$VALUE (expected $TAINT_VALUE)"; exit 1; }

[ "$EFFECT" = "$TAINT_EFFECT" ] \
  || { echo "FAIL: Taint effect=$EFFECT (expected $TAINT_EFFECT)"; exit 1; }

echo "✓ Node taint correctly configured"

# 3. Find a pod scheduled on node01
POD_INFO=$(kubectl get pods -A -o wide \
  | awk '$8=="'"$NODE"'" {print $1,$2}' | head -n1)

[ -n "$POD_INFO" ] \
  || { echo "FAIL: No pod scheduled on $NODE"; exit 1; }

POD_NAMESPACE=$(echo "$POD_INFO" | awk '{print $1}')
POD_NAME=$(echo "$POD_INFO" | awk '{print $2}')

echo "✓ Pod $POD_NAME found on $NODE"

# 4. Validate toleration on the pod
TOL_KEY=$(kubectl get pod "$POD_NAME" -n "$POD_NAMESPACE" \
  -o jsonpath='{.spec.tolerations[?(@.key=="'"$TAINT_KEY"'")].key}')

TOL_VALUE=$(kubectl get pod "$POD_NAME" -n "$POD_NAMESPACE" \
  -o jsonpath='{.spec.tolerations[?(@.key=="'"$TAINT_KEY"'")].value}')

TOL_EFFECT=$(kubectl get pod "$POD_NAME" -n "$POD_NAMESPACE" \
  -o jsonpath='{.spec.tolerations[?(@.key=="'"$TAINT_KEY"'")].effect}')

[ "$TOL_KEY" = "$TAINT_KEY" ] \
  || { echo "FAIL: Pod does not tolerate key $TAINT_KEY"; exit 1; }

[ "$TOL_VALUE" = "$TAINT_VALUE" ] \
  || { echo "FAIL: Pod toleration value=$TOL_VALUE (expected $TAINT_VALUE)"; exit 1; }

[ "$TOL_EFFECT" = "$TAINT_EFFECT" ] \
  || { echo "FAIL: Pod toleration effect=$TOL_EFFECT (expected $TAINT_EFFECT)"; exit 1; }

echo "✓ Pod toleration correctly configured"

echo "SUCCESS: Taints & Tolerations task validated"
