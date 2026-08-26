#!/bin/bash
set -e

NAMESPACE="web-app"
GATEWAY_NAME="web-gateway"
HTTPROUTE_NAME="web-route"
GATEWAY_CLASS="nginx-class"
HOSTNAME="gateway.web.k8s.local"
SERVICE_NAME="web-service"
SERVICE_PORT=80
TLS_SECRET="web-tls"

echo "🔍 Validating Kubernetes Gateway API migration..."

# 1. Verify Gateway exists
echo "Checking Gateway resource $GATEWAY_NAME..."
kubectl get gateway $GATEWAY_NAME -n $NAMESPACE >/dev/null || { echo "Gateway $GATEWAY_NAME does not exist in namespace $NAMESPACE"; exit 1; }

# 2. Check GatewayClass
echo "Validating GatewayClass on Gateway..."
gc=$(kubectl get gateway $GATEWAY_NAME -n $NAMESPACE -o jsonpath='{.spec.gatewayClassName}')
if [ "$gc" != "$GATEWAY_CLASS" ]; then
  echo "GatewayClass mismatch: expected $GATEWAY_CLASS, got $gc"
  exit 1
fi

# 3. Check Gateway listeners - one listener for HTTPS on port 443 with hostname and TLS secret
echo "Validating Gateway listeners..."
listener_count=$(kubectl get gateway $GATEWAY_NAME -n $NAMESPACE -o json | jq '.spec.listeners | length')
if [ "$listener_count" -eq 0 ]; then
  echo "No listeners configured on Gateway"
  exit 1
fi

https_listener=$(kubectl get gateway $GATEWAY_NAME -n $NAMESPACE -o json | jq -c '.spec.listeners[] | select(.protocol=="HTTPS") | {hostname,port,tls}')
if [ -z "$https_listener" ]; then
  echo "No HTTPS listener found on Gateway"
  exit 1
fi

listener_hostname=$(echo $https_listener | jq -r '.hostname')
if [ "$listener_hostname" != "$HOSTNAME" ]; then
  echo "Listener hostname mismatch: expected $HOSTNAME, got $listener_hostname"
  exit 1
fi

listener_port=$(echo $https_listener | jq -r '.port')
if [ "$listener_port" != "443" ]; then
  echo "Listener port mismatch: expected 443, got $listener_port"
  exit 1
fi

tls_secret_name=$(echo $https_listener | jq -r '.tls.certificateRefs[0].name')
if [ "$tls_secret_name" != "$TLS_SECRET" ]; then
  echo "TLS secret name mismatch: expected $TLS_SECRET, got $tls_secret_name"
  exit 1
fi

# 4. Verify HTTPRoute exists
echo "Checking HTTPRoute resource $HTTPROUTE_NAME..."
kubectl get httproute $HTTPROUTE_NAME -n $NAMESPACE >/dev/null || { echo "HTTPRoute $HTTPROUTE_NAME does not exist in namespace $NAMESPACE"; exit 1; }

# 5. Validate HTTPRoute hostname
echo "Validating HTTPRoute hostnames..."
route_hosts=$(kubectl get httproute $HTTPROUTE_NAME -n $NAMESPACE -o jsonpath='{.spec.hostnames[*]}')
if [[ ! " $route_hosts " =~ " $HOSTNAME " ]]; then
  echo "HTTPRoute does not contain hostname $HOSTNAME"
  exit 1
fi

# 6. Validate HTTPRoute backend service and port
echo "Validating HTTPRoute backend references..."
backend_service=$(kubectl get httproute $HTTPROUTE_NAME -n $NAMESPACE -o jsonpath='{.spec.rules[0].backendRefs[0].name}')
backend_port=$(kubectl get httproute $HTTPROUTE_NAME -n $NAMESPACE -o jsonpath='{.spec.rules[0].backendRefs[0].port}')
if [ "$backend_service" != "$SERVICE_NAME" ]; then
  echo "HTTPRoute backend service mismatch: expected $SERVICE_NAME, got $backend_service"
  exit 1
fi
if [ "$backend_port" != "$SERVICE_PORT" ]; then
  echo "HTTPRoute backend port mismatch: expected $SERVICE_PORT, got $backend_port"
  exit 1
fi

echo "✅ All Gateway API migration validations passed."
