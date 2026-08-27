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
if [[ ! -d "$LAB_STATE" ]]; then
  sudo mkdir -p "$LAB_STATE"
  sudo chown "$USER:libvirt" "$LAB_STATE"
  sudo chmod 0775 "$LAB_STATE"
fi
[[ -w "$LAB_STATE" ]] || { echo "Lab storage is not writable: $LAB_STATE"; exit 1; }

if [[ ! -f "$HOME/.ssh/id_ed25519.pub" ]]; then
  ssh-keygen -t ed25519 -N '' -f "$HOME/.ssh/id_ed25519"
fi
SSH_KEY="$(cat "$HOME/.ssh/id_ed25519.pub")"
BASE_SSH_KEY_PATH="$LAB_STATE/base_id_ed25519"
if [[ ! -f "$BASE_SSH_KEY_PATH" ]]; then
  ssh-keygen -t ed25519 -N '' -f "$BASE_SSH_KEY_PATH" >/dev/null
fi
BASE_SSH_KEY="$(cat "$BASE_SSH_KEY_PATH.pub")"

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
  local memory="${4:-$MEMORY_MB}"
  local vcpus="${5:-$VCPUS}"
  local base_commands=""
  local base_key_file=""
  local base_write_file=""

  if virsh -c qemu:///system dominfo "$name" >/dev/null 2>&1; then
    echo "$name already exists; skipping"
    return
  fi

  if [[ "$name" == "$BASE" ]]; then
    base_key_file=$(sed 's/^/        /' "$BASE_SSH_KEY_PATH")
    base_write_file=$(cat <<EOF
write_files:
  - path: /etc/cka-base-key
    permissions: '0600'
    content: |
$base_key_file
EOF
)
    base_commands=$(cat <<EOF
  - mkdir -p /home/$USER/.ssh
  - install -m 0600 -o $USER -g $USER /etc/cka-base-key /home/$USER/.ssh/id_ed25519
  - >
    printf '%s\\n' 'Host controlplane' '  HostName $CONTROL_IP' '  User $USER'
    '  StrictHostKeyChecking no' '  UserKnownHostsFile /dev/null' 'Host worker1'
    '  HostName $WORKER1_IP' '  User $USER' '  StrictHostKeyChecking no'
    '  UserKnownHostsFile /dev/null' 'Host worker2' '  HostName $WORKER2_IP'
    '  User $USER' '  StrictHostKeyChecking no' '  UserKnownHostsFile /dev/null'
    > /home/$USER/.ssh/config
  - chown -R $USER:$USER /home/$USER/.ssh
  - chmod 700 /home/$USER/.ssh
  - chmod 600 /home/$USER/.ssh/config
EOF
)
  fi
  mkdir -p "$seed_dir"
  cat > "$seed_dir/user-data" <<EOF
#cloud-config
hostname: $name
manage_etc_hosts: true
$base_write_file
users:
  - name: $USER
    groups: [adm, sudo]
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - $SSH_KEY
      - $BASE_SSH_KEY
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
$base_commands
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
    --memory "$memory" \
    --vcpus "$vcpus" \
    --os-variant ubuntu24.04 \
    --import \
    --disk "path=$disk,format=qcow2,bus=virtio" \
    --disk "path=$seed,device=cdrom" \
    --network "network=$NETWORK,model=virtio,mac=$mac" \
    --graphics none \
    --console pty,target_type=serial \
    --noautoconsole
}

create_vm "$BASE" "$BASE_MAC" "$BASE_IP" 2048 1
create_vm "$CONTROLPLANE" "$CONTROL_MAC" "$CONTROL_IP"
create_vm "$WORKER1" "$WORKER1_MAC" "$WORKER1_IP"
create_vm "$WORKER2" "$WORKER2_MAC" "$WORKER2_IP"
echo "VM creation complete. Run scripts/status.sh to inspect their state."
