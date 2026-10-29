"""The results file you fill in after running the test cases manually (results.csv)."""
import csv
from pathlib import Path

COLUMNS = ["id", "story", "title", "priority", "status", "actual_result", "bug_id", "root_cause", "bug_status", "notes"]
# Fishbone categories: where the defect came from (fill for Fail rows).
ROOT_CAUSES = ("requirements", "design", "code", "environment", "data", "integration", "test", "other")
# Bug life: fill when you know it, so rejection and reopen rates can be measured.
BUG_STATUSES = ("open", "fixed", "rejected", "reopened")
STATUS_ORDER = ["Pass", "Fail", "Blocked", "Skipped", "Not Run"]
STATUS_ALIASES = {
    "pass": "Pass", "passed": "Pass", "ok": "Pass",
    "fail": "Fail", "failed": "Fail",
    "blocked": "Blocked",
    "skip": "Skipped", "skipped": "Skipped", "n/a": "Skipped",
    "": "Not Run", "not run": "Not Run", "notrun": "Not Run",
}


def write_template(path: Path, cases: list) -> None:
    """Create results.csv pre-filled with the test cases. Never overwrites an existing file."""
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig opens cleanly in Excel
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for c in cases:
            writer.writerow([c["id"], c["story"], c["title"], c.get("priority", "")] + [""] * (len(COLUMNS) - 4))


def read_results(path: Path, cases: list, incidents, strict: bool = True) -> dict:
    """Return {test case id: {status, actual_result, bug_id, root_cause, bug_status, notes}} for every test case.

    strict (error-proofing): a Fail row must have actual_result, bug_id and root_cause, and a
    Blocked row must say why (actual_result or notes). Otherwise the report stops and lists the rows.
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
            root_cause = row.get("root_cause", "").lower()
            if root_cause and root_cause not in ROOT_CAUSES:
                errors.append(f"line {line} ({case_id}): root_cause '{row['root_cause']}' - use one of {', '.join(ROOT_CAUSES)}")
                continue
            bug_status = row.get("bug_status", "").lower()
            if bug_status and bug_status not in BUG_STATUSES:
                errors.append(f"line {line} ({case_id}): bug_status '{row['bug_status']}' - use one of {', '.join(BUG_STATUSES)}")
                continue
            if strict:
                missing = []
                if status == "Fail":
                    missing = [f for f in ("actual_result", "bug_id", "root_cause") if not row.get(f)]
                elif status == "Blocked" and not (row.get("actual_result") or row.get("notes")):
                    missing = ["actual_result or notes (why it is blocked)"]
                if missing:
                    errors.append(f"line {line} ({case_id}): {status} needs {', '.join(missing)}")
                    continue
            results[case_id] = {"status": status, "actual_result": row.get("actual_result", ""),
                                "bug_id": row.get("bug_id", ""), "root_cause": root_cause,
                                "bug_status": bug_status, "notes": row.get("notes", "")}

    if errors:
        raise ValueError("Fix these rows in the results file and run the report again:\n  " + "\n  ".join(errors))

    missing = [c["id"] for c in cases if c["id"] not in results]
    if missing:
        incidents.log("report", "data", f"{len(missing)} test case(s) not in results file", "reported as Not Run")
    for case_id in missing:
        results[case_id] = {"status": "Not Run", "actual_result": "", "bug_id": "", "root_cause": "",
                            "bug_status": "", "notes": ""}
    return results
