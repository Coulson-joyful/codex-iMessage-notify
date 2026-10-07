import datetime as dt
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

HOOKS = Path(__file__).parents[1] / "hooks"
sys.path.insert(0, str(HOOKS))
SPEC = importlib.util.spec_from_file_location("watch_limits", HOOKS / "watch_limits.py")
watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(watch)


class QuotaWatchTests(unittest.TestCase):
    def test_new_errors_survive_restart_without_replaying_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "codex"
            home.mkdir()
            with closing(sqlite3.connect(home / "logs_2.sqlite")) as db, db:
                db.execute("CREATE TABLE logs(id INTEGER PRIMARY KEY,level TEXT,feedback_log_body TEXT,thread_id TEXT)")
                db.execute("INSERT INTO logs VALUES(1,'WARN','Your workspace is out of credits.','task')")
            with closing(sqlite3.connect(home / "state_5.sqlite")) as db, db:
                db.execute("CREATE TABLE threads(id TEXT,title TEXT)")
                db.execute("INSERT INTO threads VALUES('task','我的任务')")
            now = 1800000000
            logs = root / "logs"
            day = logs / dt.datetime.fromtimestamp(now).strftime("%Y/%m/%d")
            day.mkdir(parents=True)
            log = day / "desktop.log"
            log.write_text("date warning bannerType=workspace_member_credits_depleted\n")
            state = root / "state.json"
            messages = []
            with mock.patch.object(watch.notify, "enqueue", side_effect=lambda text: messages.append(text) or True):
                watch.scan(home, logs, state, now)
                self.assertEqual(messages, [])
                with closing(sqlite3.connect(home / "logs_2.sqlite")) as db, db:
                    db.execute("INSERT INTO logs VALUES(2,'WARN','Your workspace is out of credits. secret-data','task')")
                    db.execute("INSERT INTO logs VALUES(3,'ERROR','network timeout','task')")
                watch.scan(home, logs, state, now + 1)
                self.assertEqual(len(messages), 1)
                self.assertTrue(messages[0].startswith("我的任务结果：额度不足"))
                self.assertNotIn("secret-data", messages[0])
                with closing(sqlite3.connect(home / "logs_2.sqlite")) as db, db:
                    db.execute("INSERT INTO logs VALUES(4,'ERROR','Your workspace is out of credits.','task')")
                watch.scan(home, logs, state, now + 2)
                self.assertEqual(len(messages), 1)
                with log.open("a") as out:
                    out.write("date warning limitReason=usage_limit")
                watch.scan(home, logs, state, now + 3)
                self.assertEqual(len(messages), 1)
                with log.open("a") as out:
                    out.write("\n")
                watch.scan(home, logs, state, now + 4)
                self.assertEqual(len(messages), 2)
                self.assertIn("Codex结果：使用额度达到上限", messages[-1])
                watch.scan(home, logs, state, now + 5)
                self.assertEqual(len(messages), 2)
                log.write_text("date warning out of credits\n")
                watch.scan(home, logs, state, now + 1000)
                self.assertEqual(len(messages), 3)

    def test_queue_failure_does_not_advance_watermark(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = 1800000000
            day = root / dt.datetime.fromtimestamp(now).strftime("%Y/%m/%d")
            day.mkdir(parents=True)
            state = root / "state.json"
            watch.scan(root, root, state, now)
            baseline = json.loads(state.read_text())
            (day / "new.log").write_text("date error You've hit your usage limit.\n")
            with mock.patch.object(watch.notify, "enqueue", return_value=False):
                with self.assertRaises(OSError):
                    watch.scan(root, root, state, now + 1)
            self.assertEqual(json.loads(state.read_text()), baseline)
            with mock.patch.object(watch.notify, "enqueue", return_value=True) as enqueue:
                watch.scan(root, root, state, now + 2)
                self.assertEqual(enqueue.call_count, 1)


if __name__ == "__main__":
    unittest.main()
