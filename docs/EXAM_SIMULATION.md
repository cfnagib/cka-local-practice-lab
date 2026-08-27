# Exam simulation

The dashboard combines an exam-style workflow with explicit training tools.
It mirrors the practical CKA workflow:

- A task panel is shown beside the terminal area. On the local Ubuntu host,
  starting a task opens a native Konsole terminal; this is the preferred
  exam-like terminal. Remote Tailscale sessions retain the embedded fallback.
- The timer counts down from two hours.
- The terminal begins on `cka-base`, not on a Kubernetes node.
- Each task identifies its target host. Use `ssh controlplane`, `ssh worker1`,
  or `ssh worker2` from `cka-base` before working.
- In the native Konsole terminal, copy and paste use `Ctrl+Shift+C` and
  `Ctrl+Shift+V`, matching the CKA terminal. Chrome reserves `Ctrl+Shift+C`
  for Inspect Element, so it cannot faithfully provide that shortcut.

The same screen also exposes explicit learning tools: video links, progressive
hints, per-question validation, saved attempts, solved status, best time, and
a practice report. Those records live in the host user's local state directory,
outside the VM snapshots, so a lab reset never erases them.

## Deliberate limits

This project does not imitate PSI Secure Browser, proctoring, webcam checks,
or the exact Linux Foundation infrastructure. It does recreate the part that
matters for hands-on practice: the base-to-host SSH workflow, a real multi-node
Kubernetes cluster, an exam-style task panel, a terminal, and timed work.

The official CKA ExamUI also provides a remote desktop with Firefox for the
allowed documentation. During a real exam, use only the permitted resources
published by Linux Foundation.
