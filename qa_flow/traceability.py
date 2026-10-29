"""Requirements traceability matrix (RTM) and the requirement gaps log.

RTM: every story (requirement) -> its scenarios -> its test cases -> results -> bugs.
Gaps: the questions raised during story analysis, kept in requirement_gaps.csv so you can
send them to the BA/dev team and record the answers. Each gap caught here is a defect
prevented before testing.
"""
import csv
from datetime import date
from pathlib import Path

GAP_COLUMNS = ["gap_id", "story", "question", "status", "answer", "raised"]
GAP_STATUSES = ("open", "answered", "closed")  # closed = no longer relevant

MATRIX_COLUMNS = [
    ("Story", "story"), ("Summary", "summary"), ("Risk", "risk"), ("Acceptance Criteria", "ac_count"),
    ("Scenarios Covered", "scenarios"), ("Test Cases", "test_cases"), ("Passed", "Pass"), ("Failed", "Fail"),
    ("Blocked", "Blocked"), ("Not Run", "Not Run"), ("Bugs", "bugs"), ("Open Gaps", "open_gaps"),
    ("Coverage Status", "coverage"),
]


# ---- gaps -----------------------------------------------------------------
def collect_gaps(analysis: dict, order: list) -> list:
    gaps = []
    for key in order:
        for n, question in enumerate(analysis.get(key, {}).get("questions") or [], 1):
            gaps.append({"gap_id": f"{key}-Q{n:02d}", "story": key, "question": question,
                         "status": "open", "answer": "", "raised": date.today().isoformat()})
    return gaps


def read_gaps(path: Path) -> list:
    if not path.exists():
        return []
    gaps, errors = [], []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            if not row.get("gap_id"):
                continue
            row["status"] = row.get("status", "").lower() or "open"
            if row["status"] not in GAP_STATUSES:
                errors.append(f"line {line} ({row['gap_id']}): status '{row['status']}' - use one of {', '.join(GAP_STATUSES)}")
                continue
            gaps.append({c: row.get(c, "") for c in GAP_COLUMNS})
    if errors:
        raise ValueError(f"Fix these rows in {path.name}:\n  " + "\n  ".join(errors))
    return gaps


def write_gaps(path: Path, gaps: list) -> list:
    """Write requirement_gaps.csv. Rows you already edited (status, answer) are kept as they are."""
    existing = {g["gap_id"]: g for g in read_gaps(path)}
    merged = [existing.get(g["gap_id"], g) for g in gaps]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=GAP_COLUMNS)
        writer.writeheader()
        writer.writerows(merged)
    return merged


# ---- traceability matrix ----------------------------------------------------
def _coverage(case_count: int, counts: dict | None) -> str:
    if not case_count:
        return "Not covered"
    if counts is None:
        return "Covered - not executed yet"
    if counts["Fail"]:
        return "Failed"
    if counts["Blocked"]:
        return "Blocked"
    if counts["Not Run"] or counts["Skipped"]:
        return "Partially executed"
    return "Passed"


def build_matrix(order: list, analysis: dict, cases: list, results: dict | None = None, gaps: list | None = None) -> list:
    """One row per story. `results` (test case id -> result) is None before execution."""
    matrix = []
    for key in order:
        a = analysis.get(key, {})
        story_cases = [c for c in cases if c["story"] == key]
        scenario_ids = {s.get("id") for s in a.get("scenarios", [])}
        covered = scenario_ids & {c.get("scenario") for c in story_cases}
        counts = None
        if results is not None:
            counts = {s: 0 for s in ("Pass", "Fail", "Blocked", "Skipped", "Not Run")}
            for c in story_cases:
                counts[results[c["id"]]["status"]] += 1
        bugs = sorted({results[c["id"]]["bug_id"] for c in story_cases
                       if results is not None and results[c["id"]].get("bug_id")})
        risk = a.get("risk")
        matrix.append({
            "story": key, "summary": a.get("summary", ""),
            "risk": f"{risk['level']} ({risk['score']})" if risk else "",
            "ac_count": len(a.get("acceptance_criteria") or []),
            "scenarios": f"{len(covered)}/{len(scenario_ids)}",
            "scenarios_covered": len(covered), "scenarios_total": len(scenario_ids),
            "test_cases": ", ".join(c["id"] for c in story_cases),
            **({s: counts[s] for s in ("Pass", "Fail", "Blocked", "Not Run")} if counts
               else {s: "" for s in ("Pass", "Fail", "Blocked", "Not Run")}),
            "bugs": ", ".join(bugs),
            "open_gaps": sum(1 for g in gaps or [] if g["story"] == key and g["status"] == "open"),
            "coverage": _coverage(len(story_cases), counts),
        })
    return matrix
