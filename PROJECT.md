# Project Specification

## Goal

Build a free, isolated, repeatable local CKA practice environment on Kubuntu. The user selects a question, receives a ready cluster, solves it in a fast terminal, validates the result, and resets the lab without manual Kubernetes setup.

## Architecture

- Three Ubuntu Server VMs managed by KVM/QEMU and libvirt.
- Kubernetes installed with kubeadm.
- containerd as the container runtime.
- Calico CNI using Pod CIDR `10.244.0.0/16`.
- libvirt NAT network `192.168.122.0/24`.
- VM disks under `/var/lib/libvirt/images`; project files remain in Google Drive.

## Daily workflow

1. Start or verify the VMs.
2. Run `practice.sh <question-number>`.
3. Solve in the control-plane terminal.
4. Validate, request a hint, or reset.

## Safety and recovery

VMs isolate kubelet, containerd, systemd, and kubeadm experiments from the host. A powered-off baseline snapshot is restored before each question. The reset script performs a clean cold boot and waits for Kubernetes readiness.

## Question bank

The initial bank is `CKA-PREP`, containing 17 questions with task text, setup scripts, validation scripts, and solution notes. It is a practice bank and does not guarantee coverage of every exam variation.

## Performance

Use KVM, virtio disks and networking, and local SSD storage. Keep VM disks outside Google Drive synchronization. Use a terminal for learning and reserve graphical remote-desktop simulation for later mock-exam work.

## Future work

- Add a local dashboard with Start, Validate, Reset, and Hint controls.
- Normalize all questions into a common metadata format.
- Add more node-level troubleshooting scenarios.
- Add timed mock-exam mode and progress tracking.
