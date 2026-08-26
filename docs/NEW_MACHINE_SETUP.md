# New Machine Setup

This guide recreates the local CKA practice lab from a fresh Ubuntu or Kubuntu
machine. It intentionally does not copy VM disks or snapshots from another
computer. The scripts create the same three-node cluster and a new baseline.

## 1. Clone the project

```bash
git clone https://github.com/cfnagib/cka-local-practice-lab.git
cd cka-local-practice-lab
```

## 2. Install host dependencies

```bash
sudo apt update
sudo apt install -y qemu-system-x86 libvirt-daemon-system libvirt-clients \
  virt-manager virtinst ovmf cloud-image-utils genisoimage curl git
sudo usermod -aG kvm,libvirt "$USER"
sudo systemctl enable --now libvirtd
```

Log out and log in again. If that is not practical immediately, start a new
shell with `newgrp libvirt` before using the lab scripts.

Verify access:

```bash
virsh -c qemu:///system list --all
```

## 3. Create the libvirt image pool

```bash
sudo mkdir -p /var/lib/libvirt/images
sudo virsh pool-define-as default dir --target /var/lib/libvirt/images 2>/dev/null || true
sudo virsh pool-build default 2>/dev/null || true
sudo virsh pool-start default 2>/dev/null || true
sudo virsh pool-autostart default
```

The standard libvirt network named `default` must be active:

```bash
virsh -c qemu:///system net-start default 2>/dev/null || true
virsh -c qemu:///system net-autostart default
```

## 4. Download the VM image

```bash
mkdir -p "$HOME/Documents/CKA-Lab/images"
curl -fL -o "$HOME/Documents/CKA-Lab/images/ubuntu-24.04-server-cloudimg-amd64.img" \
  https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
```

## 5. Configure and build the cluster

```bash
cd lab
cp config.env.example config.env
chmod +x scripts/*.sh
sg libvirt -c './scripts/create-vms.sh'
sg libvirt -c './scripts/bootstrap-k8s.sh'
sg libvirt -c './scripts/snapshot-baseline.sh'
```

The bootstrap creates the cluster with a non-overlapping Pod CIDR
`10.244.0.0/16`, installs Calico, Helm, and `crictl`, and then the snapshot
command creates the powered-off `cka-baseline` restore point.

## 6. Verify the baseline

```bash
sg libvirt -c './scripts/reset-question.sh'
ssh cfnagib@192.168.122.63 'kubectl get nodes'
```

Replace `cfnagib` and the address only if you changed `SSH_USER` or the static
addresses in `lab/config.env`.

## 7. Install and use the dashboard

From the project root:

```bash
chmod +x dashboard/*.sh
./dashboard/install-launcher.sh
```

Open **CKA Local Practice** from the application menu. The dashboard uses
`http://127.0.0.1:8790` and its terminal WebSocket uses port `8791`; these do
not conflict with CK-X on port `30080`.

## What GitHub does and does not contain

- GitHub contains the scripts, dashboard, question bank, fixes, and documents.
- GitHub does not contain the Ubuntu cloud image, VM disks, libvirt network
  state, container images, or baseline snapshots. They are host-specific and
  are recreated by the steps above.
