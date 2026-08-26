#!/bin/bash

# Validator script for Question-1: Install Argo CD using Helm without CRDs

# Check 1: Verify Argo CD Helm repository is added
echo "Checking if argocd Helm repository is added..."
helm_repo_list=$(helm repo list)
if echo "${helm_repo_list}" | grep -q "argocd.*https://argoproj.github.io/argo-helm"; then
    echo "  [PASS] Argo CD Helm repository 'argocd' is added."
    repo_added=true
else
    echo "  [FAIL] Argo CD Helm repository 'argocd' is NOT added."
    repo_added=false
fi

# Check 2: Verify /root/argo-helm.yaml file exists
echo "Checking if /root/argo-helm.yaml exists..."
if [ -f "/root/argo-helm.yaml" ]; then
    echo "  [PASS] /root/argo-helm.yaml file exists."
    file_exists=true
else
    echo "  [FAIL] /root/argo-helm.yaml file does NOT exist."
    file_exists=false
fi

# Check 3: Verify the content of /root/argo-helm.yaml
#   - Is a Helm template for Argo CD version 7.7.3
#   - Does not contain CRDs (e.g., "apiVersion: apiextensions.k8s.io/v1" or "kind: CustomResourceDefinition")
echo "Checking the content of /root/argo-helm.yaml..."
if ${file_exists}; then
    # Check for Argo CD chart version 7.7.3 (this is a heuristic, as the generated YAML itself doesn't explicitly state the chart version)
    # We will look for common annotations or labels that might indicate the chart version.
    # A more robust check would involve re-templating and comparing, which is out of scope for a simple validator.
    # For now, we'll check for the absence of CRDs and a general helm-generated structure.

    # Check for absence of CRDs
    if ! grep -q "kind: CustomResourceDefinition" "/root/argo-helm.yaml" && \
       ! grep -q "apiextensions.k8s.io/v1" "/root/argo-helm.yaml"; then
        echo "  [PASS] /root/argo-helm.yaml does NOT contain CustomResourceDefinitions."
        no_crds=true
    else
        echo "  [FAIL] /root/argo-helm.yaml contains CustomResourceDefinitions."
        no_crds=false
    fi

    # Further checks could include looking for specific Argo CD resources
    # This part is complex to validate perfectly without running 'helm template' and comparing outputs.
    # For now, we will assume if CRDs are not present and the file exists, it's a good start.

    # A very basic check to see if it looks like a Helm output for argocd
    if grep -q "app.kubernetes.io/instance: argocd" "/root/argo-helm.yaml" && \
       grep -q "app.kubernetes.io/managed-by: Helm" "/root/argo-helm.yaml"; then
        echo "  [PASS] /root/argo-helm.yaml appears to be a Helm-generated manifest for Argo CD."
        helm_manifest=true
    else
        echo "  [FAIL] /root/argo-helm.yaml does NOT appear to be a Helm-generated manifest for Argo CD."
        helm_manifest=false
    fi

else
    echo "  [SKIP] Skipping content check as /root/argo-helm.yaml does not exist."
    no_crds=false
    helm_manifest=false
fi

echo -e "\n--- Overall Result ---"
if ${repo_added} && ${file_exists} && ${no_crds} && ${helm_manifest}; then
    echo "  [SUCCESS] All checks passed for Question-1!"
    exit 0
else
    echo "  [FAILURE] One or more checks failed for Question-1."
    exit 1
fi
