"""Orchestrator: runs the agents in order for one Change Request (CR), owns the review loops
and the checkpoints.

Design phase (`python3 run.py design --cr CR-ID`):
  01 CR intake (your pasted CR text, no Jira access) -> 02 CR analysis (+review)
  -> 03 test plan (+review) -> 04 test cases (+review)
  -> test_cases.xlsx (Jira test fields), cr_analysis.md, requirement gaps, results.csv; then pauses.
Report phase (`python3 run.py report`), after you ran the cases and filled results.csv:
  05 report rows -> 06 UAT summary
  -> pot.xlsx (proof of testing), bug_reports.md (ready for Jira), uat_summary.md, quality.md.

Every step is saved when it finishes, and every review round is saved too,
so `python3 run.py resume` continues from the exact point where a run stopped.
"""
import hashlib
from collections import Counter
from pathlib import Path

from . import render
from .agents import Agents
from .excel import POT_COLUMNS, TEST_CASE_COLUMNS, simple_columns, rows_from_lists, test_case_row, write_workbook
from .intake import cr_path, read_cr
from .llm import LLM
from .quality import compute_quality
from .results import STATUS_ORDER, read_results, write_template
from .risk import check_risk, rate
from .traceability import (GAP_SHEET_COLUMNS, MATRIX_COLUMNS, build_matrix, collect_gaps, read_gaps,
                           write_gaps)

CASE_TYPES = ("positive", "negative", "boundary")
PRIORITIES = ("high", "medium", "low")
REGRESSION = "REG"   # pseudo requirement that holds the regression test cases of impacted areas


class WorkflowError(Exception):
    pass


def chunk(items: list, size: int) -> list:
    return [items[i:i + size] for i in range(0, len(items), max(1, int(size)))]


def check_keys(list_name: str, field: str, expected: list):
    """Validator: reply must contain a list covering every expected key (used for fire-back)."""
    def validate(data: dict) -> None:
        items = data.get(list_name)
        if not isinstance(items, list) or not items:
            raise ValueError(f"'{list_name}' must be a non-empty list")
        got = {item.get(field) for item in items if isinstance(item, dict)}
        missing = [k for k in expected if k not in got]
        if missing:
            raise ValueError(f"'{list_name}' is missing {field}: {', '.join(missing)}")
    return validate


def check_analysis(data: dict) -> None:
    reqs = data.get("requirements")
    if not isinstance(reqs, list) or not reqs:
        raise ValueError("'requirements' must be a non-empty list")
    ids = [r.get("id") for r in reqs]
    if len(set(ids)) != len(ids) or not all(ids) or REGRESSION in ids:
        raise ValueError(f"every requirement needs a unique 'id' (R1, R2...; '{REGRESSION}' is reserved)")
    for r in reqs:
        if not r.get("text") or not isinstance(r.get("scenarios"), list) or not r["scenarios"]:
            raise ValueError(f"requirement '{r['id']}' needs 'text' and at least one scenario")
        bad = [s.get("id") for s in r["scenarios"] if s.get("type") not in CASE_TYPES]
        if bad:
            raise ValueError(f"requirement '{r['id']}': scenario type must be one of {', '.join(CASE_TYPES)} ({bad})")
    for name in ("journey_stages", "systems", "regression_areas", "questions"):
        if not isinstance(data.get(name), list):
            raise ValueError(f"'{name}' must be a list (it can be empty)")
    check_risk(data)


def check_plan(ids: list):
    def validate(data: dict) -> None:
        for name in ("approach", "execution_order", "exit_criteria"):
            if name not in data:
                raise ValueError(f"missing '{name}'")
        missing = [k for k in ids if k not in data["execution_order"]]
        if missing:
            raise ValueError(f"'execution_order' is missing: {', '.join(missing)}")
    return validate


def check_cases(ids: list):
    def validate(data: dict) -> None:
        check_keys("test_cases", "requirement", ids)(data)
        for case in data["test_cases"]:
            name = case.get("summary", "?")
            for field in ("summary", "module", "system", "expected_result"):
                if not case.get(field):
                    raise ValueError(f"case '{name}' needs '{field}'")
            if not isinstance(case.get("steps"), list) or not case["steps"] or not all(case["steps"]):
                raise ValueError(f"case '{name}' needs 'steps' as a non-empty list of actions")
            if case.get("type") not in CASE_TYPES or case.get("priority") not in PRIORITIES:
                raise ValueError(f"case '{name}': type must be {'/'.join(CASE_TYPES)} and priority {'/'.join(PRIORITIES)}")
    return validate


def requirements_with_regression(analysis: dict) -> list:
    """CR requirements (with calculated risk) plus one pseudo requirement for the regression areas."""
    reqs = [{**r, "risk": {**rate(r["risk_impact"], r["risk_likelihood"]), "reason": r.get("risk_reason", "")}}
            for r in analysis["requirements"]]
    areas = [a for a in analysis.get("regression_areas", []) if a.get("area")]
    if areas:
        reqs.append({"id": REGRESSION, "text": "Regression of impacted areas", "risk": None,
                     "scenarios": [{"id": f"G{n}", "title": f"{a['area']} still works ({a.get('reason', '')})",
                                    "type": "positive", "priority": "medium"} for n, a in enumerate(areas, 1)]})
    return reqs


class Orchestrator:
    def __init__(self, cfg: dict, store):
        self.cfg, self.store = cfg, store
        self.flow = cfg["flow"]
        self.agents = Agents(cfg, LLM(cfg, store))

    # ---- generic building blocks ----------------------------------------
    def _step(self, key: str, fn):
        """Run fn once. If the step finished in an earlier run, return its saved result."""
        if self.store.is_done(key):
            return self.store.load(key)
        print(f"-> {key}")
        self.store.set(current_step=key)
        self.store.update_step(key, status="running")
        result = fn()
        self.store.save(key, result)
        self.store.update_step(key, status="done")
        return result

    def _reviewed(self, key: str, role: str, stage: str, task_input, validate):
        """Author (Opus) writes -> reviewer (Sonnet) checks -> author revises ...

        Loop exit: no major issues left, or max_review_rounds reached (then an incident is
        logged and the latest version is used, with open issues kept as reviewer notes).
        Saved after every author and reviewer call, so a restart resumes mid-loop.
        """
        if self.store.is_done(key):
            return self.store.load(key)
        self.store.set(current_step=key)
        saved = self.store.step(key)
        rnd, phase, issues = saved.get("round", 0), saved.get("phase", "write"), saved.get("issues", [])
        draft = self.store.load(f"{key}.draft") if phase != "write" else None

        while phase not in ("approved", "limit"):
            if phase in ("write", "revise"):
                rnd += 1
                print(f"-> {key}: {role} round {rnd}")
                draft = self.agents.write(role, task_input, key, previous=draft if phase == "revise" else None,
                                          issues=issues, validate=validate)
                self.store.save(f"{key}.draft", draft)
                phase = "review"
                self.store.update_step(key, status="running", round=rnd, phase=phase)

            print(f"-> {key}: review round {rnd}")
            review = self.agents.review(stage, task_input, draft, key, previous_issues=issues)
            issues = review["issues"]
            majors = [i for i in issues if i["severity"] == "major"]
            if not majors:
                phase = "approved"
            elif rnd >= self.flow["max_review_rounds"]:
                phase = "limit"
                self.store.incidents.log(key, "review_limit", f"{len(majors)} major issue(s) open after {rnd} rounds",
                                         "continued with the latest version; issues kept as reviewer notes")
            else:
                phase = "revise"
            self.store.update_step(key, phase=phase, issues=issues)

        self.store.save(key, draft)
        self.store.update_step(key, status="done")
        return draft

    def _notes(self, prefix: str) -> list:
        """Major issues left open when a review loop hit its round limit."""
        return [i for k, step in self.store.state["steps"].items()
                if k.startswith(prefix) and step.get("phase") == "limit"
                for i in step.get("issues", []) if i["severity"] == "major"]

    # ---- design phase ------------------------------------------------------
    def design(self, cr_id: str, cr_file: str | None = None) -> None:
        self.store.set(phase="design", status="running", cr=cr_id)
        inputs = self.cfg["inputs"]
        path = Path(cr_file) if cr_file else cr_path(inputs["crs_dir"], cr_id)
        cr = self._step("01_cr", lambda: read_cr(cr_id, path, int(inputs["cr_max_chars"]), self.store))
        print(f"   {cr['id']}: {cr['title']}")

        analysis = self._reviewed("02_analysis", "cr_analysis", "analysis",
                                  {"cr": {k: cr[k] for k in ("id", "title", "text")}}, check_analysis)
        requirements = requirements_with_regression(analysis)
        plan = self._plan(cr, analysis, requirements)
        cases = self._cases(cr, plan, requirements)

        gaps = write_gaps(self.store.dir / "requirement_gaps.csv", collect_gaps(cr["id"], analysis.get("questions", [])))
        matrix = build_matrix(requirements, cases, gaps=gaps)
        self.store.write_text("cr_analysis.md", render.cr_analysis_md(cr, analysis, requirements, gaps,
                                                                      self._notes("02_analysis")))
        self.store.write_text("test_plan.md", render.test_plan_md(cr, plan, requirements, self._notes("03_test_plan")))
        write_workbook(self.store.dir / "test_cases.xlsx", [
            ("Test Cases", TEST_CASE_COLUMNS, [test_case_row(c) for c in cases], None),
            ("Traceability", MATRIX_COLUMNS, matrix, None),
            ("Gaps for BA-Dev", GAP_SHEET_COLUMNS, gaps, None),
            ("Exploratory Charters", simple_columns(["Charter"], 100),
             rows_from_lists([[c] for c in analysis.get("exploratory_charters", [])]), None),
        ])
        if self._notes("04_cases"):
            self.store.write_text("reviewer_notes.md", render.notes_md(self._notes("04_cases")))
        write_template(self.store.dir / "results.csv", cases)  # never overwrites a file you already started
        self.store.set(status="waiting_for_results", current_step=None)
        d = self.store.dir
        print(f"\nDone: {len(cases)} test cases, {len(gaps)} gaps for the BA/dev team."
              f"\n  Test cases (enter into Jira): {d / 'test_cases.xlsx'}"
              f"\n  CR analysis and gaps:         {d / 'cr_analysis.md'}  (answers go in requirement_gaps.csv)"
              f"\n  Fill in after testing:        {d / 'results.csv'}"
              f"\n  Then run:                     python3 run.py report --run {d.name}")

    def _plan(self, cr: dict, analysis: dict, requirements: list) -> dict:
        ids = [r["id"] for r in requirements]
        task = {"cr": {"id": cr["id"], "title": cr["title"]}, "summary": analysis.get("summary", ""),
                "journey_stages": analysis.get("journey_stages", []), "systems": analysis.get("systems", []),
                "test_data_needed": analysis.get("test_data_needed", []),
                "requirements": [{"id": r["id"], "text": r["text"],
                                  "risk": r["risk"] and {"score": r["risk"]["score"], "level": r["risk"]["level"]},
                                  "scenarios": [f"{s.get('id')} {s.get('type')}/{s.get('priority')}: {s.get('title')}"
                                                for s in r.get("scenarios", [])]} for r in requirements]}
        plan = self._reviewed("03_test_plan", "test_plan", "test_plan", task, check_plan(ids))
        plan["execution_order"] = [i for i in plan["execution_order"] if i in ids]
        plan["execution_order"] += [i for i in ids if i not in plan["execution_order"]]
        return plan

    def _cases(self, cr: dict, plan: dict, requirements: list) -> list:
        by_id = {r["id"]: r for r in requirements}
        focus = {p.get("id"): p.get("focus", "") for p in plan.get("requirement_plans", [])}
        shared = {k: plan[k] for k in ("approach", "systems_and_environments", "test_data_preparation") if k in plan}
        per_req = {}
        for i, batch in enumerate(chunk(plan["execution_order"], self.flow["cases_batch_size"]), 1):
            task = {"cr": {"id": cr["id"], "title": cr["title"]}, "plan": shared,
                    "requirements": [{**{k: v for k, v in by_id[rid].items() if k not in ("risk_reason",)},
                                      "focus": focus.get(rid, "")} for rid in batch]}
            result = self._reviewed(f"04_cases_b{i:02d}", "test_cases", "test_cases", task, check_cases(batch))
            for case in result["test_cases"]:
                per_req.setdefault(case.get("requirement"), []).append(case)

        # IDs are given here, not by the agent: always unique and stable, in execution order.
        cases, n = [], 0
        for rid in plan["execution_order"]:
            for case in per_req.get(rid, []):
                n += 1
                cases.append({**case, "id": f"{cr['id']}-TC-{n:03d}", "requirement": rid})
        self.store.save("test_cases", cases)
        self.store.save("requirements", requirements)
        return cases

    # ---- report phase ------------------------------------------------------
    def report(self, results_path: str | None = None) -> None:
        cases = self.store.load("test_cases")
        if cases is None:
            raise WorkflowError("This run has no test cases yet. Finish the design phase first (resume).")
        self.store.set(phase="report", status="running", current_step="report")
        cr = self.store.load("01_cr")
        requirements = self.store.load("requirements") or []
        analysis = self.store.load("02_analysis") or {}
        plan = self.store.load("03_test_plan") or {}
        path = Path(results_path) if results_path else self.store.dir / "results.csv"
        results = read_results(path, cases, self.store.incidents, strict=self.flow["strict_results"])
        gaps_path = self.store.dir / "requirement_gaps.csv"
        gaps = read_gaps(gaps_path)

        # the report is rebuilt when the results or the gap answers change
        digest = hashlib.sha256(path.read_bytes() + (gaps_path.read_bytes() if gaps_path.exists() else b"")).hexdigest()
        if self.store.state.get("results_hash") not in (None, digest):
            self.store.incidents.log("report", "data", "results or gap answers changed since the last report",
                                     "report steps restarted")
            for prefix in ("05_", "06_"):
                self.store.reset_steps(prefix)
        self.store.set(phase="report", status="running", results_hash=digest, results_file=str(path))

        rows = [{**{k: c.get(k, "") for k in ("id", "requirement", "summary", "module", "system", "priority",
                                                "type", "expected_result")}, **results[c["id"]]} for c in cases]

        # Only rows with something to rewrite go to the agent; plain passes are formatted in Python.
        needs_text = [r for r in rows if r["status"] in ("Fail", "Blocked") or r["actual_result"] or r["notes"]]
        polished = {}
        for i, batch in enumerate(chunk(needs_text, self.flow["report_batch_size"]), 1):
            key = f"05_report_rows_b{i:02d}"
            task = {"rows": [{k: r[k] for k in ("id", "summary", "module", "system", "status", "expected_result",
                                                "actual_result", "severity", "notes") if r.get(k)} for r in batch]}
            out = self._step(key, lambda: self.agents.write("report_rows", task, key,
                                                            validate=check_keys("rows", "id", [r["id"] for r in batch])))
            polished.update({r["id"]: r for r in out["rows"]})

        for row in rows:
            extra = polished.get(row["id"], {})
            row["actual_result"] = extra.get("actual_result") or row["actual_result"] or (
                "Works as expected." if row["status"] == "Pass" else "")
            row["severity"] = row["severity"] or (extra.get("severity", "") if row["status"] == "Fail" else "")
            row["defect_title"] = extra.get("defect_title", "")
            row["recommendation"] = extra.get("recommendation", "")

        stats = compute_stats(rows)
        matrix = build_matrix(requirements, cases, results, gaps)
        quality = compute_quality(rows, [r["id"] for r in requirements], gaps, matrix)
        open_bugs = [{k: r[k] for k in ("bug_id", "defect_title", "severity", "module", "bug_status")}
                     for r in rows if r["status"] == "Fail" and r.get("bug_status") not in ("fixed", "rejected")]
        open_questions = [{k: g[k] for k in ("gap_id", "requirement", "question", "confirm_with")}
                          for g in gaps if g["status"] == "open"]
        summary = self._step("06_uat_summary", lambda: self.agents.write("uat_summary", {
            "cr": {"id": cr["id"], "title": cr["title"]},
            "what_changed": {"summary": analysis.get("summary", ""), "journey_stages": analysis.get("journey_stages", []),
                             "systems": analysis.get("systems", []),
                             "requirements": [{"id": r["id"], "text": r["text"]} for r in requirements]},
            "how_tested": {"approach": plan.get("approach", ""), "systems": plan.get("systems_and_environments", []),
                           "cases_by_type": dict(Counter(c.get("type") for c in cases)),
                           "regression_cases": sum(1 for c in cases if c["requirement"] == REGRESSION)},
            "stats": stats, "exit_criteria": plan.get("exit_criteria", []),
            "open_bugs": open_bugs, "open_questions": open_questions,
        }, "06_uat_summary"))

        d = self.store.dir
        self.store.save("report_data", {"run_id": d.name, "cr": cr["id"], "rows": rows, "stats": stats,
                                        "quality": quality, "gaps": gaps, "matrix": matrix, "summary": summary})
        write_workbook(d / "pot.xlsx", [
            (f"POT {cr['id']}", POT_COLUMNS, rows, "status"),
            ("Traceability", MATRIX_COLUMNS, matrix, None),
            ("Summary", simple_columns(["Item", "Value"], 40),
             rows_from_lists([["CR", f"{cr['id']} - {cr['title']}"], ["Environment", self.cfg["test_environment"]],
                              ["Test cases", stats["total"]], ["Executed", stats["executed"]],
                              ["Pass rate", stats["pass_rate"]]]
                             + [[s, n] for s, n in stats["by_status"].items()]), None),
        ])
        self.store.write_text("bug_reports.md", render.bug_reports_md(rows, cases, self.cfg["test_environment"]))
        self.store.write_text("uat_summary.md", render.uat_summary_md(cr, summary, stats, open_bugs, open_questions))
        self.store.write_text("quality.md", render.quality_md(cr, stats, quality, matrix, rows))
        self.store.set(status="done", current_step=None)
        print(f"\nReport ready for {cr['id']}:"
              f"\n  POT (proof of testing): {d / 'pot.xlsx'}"
              f"\n  Bug reports for Jira:   {d / 'bug_reports.md'}"
              f"\n  UAT meeting summary:    {d / 'uat_summary.md'}"
              f"\n  Quality (KPIs, Pareto): {d / 'quality.md'}")


def compute_stats(rows: list) -> dict:
    by_status = {s: 0 for s in STATUS_ORDER}
    per_requirement = {}
    for row in rows:
        by_status[row["status"]] += 1
        req = per_requirement.setdefault(row["requirement"], {s: 0 for s in STATUS_ORDER})
        req[row["status"]] += 1
    executed = len(rows) - by_status["Not Run"]
    return {
        "total": len(rows),
        "executed": executed,
        "by_status": by_status,
        "pass_rate": f"{100 * by_status['Pass'] / executed:.1f}%" if executed else "n/a",
        "failed_by_severity": {sev: sum(1 for r in rows if r["status"] == "Fail" and r.get("severity") == sev)
                               for sev in ("critical", "major", "minor", "trivial")},
        "per_requirement": per_requirement,
    }
