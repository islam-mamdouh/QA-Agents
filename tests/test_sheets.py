"""Google Sheets output against a fake spreadsheet (no network, no gspread needed)."""
import sys
import types
import unittest
from unittest import mock

from tests.helpers import FakeStore, base_cfg
from qa_flow import sheets
from qa_flow.quality import compute_quality
from qa_flow.traceability import build_matrix


class NotFound(Exception):
    pass


fake_gspread = types.ModuleType("gspread")
fake_gspread.WorksheetNotFound = NotFound
fake_gspread.exceptions = types.SimpleNamespace(APIError=type("APIError", (Exception,), {}))


class FakeWorksheet:
    def __init__(self, title, rows, cols, n):
        self.title, self.rows, self.cols, self.id, self.values = title, rows, cols, n, None

    def update(self, range_name, values):
        assert len(values) <= self.rows, f"{self.title}: {len(values)} rows > {self.rows}"
        assert all(len(v) <= self.cols for v in values), f"{self.title}: row wider than {self.cols} columns"
        self.values = values

    def format(self, *a):
        pass

    def freeze(self, **k):
        pass

    def clear(self):
        pass

    def resize(self, rows, cols):
        self.rows, self.cols = rows, cols


class FakeSpreadsheet:
    url = "https://sheet"

    def __init__(self):
        self.tabs, self.requests = {}, []

    def worksheet(self, title):
        if title not in self.tabs:
            raise NotFound(title)
        return self.tabs[title]

    def add_worksheet(self, title, rows, cols):
        self.tabs[title] = FakeWorksheet(title, rows, cols, len(self.tabs) + 1)
        return self.tabs[title]

    def batch_update(self, body):
        self.requests += body["requests"]


class SheetsTest(unittest.TestCase):
    def setUp(self):
        self.book = FakeSpreadsheet()
        self.patches = [mock.patch.dict(sys.modules, {"gspread": fake_gspread}),
                        mock.patch.object(sheets, "_open", return_value=self.book)]
        for p in self.patches:
            p.start()
        analysis = {"A": {"summary": "Pay", "scenarios": [{"id": "S1"}], "risk": {"level": "high", "score": 20}}}
        cases = [{"id": "A-TC01", "story": "A", "scenario": "S1"}]
        self.results = {"A-TC01": {"status": "Fail", "bug_id": "B-1"}}
        self.gaps = [{"gap_id": "A-Q01", "story": "A", "question": "q", "status": "open", "answer": "", "raised": "2026-11-01"}]
        self.matrix = build_matrix(["A"], analysis, cases, self.results, self.gaps)
        self.rows = [{"id": "A-TC01", "story": "A", "title": "t", "status": "Fail", "severity": "major",
                      "root_cause": "code", "bug_status": "open", "bug_id": "B-1"}]

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_design_tabs(self):
        url = sheets.publish_design(base_cfg(), self._store(), self.gaps, self.matrix)
        self.assertEqual(sorted(self.book.tabs), ["T Gaps run1", "T Traceability run1"])
        self.assertIn("#gid=", url)

    def test_report_tabs(self):
        quality = compute_quality(self.rows, ["A"], self.gaps, self.matrix)
        summary = {"executive_summary": "s", "improvement_actions": ["a"]}
        stats = {"total": 1, "executed": 1, "pass_rate": "0.0%", "by_status": {"Pass": 0, "Fail": 1},
                 "per_story": {"A": {"Pass": 0, "Fail": 1}}}
        with mock.patch.object(fake_gspread, "service_account", lambda filename: types.SimpleNamespace(
                    open_by_key=lambda key: self.book), create=True):
            cfg = base_cfg()
            cfg["google_sheets"].update(service_account_file="sa.json", spreadsheet_id="id")
            sheets.publish(cfg, self._store(), self.rows, summary, stats, quality, self.gaps, self.matrix)
        self.assertEqual(sorted(self.book.tabs), ["T Gaps run1", "T Quality run1", "T Results run1",
                                                  "T Summary run1", "T Traceability run1"])
        quality_values = [v[0] for v in self.book.tabs["T Quality run1"].values]
        self.assertIn("Pareto - failed cases by root cause", quality_values)

    def test_monthly_table(self):
        sheets.publish_table(base_cfg(), self._store(), "T Monthly 2026-11", ["a", "b"], [["1", "2"]], [100, 100], "m")
        self.assertEqual(self.book.tabs["T Monthly 2026-11"].values, [["a", "b"], ["1", "2"]])

    def _store(self):
        store = FakeStore()
        store.dir = types.SimpleNamespace(name="run1")
        return store


if __name__ == "__main__":
    unittest.main()
