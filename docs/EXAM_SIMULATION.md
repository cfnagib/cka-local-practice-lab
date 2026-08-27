# Exam simulation

The dashboard has two intentionally separate modes.

## Exam Simulation

This is the default mode. It mirrors the practical CKA workflow:

- A task panel and a remote terminal are shown side by side.
- The timer counts down from two hours.
- The terminal begins on `cka-base`, not on a Kubernetes node.
- Each task identifies its target host. Use `ssh controlplane`, `ssh worker1`,
  or `ssh worker2` from `cka-base` before working.
- Video links, hints, validation, and the training report are hidden.
- Terminal copy and paste use `Ctrl+Shift+C` and `Ctrl+Shift+V`.

## Practice Mode

Practice Mode keeps the same lab but exposes the learning tools: progressive
hints, per-question validation, saved attempts, solved status, and best time.
Those records live in the host user's local state directory, outside the VM
snapshots, so a lab reset never erases them.

## Deliberate limits

This project does not imitate PSI Secure Browser, proctoring, webcam checks,
or the exact Linux Foundation infrastructure. It does recreate the part that
matters for hands-on practice: the base-to-host SSH workflow, a real multi-node
Kubernetes cluster, an exam-style task panel, a terminal, and timed work.

The official CKA ExamUI also provides a remote desktop with Firefox for the
allowed documentation. During a real exam, use only the permitted resources
published by Linux Foundation.
