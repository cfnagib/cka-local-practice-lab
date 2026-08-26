#!/usr/bin/env bash
set -euo pipefail

# A new terminal may not yet have the user's libvirt group in its session.
# Re-exec once through sg so the normal practice command still works.
if [[ "${CKA_LIBVIRT_REEXEC:-0}" != 1 ]] && ! virsh -c qemu:///system list --all >/dev/null 2>&1; then
  exec sg libvirt -c "CKA_LIBVIRT_REEXEC=1 bash '$0' '${1:-}'"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/config.env"
QUESTION="${1:-}"

if [[ -z "$QUESTION" ]]; then
  read -r -p "Question number (1-17): " QUESTION
fi
[[ "$QUESTION" =~ ^([1-9]|1[0-7])$ ]] || { echo "Choose a question from 1 to 17."; exit 1; }

REMOTE_DIR="/tmp/cka-question-$QUESTION"
echo "Resetting lab to baseline..."
"$ROOT_DIR/scripts/reset-question.sh"
echo "Preparing Question $QUESTION..."
"$ROOT_DIR/scripts/run-question.sh" "$QUESTION"
echo
echo "Opening the exam terminal. The question will be printed last, directly above the prompt."
# Recover the local terminal if a previous SSH session was interrupted.
# Disable Ctrl-S/Ctrl-Q terminal flow control; it can make input appear frozen.
stty sane -ixon -ixoff 2>/dev/null || true
ssh -tt -o RequestTTY=force -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$CONTROL_IP" \
  "stty sane -ixon -ixoff; printf '\\n================ QUESTION $QUESTION ================\\n'; cat '$REMOTE_DIR/Questions.bash' 2>/dev/null || cat '$REMOTE_DIR/Question.bash'; printf '\\n=====================================================\\n\\n'; exec bash -i"
stty sane -ixon -ixoff 2>/dev/null || true

echo
echo "What next?"
echo "  v = validate"
echo "  h = show hints"
echo "  s = show solution notes"
echo "  r = reset this lab"
echo "  q = quit"
read -r -p "> " action
case "$action" in
  v) "$ROOT_DIR/scripts/validate-question.sh" "$QUESTION" ;;
  h) ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$CONTROL_IP" "sed -n '1,25p' '$REMOTE_DIR/SolutionNotes.bash'" ;;
  s) ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_USER@$CONTROL_IP" "cat '$REMOTE_DIR/SolutionNotes.bash'" ;;
  r) "$ROOT_DIR/scripts/reset-question.sh" ;;
  q) echo "Leaving the lab unchanged." ;;
  *) echo "Unknown option."; exit 1 ;;
esac
