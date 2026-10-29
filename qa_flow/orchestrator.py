"""Orchestrator: runs the agents in order, owns the review loops and the checkpoints.

Design phase (steps 1-13):
  01 stories agent (Jira or Linear) -> 02 story analysis (+review) -> 03 test plan (+review) -> 04 test cases (+review)
  -> outputs test_cases.md and results.csv, then pauses for manual execution.
Report phase (steps 14-15), started by `python3 run.py report`:
  05 report rows -> 06 report summary -> 07 Google Sheets.

Every step is saved when it finishes, and every review round is saved too,
so `python3 run.py resume` continues from the exact point where a run stopped.
"""
import hashlib
from pathlib import Path

from . import render
from .agents import Agents
from . import jira_agent, linear_agent
from .llm import LLM
from .quality import compute_quality
from .risk import check_risk, rate
from .results import STATUS_ORDER, read_results, write_template
from .sheets import publish, publish_design
from .traceability import build_matrix, collect_gaps, read_gaps, write_gaps


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


def both(*validators):
    """Run several validators one after the other."""
    def validate(data: dict) -> None:
        for check in validators:
            check(data)
    return validate


def check_plan(keys: list):
    def validate(data: dict) -> None:
        for name in ("approach", "story_plans", "execution_order"):
            if name not in data:
                raise ValueError(f"missing '{name}'")
        check_keys("story_plans", "key", keys)(data)
        missing = [k for k in keys if k not in data["execution_order"]]
        if missing:
            raise ValueError(f"'execution_order' is missing: {', '.join(missing)}")
    return validate


def check_cases(keys: list):
    def validate(data: dict) -> None:
        check_keys("test_cases", "story", keys)(data)
        for case in data["test_cases"]:
            steps = case.get("steps")
            if not case.get("title") or not isinstance(steps, list) or not steps:
                raise ValueError(f"case '{case.get('title', '?')}' needs a title and at least one step")
            if any(not s.get("action") or not s.get("expected") for s in steps):
                raise ValueError(f"case '{case['title']}' has a step without 'action' or 'expected'")
    return validate


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

    # ---- design phase: steps 1-13 ----------------------------------------
    def _fetch_stories(self, query):
        """query: a JQL string (Jira) or a list of issue keys (Linear); None = use config.md."""
        if self.cfg["source"] == "linear":
            return linear_agent.fetch_stories(self.cfg, self.store, query)
        return jira_agent.fetch_stories(self.cfg, self.store, query)

    def design(self, query=None) -> None:
        self.store.set(phase="design", status="running")

        data = self._step("01_stories", lambda: self._fetch_stories(query))
        stories, order = data["stories"], data["order"]
        if not order:
            raise WorkflowError(f"{self.cfg['source'].capitalize()} returned no stories for this filter.")
        self.store.write_text("stories.md", render.stories_md(stories, order))
        print(f"   {len(order)} stories, dependency order: {', '.join(order)}")

        analysis = self._analysis(stories, order)
        self.store.save("analysis", analysis)
        plan = self._plan(stories, order, analysis)
        cases = self._cases(plan, analysis)

        self.store.write_text("test_plan.md", render.test_plan_md(plan, self._notes("03_test_plan")))
        self.store.write_text("test_cases.md", render.test_cases_md(cases, plan, analysis, stories, self._notes("04_cases")))
        results = self.store.dir / "results.csv"
        write_template(results, cases)  # never overwrites a file you already started filling

        # Requirement gaps (questions for the team) and the traceability matrix, before testing
        gaps = write_gaps(self.store.dir / "requirement_gaps.csv", collect_gaps(analysis, order))
        matrix = build_matrix(plan["execution_order"], analysis, cases, gaps=gaps)
        self.store.write_text("traceability.md", render.traceability_md(matrix))
        self.store.write_text("requirement_gaps.md", render.gaps_md(gaps))
        sheet = self._step("04_design_sheets", lambda: {"url": publish_design(self.cfg, self.store, gaps, matrix)})
        self.store.set(status="waiting_for_results", current_step=None)
        print(f"\nRequirement gaps to send to the team ({len(gaps)}): {sheet['url']}"
              f"\n  record answers in {self.store.dir / 'requirement_gaps.csv'}")
        print(f"\nDone. Read:   {self.store.dir / 'test_cases.md'}"
              f"\nFill in:      {results}"
              f"\nThen run:     python3 run.py report --project {self.cfg['project']} --run {self.store.dir.name}")

    def _analysis(self, stories: dict, order: list) -> dict:
        analysis = {}
        for i, batch in enumerate(chunk(order, self.flow["analysis_batch_size"]), 1):
            task = {
                "stories": [stories[k] for k in batch],
                # stories this batch depends on: summary only, not the full text
                "dependency_context": [{"key": d, "summary": stories[d]["summary"]}
                                       for d in {d for k in batch for d in stories[k].get("depends_on", [])}
                                       if d not in batch],
            }
            result = self._reviewed(f"02_analysis_b{i:02d}", "story_analysis", "analysis", task,
                                    both(check_keys("stories", "key", batch), check_risk))
            for item in result["stories"]:
                if item.get("key") in stories:
                    source = stories[item["key"]]
                    analysis[item["key"]] = {**item, "summary": source["summary"],
                                             "priority": source.get("priority", ""),
                                             "depends_on": source.get("depends_on", []),
                                             "risk": {**rate(item.get("risk_impact", 3), item.get("risk_likelihood", 3)),
                                                      "reason": item.get("risk_reason", "")}}
        return analysis

    def _plan(self, stories: dict, order: list, analysis: dict) -> dict:
        task = {"dependency_order": order, "stories": [
            {"key": k, "summary": a["summary"], "priority": a["priority"], "depends_on": a["depends_on"],
             "scenarios": [f"{s.get('id')} {s.get('type')}/{s.get('priority')}: {s.get('title')}"
                           for s in a.get("scenarios", [])],
             "risks": a.get("risks", [])[:5],
             "risk": {"score": a["risk"]["score"], "level": a["risk"]["level"]}}
            for k, a in ((k, analysis[k]) for k in order)]}
        plan = self._reviewed("03_test_plan", "test_plan", "test_plan", task, check_plan(order))
        plan["execution_order"] = [k for k in plan["execution_order"] if k in stories]
        for story_plan in plan["story_plans"]:  # the calculated risk is shown next to each story
            if story_plan.get("key") in analysis:
                story_plan["risk"] = analysis[story_plan["key"]]["risk"]
        return plan

    def _cases(self, plan: dict, analysis: dict) -> list:
        shared = {k: plan[k] for k in ("approach", "test_types", "environments") if k in plan}
        per_story = {}
        for i, batch in enumerate(chunk(plan["execution_order"], self.flow["cases_batch_size"]), 1):
            task = {"plan": shared,
                    "story_plans": [p for p in plan["story_plans"] if p.get("key") in batch],
                    "analyses": [analysis[k] for k in batch]}
            result = self._reviewed(f"04_cases_b{i:02d}", "test_cases", "test_cases", task, check_cases(batch))
            for case in result["test_cases"]:
                per_story.setdefault(case.get("story"), []).append(case)

        # IDs are given here, not by the agent: always unique and stable.
        cases = []
        for key in plan["execution_order"]:
            for n, case in enumerate(per_story.get(key, []), 1):
                cases.append({"id": f"{key}-TC{n:02d}", **case, "story": key})
        self.store.save("test_cases", cases)
        return cases

    def _notes(self, prefix: str) -> list:
        """Major issues left open when a review loop hit its round limit."""
        return [i for k, step in self.store.state["steps"].items()
                if k.startswith(prefix) and step.get("phase") == "limit"
                for i in step.get("issues", []) if i["severity"] == "major"]

    def _stories_in_scope(self) -> list:
        data = self.store.load("01_stories") or {}
        return data.get("order", [])

    def _load_analysis(self) -> dict:
        """The combined story analysis (rebuilt from the batch outputs for runs made before it was saved)."""
        analysis = self.store.load("analysis")
        if analysis is not None:
            return analysis
        stories = (self.store.load("01_stories") or {}).get("stories", {})
        analysis = {}
        for key in self.store.state["steps"]:
            if key.startswith("02_analysis"):
                for item in (self.store.load(key) or {}).get("stories", []):
                    analysis[item.get("key")] = {**item, "summary": stories.get(item.get("key"), {}).get("summary", ""),
                                                 "risk": rate(item.get("risk_impact", 3), item.get("risk_likelihood", 3))}
        return analysis

    # ---- report phase: steps 14-15 ---------------------------------------
    def report(self, results_path: str | None = None) -> None:
        cases = self.store.load("test_cases")
        if cases is None:
            raise WorkflowError("This run has no test cases yet. Finish the design phase first (resume).")
        self.store.set(phase="report", status="running", current_step="report")
        path = Path(results_path) if results_path else self.store.dir / "results.csv"
        results = read_results(path, cases, self.store.incidents, strict=self.flow["strict_results"])
        gaps_path = self.store.dir / "requirement_gaps.csv"
        gaps = read_gaps(gaps_path)

        # the report is rebuilt when the results or the gap answers change
        digest = hashlib.sha256(path.read_bytes() + (gaps_path.read_bytes() if gaps_path.exists() else b"")).hexdigest()
        if self.store.state.get("results_hash") not in (None, digest):
            self.store.incidents.log("report", "data", "results or gap answers changed since the last report",
                                     "report steps restarted")
            for prefix in ("05_", "06_", "07_"):
                self.store.reset_steps(prefix)
        self.store.set(phase="report", status="running", results_hash=digest, results_file=str(path))

        rows = []
        for case in cases:
            result = results[case["id"]]
            rows.append({"id": case["id"], "story": case["story"], "title": case["title"],
                         "priority": case.get("priority", ""), "type": case.get("type", ""),
                         "expected": case["steps"][-1]["expected"], **result})

        # Only rows with something to rewrite go to the agent; plain passes are formatted in Python.
        needs_text = [r for r in rows if r["status"] in ("Fail", "Blocked") or r["actual_result"] or r["notes"]]
        polished = {}
        for i, batch in enumerate(chunk(needs_text, self.flow["report_batch_size"]), 1):
            key = f"05_report_rows_b{i:02d}"
            task = {"rows": [{k: v for k, v in r.items() if v and k not in ("story", "type", "root_cause", "bug_status")}
                             for r in batch]}
            out = self._step(key, lambda: self.agents.write("report_rows", task, key,
                                                            validate=check_keys("rows", "id", [r["id"] for r in batch])))
            polished.update({r["id"]: r for r in out["rows"]})

        for row in rows:
            extra = polished.get(row["id"], {})
            row["actual_result"] = extra.get("actual_result") or row["actual_result"] or (
                "Works as expected." if row["status"] == "Pass" else "")
            for field in ("defect_summary", "severity", "recommendation"):
                row[field] = extra.get(field, "")

        stats = compute_stats(rows)
        plan = self.store.load("03_test_plan") or {}
        analysis = self._load_analysis()
        matrix = build_matrix(plan.get("execution_order") or self._stories_in_scope(), analysis, cases, results, gaps)
        quality = compute_quality(rows, self._stories_in_scope(), gaps, matrix)
        summary = self._step("06_report_summary", lambda: self.agents.write("report_summary", {
            "stats": stats,
            "quality": {k: quality[k] for k in ("kpis", "pareto_by_story", "pareto_by_root_cause", "severity")},
            "exit_criteria": plan.get("exit_criteria", []),
            "problems": [{k: r[k] for k in ("id", "title", "priority", "status", "severity", "root_cause", "defect_summary")}
                         for r in rows if r["status"] in ("Fail", "Blocked")],
        }, "06_report_summary"))

        self.store.save("report_data", {"run_id": self.store.dir.name, "rows": rows, "stats": stats,
                                        "quality": quality, "gaps": gaps, "matrix": matrix, "summary": summary})
        self.store.write_text("report.md", render.report_md(summary, stats, rows, quality))
        self.store.write_text("traceability.md", render.traceability_md(matrix))
        self.store.write_text("bug_reports.md", render.bug_reports_md(rows, cases, plan))
        sheet = self._step("07_google_sheets",
                           lambda: {"url": publish(self.cfg, self.store, rows, summary, stats, quality, gaps, matrix)})
        self.store.set(status="done", current_step=None)
        print(f"\nReport ready: {sheet['url']}\nLocal copy:   {self.store.dir / 'report.md'}"
              f"\nBug drafts:   {self.store.dir / 'bug_reports.md'}")


def compute_stats(rows: list) -> dict:
    by_status = {s: 0 for s in STATUS_ORDER}
    per_story = {}
    for row in rows:
        by_status[row["status"]] += 1
        story = per_story.setdefault(row["story"], {s: 0 for s in STATUS_ORDER})
        story[row["status"]] += 1
    executed = len(rows) - by_status["Not Run"]
    return {
        "total": len(rows),
        "executed": executed,
        "by_status": by_status,
        "pass_rate": f"{100 * by_status['Pass'] / executed:.1f}%" if executed else "n/a",
        "failed_by_severity": {sev: sum(1 for r in rows if r["status"] == "Fail" and r.get("severity") == sev)
                               for sev in ("critical", "major", "minor", "trivial")},
        "per_story": per_story,
    }
