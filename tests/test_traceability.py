import unittest

from tests.helpers import temp_dir
from qa_flow.traceability import build_matrix, collect_gaps, read_gaps, write_gaps

ANALYSIS = {
    "A": {"summary": "Pay", "questions": ["Which currency?", "Max amount?"], "acceptance_criteria": ["a", "b"],
          "scenarios": [{"id": "S1"}, {"id": "S2"}], "risk": {"level": "high", "score": 20}},
    "B": {"summary": "Login", "questions": [], "scenarios": [{"id": "S1"}]},
    "C": {"summary": "Profile", "scenarios": [{"id": "S1"}]},
}
CASES = [{"id": "A-TC01", "story": "A", "scenario": "S1"}, {"id": "A-TC02", "story": "A", "scenario": "S1"},
         {"id": "B-TC01", "story": "B", "scenario": "S1"}]


class GapsTest(unittest.TestCase):
    def test_collect_write_and_keep_answers(self):
        path = temp_dir() / "requirement_gaps.csv"
        gaps = write_gaps(path, collect_gaps(ANALYSIS, ["A", "B"]))
        self.assertEqual([g["gap_id"] for g in gaps], ["A-Q01", "A-Q02"])
        text = path.read_text(encoding="utf-8-sig").replace("Which currency?,open,", "Which currency?,answered,SAR only")
        path.write_text(text, encoding="utf-8-sig")
        merged = write_gaps(path, collect_gaps(ANALYSIS, ["A", "B"]))  # run again: answers are kept
        self.assertEqual(merged[0]["status"], "answered")
        self.assertEqual(merged[0]["answer"], "SAR only")
        self.assertEqual(read_gaps(path)[1]["status"], "open")

    def test_bad_status(self):
        path = temp_dir() / "g.csv"
        path.write_text("gap_id,story,question,status\nA-Q01,A,q,maybe\n", encoding="utf-8-sig")
        with self.assertRaises(ValueError):
            read_gaps(path)


class MatrixTest(unittest.TestCase):
    def test_before_execution(self):
        m = {r["story"]: r for r in build_matrix(["A", "B", "C"], ANALYSIS, CASES)}
        self.assertEqual(m["A"]["scenarios"], "1/2")
        self.assertEqual(m["A"]["risk"], "high (20)")
        self.assertEqual(m["A"]["ac_count"], 2)
        self.assertEqual(m["A"]["coverage"], "Covered - not executed yet")
        self.assertEqual(m["C"]["coverage"], "Not covered")

    def test_with_results(self):
        results = {"A-TC01": {"status": "Pass", "bug_id": ""}, "A-TC02": {"status": "Fail", "bug_id": "BUG-7"},
                   "B-TC01": {"status": "Pass", "bug_id": ""}}
        gaps = [{"story": "A", "status": "open"}, {"story": "A", "status": "answered"}]
        m = {r["story"]: r for r in build_matrix(["A", "B"], ANALYSIS, CASES, results, gaps)}
        self.assertEqual(m["A"]["coverage"], "Failed")
        self.assertEqual(m["A"]["bugs"], "BUG-7")
        self.assertEqual(m["A"]["open_gaps"], 1)
        self.assertEqual(m["B"]["coverage"], "Passed")


if __name__ == "__main__":
    unittest.main()
