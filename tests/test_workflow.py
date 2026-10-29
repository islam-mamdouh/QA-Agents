"""End-to-end: design -> fill results -> report, with fake agents and no Google Sheets."""
import csv
import unittest
from unittest import mock

from tests.helpers import base_cfg, temp_dir
from qa_flow import orchestrator
from qa_flow.store import RunStore

STORIES = {"order": ["Z-1", "Z-2"], "stories": {
    "Z-1": {"key": "Z-1", "summary": "Create simplified invoice"},
    "Z-2": {"key": "Z-2", "summary": "Credit note", "depends_on": ["Z-1"]}}}


def fake_write(self, role, task, step, previous=None, issues=None, validate=None):
    if role == "story_analysis":
        out = {"stories": [{"key": s["key"], "business_goal": "g", "acceptance_criteria": ["ac"],
                            "scenarios": [{"id": "S1", "title": "happy", "type": "positive", "priority": "high"},
                                          {"id": "S2", "title": "vat", "type": "edge", "priority": "high"}],
                            "risks": ["r"], "risk_impact": 5, "risk_likelihood": 4 if s["key"] == "Z-1" else 2,
                            "risk_reason": "money", "questions": ["Rounding rule?"], "test_data": ["d"]}
                           for s in task["stories"]]}
    elif role == "test_plan":
        keys = [s["key"] for s in task["stories"]]
        out = {"approach": "a", "environments": ["staging"], "exit_criteria": ["no critical open"],
               "execution_order": keys, "story_plans": [{"key": k, "priority": "high", "focus": "f"} for k in keys]}
    elif role == "test_cases":
        out = {"test_cases": [{"story": p["key"], "scenario": "S1", "title": f"{p['key']} happy", "priority": "high",
                               "type": "positive", "preconditions": ["logged in"],
                               "steps": [{"action": "create", "expected": "created"}]}
                              for p in task["story_plans"] for _ in range(2)]}
    elif role == "report_rows":
        out = {"rows": [{"id": r["id"], "actual_result": r.get("actual_result", ""),
                         "defect_summary": "VAT wrong" if r["status"] == "Fail" else "",
                         "severity": "critical" if r["status"] == "Fail" else "", "recommendation": ""}
                        for r in task["rows"]]}
    elif role == "report_summary":
        assert "quality" in task and task["quality"]["kpis"]
        out = {"executive_summary": "s", "quality_assessment": "q", "exit_criteria": [], "key_risks": [],
               "recommendations": [], "improvement_actions": ["Add a rounding rule to the requirements checklist"]}
    if validate:
        validate(out)
    return out


class WorkflowTest(unittest.TestCase):
    def test_design_and_report(self):
        cfg = base_cfg(temp_dir())
        store = RunStore.create(cfg["flow"]["runs_dir"])
        with mock.patch.object(orchestrator.Agents, "write", fake_write), \
                mock.patch.object(orchestrator.Agents, "review", lambda *a, **k: {"issues": []}), \
                mock.patch.object(orchestrator.jira_agent, "fetch_stories", lambda *a: STORIES), \
                mock.patch.object(orchestrator, "publish_design", return_value="https://sheet/gaps") as design_sheet, \
                mock.patch.object(orchestrator, "publish", return_value="https://sheet/report") as report_sheet, \
                mock.patch.object(orchestrator, "LLM", lambda cfg, store: None):
            flow = orchestrator.Orchestrator(cfg, store)
            flow.design()

            for name in ("test_plan.md", "test_cases.md", "traceability.md", "requirement_gaps.md",
                         "requirement_gaps.csv", "results.csv"):
                self.assertTrue((store.dir / name).exists(), name)
            self.assertIn("high (20 = 5x4)", (store.dir / "test_plan.md").read_text())
            self.assertIn("Covered - not executed yet", (store.dir / "traceability.md").read_text())
            design_sheet.assert_called_once()

            # fill in the results like a tester would
            path = store.dir / "results.csv"
            rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
            rows[0].update(status="Fail", actual_result="VAT 14%", bug_id="BUG-1", root_cause="code")
            for r in rows[1:]:
                r["status"] = "Pass"
            with path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            flow.report()

        report = (store.dir / "report.md").read_text()
        self.assertIn("## Quality KPIs", report)
        self.assertIn("Add a rounding rule", report)
        bugs = (store.dir / "bug_reports.md").read_text()
        self.assertIn("BUG-1 - VAT wrong", bugs)
        self.assertIn("1. create", bugs)
        self.assertIn(" Failed |", (store.dir / "traceability.md").read_text())
        data = store.load("report_data")
        self.assertEqual(len(data["gaps"]), 2)
        self.assertEqual(data["matrix"][0]["coverage"], "Failed")
        report_sheet.assert_called_once()


if __name__ == "__main__":
    unittest.main()
