#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT_DIR/config.env"
if [[ ! -f "$CONFIG" ]]; then
  cp "$ROOT_DIR/config.env.example" "$CONFIG"
  echo "Created $CONFIG; review it and run this script again."
  exit 0
fi
source "$CONFIG"

command -v virsh >/dev/null || { echo "virsh is required"; exit 1; }
command -v virt-install >/dev/null || { echo "virt-install is required"; exit 1; }
command -v cloud-localds >/dev/null || { echo "cloud-localds is required"; exit 1; }
command -v qemu-img >/dev/null || { echo "qemu-img is required"; exit 1; }
[[ -f "$IMAGE" ]] || { echo "Ubuntu image not found: $IMAGE"; exit 1; }

LAB_STATE="/var/lib/libvirt/images/cka-lab"
LIBVIRT_IMAGE_DIR="/var/lib/libvirt/images"
BASE_IMAGE="$LIBVIRT_IMAGE_DIR/cka-ubuntu-24.04-base.img"
sudo mkdir -p "$LAB_STATE"
sudo chown "$USER:libvirt" "$LAB_STATE"
sudo chmod 0775 "$LAB_STATE"

if [[ ! -f "$HOME/.ssh/id_ed25519.pub" ]]; then
  ssh-keygen -t ed25519 -N '' -f "$HOME/.ssh/id_ed25519"
fi
SSH_KEY="$(cat "$HOME/.ssh/id_ed25519.pub")"

if [[ ! -f "$BASE_IMAGE" ]]; then
  echo "Installing the base image into libvirt storage..."
  sudo install -m 0644 "$IMAGE" "$BASE_IMAGE"
fi

create_vm() {
  local name="$1"
  local disk="$LAB_STATE/${name}.qcow2"
  local seed_dir="$LAB_STATE/${name}-seed"
  local seed="$LAB_STATE/${name}-seed.iso"
  local mac="$2"
  local ip="$3"

  if virsh -c qemu:///system dominfo "$name" >/dev/null 2>&1; then
    echo "$name already exists; skipping"
    return
  fi

  mkdir -p "$seed_dir"
  cat > "$seed_dir/user-data" <<EOF
#cloud-config
hostname: $name
manage_etc_hosts: true
users:
  - name: $USER
    groups: [adm, sudo]
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - $SSH_KEY
ssh_pwauth: false
package_update: true
packages:
  - openssh-server
  - qemu-guest-agent
  - curl
  - vim
  - tmux
  - jq
runcmd:
  - systemctl enable --now ssh
  - systemctl enable --now qemu-guest-agent
EOF
  cat > "$seed_dir/meta-data" <<EOF
instance-id: $name
local-hostname: $name
EOF
  cloud-localds "$seed" "$seed_dir/user-data"
  qemu-img create -f qcow2 -F qcow2 -b "$BASE_IMAGE" "$disk" 40G >/dev/null
  virsh -c qemu:///system net-update "$NETWORK" add ip-dhcp-host "<host mac='$mac' name='$name' ip='$ip'/>" --live --config 2>/dev/null || true
  virt-install \
    --connect qemu:///system \
    --name "$name" \
    --memory "$MEMORY_MB" \
    --vcpus "$VCPUS" \
    --os-variant ubuntu24.04 \
    --import \
    --disk "path=$disk,format=qcow2,bus=virtio" \
    --disk "path=$seed,device=cdrom" \
    --network "network=$NETWORK,model=virtio,mac=$mac" \
    --graphics none \
    --console pty,target_type=serial \
    --noautoconsole
}

create_vm "$CONTROLPLANE" "$CONTROL_MAC" "$CONTROL_IP"
create_vm "$WORKER1" "$WORKER1_MAC" "$WORKER1_IP"
create_vm "$WORKER2" "$WORKER2_MAC" "$WORKER2_IP"
echo "VM creation complete. Run scripts/status.sh to inspect their state."
