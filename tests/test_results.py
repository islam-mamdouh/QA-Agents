import csv
import unittest

from tests.helpers import FakeIncidents, temp_dir
from qa_flow.results import COLUMNS, read_results, write_template

CASES = [{"id": f"S-1-TC0{i}", "story": "S-1", "title": "t", "priority": "high"} for i in (1, 2, 3)]


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


class ResultsTest(unittest.TestCase):
    def setUp(self):
        self.path = temp_dir() / "results.csv"

    def test_template_has_all_cases_and_is_never_overwritten(self):
        write_template(self.path, CASES)
        first = self.path.read_text(encoding="utf-8-sig")
        self.assertEqual(first.splitlines()[0], ",".join(COLUMNS))
        self.path.write_text("edited", encoding="utf-8")
        write_template(self.path, CASES)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "edited")

    def test_reads_and_normalises(self):
        write(self.path, [
            {"id": "S-1-TC01", "status": "passed"},
            {"id": "S-1-TC02", "status": "FAIL", "actual_result": "500 error", "bug_id": "B-1",
             "root_cause": "Code", "bug_status": "Reopened"},
            {"id": "X-9", "status": "pass"},
        ])
        incidents = FakeIncidents()
        results = read_results(self.path, CASES, incidents)
        self.assertEqual(results["S-1-TC01"]["status"], "Pass")
        self.assertEqual(results["S-1-TC02"]["root_cause"], "code")
        self.assertEqual(results["S-1-TC02"]["bug_status"], "reopened")
        self.assertEqual(results["S-1-TC03"]["status"], "Not Run")
        self.assertEqual(len(incidents.logged), 2)  # unknown id + missing case

    def test_error_proofing_for_fail_and_blocked(self):
        write(self.path, [{"id": "S-1-TC01", "status": "Fail"}, {"id": "S-1-TC02", "status": "Blocked"}])
        with self.assertRaises(ValueError) as error:
            read_results(self.path, CASES, FakeIncidents())
        self.assertIn("actual_result, bug_id, root_cause", str(error.exception))
        self.assertIn("why it is blocked", str(error.exception))
        self.assertEqual(read_results(self.path, CASES, FakeIncidents(), strict=False)["S-1-TC01"]["status"], "Fail")

    def test_rejects_unknown_values(self):
        write(self.path, [{"id": "S-1-TC01", "status": "Fail", "actual_result": "x", "bug_id": "B",
                           "root_cause": "bad luck"}, {"id": "S-1-TC02", "status": "maybe"}])
        with self.assertRaises(ValueError) as error:
            read_results(self.path, CASES, FakeIncidents())
        self.assertIn("root_cause 'bad luck'", str(error.exception))
        self.assertIn("status 'maybe'", str(error.exception))


if __name__ == "__main__":
    unittest.main()
