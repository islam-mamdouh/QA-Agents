import json
import unittest

from openpyxl import load_workbook

from tests.helpers import base_cfg, temp_dir
from qa_flow import monthly


def report(run_id, fails, passes=3, cause="code", build="b1", gaps=()):
    rows = [{"id": f"{run_id}-F{i}", "status": "Fail", "bug_id": f"B-{run_id}-{i}", "root_cause": cause,
             "severity": "major", "bug_status": "fixed", "module": "Declarations", "build": build, "evidence": "f.png"}
            for i in range(fails)]
    rows += [{"id": f"{run_id}-P{i}", "status": "Pass", "module": "EDI", "build": build, "evidence": "p.png"}
             for i in range(passes)]
    return {"run_id": run_id, "cr": f"CR-{run_id}", "rows": rows, "gaps": list(gaps),
            "matrix": [{"requirement": "R1", "coverage": "Passed"}, {"requirement": "R2", "coverage": "Not covered"},
                       {"requirement": "REG", "coverage": "Passed"}]}


ESCAPED = [{"date": "2026-11-20", "bug_id": "P-1", "cr": "CR-9", "title": "t", "severity": "critical",
            "module": "Release", "root_cause": "requirements", "five_whys": "", "found_by": "UAT", "notes": ""}]


class MonthlyTest(unittest.TestCase):
    def test_control_chart_flags_a_spike(self):
        chart = monthly.control_chart([("b1", 2), ("b2", 3), ("b3", 2), ("b4", 2), ("b5", 3), ("b6", 2),
                                       ("b7", 3), ("b8", 2), ("b9", 2), ("b10", 14)])
        self.assertEqual([p["build"] for p in chart["points"] if p["signal"]], ["b10"])
        self.assertEqual(monthly.control_chart([])["points"], [])

    def test_defects_are_counted_per_build(self):
        points = monthly.defects_per_build([report("r1", 2, build="1.0"), report("r2", 1, build="1.0"),
                                            report("r3", 4, build="")])
        self.assertEqual(points, [("1.0", 3), ("r3", 4)])  # no build -> run id

    def test_leakage_pareto_and_audit(self):
        m = monthly.month_metrics([report("20261102-1", 2), report("20261110-1", 1)], ESCAPED)
        kpis = {k["kpi"]: k["value"] for k in m["kpis"]}
        self.assertEqual(kpis["CRs reported"], "2")
        self.assertEqual(kpis["Defects found in testing"], "3")
        self.assertEqual(kpis["Defect leakage"], "25.0%")
        self.assertEqual(kpis["Defect detection effectiveness"], "75.0%")
        self.assertEqual(kpis["Requirements coverage"], "50.0%")  # REG is not a requirement
        self.assertEqual(kpis["POT evidence complete"], "100.0%")
        self.assertEqual(m["pareto_by_module"][0]["item"], "Declarations")
        checks = {a["check"]: a["result"] for a in monthly.audit(m, ["20261115-1"])}
        self.assertEqual(checks["Every run of the month has a finished report"], "No")
        self.assertEqual(checks["Every CR requirement has test cases"], "No")
        self.assertEqual(checks["Every executed case has POT evidence"], "Yes")
        self.assertEqual(checks["Root cause recorded for at least 95% of failed cases"], "Yes")
        self.assertEqual(checks["Every escaped defect has a root cause and a 5 Whys analysis"], "No")

    def test_escaped_file_validation(self):
        path = temp_dir() / "escaped_defects.csv"
        monthly.ensure_escaped_file(path)
        self.assertEqual(monthly.read_escaped(path), [])
        self.assertIn("five_whys", path.read_text(encoding="utf-8-sig"))
        path.write_text(path.read_text(encoding="utf-8-sig") + "20/11/2026,B,CR-1,t,major,M,code,,UAT,\n",
                        encoding="utf-8-sig")
        with self.assertRaises(ValueError):
            monthly.read_escaped(path)

    def test_previous_month(self):
        self.assertEqual(monthly.previous_month("2026-01"), "2025-12")
        self.assertEqual(monthly.previous_month("2026-11"), "2026-10")

    def test_build_with_trend_and_excel_without_agent(self):
        project = temp_dir()
        runs = project / "runs"
        for run_id, data in (("20261020-090000-CR-1", report("20261020-090000-CR-1", 4)),
                             ("20261105-090000-CR-2", report("20261105-090000-CR-2", 1))):
            (runs / run_id / "artifacts").mkdir(parents=True)
            (runs / run_id / "artifacts" / "report_data.json").write_text(json.dumps(data))
        out = monthly.build_monthly(base_cfg(runs), "2026-11", use_agent=False)
        self.assertEqual(out["runs"], 1)
        text = out["report"].read_text()
        self.assertIn("Monthly Quality Report - 2026-11", text)
        self.assertIn("| Defects found in testing | 1 | 4 |", text)  # this month vs last month
        self.assertIn("Pareto - defects by module", text)
        self.assertTrue((project / "escaped_defects.csv").exists())
        ws = load_workbook(out["excel"]).active
        self.assertEqual(ws["A1"].value, "Section")


if __name__ == "__main__":
    unittest.main()
