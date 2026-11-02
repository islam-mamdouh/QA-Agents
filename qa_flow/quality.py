"""Quality metrics for one CR: KPIs, Pareto analysis and severity distribution.

Plain Python, no LLM. Based on classic quality-control tools:
- KPIs (key performance indicators) to measure the test process and the product.
- Pareto (80/20): which few modules and root causes produce most of the defects, to focus regression.
- Fishbone categories: every defect gets one root cause from ROOT_CAUSES (see results.py).
"""
from collections import Counter

from .results import ROOT_CAUSES, SEVERITIES


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "n/a"


def pareto(counts: Counter) -> list:
    """Sort items by count and mark the 'vital few' that make up the first ~80% of defects."""
    total = sum(counts.values())
    rows, running = [], 0
    for item, count in counts.most_common():
        vital = running < 0.8 * total  # an item is vital if the total before it is still under 80%
        running += count
        rows.append({"item": item, "count": count, "percent": _pct(count, total),
                     "cumulative": _pct(running, total), "vital": "Yes" if vital else ""})
    return rows


def compute_quality(rows: list, requirement_ids: list, gaps: list, matrix: list) -> dict:
    total = len(rows)
    executed = [r for r in rows if r["status"] != "Not Run"]
    passed_or_failed = [r for r in rows if r["status"] in ("Pass", "Fail")]
    failed = [r for r in rows if r["status"] == "Fail"]
    blocked = [r for r in rows if r["status"] == "Blocked"]

    covered = {m["requirement"] for m in matrix if m["coverage"] != "Not covered"}
    tracked = [r for r in failed if r.get("bug_status")]
    rejected = sum(1 for r in tracked if r["bug_status"] == "rejected")
    reopened = sum(1 for r in tracked if r["bug_status"] == "reopened")
    serious = sum(1 for r in failed if r.get("severity") in ("critical", "major"))
    with_cause = sum(1 for r in failed if r.get("root_cause"))
    with_evidence = sum(1 for r in passed_or_failed if r.get("evidence"))
    resolved_gaps = sum(1 for g in gaps if g["status"] in ("answered", "closed"))
    scenarios_total = sum(m["scenarios_total"] for m in matrix)
    scenarios_covered = sum(m["scenarios_covered"] for m in matrix)

    kpis = [
        ("Requirements coverage", _pct(len(covered), len(requirement_ids)), "CR requirements that have test cases"),
        ("Scenario coverage", _pct(scenarios_covered, scenarios_total),
         "Analysed test scenarios that have at least one test case"),
        ("Execution rate", _pct(len(executed), total), "Test cases executed out of all test cases"),
        ("Pass rate", _pct(sum(1 for r in executed if r["status"] == "Pass"), len(executed)),
         "Passed out of executed test cases"),
        ("Blocked rate", _pct(len(blocked), total),
         "Cases that could not run (environment, data, dependency) - Lean waste: waiting"),
        ("POT evidence complete", _pct(with_evidence, len(passed_or_failed)),
         "Passed/failed cases with a screenshot reference"),
        ("Critical + major share", _pct(serious, len(failed)), "Failed cases with critical or major severity"),
        ("Requirement gaps found early", str(len(gaps)), "Questions raised in CR analysis (defects prevented)"),
        ("Requirement gaps resolved", _pct(resolved_gaps, len(gaps)), "Gaps answered or closed by the BA/dev team"),
        ("Bug rejection rate", _pct(rejected, len(tracked)), "Reported bugs rejected (lower = clearer bug reports)"),
        ("Bug reopen rate", _pct(reopened, len(tracked)), "Fixed bugs that failed retest"),
        ("Root cause recorded", _pct(with_cause, len(failed)), "Failed cases with a root cause filled in"),
    ]
    return {
        "kpis": [{"kpi": k, "value": v, "meaning": m} for k, v, m in kpis],
        "pareto_by_module": pareto(Counter(r.get("module") or "not set" for r in failed)),
        "pareto_by_root_cause": pareto(Counter(r.get("root_cause") or "not set" for r in failed)),
        "severity": [{"severity": s, "count": sum(1 for r in failed if r.get("severity") == s)} for s in SEVERITIES],
        "root_cause_options": list(ROOT_CAUSES),
    }
