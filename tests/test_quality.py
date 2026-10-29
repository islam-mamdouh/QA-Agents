import unittest
from collections import Counter

from qa_flow.quality import compute_quality, pareto
from qa_flow.risk import check_risk, rate


def row(story, status, **extra):
    return {"id": f"{story}-{status}-{len(extra)}", "story": story, "status": status, **extra}


class RiskTest(unittest.TestCase):
    def test_score_and_levels(self):
        self.assertEqual(rate(5, 4), {"impact": 5, "likelihood": 4, "score": 20, "level": "high"})
        self.assertEqual(rate(3, 3)["level"], "medium")
        self.assertEqual(rate(2, 3)["level"], "low")

    def test_validator(self):
        check_risk({"stories": [{"key": "A", "risk_impact": 5, "risk_likelihood": 1}]})
        for bad in (0, 6, "3", 2.5, True, None):
            with self.assertRaises(ValueError):
                check_risk({"stories": [{"key": "A", "risk_impact": bad, "risk_likelihood": 3}]})


class QualityTest(unittest.TestCase):
    def test_pareto_marks_vital_few(self):
        rows = pareto(Counter({"code": 6, "requirements": 2, "data": 1, "test": 1}))
        self.assertEqual([r["item"] for r in rows], ["code", "requirements", "data", "test"])
        self.assertEqual([r["vital"] for r in rows], ["Yes", "Yes", "", ""])
        self.assertEqual(rows[-1]["cumulative"], "100.0%")
        self.assertEqual(pareto(Counter()), [])

    def test_kpis(self):
        rows = [row("A", "Pass"), row("A", "Fail", severity="critical", root_cause="code", bug_status="rejected"),
                row("B", "Fail", severity="minor", bug_status="fixed"), row("B", "Blocked"), row("B", "Not Run")]
        gaps = [{"status": "open"}, {"status": "answered"}, {"status": "closed"}, {"status": "open"}]
        matrix = [{"scenarios_covered": 2, "scenarios_total": 3}, {"scenarios_covered": 1, "scenarios_total": 1}]
        q = compute_quality(rows, ["A", "B", "C", "D"], gaps, matrix)
        kpis = {k["kpi"]: k["value"] for k in q["kpis"]}
        self.assertEqual(kpis["Requirements coverage"], "50.0%")
        self.assertEqual(kpis["Scenario coverage"], "75.0%")
        self.assertEqual(kpis["Stories fully executed"], "25.0%")
        self.assertEqual(kpis["Execution rate"], "80.0%")
        self.assertEqual(kpis["Pass rate"], "25.0%")
        self.assertEqual(kpis["Defect density"], "1.00")
        self.assertEqual(kpis["Critical + major share"], "50.0%")
        self.assertEqual(kpis["Requirement gaps found early"], "4")
        self.assertEqual(kpis["Requirement gaps resolved"], "50.0%")
        self.assertEqual(kpis["Bug rejection rate"], "50.0%")
        self.assertEqual(kpis["Root cause recorded"], "50.0%")
        self.assertEqual(q["pareto_by_root_cause"][0]["item"], "code")

    def test_empty_run_does_not_divide_by_zero(self):
        q = compute_quality([], [], [], [])
        self.assertTrue(all(k["value"] in ("n/a", "0") for k in q["kpis"]))


if __name__ == "__main__":
    unittest.main()
