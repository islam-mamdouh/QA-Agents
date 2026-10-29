"""Turns agent JSON into readable markdown files. Edit here to change how outputs look."""


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


def stories_md(stories: dict, order: list) -> str:
    rows = ["# Stories (dependency order)", "",
            "| # | Key | Summary | Priority | Depends on | Outside this set |",
            "|---|-----|---------|----------|------------|------------------|"]
    for n, key in enumerate(order, 1):
        s = stories[key]
        rows.append(f"| {n} | {key} | {_cell(s['summary'])} | {_cell(s.get('priority'))} | "
                    f"{_cell(s.get('depends_on'))} | {_cell(s.get('external_depends_on'))} |")
    return "\n".join(rows) + "\n"


def test_plan_md(plan: dict, notes: list) -> str:
    scope = plan.get("scope", {})
    parts = [
        "# Test Plan", "",
        "## Approach", plan.get("approach", ""), "",
        "## Scope", "**In scope**", _bullets(scope.get("in")), "", "**Out of scope**", _bullets(scope.get("out")), "",
        "## Test types", _bullets(plan.get("test_types")), "",
        "## Environments", _bullets(plan.get("environments")), "",
        "## Entry criteria", _bullets(plan.get("entry_criteria")), "",
        "## Exit criteria", _bullets(plan.get("exit_criteria")), "",
        "## Risks", _bullets(f"{r.get('risk')} - mitigation: {r.get('mitigation')}" for r in plan.get("risks", [])), "",
        "## Execution order", " -> ".join(plan.get("execution_order", [])), "",
        "## Per story (risk = impact x likelihood)",
        "| Story | Risk | Priority | Focus | Test types |", "|-------|------|----------|-------|------------|",
    ]
    parts += [f"| {p.get('key')} | {_risk(p.get('risk'))} | {_cell(p.get('priority'))} | {_cell(p.get('focus'))} | "
              f"{_cell(p.get('test_types'))} |" for p in plan.get("story_plans", [])]
    return "\n".join(parts) + "\n" + _notes(notes)


def test_cases_md(cases: list, plan: dict, analysis: dict, stories: dict, notes: list) -> str:
    out = ["# Manual Test Cases", "",
           f"Total: **{len(cases)}** test cases. Run them in the order below "
           "(stories are ordered by dependency).", "",
           "Record each result in `results.csv`: status = Pass / Fail / Blocked / Skipped, "
           "plus actual result, bug id and notes in your own words.", _notes(notes), ""]
    for key in plan.get("execution_order", []):
        story_cases = [c for c in cases if c["story"] == key]
        if not story_cases:
            continue
        a = analysis.get(key, {})
        out += [f"## {key} - {stories[key]['summary']}", ""]
        if a.get("risk"):
            out.append(f"Risk: **{_risk(a['risk'])}** - {_cell(a['risk'].get('reason'))}  ")
        if a.get("depends_on"):
            out.append(f"Depends on: {', '.join(a['depends_on'])}  ")
        if a.get("questions"):
            out += ["**Open questions for the team:**", _bullets(a["questions"]), ""]
        for c in story_cases:
            out += [f"### {c['id']} - {c['title']}",
                    f"**Priority:** {c.get('priority', '')} | **Type:** {c.get('type', '')} | "
                    f"**Scenario:** {c.get('scenario', '')}", ""]
            if c.get("preconditions"):
                out += ["**Preconditions:**", _bullets(c["preconditions"]), ""]
            if c.get("test_data"):
                out += [f"**Test data:** {_cell(c['test_data'])}", ""]
            out += ["| # | Step | Expected result |", "|---|------|-----------------|"]
            out += [f"| {n} | {_cell(s['action'])} | {_cell(s['expected'])} |" for n, s in enumerate(c["steps"], 1)]
            out.append("")
    return "\n".join(out)


def report_md(summary: dict, stats: dict, rows: list, quality: dict) -> str:
    s = stats["by_status"]
    out = ["# Test Execution Report", "",
           "## Executive summary", summary.get("executive_summary", ""), "",
           "## Results", f"Total {stats['total']} | Executed {stats['executed']} | Pass rate {stats['pass_rate']}", "",
           "| " + " | ".join(s) + " |", "|" + "---|" * len(s), "| " + " | ".join(str(v) for v in s.values()) + " |", "",
           "## Quality assessment", summary.get("quality_assessment", ""), "",
           "## Exit criteria"]
    out += [f"- {_cell(e.get('criterion'))}: **{e.get('met')}** {_cell(e.get('note'))}" for e in summary.get("exit_criteria", [])]
    out += ["", "## Key risks", _bullets(summary.get("key_risks")), "",
            "## Recommendations", _bullets(summary.get("recommendations")), "",
            "## Improvement actions", _bullets(summary.get("improvement_actions")), "",
            "## Quality KPIs", "| KPI | Value | What it means |", "|---|---|---|"]
    out += [f"| {k['kpi']} | {k['value']} | {_cell(k['meaning'])} |" for k in quality["kpis"]]
    for title, key in (("Pareto - failed cases by story", "pareto_by_story"),
                       ("Pareto - failed cases by root cause", "pareto_by_root_cause")):
        out += ["", f"## {title}", "| Item | Failed | % | Cumulative % | Vital few |", "|---|---|---|---|---|"]
        out += [f"| {p['item']} | {p['count']} | {p['percent']} | {p['cumulative']} | {p['vital']} |"
                for p in quality[key]] or ["| none | | | | |"]
    out += ["", "## Failed and blocked", "| ID | Title | Status | Severity | Root cause | Defect | Bug |",
            "|---|---|---|---|---|---|---|"]
    out += [f"| {r['id']} | {_cell(r['title'])} | {r['status']} | {r['severity']} | {r.get('root_cause', '')} | "
            f"{_cell(r['defect_summary'])} | {r['bug_id']} |"
            for r in rows if r["status"] in ("Fail", "Blocked")]
    return "\n".join(out) + "\n"


def traceability_md(matrix: list) -> str:
    from .traceability import MATRIX_COLUMNS
    out = ["# Requirements Traceability Matrix", "",
           "Each story (requirement) -> scenarios -> test cases -> results -> bugs.", "",
           "| " + " | ".join(h for h, _ in MATRIX_COLUMNS) + " |", "|" + "---|" * len(MATRIX_COLUMNS)]
    out += ["| " + " | ".join(_cell(row.get(f)) for _, f in MATRIX_COLUMNS) + " |" for row in matrix]
    return "\n".join(out) + "\n"


def gaps_md(gaps: list) -> str:
    out = ["# Requirement Gaps", "",
           "Questions found while analysing the stories. Send them to the BA/dev team before testing,",
           "then record each answer and set status (open / answered / closed) in `requirement_gaps.csv`.", "",
           "| Gap ID | Story | Question | Status | Answer |", "|---|---|---|---|---|"]
    out += [f"| {g['gap_id']} | {g['story']} | {_cell(g['question'])} | {g['status']} | {_cell(g['answer'])} |" for g in gaps]
    return "\n".join(out if gaps else out[:3] + ["No gaps were found."]) + "\n"


def bug_reports_md(rows: list, cases: list, plan: dict) -> str:
    """Ready-to-paste bug reports for every failed case, built from the test case (no tokens)."""
    by_id = {c["id"]: c for c in cases}
    environments = "; ".join(plan.get("environments") or []) or "(fill in)"
    out = ["# Bug Reports (drafts)", "",
           "One draft per failed test case. Every field is filled from the test case and your results;",
           "attach the evidence and paste into the bug tracker.", ""]
    failed = [r for r in rows if r["status"] == "Fail"]
    if not failed:
        return "\n".join(out + ["No failed test cases."]) + "\n"
    for r in failed:
        case = by_id[r["id"]]
        steps = case.get("steps", [])
        out += [f"## {r.get('bug_id') or '(new bug)'} - {r.get('defect_summary') or case['title']}", "",
                "| Field | Value |", "|---|---|",
                f"| Story | {r['story']} |", f"| Test case | {r['id']} - {_cell(case['title'])} |",
                f"| Severity | {r.get('severity') or '(fill in)'} |", f"| Priority | {case.get('priority', '')} |",
                f"| Root cause | {r.get('root_cause') or '(fill in)'} |", f"| Environment | {_cell(environments)} |",
                "", "**Preconditions**", _bullets(case.get("preconditions")), ""]
        if case.get("test_data"):
            out += [f"**Test data:** {_cell(case['test_data'])}", ""]
        out += ["**Steps to reproduce**"] + [f"{n}. {s['action']}" for n, s in enumerate(steps, 1)]
        out += ["", f"**Expected result:** {steps[-1]['expected'] if steps else ''}",
                f"**Actual result:** {r.get('actual_result') or '(fill in)'}",
                "**Evidence:** (attach screenshot, video or logs)", ""]
        if r.get("recommendation"):
            out += [f"**Note:** {r['recommendation']}", ""]
    return "\n".join(out) + "\n"


def monthly_md(month: str, m: dict) -> str:
    s = m.get("summary") or {}
    chart = m["control_chart"]
    out = [f"# Monthly Quality Report - {month}", "",
           "## Executive summary", s.get("executive_summary") or "(no finished runs this month)", "",
           "## Trend", s.get("trend_assessment", ""), "",
           "## KPIs", "| KPI | This month | Last month | What it means |", "|---|---|---|---|"]
    out += [f"| {k['kpi']} | {k['value']} | {k['last_month']} | {_cell(k['meaning'])} |" for k in m["kpis"]]
    out += ["", "## Control chart - failed cases per run",
            f"Centre line {chart['mean']} | upper limit (UCL) {chart['ucl']} | lower limit (LCL) {chart['lcl']}", "",
            "| Run | Failed | Signal |", "|---|---|---|"]
    out += [f"| {p['run']} | {p['failed']} | {p['signal']} |" for p in chart["points"]] or ["| none | | |"]
    out += ["", "## Pareto - defects by root cause (testing + escaped)",
            "| Root cause | Count | % | Cumulative % | Vital few |", "|---|---|---|---|---|"]
    out += [f"| {p['item']} | {p['count']} | {p['percent']} | {p['cumulative']} | {p['vital']} |"
            for p in m["pareto_by_root_cause"]] or ["| none | | | | |"]
    out += ["", "## Severity", "| Severity | In testing | Escaped |", "|---|---|---|"]
    out += [f"| {r['severity']} | {r['testing']} | {r['escaped']} |" for r in m["severity"]]
    out += ["", "## Escaped defects", "| Date | Bug | Title | Severity | Root cause | Found by |", "|---|---|---|---|---|---|"]
    out += [f"| {e['date']} | {e['bug_id']} | {_cell(e['title'])} | {e['severity']} | {e['root_cause']} | {_cell(e['found_by'])} |"
            for e in m["escaped"]] or ["| none | | | | | |"]
    out += ["", "## Process audit (automatic)", "| Check | Result | Evidence |", "|---|---|---|"]
    out += [f"| {a['check']} | {a['result']} | {_cell(a['evidence'])} |" for a in m["audit"]]
    out += ["", "For the manual part of the audit use `templates/monthly_audit_checklist.md`.",
            "", "## Improvement actions", _bullets(s.get("improvement_actions"))]
    return "\n".join(out) + "\n"
