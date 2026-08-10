#!/bin/bash
# Deliver desktop-hook queue messages under a user LaunchAgent, not Codex Desktop.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../config.env"
QUEUE="${IMSG_CODEX_QUEUE_DIR:-$HERE/../state/desktop-notify}"
INTERVAL="${IMSG_CODEX_NOTIFY_INTERVAL:-2}"
mkdir -p "$QUEUE"
while true; do
  for pending in "$QUEUE"/*.msg; do
    [ -f "$pending" ] || continue
    claimed="${pending%.msg}.sending"
    mv "$pending" "$claimed" 2>/dev/null || continue
    message="$(<"$claimed")"
    if "$HERE/../bin/send.sh" "$message" >/dev/null 2>&1; then rm -f "$claimed"; else mv "$claimed" "$pending" 2>/dev/null || true; fi
  done
  sleep "$INTERVAL"
done
