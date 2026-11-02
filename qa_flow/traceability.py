"""Requirements traceability matrix (RTM) and the requirement gaps log.

RTM: every CR requirement -> its scenarios -> test cases -> results -> POT evidence -> bugs
(ISO 9001 style traceability, plan-do-check-act).
Gaps: the questions raised while analysing the CR, kept in requirement_gaps.csv so you can send
them to the BA/dev team before development finishes and record the answers. Each gap caught
here is a defect prevented (QA, not only QC).
"""
import csv
from datetime import date
from pathlib import Path

GAP_COLUMNS = ["gap_id", "requirement", "question", "confirm_with", "status", "answer", "raised"]
GAP_STATUSES = ("open", "answered", "closed")  # closed = no longer relevant

MATRIX_COLUMNS = [
    ("Requirement", "requirement", 12), ("Description", "text", 50), ("Risk", "risk", 14),
    ("Scenarios Covered", "scenarios", 12), ("Test Cases", "test_cases", 40), ("Passed", "Pass", 8),
    ("Failed", "Fail", 8), ("Blocked", "Blocked", 8), ("Not Run", "Not Run", 8), ("POT Evidence", "evidence", 12),
    ("Bugs", "bugs", 20), ("Open Gaps", "open_gaps", 10), ("Coverage Status", "coverage", 22),
]
GAP_SHEET_COLUMNS = [("Gap ID", "gap_id", 18), ("Requirement", "requirement", 12), ("Question", "question", 70),
                     ("Confirm With", "confirm_with", 16), ("Status", "status", 10), ("Answer", "answer", 50)]


# ---- gaps -----------------------------------------------------------------
def collect_gaps(cr_id: str, questions: list) -> list:
    return [{"gap_id": f"{cr_id}-Q{n:02d}", "requirement": q.get("requirement", ""), "question": q.get("question", ""),
             "confirm_with": q.get("confirm_with", "BA"), "status": "open", "answer": "",
             "raised": date.today().isoformat()}
            for n, q in enumerate(questions, 1) if q.get("question")]


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


def build_matrix(requirements: list, cases: list, results: dict | None = None, gaps: list | None = None) -> list:
    """One row per CR requirement. `results` (test case id -> result) is None before execution."""
    matrix = []
    for req in requirements:
        rid = req["id"]
        req_cases = [c for c in cases if c["requirement"] == rid]
        scenario_ids = {s.get("id") for s in req.get("scenarios", [])}
        covered = scenario_ids & {sid.strip() for c in req_cases for sid in str(c.get("scenario", "")).split(",")}
        counts, evidence, bugs = None, "", ""
        if results is not None:
            counts = {s: 0 for s in ("Pass", "Fail", "Blocked", "Skipped", "Not Run")}
            for c in req_cases:
                counts[results[c["id"]]["status"]] += 1
            executed = [c for c in req_cases if results[c["id"]]["status"] in ("Pass", "Fail")]
            evidence = f"{sum(1 for c in executed if results[c['id']].get('evidence'))}/{len(executed)}"
            bugs = ", ".join(sorted({results[c["id"]]["bug_id"] for c in req_cases if results[c["id"]].get("bug_id")}))
        risk = req.get("risk")
        matrix.append({
            "requirement": rid, "text": req.get("text", ""),
            "risk": f"{risk['level']} ({risk['score']})" if risk else "",
            "scenarios": f"{len(covered)}/{len(scenario_ids)}",
            "scenarios_covered": len(covered), "scenarios_total": len(scenario_ids),
            "test_cases": ", ".join(c["id"] for c in req_cases),
            **({s: counts[s] for s in ("Pass", "Fail", "Blocked", "Not Run")} if counts
               else {s: "" for s in ("Pass", "Fail", "Blocked", "Not Run")}),
            "evidence": evidence, "bugs": bugs,
            "open_gaps": sum(1 for g in gaps or [] if g["requirement"] == rid and g["status"] == "open"),
            "coverage": _coverage(len(req_cases), counts),
        })
    return matrix
