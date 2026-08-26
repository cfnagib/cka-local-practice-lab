#!/bin/bash

# Validator script for Question: SideCar
# Validates the wordpress deployment configuration

set -e

DEPLOYMENT="wordpress"
NAMESPACE="default"
PASS=true

# Check if deployment exists
if ! kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" >/dev/null 2>&1; then
  echo "❌ Deployment '$DEPLOYMENT' not found in namespace '$NAMESPACE'"
  exit 1
fi

# Check for sidecar container
if ! kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[*].name}' | grep -qw "sidecar"; then
  echo "❌ Sidecar container 'sidecar' not found in deployment"
  PASS=false
fi

# Check image of sidecar
IMAGE=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[?(@.name=="sidecar")].image}')
if [[ "$IMAGE" != "busybox:stable" ]]; then
  echo "❌ Sidecar image should be 'busybox:stable' but found '$IMAGE'"
  PASS=false
fi

# Check command
CMD=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[?(@.name=="sidecar")].command}')
if [[ "$CMD" != *"/bin/sh"* || "$CMD" != *"tail -f /var/log/wordpress.log"* ]]; then
  echo "❌ Sidecar command incorrect. Expected: '/bin/sh -c tail -f /var/log/wordpress.log'"
  PASS=false
fi

# Check volume mounts for /var/log
MOUNT_PATH=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[?(@.name=="sidecar")].volumeMounts[*].mountPath}')
if [[ "$MOUNT_PATH" != *"/var/log"* ]]; then
  echo "❌ Sidecar does not have /var/log volume mounted"
  PASS=false
fi

# Check that the main container also mounts /var/log (shared volume)
MAIN_MOUNT=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[?(@.name!="sidecar")].volumeMounts[*].mountPath}')
if [[ "$MAIN_MOUNT" != *"/var/log"* ]]; then
  echo "❌ Main container does not share /var/log volume with sidecar"
  PASS=false
fi

# Check that volume exists in pod spec
VOLUME=$(kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.volumes[*].name}')
if [[ -z "$VOLUME" ]]; then
  echo "❌ No volume defined in pod spec"
  PASS=false
fi

if [[ "$PASS" == true ]]; then
  echo "✅ Validation Passed: Sidecar container correctly configured in $DEPLOYMENT"
  exit 0
else
  echo "❌ Validation Failed: Please review the errors above."
  exit 1
fi
