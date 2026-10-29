import json
import unittest
from unittest import mock

from tests.helpers import base_cfg, temp_dir
from qa_flow import monthly


def report(run_id, fails, passes=3, cause="code", gaps=()):
    rows = [{"id": f"{run_id}-F{i}", "status": "Fail", "bug_id": f"B-{run_id}-{i}", "root_cause": cause,
             "severity": "major", "bug_status": "fixed"} for i in range(fails)]
    rows += [{"id": f"{run_id}-P{i}", "status": "Pass"} for i in range(passes)]
    return {"run_id": run_id, "rows": rows, "gaps": list(gaps),
            "matrix": [{"coverage": "Passed"}, {"coverage": "Not covered"}]}


class MonthlyTest(unittest.TestCase):
    def test_control_chart_flags_a_spike(self):
        chart = monthly.control_chart([("r1", 2), ("r2", 3), ("r3", 2), ("r4", 2), ("r5", 3), ("r6", 2),
                                       ("r7", 3), ("r8", 2), ("r9", 2), ("r10", 14)])
        self.assertEqual([p["run"] for p in chart["points"] if p["signal"]], ["r10"])
        self.assertEqual(monthly.control_chart([])["points"], [])

    def test_leakage_and_audit(self):
        escaped = [{"date": "2026-11-20", "bug_id": "P-1", "title": "t", "severity": "critical",
                    "root_cause": "requirements", "found_by": "user", "story": "", "notes": ""}]
        m = monthly.month_metrics([report("20261102-1", 2), report("20261110-1", 1)], escaped)
        kpis = {k["kpi"]: k["value"] for k in m["kpis"]}
        self.assertEqual(kpis["Defects found in testing"], "3")
        self.assertEqual(kpis["Defect leakage"], "25.0%")
        self.assertEqual(kpis["Defect detection effectiveness"], "75.0%")
        self.assertEqual(kpis["Requirements coverage"], "50.0%")
        checks = {a["check"]: a["result"] for a in monthly.audit(m, ["20261115-1"])}
        self.assertEqual(checks["Every run of the month has a finished report"], "No")
        self.assertEqual(checks["Every story in scope has test cases"], "No")
        self.assertEqual(checks["Root cause recorded for at least 95% of failed cases"], "Yes")
        self.assertEqual(checks["Every escaped defect has a root cause"], "Yes")

    def test_escaped_file_validation(self):
        path = temp_dir() / "escaped_defects.csv"
        monthly.ensure_escaped_file(path)
        self.assertEqual(monthly.read_escaped(path), [])
        path.write_text(path.read_text(encoding="utf-8-sig") + "20/11/2026,B,t,major,S,code,user,\n", encoding="utf-8-sig")
        with self.assertRaises(ValueError):
            monthly.read_escaped(path)

    def test_previous_month(self):
        self.assertEqual(monthly.previous_month("2026-01"), "2025-12")
        self.assertEqual(monthly.previous_month("2026-11"), "2026-10")

    def test_build_with_trend_without_agent_or_sheets(self):
        project = temp_dir()
        runs = project / "runs"
        for run_id, data in (("20261020-090000", report("20261020-090000", 4)),
                             ("20261105-090000", report("20261105-090000", 1))):
            (runs / run_id / "artifacts").mkdir(parents=True)
            (runs / run_id / "artifacts" / "report_data.json").write_text(json.dumps(data))
        cfg = base_cfg(runs)
        with mock.patch("qa_flow.sheets.publish_table", return_value="https://sheet"):
            out = monthly.build_monthly(cfg, "2026-11", use_agent=False)
        self.assertEqual(out["runs"], 1)
        self.assertEqual(out["url"], "https://sheet")
        text = out["report"].read_text()
        self.assertIn("Monthly Quality Report - 2026-11", text)
        self.assertIn("| Defects found in testing | 1 | 4 |", text)  # this month vs last month
        self.assertTrue((project / "escaped_defects.csv").exists())


if __name__ == "__main__":
    unittest.main()
