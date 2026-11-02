"""The results file you fill in after running the test cases manually (results.csv).

It also feeds the POT (proof of testing): every executed case needs a screenshot reference and,
where the flow creates them, reference / message numbers (manifest, B/L, declaration, EDI message...).
"""
import csv
from pathlib import Path

COLUMNS = ["id", "summary", "priority", "status", "actual_result", "evidence", "reference_numbers",
           "bug_id", "severity", "root_cause", "bug_status", "build", "notes"]
# Fishbone categories: where the defect came from (fill for Fail rows).
ROOT_CAUSES = ("requirements", "code", "environment", "data", "test", "people")
# Bug life: fill when you know it, so rejection and reopen rates can be measured.
BUG_STATUSES = ("open", "fixed", "rejected", "reopened")
SEVERITIES = ("critical", "major", "minor", "trivial")
STATUS_ORDER = ["Pass", "Fail", "Blocked", "Skipped", "Not Run"]
STATUS_ALIASES = {
    "pass": "Pass", "passed": "Pass", "ok": "Pass",
    "fail": "Fail", "failed": "Fail",
    "blocked": "Blocked",
    "skip": "Skipped", "skipped": "Skipped", "n/a": "Skipped",
    "": "Not Run", "not run": "Not Run", "notrun": "Not Run",
}
EMPTY = {c: "" for c in COLUMNS if c not in ("id", "summary", "priority", "status")}


def write_template(path: Path, cases: list) -> None:
    """Create results.csv pre-filled with the test cases. Never overwrites an existing file."""
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig opens cleanly in Excel
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for c in cases:
            writer.writerow([c["id"], c["summary"], c.get("priority", "")] + [""] * (len(COLUMNS) - 3))


def _choice(row: dict, field: str, options: tuple, line: int, case_id: str, errors: list) -> str | None:
    value = row.get(field, "").lower()
    if value and value not in options:
        errors.append(f"line {line} ({case_id}): {field} '{row[field]}' - use one of {', '.join(options)}")
        return None
    return value


def read_results(path: Path, cases: list, incidents, strict: bool = True) -> dict:
    """Return {test case id: {status, actual_result, evidence, ...}} for every test case.

    strict (error-proofing / Poka-Yoke):
    - Pass and Fail rows need a screenshot reference in `evidence` (the POT needs it);
    - Fail rows also need actual_result, bug_id and root_cause;
    - Blocked rows must say why (actual_result or notes).
    Otherwise the report stops and lists every row to fix.
    """
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {path}")
    known = {c["id"] for c in cases}
    results, errors = {}, []

    with path.open(newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            case_id = row.get("id", "")
            if not case_id:
                continue
            if case_id not in known:
                incidents.log("report", "data", f"unknown test case id '{case_id}' in results (line {line})", "row ignored")
                continue
            status = STATUS_ALIASES.get(row.get("status", "").lower())
            if status is None:
                errors.append(f"line {line} ({case_id}): status '{row['status']}' - use one of {', '.join(STATUS_ORDER)}")
                continue
            picked = {field: _choice(row, field, options, line, case_id, errors)
                      for field, options in (("root_cause", ROOT_CAUSES), ("bug_status", BUG_STATUSES),
                                             ("severity", SEVERITIES))}
            if None in picked.values():
                continue
            if strict:
                needed = []
                if status in ("Pass", "Fail"):
                    needed.append("evidence")
                if status == "Fail":
                    needed += ["actual_result", "bug_id", "root_cause"]
                missing = [f for f in needed if not (picked.get(f) or row.get(f))]
                if status == "Blocked" and not (row.get("actual_result") or row.get("notes")):
                    missing.append("actual_result or notes (why it is blocked)")
                if missing:
                    errors.append(f"line {line} ({case_id}): {status} needs {', '.join(missing)}")
                    continue
            results[case_id] = {**{f: row.get(f, "") for f in EMPTY}, **picked, "status": status}

    if errors:
        raise ValueError("Fix these rows in the results file and run the report again:\n  " + "\n  ".join(errors))

    missing = [c["id"] for c in cases if c["id"] not in results]
    if missing:
        incidents.log("report", "data", f"{len(missing)} test case(s) not in results file", "reported as Not Run")
    for case_id in missing:
        results[case_id] = {**EMPTY, "status": "Not Run"}
    return results
