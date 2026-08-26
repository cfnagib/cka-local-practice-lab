#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/config.env"
SSH_USER="${SSH_USER:?Set SSH_USER in config.env}"
CONTROL_IP="${CONTROL_IP:?Set CONTROL_IP to the control-plane IP}"
WORKER1_IP="${WORKER1_IP:?Set WORKER1_IP to the first worker IP}"
WORKER2_IP="${WORKER2_IP:?Set WORKER2_IP to the second worker IP}"
SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

remote() {
  local ip="$1"
  shift
  ssh "${SSH_OPTS[@]}" "$SSH_USER@$ip" "$@"
}

install_node() {
  local ip="$1"
  echo "Installing Kubernetes prerequisites on $ip"
  remote "$ip" 'bash -s' <<'NODE_SCRIPT'
set -euo pipefail
sudo swapoff -a
sudo sed -i.bak '/\sswap\s/s/^/#/' /etc/fstab
sudo modprobe overlay
sudo modprobe br_netfilter
cat <<'SYSCTL' | sudo tee /etc/sysctl.d/99-kubernetes-cka.conf >/dev/null
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
SYSCTL
sudo sysctl --system >/dev/null
sudo apt-get update
sudo apt-get install -y ca-certificates curl gpg apt-transport-https containerd
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | sudo gpg --dearmor --yes -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list >/dev/null
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
sudo systemctl enable kubelet
NODE_SCRIPT
}

install_node "$CONTROL_IP"
install_node "$WORKER1_IP"
install_node "$WORKER2_IP"

echo "Installing Helm on the control plane"
remote "$CONTROL_IP" 'sudo snap install helm --classic 2>/dev/null || sudo apt-get install -y helm'

echo "Initializing control plane"
remote "$CONTROL_IP" 'sudo kubeadm init --pod-network-cidr=10.244.0.0/16'
remote "$CONTROL_IP" 'mkdir -p "$HOME/.kube" && sudo cp /etc/kubernetes/admin.conf "$HOME/.kube/config" && sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"'

echo "Installing Calico CNI"
remote "$CONTROL_IP" 'curl -fsSL https://raw.githubusercontent.com/projectcalico/calico/v3.29.2/manifests/calico.yaml | sed "s#192\\.168\\.0\\.0/16#10.244.0.0/16#g" | kubectl apply -f -'
JOIN_COMMAND="$(remote "$CONTROL_IP" 'sudo kubeadm token create --print-join-command')"
echo "Joining worker nodes"
remote "$WORKER1_IP" "sudo $JOIN_COMMAND"
remote "$WORKER2_IP" "sudo $JOIN_COMMAND"

echo "Bootstrap complete"
remote "$CONTROL_IP" 'kubectl get nodes -o wide'
