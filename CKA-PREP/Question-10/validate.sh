#!/bin/bash

set -e

HPA_NAME="apache-server"
NAMESPACE="autoscale"
TARGET_DEPLOYMENT="apache-deployment"
MIN_REPLICAS=1
MAX_REPLICAS=4
CPU_TARGET=50
DOWNSCALE_WINDOW=30

echo "Validating HorizontalPodAutoscaler configuration..."

# 1. HPA exists
kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" >/dev/null 2>&1 \
  || { echo "FAIL: HPA $HPA_NAME not found in namespace $NAMESPACE"; exit 1; }

echo "✓ HPA exists"

# 2. Target deployment
TARGET=$(kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.spec.scaleTargetRef.name}')

[ "$TARGET" = "$TARGET_DEPLOYMENT" ] \
  || { echo "FAIL: Target is $TARGET (expected $TARGET_DEPLOYMENT)"; exit 1; }

echo "✓ Targets correct Deployment"

# 3. Min replicas
MIN=$(kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.spec.minReplicas}')

[ "$MIN" = "$MIN_REPLICAS" ] \
  || { echo "FAIL: minReplicas=$MIN (expected $MIN_REPLICAS)"; exit 1; }

echo "✓ minReplicas correct"

# 4. Max replicas
MAX=$(kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.spec.maxReplicas}')

[ "$MAX" = "$MAX_REPLICAS" ] \
  || { echo "FAIL: maxReplicas=$MAX (expected $MAX_REPLICAS)"; exit 1; }

echo "✓ maxReplicas correct"

# 5. CPU utilization target
CPU=$(kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')

[ "$CPU" = "$CPU_TARGET" ] \
  || { echo "FAIL: CPU target=$CPU (expected $CPU_TARGET)"; exit 1; }

echo "✓ CPU utilization target correct"

# 6. Downscale stabilization window
WINDOW=$(kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" \
  -o jsonpath='{.spec.behavior.scaleDown.stabilizationWindowSeconds}')

[ "$WINDOW" = "$DOWNSCALE_WINDOW" ] \
  || { echo "FAIL: Downscale window=$WINDOW (expected $DOWNSCALE_WINDOW)"; exit 1; }

echo "✓ Downscale stabilization window correct"

echo "SUCCESS: HPA validation PASSED"
