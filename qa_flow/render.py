"""Turns agent JSON into readable markdown files. Edit here to change how outputs look.

All deliverables are in English: CR analysis, test plan, bug reports (ready to paste into Jira),
UAT meeting summary, quality report and monthly report.
"""


def _cell(value) -> str:
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value)
    return str(value or "").replace("|", "/").replace("\n", " ")


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items or []) or "- none"


def _risk(risk) -> str:
    if not risk:
        return ""
    return f"{risk['level']} ({risk['score']} = {risk['impact']}x{risk['likelihood']})"


def _notes(issues: list) -> str:
    if not issues:
        return ""
    lines = [f"- [{i['severity']}] {i.get('where', '')}: {i['problem']}" for i in issues]
    return "\n\n> **Reviewer notes (not fixed)**\n> " + "\n> ".join(lines) + "\n"


def notes_md(issues: list) -> str:
    return "# Reviewer notes on the test cases (not fixed)\n" + _notes(issues)


def cr_analysis_md(cr: dict, analysis: dict, requirements: list, gaps: list, notes: list) -> str:
    out = [f"# CR Analysis - {cr['id']}: {cr['title']}", "",
           "## Summary", analysis.get("summary", ""), "",
           "## Shipment journey stages touched", _bullets(analysis.get("journey_stages")), "",
           "## Systems touched", _bullets(analysis.get("systems")), "",
           "## Requirements (risk = impact x likelihood)"]
    for r in requirements:
        out += ["", f"### {r['id']} - {r['text']}"]
        if r.get("risk"):
            out.append(f"Risk: **{_risk(r['risk'])}** - {_cell(r['risk'].get('reason'))}  ")
        if r.get("modules") or r.get("systems"):
            out.append(f"Modules: {_cell(r.get('modules'))} | Systems: {_cell(r.get('systems'))}  ")
        if r.get("acceptance_criteria"):
            out += ["**Acceptance criteria**", _bullets(r["acceptance_criteria"])]
        out += ["**Scenarios**"] + [f"- {s.get('id')} [{s.get('type')}/{s.get('priority')}] {s.get('title')}"
                                    for s in r.get("scenarios", [])]
        if r.get("risks"):
            out += ["**Risks**", _bullets(r["risks"])]
    out += ["", "## Impacted areas for regression"]
    out += [f"- **{a.get('area')}**: {a.get('reason', '')}" for a in analysis.get("regression_areas", [])] or ["- none"]
    out += ["", "## Gaps - questions for the BA / dev team",
            "Send these before development finishes; record answers and status in `requirement_gaps.csv`.", "",
            "| Gap ID | Requirement | Question | Confirm with | Status |", "|---|---|---|---|---|"]
    out += [f"| {g['gap_id']} | {g['requirement']} | {_cell(g['question'])} | {g['confirm_with']} | {g['status']} |"
            for g in gaps] or ["| none | | | | |"]
    out += ["", "## Exploratory testing charters", _bullets(analysis.get("exploratory_charters")), "",
            "## Test data needed", _bullets(analysis.get("test_data_needed"))]
    return "\n".join(out) + "\n" + _notes(notes)


def test_plan_md(cr: dict, plan: dict, requirements: list, notes: list) -> str:
    risks = {r["id"]: r.get("risk") for r in requirements}
    parts = [
        f"# Test Plan - {cr['id']}: {cr['title']}", "",
        "## Approach", plan.get("approach", ""), "",
        "## In scope", _bullets(plan.get("in_scope")), "",
        "## Out of scope", _bullets(plan.get("out_of_scope")), "",
        "## Systems and environments", _bullets(plan.get("systems_and_environments")), "",
        "## Test data preparation", _bullets(plan.get("test_data_preparation")), "",
        "## Regression scope", _bullets(plan.get("regression_scope")), "",
        "## Entry criteria", _bullets(plan.get("entry_criteria")), "",
        "## Exit criteria", _bullets(plan.get("exit_criteria")), "",
        "## Execution order", " -> ".join(plan.get("execution_order", [])), "",
        "## Per requirement", "| Requirement | Risk | Focus |", "|---|---|---|",
    ]
    parts += [f"| {p.get('id')} | {_risk(risks.get(p.get('id')))} | {_cell(p.get('focus'))} |"
              for p in plan.get("requirement_plans", [])]
    return "\n".join(parts) + "\n" + _notes(notes)


def bug_reports_md(rows: list, cases: list, environment: str) -> str:
    """Ready-to-paste Jira bug reports for every failed case, built from the test case (no tokens).

    Mandatory fields are always present (error-proofing); a critical bug also gets a 5 Whys block.
    """
    by_id = {c["id"]: c for c in cases}
    out = ["# Bug Reports", "",
           "One report per failed test case, ready to paste into Jira. Attach the evidence files named below.", ""]
    failed = [r for r in rows if r["status"] == "Fail"]
    if not failed:
        return "\n".join(out + ["No failed test cases."]) + "\n"
    for r in failed:
        case = by_id[r["id"]]
        title = r.get("defect_title") or f"[{case.get('module', '')}] {case['summary']}"
        env = environment + (f" - build {r['build']}" if r.get("build") else "")
        evidence = "; ".join(x for x in (r.get("evidence"), r.get("reference_numbers") and
                                         f"reference numbers: {r['reference_numbers']}") if x) or "(fill in)"
        out += [f"## {r.get('bug_id') or '(new bug)'}", "",
                f"**Title:** {title}", "",
                f"**Environment:** {env} | System: {case.get('system', '')} | Module: {case.get('module', '')}", "",
                "**Preconditions:**", _bullets(case.get("preconditions")), ""]
        if case.get("test_data"):
            out += [f"**Test data:** {case['test_data']}", ""]
        out += ["**Steps to reproduce:**"] + [f"{n}. {step}" for n, step in enumerate(case.get("steps", []), 1)]
        out += ["", f"**Expected result:** {case.get('expected_result', '')}", "",
                f"**Actual result:** {r.get('actual_result') or '(fill in)'}", "",
                f"**Evidence reference:** {evidence}", "",
                f"**Severity:** {r.get('severity') or '(fill in)'} | **Priority:** {case.get('priority', '')}", "",
                f"Test case: {r['id']} | Root cause: {r.get('root_cause') or '(fill in)'}", ""]
        if r.get("severity") == "critical":
            out += ["**Root cause analysis (5 Whys) - critical defect**",
                    "1. Why did it happen?", "2. Why?", "3. Why?", "4. Why?", "5. Why? (root cause)",
                    "Fishbone category: requirements / code / environment / data / test / people", ""]
    return "\n".join(out) + "\n"


def uat_summary_md(cr: dict, s: dict, stats: dict, open_bugs: list, open_questions: list) -> str:
    st = stats["by_status"]
    out = [f"# UAT Meeting Summary - {cr['id']}: {cr['title']}", "",
           "## What changed", _bullets(s.get("what_changed")), "",
           "## How it was tested", _bullets(s.get("how_tested")), "",
           "## Results", s.get("results", ""), "",
           f"Test cases: {stats['total']} | Executed: {stats['executed']} | Pass rate: {stats['pass_rate']}", "",
           "| " + " | ".join(st) + " |", "|" + "---|" * len(st), "| " + " | ".join(str(v) for v in st.values()) + " |", "",
           "## Exit criteria"]
    out += [f"- {_cell(e.get('criterion'))}: **{e.get('met')}** {_cell(e.get('note'))}"
            for e in s.get("exit_criteria", [])] or ["- none"]
    out += ["", "## Open bugs", "| Bug | Title | Severity | Module | Status |", "|---|---|---|---|---|"]
    out += [f"| {b['bug_id']} | {_cell(b['defect_title'])} | {b['severity']} | {b['module']} | {b['bug_status'] or 'open'} |"
            for b in open_bugs] or ["| none | | | | |"]
    out += ["", "## Open questions", "| Gap | Requirement | Question | Confirm with |", "|---|---|---|---|"]
    out += [f"| {q['gap_id']} | {q['requirement']} | {_cell(q['question'])} | {q['confirm_with']} |"
            for q in open_questions] or ["| none | | | |"]
    out += ["", "## Recommendation", s.get("recommendation", "")]
    if s.get("risks"):
        out += ["", "## Risks", _bullets(s["risks"])]
    return "\n".join(out) + "\n"


def quality_md(cr: dict, stats: dict, quality: dict, matrix: list, rows: list) -> str:
    from .traceability import MATRIX_COLUMNS
    out = [f"# Quality Report - {cr['id']}", "",
           "## KPIs", "| KPI | Value | What it means |", "|---|---|---|"]
    out += [f"| {k['kpi']} | {k['value']} | {_cell(k['meaning'])} |" for k in quality["kpis"]]
    for title, key in (("Pareto - failed cases by module", "pareto_by_module"),
                       ("Pareto - failed cases by root cause", "pareto_by_root_cause")):
        out += ["", f"## {title}", "| Item | Failed | % | Cumulative % | Vital few |", "|---|---|---|---|---|"]
        out += [f"| {p['item']} | {p['count']} | {p['percent']} | {p['cumulative']} | {p['vital']} |"
                for p in quality[key]] or ["| none | | | | |"]
    out += ["", "## Severity", "| Severity | Failed |", "|---|---|"]
    out += [f"| {x['severity']} | {x['count']} |" for x in quality["severity"]]
    out += ["", "## Requirements traceability",
            "| " + " | ".join(h for h, _, _ in MATRIX_COLUMNS) + " |", "|" + "---|" * len(MATRIX_COLUMNS)]
    out += ["| " + " | ".join(_cell(m.get(f)) for _, f, _ in MATRIX_COLUMNS) + " |" for m in matrix]
    out += ["", "## Failed and blocked", "| ID | Summary | Status | Severity | Module | Root cause | Bug |",
            "|---|---|---|---|---|---|---|"]
    out += [f"| {r['id']} | {_cell(r['summary'])} | {r['status']} | {r['severity']} | {r['module']} | "
            f"{r.get('root_cause', '')} | {r['bug_id']} |" for r in rows if r["status"] in ("Fail", "Blocked")] \
        or ["| none | | | | | | |"]
    return "\n".join(out) + "\n"


def monthly_md(month: str, m: dict) -> str:
    s = m.get("summary") or {}
    chart = m["control_chart"]
    out = [f"# Monthly Quality Report - {month}", "",
           "## Executive summary", s.get("executive_summary") or "(no finished runs this month)", "",
           "## Trend", s.get("trend_assessment", ""), "",
           "## KPIs", "| KPI | This month | Last month | What it means |", "|---|---|---|---|"]
    out += [f"| {k['kpi']} | {k['value']} | {k['last_month']} | {_cell(k['meaning'])} |" for k in m["kpis"]]
    out += ["", "## Control chart - defects per build",
            f"Centre line {chart['mean']} | upper limit (UCL) {chart['ucl']} | lower limit (LCL) {chart['lcl']}", "",
            "| Build | Failed cases | Signal |", "|---|---|---|"]
    out += [f"| {p['build']} | {p['failed']} | {p['signal']} |" for p in chart["points"]] or ["| none | | |"]
    for title, key in (("module", "pareto_by_module"), ("root cause", "pareto_by_root_cause")):
        out += ["", f"## Pareto - defects by {title} (testing + escaped)",
                f"| {title.capitalize()} | Count | % | Cumulative % | Vital few |", "|---|---|---|---|---|"]
        out += [f"| {p['item']} | {p['count']} | {p['percent']} | {p['cumulative']} | {p['vital']} |"
                for p in m[key]] or ["| none | | | | |"]
    out += ["", "## Severity", "| Severity | In testing | Escaped |", "|---|---|---|"]
    out += [f"| {r['severity']} | {r['testing']} | {r['escaped']} |" for r in m["severity"]]
    out += ["", "## Escaped defects", "| Date | Bug | CR | Title | Severity | Module | Root cause | 5 Whys | Found by |",
            "|---|---|---|---|---|---|---|---|---|"]
    out += [f"| {e['date']} | {e['bug_id']} | {e['cr']} | {_cell(e['title'])} | {e['severity']} | {e['module']} | "
            f"{e['root_cause']} | {_cell(e['five_whys']) or 'missing'} | {_cell(e['found_by'])} |"
            for e in m["escaped"]] or ["| none | | | | | | | | |"]
    out += ["", "## Process audit (automatic)", "| Check | Result | Evidence |", "|---|---|---|"]
    out += [f"| {a['check']} | {a['result']} | {_cell(a['evidence'])} |" for a in m["audit"]]
    out += ["", "For the manual part of the audit use `templates/monthly_audit_checklist.md`.",
            "", "## Improvement actions", _bullets(s.get("improvement_actions"))]
    return "\n".join(out) + "\n"
