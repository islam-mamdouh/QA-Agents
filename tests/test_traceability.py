import unittest

from tests.helpers import temp_dir
from qa_flow.traceability import build_matrix, collect_gaps, read_gaps, write_gaps

REQUIREMENTS = [
    {"id": "R1", "text": "Weight check", "scenarios": [{"id": "S1"}, {"id": "S2"}], "risk": {"level": "high", "score": 20}},
    {"id": "R2", "text": "Reject message", "scenarios": [{"id": "S1"}]},
    {"id": "R3", "text": "Report", "scenarios": [{"id": "S1"}]},
]
CASES = [{"id": "T1", "requirement": "R1", "scenario": "S1,S2"}, {"id": "T2", "requirement": "R1", "scenario": "S1"},
         {"id": "T3", "requirement": "R2", "scenario": "S1"}]
QUESTIONS = [{"requirement": "R1", "question": "Which unit?", "confirm_with": "BA"},
             {"requirement": "general", "question": "Which ports?", "confirm_with": "official documentation"},
             {"requirement": "R2", "question": ""}]


class GapsTest(unittest.TestCase):
    def test_collect_write_and_keep_answers(self):
        path = temp_dir() / "requirement_gaps.csv"
        gaps = write_gaps(path, collect_gaps("CR-7", QUESTIONS))
        self.assertEqual([g["gap_id"] for g in gaps], ["CR-7-Q01", "CR-7-Q02"])  # empty question skipped
        self.assertEqual(gaps[1]["confirm_with"], "official documentation")
        text = path.read_text(encoding="utf-8-sig").replace("Which unit?,BA,open,", "Which unit?,BA,answered,KG")
        path.write_text(text, encoding="utf-8-sig")
        merged = write_gaps(path, collect_gaps("CR-7", QUESTIONS))  # run again: answers are kept
        self.assertEqual(merged[0]["status"], "answered")
        self.assertEqual(merged[0]["answer"], "KG")
        self.assertEqual(read_gaps(path)[1]["status"], "open")

    def test_bad_status(self):
        path = temp_dir() / "g.csv"
        path.write_text("gap_id,requirement,question,status\nCR-1-Q01,R1,q,maybe\n", encoding="utf-8-sig")
        with self.assertRaises(ValueError):
            read_gaps(path)


class MatrixTest(unittest.TestCase):
    def test_before_execution(self):
        m = {r["requirement"]: r for r in build_matrix(REQUIREMENTS, CASES)}
        self.assertEqual(m["R1"]["scenarios"], "2/2")  # "S1,S2" counts both scenarios
        self.assertEqual(m["R1"]["risk"], "high (20)")
        self.assertEqual(m["R1"]["coverage"], "Covered - not executed yet")
        self.assertEqual(m["R3"]["coverage"], "Not covered")

    def test_with_results_and_evidence(self):
        results = {"T1": {"status": "Pass", "bug_id": "", "evidence": "t1.png"},
                   "T2": {"status": "Fail", "bug_id": "BUG-7", "evidence": ""},
                   "T3": {"status": "Pass", "bug_id": "", "evidence": "t3.png"}}
        gaps = [{"requirement": "R1", "status": "open"}, {"requirement": "R1", "status": "answered"}]
        m = {r["requirement"]: r for r in build_matrix(REQUIREMENTS[:2], CASES, results, gaps)}
        self.assertEqual(m["R1"]["coverage"], "Failed")
        self.assertEqual(m["R1"]["bugs"], "BUG-7")
        self.assertEqual(m["R1"]["evidence"], "1/2")
        self.assertEqual(m["R1"]["open_gaps"], 1)
        self.assertEqual(m["R2"]["coverage"], "Passed")


if __name__ == "__main__":
    unittest.main()
