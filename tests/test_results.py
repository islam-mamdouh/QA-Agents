import csv
import unittest

from tests.helpers import FakeIncidents, temp_dir
from qa_flow.results import COLUMNS, read_results, write_template

CASES = [{"id": f"CR-1-TC-00{i}", "summary": "t", "priority": "high"} for i in (1, 2, 3)]


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
        self.assertEqual(len(first.splitlines()), 4)
        self.path.write_text("edited", encoding="utf-8")
        write_template(self.path, CASES)
        self.assertEqual(self.path.read_text(encoding="utf-8"), "edited")

    def test_reads_and_normalises(self):
        write(self.path, [
            {"id": "CR-1-TC-001", "status": "passed", "evidence": "TC001.png", "reference_numbers": "DEC 123"},
            {"id": "CR-1-TC-002", "status": "FAIL", "actual_result": "500 error", "bug_id": "B-1", "evidence": "x.png",
             "root_cause": "People", "bug_status": "Reopened", "severity": "Major", "build": "1.4.2"},
            {"id": "X-9", "status": "pass"},
        ])
        incidents = FakeIncidents()
        results = read_results(self.path, CASES, incidents)
        self.assertEqual(results["CR-1-TC-001"]["status"], "Pass")
        self.assertEqual(results["CR-1-TC-001"]["reference_numbers"], "DEC 123")
        self.assertEqual(results["CR-1-TC-002"]["root_cause"], "people")
        self.assertEqual(results["CR-1-TC-002"]["severity"], "major")
        self.assertEqual(results["CR-1-TC-002"]["build"], "1.4.2")
        self.assertEqual(results["CR-1-TC-003"]["status"], "Not Run")
        self.assertEqual(len(incidents.logged), 2)  # unknown id + missing case

    def test_error_proofing_for_evidence_fail_and_blocked(self):
        write(self.path, [{"id": "CR-1-TC-001", "status": "Fail"}, {"id": "CR-1-TC-002", "status": "Blocked"},
                          {"id": "CR-1-TC-003", "status": "Pass"}])
        with self.assertRaises(ValueError) as error:
            read_results(self.path, CASES, FakeIncidents())
        message = str(error.exception)
        self.assertIn("Fail needs evidence, actual_result, bug_id, root_cause", message)
        self.assertIn("why it is blocked", message)
        self.assertIn("Pass needs evidence", message)
        self.assertEqual(read_results(self.path, CASES, FakeIncidents(), strict=False)["CR-1-TC-001"]["status"], "Fail")

    def test_rejects_unknown_values(self):
        write(self.path, [{"id": "CR-1-TC-001", "status": "Fail", "actual_result": "x", "bug_id": "B", "evidence": "e",
                           "root_cause": "design"}, {"id": "CR-1-TC-002", "status": "maybe"}])
        with self.assertRaises(ValueError) as error:
            read_results(self.path, CASES, FakeIncidents())
        self.assertIn("root_cause 'design'", str(error.exception))
        self.assertIn("status 'maybe'", str(error.exception))


if __name__ == "__main__":
    unittest.main()
