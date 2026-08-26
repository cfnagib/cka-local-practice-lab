# Local Lab Audit

Audit date: 2026-08-26

## Baseline

The baseline snapshot has been verified with three Ready nodes and these tools on
the control plane:

- `kubectl`
- `kubeadm`
- `helm`
- `crictl`

The Pod CIDR is `10.244.0.0/16`, which does not overlap with the libvirt host
network `192.168.122.0/24`.

## Question Inventory

The current practice set contains 17 questions, all from the vendored
`CameronMetcalfe22/CKA-PREP` source. Every question directory includes the task,
setup script, solution notes, and validator file.

| Question | Setup result | Practice status | Notes |
| --- | --- | --- | --- |
| 1 | Passed | Ready | Helm is part of the baseline. |
| 2 | Passed | Ready | Sidecar deployment is created. |
| 3 | Passed | Configuration ready | Gateway API CRDs and a GatewayClass are created; no real Gateway controller is installed. |
| 4 | Passed | Ready | Resource-limit scenario. |
| 5 | Passed | Ready | StorageClass configuration scenario. |
| 6 | Passed | Ready | PriorityClass and deployment are created. |
| 7 | Passed | Configuration ready | Service and Ingress can be created, but end-to-end HTTP routing needs an Ingress controller. |
| 8 | Passed | Ready | cert-manager CRDs are created. |
| 9 | Passed after repair | Ready | Policy files are correctly created under `/root/network-policies`. |
| 10 | Passed | Ready | metrics-server and the Apache target are created. |
| 11 | No setup required by source | Special scenario | The baseline already uses Calico. This is not a clean CNI-install-from-zero scenario. |
| 12 | Passed | Ready | Retained PV recovery scenario. |
| 13 | Passed after repair | Ready | The package is downloaded to `~/cri-dockerd.deb` as required by the task. |
| 14 | Passed | Ready | The setup intentionally breaks the API server for troubleshooting. |
| 15 | Passed | Ready | The local node name is `cka-worker1`, and the task/validator use that name. |
| 16 | Passed | Ready | NodePort deployment scenario. |
| 17 | Passed after repair | Ready | The setup creates the `nginx-service` service named by the task. |

## Repairs Made During This Audit

- Added Helm and `crictl` to the baseline and to future bootstrap builds.
- Reset retains an already active libvirt bridge instead of destroying it.
  If the bridge is inactive, reset starts it safely and waits for it to become
  active before restoring the VMs. This avoids a libvirt start-state race that
  could otherwise cause a dashboard preparation failure.
- The network check captures `virsh net-info` output before inspecting it.
  With Bash `pipefail`, piping that command to `grep -q` can incorrectly fail
  because `grep` closes the pipe as soon as it finds a match.
- Run the dashboard as a systemd user service rather than through `setsid`.
  `setsid` caused domains started after a snapshot restore to be destroyed when
  the reset subprocess ended.
- Fixed Question 9 to write its prepared policy files with the required privileges.
- Fixed Question 13 to place the downloaded package at the task's requested path.
- Adapted Question 15 to the local worker name.
- Fixed the service-name mismatch in Question 17.

## Deliberate Limits

Questions 3 and 7 are suitable for creating and validating the requested
Kubernetes objects, but they do not currently provide data-plane traffic through
a Gateway or Ingress controller. Question 11 is intentionally kept separate from
the normal baseline because replacing a cluster CNI is a disruptive exercise.
