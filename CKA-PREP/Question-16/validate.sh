#!/bin/bash
set -e

DEPLOYMENT="nodeport-deployment"
SERVICE="nodeport-service"
EXPECTED_NODEPORT="30080"
EXPECTED_PORT="80"

echo "Starting NodePort validation..."

# -------------------------------------------------
# 1. Deployment exists (any namespace)
# -------------------------------------------------
NS=$(kubectl get deploy -A --no-headers | awk '$2=="'"$DEPLOYMENT"'" {print $1}')

if [ -z "$NS" ]; then
  echo "FAIL: Deployment $DEPLOYMENT not found"
  exit 1
fi

echo "✓ Deployment found in namespace: $NS"

# -------------------------------------------------
# 2. Deployment exposes container port 80/http/TCP
# -------------------------------------------------
kubectl get deploy "$DEPLOYMENT" -n "$NS" -o yaml | grep -q "containerPort: 80" \
  || { echo "FAIL: containerPort 80 not found"; exit 1; }

kubectl get deploy "$DEPLOYMENT" -n "$NS" -o yaml | grep -q "name: http" \
  || { echo "FAIL: port name http not found"; exit 1; }

kubectl get deploy "$DEPLOYMENT" -n "$NS" -o yaml | grep -q "protocol: TCP" \
  || { echo "FAIL: protocol TCP not found"; exit 1; }

echo "✓ Deployment exposes port 80/http/TCP"

# -------------------------------------------------
# 3. Service exists
# -------------------------------------------------
kubectl get svc "$SERVICE" -n "$NS" >/dev/null 2>&1 \
  || { echo "FAIL: Service $SERVICE not found"; exit 1; }

echo "✓ Service exists"

# -------------------------------------------------
# 4. Service type and ports
# -------------------------------------------------
TYPE=$(kubectl get svc "$SERVICE" -n "$NS" -o jsonpath='{.spec.type}')
NODEPORT=$(kubectl get svc "$SERVICE" -n "$NS" -o jsonpath='{.spec.ports[0].nodePort}')
PORT=$(kubectl get svc "$SERVICE" -n "$NS" -o jsonpath='{.spec.ports[0].port}')
TARGETPORT=$(kubectl get svc "$SERVICE" -n "$NS" -o jsonpath='{.spec.ports[0].targetPort}')

[ "$TYPE" = "NodePort" ] || { echo "FAIL: Service is not NodePort"; exit 1; }
[ "$NODEPORT" = "$EXPECTED_NODEPORT" ] || { echo "FAIL: nodePort=$NODEPORT"; exit 1; }
[ "$PORT" = "$EXPECTED_PORT" ] || { echo "FAIL: port=$PORT"; exit 1; }
[ "$TARGETPORT" = "$EXPECTED_PORT" ] || { echo "FAIL: targetPort=$TARGETPORT"; exit 1; }

echo "✓ Service ports correctly configured"

# -------------------------------------------------
# 5. Service actually exposes Pods (CORRECT METHOD)
# -------------------------------------------------
ENDPOINTS=$(kubectl get endpoints "$SERVICE" -n "$NS" -o jsonpath='{.subsets[*].addresses[*].ip}')

if [ -z "$ENDPOINTS" ]; then
  echo "FAIL: Service has no active endpoints (no pods exposed)"
  exit 1
fi

COUNT=$(echo "$ENDPOINTS" | wc -w)

echo "✓ Service exposes $COUNT pod endpoint(s)"

echo
echo "SUCCESS: NodePort configuration is VALID"
