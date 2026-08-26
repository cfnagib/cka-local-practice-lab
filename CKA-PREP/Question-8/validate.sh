#!/bin/bash

set -e

CRD_LIST_FILE="/root/resources.yaml"
SUBJECT_FILE="/root/subject.yaml"
CERT_CRD="certificates.cert-manager.io"

echo "Validating CRD documentation task..."

# 1. Validate CRD list file exists
[ -f "$CRD_LIST_FILE" ] \
  || { echo "FAIL: $CRD_LIST_FILE does not exist"; exit 1; }

echo "✓ CRD list file exists"

# 2. Validate cert-manager CRDs listed
grep -q "cert-manager.io" "$CRD_LIST_FILE" \
  || { echo "FAIL: $CRD_LIST_FILE does not contain cert-manager CRDs"; exit 1; }

echo "✓ cert-manager CRDs present in resources.yaml"

# Optional: verify known CRDs are included
KNOWN_CRDS=(
  "certificates.cert-manager.io"
  "issuers.cert-manager.io"
  "clusterissuers.cert-manager.io"
  "certificaterequests.cert-manager.io"
)

for crd in "${KNOWN_CRDS[@]}"; do
  grep -q "$crd" "$CRD_LIST_FILE" \
    || echo "WARN: $crd not found in resources.yaml"
done

# 3. Validate subject.yaml exists
[ -f "$SUBJECT_FILE" ] \
  || { echo "FAIL: $SUBJECT_FILE does not exist"; exit 1; }

echo "✓ subject.yaml exists"

# 4. Validate subject spec documentation
grep -Eiq "subject" "$SUBJECT_FILE" \
  || { echo "FAIL: subject.yaml does not reference subject field"; exit 1; }

grep -Eiq "(commonName|organizations|countries|localities)" "$SUBJECT_FILE" \
  || { echo "FAIL: subject.yaml does not appear to document Certificate spec.subject"; exit 1; }

echo "✓ subject field documentation detected"

# 5. Validate source CRD exists in cluster
kubectl get crd "$CERT_CRD" >/dev/null 2>&1 \
  || { echo "FAIL: Certificate CRD not found in cluster"; exit 1; }

echo "✓ Certificate CRD exists"

echo "SUCCESS: CRD task validation PASSED"
