import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).parents[1] / "hooks" / "notify.py"
SPEC = importlib.util.spec_from_file_location("notify_hook", MODULE_PATH)
notify_hook = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(notify_hook)


class NotifyHookTests(unittest.TestCase):
    def test_stop_preserves_visible_formatting(self):
        with tempfile.TemporaryDirectory() as directory:
            event = {
                "hook_event_name": "Stop",
                "turn_id": "format-test",
                "cwd": "/tmp/GreenTune",
                "last_assistant_message": "第一段\n\n第二段第一行\n第二段第二行\n",
            }
            with mock.patch.object(notify_hook, "QUEUE", directory), \
                 mock.patch.object(notify_hook, "SEEN", os.path.join(directory, ".seen")), \
                 mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))):
                notify_hook.main()

            messages = list(pathlib.Path(directory).glob("*.msg"))
            self.assertEqual(len(messages), 1)
            self.assertEqual(
                messages[0].read_text(encoding="utf-8"),
                "GreenTune结果：已完成\n第一段\n\n第二段第一行\n第二段第二行\n",
            )

    def test_duplicate_turn_is_only_enqueued_once(self):
        with tempfile.TemporaryDirectory() as directory:
            event = {
                "hook_event_name": "Stop",
                "turn_id": "same-turn",
                "cwd": "/tmp/project",
                "last_assistant_message": "done",
            }
            with mock.patch.object(notify_hook, "QUEUE", directory), \
                 mock.patch.object(notify_hook, "SEEN", os.path.join(directory, ".seen")):
                for _ in range(2):
                    with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(event))):
                        notify_hook.main()
            self.assertEqual(len(list(pathlib.Path(directory).glob("*.msg"))), 1)


if __name__ == "__main__":
    unittest.main()
