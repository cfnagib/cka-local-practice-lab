#!/bin/bash
# Validator script for StorageClass CKA task
# Checks:
# 1. StorageClass named 'local-storage' exists
# 2. provisioner = rancher.io/local-path
# 3. volumeBindingMode = WaitForFirstConsumer
# 4. Is default
# 5. No other SCs are default

set -e

SC_NAME="local-storage"

echo "🔍 Validating StorageClass configuration..."

# Check if StorageClass exists
if ! kubectl get sc "$SC_NAME" &>/dev/null; then
  echo "❌ StorageClass '$SC_NAME' does not exist."
  exit 1
fi

# Check provisioner
provisioner=$(kubectl get sc "$SC_NAME" -o jsonpath='{.provisioner}')
if [[ "$provisioner" != "rancher.io/local-path" ]]; then
  echo "❌ Provisioner is '$provisioner', expected 'rancher.io/local-path'."
  exit 1
else
  echo "✅ Provisioner is correct: $provisioner"
fi

# Check VolumeBindingMode
mode=$(kubectl get sc "$SC_NAME" -o jsonpath='{.volumeBindingMode}')
if [[ "$mode" != "WaitForFirstConsumer" ]]; then
  echo "❌ VolumeBindingMode is '$mode', expected 'WaitForFirstConsumer'."
  exit 1
else
  echo "✅ VolumeBindingMode is correct: $mode"
fi

# Check default annotation
default_annotation=$(kubectl get sc "$SC_NAME" -o jsonpath='{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}')
if [[ "$default_annotation" != "true" ]]; then
  echo "❌ StorageClass '$SC_NAME' is not set as default."
  exit 1
else
  echo "✅ '$SC_NAME' is marked as the default StorageClass."
fi

# Ensure no other default SCs exist
other_defaults=$(kubectl get sc -o jsonpath='{range .items[*]}{.metadata.name}{"="}{.metadata.annotations.storageclass\.kubernetes\.io/is-default-class}{"\n"}{end}' | grep "=true" | grep -v "^$SC_NAME=" || true)

if [[ -n "$other_defaults" ]]; then
  echo "❌ Another StorageClass is also marked as default:"
  echo "$other_defaults"
  exit 1
else
  echo "✅ '$SC_NAME' is the only default StorageClass."
fi

echo "🎉 All validations passed successfully!"
exit 0
