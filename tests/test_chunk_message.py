import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "bin" / "chunk_message.py"
SPEC = importlib.util.spec_from_file_location("chunk_message", MODULE_PATH)
chunk_message = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(chunk_message)


class ChunkMessageTests(unittest.TestCase):
    def test_short_message_is_unchanged(self):
        text = "第一段\n\n第二段\n第三行"
        self.assertEqual(chunk_message.split_text(text, 1200), [text])

    def test_paragraph_and_line_breaks_survive_chunking(self):
        text = "任务结果：\n第一段内容\n\n第二段第一行\n第二段第二行\n\n结尾"
        parts = chunk_message.split_text(text, 20)
        self.assertGreater(len(parts), 1)
        self.assertEqual("".join(parts), text)
        self.assertIn("\n\n", "".join(parts))

    def test_spaces_are_not_trimmed_at_boundaries(self):
        text = "alpha beta gamma delta"
        self.assertEqual("".join(chunk_message.split_text(text, 10)), text)

    def test_leading_and_trailing_newlines_are_preserved(self):
        text = "\n第一段\n\n第二段\n"
        self.assertEqual("".join(chunk_message.split_text(text, 8)), text)


if __name__ == "__main__":
    unittest.main()
