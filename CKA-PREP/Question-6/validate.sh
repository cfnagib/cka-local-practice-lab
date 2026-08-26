#!/bin/bash
# Validator script for the "high-priority" PriorityClass CKA task
# Tasks checked:
# 1. Ensure PriorityClass 'high-priority' exists.
# 2. Ensure its value = (max existing user-defined PriorityClass value) - 1.
# 3. Ensure deployment 'busybox-logger' in 'priority' namespace uses it.

set -e

DEPLOYMENT="busybox-logger"
NAMESPACE="priority"
PC_NAME="high-priority"

echo "🔍 Validating PriorityClass and Deployment setup..."

# Get all user-defined PriorityClasses (exclude system ones)
user_pcs=$(kubectl get priorityclass -o jsonpath='{range .items[*]}{.metadata.name}{"="}{.value}{"\n"}{end}' | grep -vE 'system-cluster-critical|system-node-critical' || true)

if [[ -z "$user_pcs" ]]; then
  echo "❌ No user-defined PriorityClasses found in cluster."
  exit 1
fi

# Find highest value among user-defined PCs
highest_value=$(echo "$user_pcs" | awk -F= '{print $2}' | sort -nr | head -1)

# Verify 'high-priority' exists
if ! kubectl get priorityclass "$PC_NAME" &>/dev/null; then
  echo "❌ PriorityClass '$PC_NAME' not found."
  exit 1
fi

# Get its value
pc_value=$(kubectl get priorityclass "$PC_NAME" -o jsonpath='{.value}')

# Expected = highest - 1
expected_value=$((highest_value - 1))

if [[ "$pc_value" -ne "$expected_value" ]]; then
  echo "❌ '$PC_NAME' has value $pc_value, expected $expected_value (one less than highest user-defined PC: $highest_value)."
  exit 1
else
  echo "✅ '$PC_NAME' value is correct: $pc_value (one less than $highest_value)."
fi

# Verify Deployment uses this PriorityClass
if ! kubectl get deploy "$DEPLOYMENT" -n "$NAMESPACE" &>/dev/null; then
  echo "❌ Deployment '$DEPLOYMENT' not found in namespace '$NAMESPACE'."
  exit 1
fi

dep_pc=$(kubectl get deploy "$DEPLOYMENT" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.priorityClassName}')

if [[ "$dep_pc" != "$PC_NAME" ]]; then
  echo "❌ Deployment '$DEPLOYMENT' in '$NAMESPACE' uses '$dep_pc', expected '$PC_NAME'."
  exit 1
else
  echo "✅ Deployment '$DEPLOYMENT' in '$NAMESPACE' uses the correct PriorityClass: $dep_pc"
fi

echo "🎉 All validations passed successfully!"
exit 0
