#!/bin/bash

set -e

NAMESPACE="echo-sound"
SERVICE="echo-service"
INGRESS="echo"
EXPECTED_PORT=8080
EXPECTED_HOST="example.org"
EXPECTED_PATH="/echo"

echo "Validating Service: $SERVICE"

# Check Service exists
kubectl get svc "$SERVICE" -n "$NAMESPACE" >/dev/null 2>&1 \
  || { echo "FAIL: Service $SERVICE not found"; exit 1; }

# Validate Service type
TYPE=$(kubectl get svc "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.spec.type}')
[ "$TYPE" = "NodePort" ] \
  || { echo "FAIL: Service type is $TYPE (expected NodePort)"; exit 1; }

# Validate Service port
PORT=$(kubectl get svc "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}')
[ "$PORT" = "$EXPECTED_PORT" ] \
  || { echo "FAIL: Service port is $PORT (expected $EXPECTED_PORT)"; exit 1; }

# Validate NodePort assigned
NODEPORT=$(kubectl get svc "$SERVICE" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}')
[ -n "$NODEPORT" ] \
  || { echo "FAIL: NodePort not assigned"; exit 1; }

echo "Service validation PASSED (NodePort=$NODEPORT)"

echo "Validating Ingress: $INGRESS"

# Check Ingress exists
kubectl get ingress "$INGRESS" -n "$NAMESPACE" >/dev/null 2>&1 \
  || { echo "FAIL: Ingress $INGRESS not found"; exit 1; }

# Validate host
HOST=$(kubectl get ingress "$INGRESS" -n "$NAMESPACE" \
  -o jsonpath='{.spec.rules[0].host}')
[ "$HOST" = "$EXPECTED_HOST" ] \
  || { echo "FAIL: Ingress host is $HOST (expected $EXPECTED_HOST)"; exit 1; }

# Validate path
PATH_VALUE=$(kubectl get ingress "$INGRESS" -n "$NAMESPACE" \
  -o jsonpath='{.spec.rules[0].http.paths[0].path}')
[ "$PATH_VALUE" = "$EXPECTED_PATH" ] \
  || { echo "FAIL: Ingress path is $PATH_VALUE (expected $EXPECTED_PATH)"; exit 1; }

# Validate backend service
BACKEND_SVC=$(kubectl get ingress "$INGRESS" -n "$NAMESPACE" \
  -o jsonpath='{.spec.rules[0].http.paths[0].backend.service.name}')
[ "$BACKEND_SVC" = "$SERVICE" ] \
  || { echo "FAIL: Backend service is $BACKEND_SVC (expected $SERVICE)"; exit 1; }

# Validate backend port
BACKEND_PORT=$(kubectl get ingress "$INGRESS" -n "$NAMESPACE" \
  -o jsonpath='{.spec.rules[0].http.paths[0].backend.service.port.number}')
[ "$BACKEND_PORT" = "$EXPECTED_PORT" ] \
  || { echo "FAIL: Backend port is $BACKEND_PORT (expected $EXPECTED_PORT)"; exit 1; }

echo "Ingress validation PASSED"

echo "SUCCESS: All Ingress requirements validated"
