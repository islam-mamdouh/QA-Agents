import unittest

from tests.helpers import FakeStore, temp_dir
from qa_flow.intake import IntakeError, story_path, read_story


class IntakeTest(unittest.TestCase):
    def setUp(self):
        self.stories_dir_ = temp_dir()

    def test_reads_title_and_cleans_text(self):
        path = story_path(str(self.stories_dir_), "US-1234")
        path.write_text("# US-1234 Employee submits a leave request\r\n\r\n\r\n\r\nThe employee must...   \nMore text here.",
                        encoding="utf-8")
        story = read_story("US-1234", path, 1000, FakeStore())
        self.assertEqual(story["title"], "US-1234 Employee submits a leave request")
        self.assertEqual(story["text"], "# US-1234 Employee submits a leave request\n\nThe employee must...\nMore text here.")

    def test_long_text_is_trimmed_with_incident(self):
        path = story_path(str(self.stories_dir_), "US-1")
        path.write_text("Title\n" + "x" * 500, encoding="utf-8")
        store = FakeStore()
        story = read_story("US-1", path, 100, store)
        self.assertTrue(story["text"].endswith("...[trimmed]"))
        self.assertEqual(len(store.incidents.logged), 1)

    def test_missing_empty_and_bad_id(self):
        with self.assertRaises(IntakeError):
            read_story("US-9", story_path(str(self.stories_dir_), "US-9"), 100, FakeStore())
        path = story_path(str(self.stories_dir_), "US-2")
        path.write_text("short", encoding="utf-8")
        with self.assertRaises(IntakeError):
            read_story("US-2", path, 100, FakeStore())
        with self.assertRaises(IntakeError):
            story_path(str(self.stories_dir_), "../secret")


if __name__ == "__main__":
    unittest.main()
