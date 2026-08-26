#!/bin/bash

set -e

NAMESPACE="mariadb"
PVC_NAME="mariadb"
DEPLOYMENT="mariadb"
EXPECTED_STORAGE="250Mi"
EXPECTED_ACCESS="ReadWriteOnce"

echo "Validating MariaDB recovery with persistent storage..."

# 1. Namespace exists
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 \
  || { echo "FAIL: Namespace $NAMESPACE does not exist"; exit 1; }

echo "✓ Namespace exists"

# 2. Exactly one PV exists
PV_COUNT=$(kubectl get pv --no-headers | wc -l)
[ "$PV_COUNT" -eq 1 ] \
  || { echo "FAIL: Expected exactly 1 PV, found $PV_COUNT"; exit 1; }

echo "✓ Single PersistentVolume exists"

# 3. PVC exists
kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" >/dev/null 2>&1 \
  || { echo "FAIL: PVC $PVC_NAME not found"; exit 1; }

echo "✓ PVC exists"

# 4. PVC access mode
ACCESS_MODE=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.spec.accessModes[0]}')

[ "$ACCESS_MODE" = "$EXPECTED_ACCESS" ] \
  || { echo "FAIL: accessMode=$ACCESS_MODE (expected $EXPECTED_ACCESS)"; exit 1; }

echo "✓ PVC access mode correct"

# 5. PVC storage size
STORAGE=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.spec.resources.requests.storage}')

[ "$STORAGE" = "$EXPECTED_STORAGE" ] \
  || { echo "FAIL: storage=$STORAGE (expected $EXPECTED_STORAGE)"; exit 1; }

echo "✓ PVC storage size correct"

# 6. PVC is bound
STATUS=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.status.phase}')

[ "$STATUS" = "Bound" ] \
  || { echo "FAIL: PVC status=$STATUS (expected Bound)"; exit 1; }

echo "✓ PVC is Bound"

# 7. Deployment exists
kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" >/dev/null 2>&1 \
  || { echo "FAIL: Deployment $DEPLOYMENT not found"; exit 1; }

echo "✓ Deployment exists"

# 8. Deployment uses the PVC
CLAIM=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" \
  -o jsonpath='{.spec.template.spec.volumes[*].persistentVolumeClaim.claimName}')

echo "$CLAIM" | grep -qw "$PVC_NAME" \
  || { echo "FAIL: Deployment does not reference PVC $PVC_NAME"; exit 1; }

echo "✓ Deployment uses PVC"

# 9. Deployment stability
READY=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" \
  -o jsonpath='{.status.readyReplicas}')

DESIRED=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" \
  -o jsonpath='{.spec.replicas}')

[ "$READY" = "$DESIRED" ] \
  || { echo "FAIL: Deployment not stable (ready=$READY desired=$DESIRED)"; exit 1; }

echo "✓ Deployment is running and stable"

echo "SUCCESS: MariaDB deployment successfully restored with preserved data"
