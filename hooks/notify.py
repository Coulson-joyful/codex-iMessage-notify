#!/usr/bin/env python3
"""Codex lifecycle hook: atomically enqueue the visible final result."""
import json, os, sys, tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def local_config():
    values = {}
    try:
        for line in Path(ROOT, "config.env").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values

CONFIG = local_config()
QUEUE = (os.environ.get("IMSG_CODEX_QUEUE_DIR")
         or CONFIG.get("IMSG_CODEX_QUEUE_DIR")
         or os.path.join(ROOT, "state", "desktop-notify"))
SEEN = os.path.join(QUEUE, ".seen")
MARKERS = ("?", "？", "请选择", "请确认", "需要你", "要不要", "是否", "你想", "确认一下")

def task_name(event):
    configured = (os.environ.get("IMSG_TASK_NAME") or CONFIG.get("IMSG_TASK_NAME") or "").strip()
    if configured:
        return configured
    cwd = str(event.get("cwd") or "").strip()
    return Path(cwd).name if cwd else "Codex任务"

def enqueue(message):
    try:
        os.makedirs(QUEUE, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="pending-", suffix=".tmp", dir=QUEUE)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            # Preserve the full user-visible result; the bridge chunks it for
            # iMessage instead of silently reducing it to one short line.
            out.write(message[:12000]); out.flush(); os.fsync(out.fileno())
        os.replace(tmp, tmp[:-4] + ".msg")
        return True
    except Exception:
        return False

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
        text = event.get("last_assistant_message") or ""
        if isinstance(text, str) and text.strip():
            waiting = any(marker in text[-260:] for marker in MARKERS)
            if waiting:
                enqueue(f"{task_name(event)}结果：等待你的选择\n{text[-12000:]}")
            else:
                enqueue(f"{task_name(event)}结果：已完成\n{text[:12000]}")

if __name__ == "__main__": main()
