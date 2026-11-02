"""End-to-end for one CR: design -> fill results -> report, with fake agents (no Claude, no network)."""
import csv
import unittest
from unittest import mock

from openpyxl import load_workbook

from tests.helpers import base_cfg, temp_dir
from qa_flow import orchestrator
from qa_flow.store import RunStore

CR_TEXT = """# CR-1234 Container weight validation on import declaration
The broker must enter the gross weight for each container. The system rejects a declaration
when the declared weight differs from the manifest weight by more than the allowed tolerance."""


def fake_write(self, role, task, step, previous=None, issues=None, validate=None):
    if role == "cr_analysis":
        assert "CR-1234" in task["cr"]["text"]
        out = {"summary": "Weight check", "journey_stages": ["import declaration"], "systems": ["Fasah portal", "DB"],
               "requirements": [
                   {"id": "R1", "text": "Broker enters gross weight per container", "acceptance_criteria": ["ac"],
                    "modules": ["Declarations"], "systems": ["Fasah portal"],
                    "scenarios": [{"id": "S1", "title": "valid weight", "type": "positive", "priority": "high"},
                                  {"id": "S2", "title": "empty weight", "type": "negative", "priority": "high"}],
                    "risks": ["r"], "risk_impact": 5, "risk_likelihood": 4, "risk_reason": "blocks clearance"},
                   {"id": "R2", "text": "Reject when weight is outside tolerance", "modules": ["Declarations"],
                    "scenarios": [{"id": "S1", "title": "at tolerance", "type": "boundary", "priority": "high"}],
                    "risks": [], "risk_impact": 4, "risk_likelihood": 3, "risk_reason": "status logic"}],
               "regression_areas": [{"area": "Manifest weight", "reason": "same field"}],
               "questions": [{"requirement": "R2", "question": "What is the tolerance?", "confirm_with": "BA"}],
               "exploratory_charters": ["Explore weight units"], "test_data_needed": ["B/L with 2 containers"]}
    elif role == "test_plan":
        ids = [r["id"] for r in task["requirements"]]
        assert "REG" in ids
        out = {"approach": "a", "systems_and_environments": ["Fasah portal", "DB"], "exit_criteria": ["no critical open"],
               "execution_order": ids, "requirement_plans": [{"id": i, "focus": "f"} for i in ids]}
    elif role == "test_cases":
        out = {"test_cases": [{"requirement": r["id"], "scenario": s["id"], "summary": f"{r['id']} {s['title']}",
                               "module": "Declarations", "system": "Fasah portal", "preconditions": ["Broker role"],
                               "steps": ["Open declaration", "Enter weight", "Submit"], "test_data": "B/L 1",
                               "expected_result": "UI: saved\nDB: status accepted", "type": s["type"],
                               "priority": s["priority"]}
                              for r in task["requirements"] for s in r["scenarios"]]}
    elif role == "report_rows":
        out = {"rows": [{"id": r["id"], "actual_result": r.get("actual_result", ""),
                         "defect_title": "[Declarations] Weight accepted outside tolerance" if r["status"] == "Fail" else "",
                         "severity": "critical" if r["status"] == "Fail" else "", "recommendation": ""}
                        for r in task["rows"]]}
    elif role == "uat_summary":
        assert task["open_questions"] and task["open_bugs"]
        out = {"what_changed": ["Weight check"], "how_tested": ["Positive, negative, boundary"], "results": "r",
               "exit_criteria": [{"criterion": "no critical open", "met": "No", "note": "1 critical"}],
               "recommendation": "Not ready for sign-off until BUG-1 is fixed.", "risks": []}
    if validate:
        validate(out)
    return out


class WorkflowTest(unittest.TestCase):
    def test_design_and_report(self):
        cfg = base_cfg(temp_dir())
        crs = temp_dir()
        (crs / "CR-1234.md").write_text(CR_TEXT, encoding="utf-8")
        cfg["inputs"]["crs_dir"] = str(crs)
        store = RunStore.create(cfg["flow"]["runs_dir"], "CR-1234")
        self.assertTrue(store.dir.name.endswith("-CR-1234"))
        with mock.patch.object(orchestrator.Agents, "write", fake_write), \
                mock.patch.object(orchestrator.Agents, "review", lambda *a, **k: {"issues": []}), \
                mock.patch.object(orchestrator, "LLM", lambda cfg, store: None):
            flow = orchestrator.Orchestrator(cfg, store)
            flow.design("CR-1234")

            for name in ("cr_analysis.md", "test_plan.md", "test_cases.xlsx", "requirement_gaps.csv", "results.csv"):
                self.assertTrue((store.dir / name).exists(), name)
            analysis = (store.dir / "cr_analysis.md").read_text()
            self.assertIn("high (20 = 5x4)", analysis)
            self.assertIn("What is the tolerance?", analysis)
            wb = load_workbook(store.dir / "test_cases.xlsx")
            self.assertEqual(wb.sheetnames, ["Test Cases", "Traceability", "Gaps for BA-Dev", "Exploratory Charters"])
            ws = wb["Test Cases"]
            self.assertEqual(ws["A2"].value, "CR-1234-TC-001")
            self.assertEqual(ws.max_row - 1, 4)  # 3 requirement scenarios + 1 regression area
            self.assertEqual(ws["F2"].value, "1. Open declaration\n2. Enter weight\n3. Submit")

            # fill in the results like a tester would
            path = store.dir / "results.csv"
            with path.open(encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            rows[0].update(status="Fail", actual_result="Weight 0 accepted", bug_id="BUG-1", root_cause="code",
                           evidence="TC001.png", reference_numbers="DEC 2026-55", build="1.4.2")
            for r in rows[1:]:
                r.update(status="Pass", evidence=f"{r['id']}.png", build="1.4.2")
            with path.open("w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            flow.report()

        pot = load_workbook(store.dir / "pot.xlsx")["POT CR-1234"]
        self.assertEqual([c.value for c in pot[1]][4:8],
                         ["Result", "Actual Result", "Screenshot Reference", "Reference / Message Numbers"])
        self.assertEqual(pot["E2"].value, "Fail")
        self.assertEqual(pot["H2"].value, "DEC 2026-55")
        bugs = (store.dir / "bug_reports.md").read_text()
        self.assertIn("**Title:** [Declarations] Weight accepted outside tolerance", bugs)
        self.assertIn("QA environment - build 1.4.2", bugs)
        self.assertIn("TC001.png; reference numbers: DEC 2026-55", bugs)
        self.assertIn("5 Whys", bugs)  # critical defect
        uat = (store.dir / "uat_summary.md").read_text()
        self.assertIn("Not ready for sign-off", uat)
        self.assertIn("What is the tolerance?", uat)
        quality = (store.dir / "quality.md").read_text()
        self.assertIn("Pareto - failed cases by module", quality)
        data = store.load("report_data")
        self.assertEqual(data["cr"], "CR-1234")
        self.assertEqual(data["matrix"][0]["coverage"], "Failed")
        self.assertEqual(RunStore.open(cfg["flow"]["runs_dir"], cr_id="CR-1234").dir, store.dir)


if __name__ == "__main__":
    unittest.main()
