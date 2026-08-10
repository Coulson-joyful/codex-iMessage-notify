#!/bin/bash
# Send only to one of the configured self handles.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../config.env"
if [ "$#" -ge 2 ]; then TO="$1"; MESSAGE="$2"; else TO="${IMSG_REPLY_TO:?Set IMSG_REPLY_TO}"; MESSAGE="${1:-}"; fi
allowed=0
IFS=',' read -ra handles <<< "${IMSG_HANDLES:-}"
for handle in "${handles[@]}"; do
  handle="$(echo "$handle" | xargs)"
  [ "$handle" = "$TO" ] && allowed=1
done
# Codex completion notifications intentionally use the configured phone target,
# which may be separate from the Apple-ID self handle used by remote commands.
[ "${IMSG_NOTIFY_TO:-}" = "$TO" ] && allowed=1
[ "$allowed" = 1 ] || { echo "Refusing non-self recipient." >&2; exit 2; }
/usr/bin/osascript - "$TO" "$MESSAGE" <<'OSA'
on run argv
  tell application "Messages"
    set svc to 1st account whose service type = iMessage
    set buddyTarget to participant (item 1 of argv) of svc
    send (item 2 of argv) to buddyTarget
  end tell
end run
OSA
