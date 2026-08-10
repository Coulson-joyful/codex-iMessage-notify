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
    message=""
    IFS= read -r -d '' message < "$claimed" || true
    target="${IMSG_NOTIFY_TO:-${IMSG_REPLY_TO:-}}"
    chunk_size="${IMSG_CODEX_CHUNK_SIZE:-1200}"
    max_chunks="${IMSG_CODEX_MAX_CHUNKS:-20}"
    delivered=1
    while IFS= read -r -d '' chunk; do
      "$HERE/../bin/send.sh" "$target" "$chunk" >/dev/null 2>&1 || delivered=0
      sleep 1
    done < <(printf '%s' "$message" | CHUNK_SIZE="$chunk_size" MAX_CHUNKS="$max_chunks" python3 "$HERE/../bin/chunk_message.py")
    if [ "$delivered" -eq 1 ]; then rm -f "$claimed"; else mv "$claimed" "$pending" 2>/dev/null || true; fi
  done
  sleep "$INTERVAL"
done
