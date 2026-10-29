"""Monthly quality report: all finished runs of a month + the defects that escaped to production.

  python3 run.py monthly --project zatca [--month 2026-11]

Inputs
- every run of the project whose report finished in that month (runs/<id>/artifacts/report_data.json)
- projects/<name>/escaped_defects.csv: bugs found after release (by users, support or production
  monitoring). You keep this file; it is created empty the first time.

Output (projects/<name>/monthly/<month>/): monthly_report.md, metrics.json and a Google Sheets tab.
It includes KPIs with the change from last month, defect leakage, a control chart of failures
per run, Pareto by root cause and an automatic process audit (internal audit, ISO 19011 style).
"""
import csv
import json
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from .quality import SEVERITIES, _pct, pareto
from .results import ROOT_CAUSES

ESCAPED_COLUMNS = ["date", "bug_id", "title", "severity", "story", "root_cause", "found_by", "notes"]


# ---- inputs ---------------------------------------------------------------
def ensure_escaped_file(path: Path) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(ESCAPED_COLUMNS)


def read_escaped(path: Path) -> list:
    """Escaped defects. date = YYYY-MM-DD when it was found; root_cause uses the results.csv options."""
    if not path.exists():
        return []
    rows, errors = [], []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            if not any(row.values()):
                continue
            try:
                datetime.strptime(row.get("date", ""), "%Y-%m-%d")
            except ValueError:
                errors.append(f"line {line}: date '{row.get('date', '')}' must be YYYY-MM-DD")
                continue
            row["root_cause"] = row.get("root_cause", "").lower()
            if row["root_cause"] and row["root_cause"] not in ROOT_CAUSES:
                errors.append(f"line {line}: root_cause '{row['root_cause']}' - use one of {', '.join(ROOT_CAUSES)}")
                continue
            row["severity"] = row.get("severity", "").lower()
            rows.append({c: row.get(c, "") for c in ESCAPED_COLUMNS})
    if errors:
        raise ValueError(f"Fix these rows in {path.name}:\n  " + "\n  ".join(errors))
    return rows


def previous_month(month: str) -> str:
    year, mon = map(int, month.split("-"))
    return f"{year - 1}-12" if mon == 1 else f"{year}-{mon - 1:02d}"


def runs_of_month(runs_dir: Path, month: str) -> dict:
    """Runs created in the month (run ids start with YYYYMMDD): finished reports and unfinished runs."""
    prefix = month.replace("-", "")
    reports, unfinished = [], []
    for run in sorted(runs_dir.glob(f"{prefix}*")) if runs_dir.exists() else []:
        data_file = run / "artifacts" / "report_data.json"
        if data_file.exists():
            reports.append(json.loads(data_file.read_text(encoding="utf-8")))
        elif (run / "state.json").exists():
            unfinished.append(run.name)
    return {"reports": reports, "unfinished": unfinished}


# ---- calculations -----------------------------------------------------------
def control_chart(points: list) -> dict:
    """c-chart for the number of failed cases per run: centre line and 3-sigma limits.

    A run above the upper limit is a signal that something in the process changed
    (a weak release, a new area, environment problems) and should be investigated.
    """
    if not points:
        return {"mean": 0, "ucl": 0, "lcl": 0, "points": []}
    mean = sum(c for _, c in points) / len(points)
    ucl, lcl = mean + 3 * math.sqrt(mean), max(0.0, mean - 3 * math.sqrt(mean))
    return {"mean": round(mean, 2), "ucl": round(ucl, 2), "lcl": round(lcl, 2),
            "points": [{"run": label, "failed": c, "signal": "above UCL" if c > ucl else ("below LCL" if c < lcl else "")}
                       for label, c in points]}


def month_metrics(reports: list, escaped: list) -> dict:
    rows = [r for rep in reports for r in rep["rows"]]
    executed = [r for r in rows if r["status"] != "Not Run"]
    failed = [r for r in rows if r["status"] == "Fail"]
    tracked = [r for r in failed if r.get("bug_status")]
    gaps = [g for rep in reports for g in rep.get("gaps", [])]
    found = len({r["bug_id"] for r in failed if r.get("bug_id")} | {r["id"] for r in failed if not r.get("bug_id")})
    stories = [m for rep in reports for m in rep.get("matrix", [])]
    covered = sum(1 for m in stories if m["coverage"] != "Not covered")

    def kpi(name, value, meaning):
        return {"kpi": name, "value": value, "meaning": meaning}

    kpis = [
        kpi("Runs reported", str(len(reports)), "Test runs with a finished report this month"),
        kpi("Test cases executed", str(len(executed)), "Across all runs"),
        kpi("Pass rate", _pct(sum(1 for r in executed if r["status"] == "Pass"), len(executed)), "Passed out of executed"),
        kpi("Requirements coverage", _pct(covered, len(stories)), "Stories with test cases, across all runs"),
        kpi("Defects found in testing", str(found), "Unique bugs from failed cases"),
        kpi("Escaped defects", str(len(escaped)), "Bugs found after release (escaped_defects.csv)"),
        kpi("Defect leakage", _pct(len(escaped), found + len(escaped)),
            "Escaped / (found in testing + escaped). Lower is better"),
        kpi("Defect detection effectiveness", _pct(found, found + len(escaped)),
            "Share of all known defects caught by testing. Higher is better"),
        kpi("Requirement gaps found early", str(len(gaps)), "Questions raised before testing (defects prevented)"),
        kpi("Requirement gaps resolved", _pct(sum(1 for g in gaps if g["status"] != "open"), len(gaps)),
            "Answered or closed by the team"),
        kpi("Bug rejection rate", _pct(sum(1 for r in tracked if r["bug_status"] == "rejected"), len(tracked)),
            "Lower = more accurate bug reports"),
        kpi("Bug reopen rate", _pct(sum(1 for r in tracked if r["bug_status"] == "reopened"), len(tracked)),
            "Fixed bugs that failed retest"),
    ]
    causes = Counter(r.get("root_cause") or "not set" for r in failed)
    causes.update(e.get("root_cause") or "not set" for e in escaped)
    return {
        "kpis": kpis,
        "control_chart": control_chart([(rep["run_id"], sum(1 for r in rep["rows"] if r["status"] == "Fail"))
                                        for rep in reports]),
        "pareto_by_root_cause": pareto(causes),
        "severity": [{"severity": s, "testing": sum(1 for r in failed if r.get("severity") == s),
                      "escaped": sum(1 for e in escaped if e.get("severity") == s)} for s in SEVERITIES],
        "escaped": escaped,
        "_raw": {"failed": len(failed), "with_cause": sum(1 for r in failed if r.get("root_cause")),
                 "stories": len(stories), "covered": covered, "gaps_open": sum(1 for g in gaps if g["status"] == "open"),
                 "rejected": sum(1 for r in tracked if r["bug_status"] == "rejected"), "tracked": len(tracked)},
    }


def audit(metrics: dict, unfinished: list) -> list:
    """Automatic internal audit of the test process. Each check: Yes / No / n/a with evidence."""
    raw, chart, escaped = metrics["_raw"], metrics["control_chart"], metrics["escaped"]

    def check(name, ok, evidence):
        return {"check": name, "result": "n/a" if ok is None else ("Yes" if ok else "No"), "evidence": evidence}

    signals = [p["run"] for p in chart["points"] if p["signal"] == "above UCL"]
    return [
        check("Every run of the month has a finished report", not unfinished,
              "unfinished: " + ", ".join(unfinished) if unfinished else "all runs reported"),
        check("Every story in scope has test cases", raw["covered"] == raw["stories"] if raw["stories"] else None,
              f"{raw['covered']}/{raw['stories']} stories covered"),
        check("Root cause recorded for at least 95% of failed cases",
              raw["with_cause"] >= 0.95 * raw["failed"] if raw["failed"] else None,
              f"{raw['with_cause']}/{raw['failed']} failed cases"),
        check("No requirement gap left open", raw["gaps_open"] == 0, f"{raw['gaps_open']} open"),
        check("Bug rejection rate is 10% or less", raw["rejected"] <= 0.10 * raw["tracked"] if raw["tracked"] else None,
              f"{raw['rejected']}/{raw['tracked']} tracked bugs rejected"),
        check("Every escaped defect has a root cause", all(e["root_cause"] for e in escaped) if escaped else None,
              f"{sum(1 for e in escaped if e['root_cause'])}/{len(escaped)} analysed"),
        check("No run above the control limit (or each one investigated)", not signals,
              "signals: " + ", ".join(signals) if signals else "process in control"),
    ]


def with_trend(current: list, previous: list | None) -> list:
    before = {k["kpi"]: k["value"] for k in previous or []}
    return [{**k, "last_month": before.get(k["kpi"], "n/a")} for k in current]


# ---- build ------------------------------------------------------------------
def build_monthly(cfg: dict, month: str | None = None, use_agent: bool = True) -> dict:
    from . import render
    from .store import RunStore

    month = month or date.today().strftime("%Y-%m")
    datetime.strptime(month, "%Y-%m")  # raises ValueError for a wrong format
    project_dir = Path(cfg["flow"]["runs_dir"]).parent
    escaped_path = project_dir / "escaped_defects.csv"
    ensure_escaped_file(escaped_path)
    all_escaped = read_escaped(escaped_path)

    runs_dir = Path(cfg["flow"]["runs_dir"])
    current = runs_of_month(runs_dir, month)
    metrics = month_metrics(current["reports"], [e for e in all_escaped if e["date"].startswith(month)])
    prev = runs_of_month(runs_dir, previous_month(month))
    prev_metrics = month_metrics(prev["reports"], [e for e in all_escaped if e["date"].startswith(previous_month(month))]) \
        if prev["reports"] else None
    metrics["kpis"] = with_trend(metrics["kpis"], prev_metrics and prev_metrics["kpis"])
    metrics["audit"] = audit(metrics, current["unfinished"])

    store = RunStore(project_dir / "monthly" / month)
    summary = {}
    if use_agent and current["reports"]:
        from .agents import Agents
        from .llm import LLM
        summary = Agents(cfg, LLM(cfg, store)).write("monthly_summary", {
            "month": month,
            "kpis": metrics["kpis"],
            "control_chart": metrics["control_chart"],
            "pareto_by_root_cause": metrics["pareto_by_root_cause"],
            "severity": metrics["severity"],
            "audit": metrics["audit"],
            "escaped": [{k: e[k] for k in ("title", "severity", "root_cause")} for e in metrics["escaped"]],
        }, "monthly_summary")
    metrics["summary"] = summary

    store.save("metrics", {k: v for k, v in metrics.items() if k != "_raw"})
    report_path = store.write_text("monthly_report.md", render.monthly_md(month, metrics))
    url = None
    if current["reports"]:
        from .sheets import publish_table
        prefix = cfg["google_sheets"].get("worksheet_prefix", "QA")
        url = publish_table(cfg, store, f"{prefix} Monthly {month}", ["Section", "Item", "Value", "Last month / note"],
                            monthly_rows(metrics), [170, 320, 120, 380], "monthly_sheet")
    return {"month": month, "runs": len(current["reports"]), "report": report_path, "url": url,
            "escaped_file": escaped_path}


def monthly_rows(metrics: dict) -> list:
    """Flat rows for the Google Sheets tab."""
    s = metrics.get("summary") or {}
    rows = [["Summary", "Executive summary", "", s.get("executive_summary", "")],
            ["Summary", "Trend", "", s.get("trend_assessment", "")]]
    rows += [["KPI", k["kpi"], k["value"], k["last_month"]] for k in metrics["kpis"]]
    chart = metrics["control_chart"]
    rows += [["Control chart", "Centre line / UCL / LCL", f"{chart['mean']} / {chart['ucl']} / {chart['lcl']}",
              "failed cases per run"]]
    rows += [["Control chart", p["run"], p["failed"], p["signal"]] for p in chart["points"]]
    rows += [["Pareto root cause", p["item"], p["count"], f"{p['cumulative']} cumulative {'(vital few)' if p['vital'] else ''}"]
             for p in metrics["pareto_by_root_cause"]]
    rows += [["Severity", r["severity"], r["testing"], f"escaped: {r['escaped']}"] for r in metrics["severity"]]
    rows += [["Escaped defect", e["bug_id"] or e["title"], e["severity"], f"{e['root_cause']} - {e['title']}"]
             for e in metrics["escaped"]]
    rows += [["Process audit", a["check"], a["result"], a["evidence"]] for a in metrics["audit"]]
    rows += [["Improvement action", a, "", ""] for a in s.get("improvement_actions", [])]
    return rows
