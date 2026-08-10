#!/usr/bin/env python3
"""Codex lifecycle hook: atomically enqueue a local iMessage notification."""
import json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.environ.get("IMSG_CODEX_QUEUE_DIR") or os.path.join(ROOT, "state", "desktop-notify")
MARKERS = ("?", "？", "请选择", "请确认", "需要你", "要不要", "是否", "你想", "确认一下")

def enqueue(message):
    try:
        os.makedirs(QUEUE, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="pending-", suffix=".tmp", dir=QUEUE)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(message[:600]); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, tmp[:-4] + ".msg")
    except Exception:
        pass

def main():
    try: event = json.load(sys.stdin)
    except Exception: return
    kind = event.get("hook_event_name")
    if kind == "PermissionRequest":
        tool = event.get("tool_name", "tool")
        reason = (event.get("tool_input") or {}).get("description", "")
        enqueue(f"🤖 Codex 等待授权：{tool}\n{reason}")
    elif kind == "Stop" and not event.get("stop_hook_active"):
        text = (event.get("last_assistant_message") or "").strip()
        if text:
            waiting = any(marker in text[-260:] for marker in MARKERS)
            body = text[-500:] if waiting else text[:500]
            enqueue(("🤖 Codex 等待你的选择\n" if waiting else "✅ Codex 完成\n") + body)

if __name__ == "__main__": main()
