#!/usr/bin/env python3
"""Read quota errors independently of model/Stop hooks; reuse the notify queue."""
import datetime as dt
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

import notify


def limit_message(text):
    text = text.lower()
    if any(word in text for word in (
        "out of credits", "credits_depleted", "insufficient credits",
        "insufficient_quota", "quota_exceeded",
    )):
        return ("额度不足\n工作区或账户可用 credits/余额不足，模型请求受阻。"
                "请查看任务界面确认进度；联系工作区管理员补充 credits，"
                "或补充当前账户/API 余额后回到原任务继续。")
    if any(word in text for word in (
        "hit your usage limit", "usage_limit_reached", "rate_limit_reached",
        "limitreason=usage_limit", "usage limit reached", "usage_limit_exceeded",
    )):
        return ("使用额度达到上限\n模型请求受限。请在 Codex 额度页面查看恢复时间，"
                "等待额度恢复或使用账户提供的补充额度选项后，回到原任务继续。")
    return ""


def thread_name(home, thread_id):
    if thread_id:
        for path in sorted(home.glob("state_*.sqlite"), reverse=True):
            try:
                with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
                    row = db.execute("SELECT title FROM threads WHERE id=?", (thread_id,)).fetchone()
                    if row and row[0]:
                        return row[0]
            except sqlite3.Error:
                continue
    return "Codex"


def scan(home, log_root, state_path, now=None):
    now = time.time() if now is None else now
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        state = {"db": {}, "files": {}, "sent": {}}
    initial = not state_path.exists()

    def alert(text, thread_id=""):
        message = limit_message(text)
        if not message:
            return
        key = thread_id + ":" + message.split("\n", 1)[0]
        # ponytail: suppress repeated quota errors for 15 minutes; per-turn IDs
        # can replace this if the runtime exposes terminal errors consistently.
        if now - state["sent"].get(key, 0) < 900:
            return
        if not notify.enqueue(thread_name(home, thread_id) + "结果：" + message):
            raise OSError("Could not enqueue quota notification")
        state["sent"][key] = now

    for path in home.glob("logs_*.sqlite"):
        key = str(path)
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
                maximum = db.execute("SELECT COALESCE(MAX(id),0) FROM logs").fetchone()[0]
                previous = state["db"].get(key, maximum if initial else 0)
                if previous > maximum:
                    previous = 0
                for text, thread_id in db.execute(
                    "SELECT feedback_log_body,thread_id FROM logs WHERE id>? AND id<=? "
                    "AND level IN ('WARN','ERROR') ORDER BY id", (previous, maximum)
                ):
                    alert(text or "", thread_id or "")
                state["db"][key] = maximum
        except sqlite3.Error as error:
            print(f"quota watcher: {path.name}: {error}", file=sys.stderr)

    for day in (dt.datetime.fromtimestamp(now).date(),
                dt.datetime.fromtimestamp(now).date() - dt.timedelta(days=1)):
        for path in (log_root / day.strftime("%Y/%m/%d")).glob("*.log"):
            key = str(path)
            with path.open("rb") as source:
                stat = os.fstat(source.fileno())
                inode, offset = state["files"].get(key, [stat.st_ino, stat.st_size if initial else 0])
                if inode != stat.st_ino or offset > stat.st_size:
                    offset = 0
                source.seek(offset)
                while True:
                    line = source.readline()
                    if not line:
                        break
                    if not line.endswith(b"\n"):
                        source.seek(-len(line), 1)
                        break
                    text = line.decode("utf-8", errors="replace")
                    if " warning " in text or " error " in text:
                        alert(text)
                state["files"][key] = [stat.st_ino, source.tell()]
    state["sent"] = {key: stamp for key, stamp in state["sent"].items() if now - stamp < 900}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=state_path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(state, out)
    os.replace(temporary, state_path)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--error-file":
        text = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
        print(limit_message(text) or "执行失败\n请在 Mac 查看 /tmp/imsg-codex.err 后重试。")
    else:
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        log_root = Path.home() / "Library/Logs/com.openai.codex"
        scan(home, log_root, Path(notify.QUEUE).parent / "quota-watch.json")
