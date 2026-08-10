#!/usr/bin/env python3
"""Codex lifecycle hook: atomically enqueue a local iMessage notification."""
import json, os, sys, tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.environ.get("IMSG_CODEX_QUEUE_DIR") or os.path.join(ROOT, "state", "desktop-notify")
SEEN = os.path.join(QUEUE, ".seen")
MARKERS = ("?", "？", "请选择", "请确认", "需要你", "要不要", "是否", "你想", "确认一下")

def task_name(event):
    configured = os.environ.get("IMSG_TASK_NAME", "").strip()
    if configured:
        return configured
    cwd = str(event.get("cwd") or "").strip()
    return Path(cwd).name if cwd else "Codex任务"

def enqueue(message):
    try:
        os.makedirs(QUEUE, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="pending-", suffix=".tmp", dir=QUEUE)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(message[:600]); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, tmp[:-4] + ".msg")
    except Exception:
        pass

def claim(event):
    """Suppress duplicate project- and user-level hooks for the same turn."""
    turn_id = str(event.get("turn_id") or "").strip()
    kind = str(event.get("hook_event_name") or "").strip()
    if not turn_id or not kind:
        return True
    try:
        os.makedirs(SEEN, mode=0o700, exist_ok=True)
        marker = os.path.join(SEEN, f"{turn_id}-{kind}")
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return True

def main():
    try: event = json.load(sys.stdin)
    except Exception: return
    kind = event.get("hook_event_name")
    if not claim(event):
        return
    if kind == "PermissionRequest":
        tool = event.get("tool_name", "tool")
        reason = (event.get("tool_input") or {}).get("description", "")
        enqueue(f"{task_name(event)}结果：等待授权 {tool}\n{reason}")
    elif kind == "Stop" and not event.get("stop_hook_active"):
        text = (event.get("last_assistant_message") or "").strip()
        if text:
            waiting = any(marker in text[-260:] for marker in MARKERS)
            body = text[-500:] if waiting else text[:500]
            status = "等待你的选择\n" if waiting else "已完成\n"
            enqueue(f"{task_name(event)}结果：{status}" + body)

if __name__ == "__main__": main()
