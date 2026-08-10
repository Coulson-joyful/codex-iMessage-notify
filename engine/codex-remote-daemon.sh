#!/bin/bash
# Phone `Codex <prompt>` -> isolated `codex exec` -> iMessage final answer.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/../config.env"
# Homebrew's Codex launcher uses `env node`; launchd's default PATH omits both.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
PYTHON_BIN="${IMSG_PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ] && [ -x "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python" ]; then
  # Reuse the interpreter that already has Full Disk Access for the working cc daemon.
  PYTHON_BIN="/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python"
fi
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
# launchd has a minimal PATH, so resolve the common macOS install locations
# before falling back to PATH. CODEX_BIN in config.env still takes precedence.
CODEX_BIN="${CODEX_BIN:-}"
if [ -z "$CODEX_BIN" ]; then
  for candidate in /opt/homebrew/bin/codex /usr/local/bin/codex; do
    if [ -x "$candidate" ]; then
      CODEX_BIN="$candidate"
      break
    fi
  done
fi
CODEX_BIN="${CODEX_BIN:-codex}"
if ! command -v "$CODEX_BIN" >/dev/null 2>&1 && [ ! -x "$CODEX_BIN" ]; then
  echo "[imsg-codex-remote] Codex executable not found: $CODEX_BIN" >&2
  exit 127
fi
WORKDIR="${CODEX_WORKDIR:-$HERE/..}"
INTERVAL="${IMSG_POLL_INTERVAL:-15}"
SANDBOX="${CODEX_REMOTE_SANDBOX:-read-only}"
APPROVE="${CODEX_REMOTE_APPROVE:-0}"
mkdir -p "$HERE/../state"

send_reply() {
  local target="$1" reply="$2" chunk_size="${IMSG_CHUNK_SIZE:-1200}" max_chunks="${IMSG_MAX_CHUNKS:-10}"
  local count=0
  while IFS= read -r -d '' chunk; do
    "$HERE/../bin/send.sh" "$target" "$chunk" || return 1
    count=$((count + 1))
    sleep 1
  done < <(printf '%s' "$reply" | CHUNK_SIZE="$chunk_size" MAX_CHUNKS="$max_chunks" python3 -c '
import os, sys
text = sys.stdin.read(); size = max(1, int(os.environ["CHUNK_SIZE"])); limit = max(1, int(os.environ["MAX_CHUNKS"]))
chunks = [text[i:i + size] for i in range(0, len(text), size)] or ["（空回复）"]
truncated = len(chunks) > limit; chunks = chunks[:limit]
for index, chunk in enumerate(chunks, 1):
    prefix = f"({index}/{len(chunks)}) " if len(chunks) > 1 else ""
    tail = f"\n\n…（过长，已发送前 {limit} 条）" if truncated and index == len(chunks) else ""
    sys.stdout.write(prefix + chunk + tail + "\0")
')
  [ "$count" -gt 0 ]
}

# Establish a watermark only on first install. Reinitializing on every restart
# would silently discard commands that arrived while the daemon was down.
[ -f "$HERE/../state/last_rowid" ] || "$PYTHON_BIN" "$HERE/../bin/poll.py" --init >/dev/null 2>&1
echo "[imsg-codex-remote] polling every ${INTERVAL}s"
while true; do
  while IFS=$'\t' read -r handle prompt; do
    [ -n "${prompt:-}" ] || continue
    echo "[$(date '+%H:%M:%S')] received Codex command from configured self handle"
    result_file="$(mktemp "$HERE/../state/codex-result.XXXXXX")"
    args=(exec --cd "$WORKDIR" --sandbox "$SANDBOX" --output-last-message "$result_file" -)
    [ "$APPROVE" = 1 ] && args+=(--approve-for-me)
    instruction="You are replying through an iMessage remote channel. Give a concise plain-text conclusion first. Do not expose secrets.\n\n${prompt}"
    if ! printf '%s' "$instruction" | "$CODEX_BIN" "${args[@]}" >/tmp/imsg-codex.out 2>/tmp/imsg-codex.err; then
      reply="⚠️ Codex execution failed; inspect /tmp/imsg-codex.err on the Mac."
    else
      reply="$(<"$result_file")"
      [ -n "$reply" ] || reply="（Codex returned an empty final message）"
    fi
    rm -f "$result_file"
    target="${IMSG_NOTIFY_TO:-$handle}"
    send_reply "$target" "$reply" && echo "[$(date '+%H:%M:%S')] reply delivered" || echo "[imsg-codex-remote] delivery failed" >&2
  done < <("$PYTHON_BIN" "$HERE/../bin/poll.py" 2>/tmp/imsg-codex-poll.err)
  sleep "$INTERVAL"
done
