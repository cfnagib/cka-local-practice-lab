# CKA Local Practice Lab

This project provides an isolated, repeatable local environment for practical CKA preparation. Kubernetes runs inside KVM/libvirt VMs, so experiments do not affect the host operating system.

## Contents

- `CKA-PREP/`: 17 hands-on CKA practice questions with setup and validation scripts.
- `lab/`: local three-node Kubernetes lab automation.
- `PROJECT.md`: architecture and design decisions.
- `ROADMAP.md`: implementation status and future work.

## New-machine setup

The repository contains automation and documentation, not VM disk images or
libvirt snapshots. Follow [NEW_MACHINE_SETUP.md](docs/NEW_MACHINE_SETUP.md) once
on a new Ubuntu or Kubuntu host to recreate the same environment.

## Local workflow

Run commands from `lab/`:

```bash
sg libvirt -c './scripts/create-vms.sh'
sg libvirt -c './scripts/bootstrap-k8s.sh'
sg libvirt -c './scripts/snapshot-baseline.sh'
./scripts/practice.sh 1
```

For the dashboard launcher, run `./dashboard/install-launcher.sh` once and then
open **CKA Local Practice** from the application menu.

The dashboard restores the baseline, prepares the selected question, and opens
a native Konsole SSH terminal on the base host for local sessions. This gives
you the real Linux terminal clipboard shortcuts (`Ctrl+Shift+C` and
`Ctrl+Shift+V`). It also provides progressive hints, validation,
and a persistent practice report. Progress is stored locally outside the VMs,
so resetting a question never erases solved status, attempts, or recorded time.

See [EXAM_SIMULATION.md](docs/EXAM_SIMULATION.md) for the exam-style workflow.
The dashboard starts on `cka-base`; use SSH aliases to enter the task host,
matching the official CKA workflow while retaining training tools.

## Tailscale access

When Tailscale is installed and connected, launching **CKA Local Practice** also
binds the dashboard to this host's Tailscale IPv4 address. From a Tailscale
connected Mac, open `http://TAILSCALE-IP:8790` in a browser. Remote sessions
continue to use the embedded terminal, while local Ubuntu sessions open the
native Konsole terminal. The dashboard is not exposed on the
public internet or on the ordinary LAN.

## Training method

Read each task first, make a short plan, solve it independently, validate it, and use hints only after an honest attempt. Work through the task in the same order as written. Remember short common commands; use Kubernetes or Helm documentation for long commands and exact flags. These questions are practice patterns, not exam dumps.

## Sources

- [CKA-PREP](https://github.com/CameronMetcalfe22/CKA-PREP)
- [Kubernetes documentation](https://kubernetes.io/docs/)
- [Killer.sh CKA simulator](https://killer.sh/cka)

## Troubleshooting

The libvirt network is `192.168.122.0/24`. The Kubernetes Pod CIDR is intentionally `10.244.0.0/16`; using Calico's default `192.168.0.0/16` overlaps the libvirt subnet and can make ping and SSH fail after Calico starts. Baseline snapshots must be created while VMs are powered off. Check `domstate`, `domifaddr`, ping, and SSH in that order.

## Coaching rules

The assistant should explain the task first, then guide one part at a time in the order written. It should provide progressive hints rather than complete solutions, explain what to search for in documentation, and wait for validation before moving to the next part.
