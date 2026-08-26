# Local CKA Lab

This directory contains repeatable local lab automation for a three-node Ubuntu Server environment managed by libvirt/KVM.

Planned commands:

```bash
./scripts/create-vms.sh
./scripts/start.sh
./scripts/status.sh
./scripts/stop.sh
./scripts/reset.sh
```

The scripts are introduced in stages: first VMs, then Kubernetes, then question setup/validation and the dashboard.
