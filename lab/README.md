# Local CKA Lab

This directory contains repeatable local lab automation for a three-node Ubuntu Server environment managed by libvirt/KVM.

## Network design and the reset fix

The libvirt network is `192.168.122.0/24`. The Kubernetes Pod CIDR must not overlap it; the bootstrap script therefore uses `10.244.0.0/16` for Pods and rewrites the Calico pool to the same range. Using Calico's default `192.168.0.0/16` overlaps the libvirt subnet and can make SSH/ping disappear after Calico starts.

The baseline snapshot must be created with all VMs powered off. `snapshot-baseline.sh` enforces this, and `reset-question.sh` performs a clean cold boot. If connectivity is ever lost, diagnose in this order: `virsh domstate`, `virsh domifaddr`, `ping`, then SSH. A DHCP lease alone does not prove that traffic is flowing.

Planned commands:

```bash
./scripts/create-vms.sh
./scripts/start.sh
./scripts/status.sh
./scripts/stop.sh
./scripts/reset.sh
```

The scripts are introduced in stages: first VMs, then Kubernetes, then question setup/validation and the dashboard.
