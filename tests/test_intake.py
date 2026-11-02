import unittest

from tests.helpers import FakeStore, temp_dir
from qa_flow.intake import IntakeError, cr_path, read_cr


class IntakeTest(unittest.TestCase):
    def setUp(self):
        self.crs = temp_dir()

    def test_reads_title_and_cleans_text(self):
        path = cr_path(str(self.crs), "CR-1234")
        path.write_text("# CR-1234 Add container weight check\r\n\r\n\r\n\r\nThe broker must...   \nMore text here.",
                        encoding="utf-8")
        cr = read_cr("CR-1234", path, 1000, FakeStore())
        self.assertEqual(cr["title"], "CR-1234 Add container weight check")
        self.assertEqual(cr["text"], "# CR-1234 Add container weight check\n\nThe broker must...\nMore text here.")

    def test_long_text_is_trimmed_with_incident(self):
        path = cr_path(str(self.crs), "CR-1")
        path.write_text("Title\n" + "x" * 500, encoding="utf-8")
        store = FakeStore()
        cr = read_cr("CR-1", path, 100, store)
        self.assertTrue(cr["text"].endswith("...[trimmed]"))
        self.assertEqual(len(store.incidents.logged), 1)

    def test_missing_empty_and_bad_id(self):
        with self.assertRaises(IntakeError):
            read_cr("CR-9", cr_path(str(self.crs), "CR-9"), 100, FakeStore())
        path = cr_path(str(self.crs), "CR-2")
        path.write_text("short", encoding="utf-8")
        with self.assertRaises(IntakeError):
            read_cr("CR-2", path, 100, FakeStore())
        with self.assertRaises(IntakeError):
            cr_path(str(self.crs), "../secret")


if __name__ == "__main__":
    unittest.main()
