"""Writes the Excel deliverables (test cases, POT, monthly report). Edit here to change columns or style.

Test case columns match the Jira test fields, so each row can be entered into Jira by hand.
"""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# (header, field, width). The first sheet of test_cases.xlsx uses exactly these columns.
TEST_CASE_COLUMNS = [
    ("Test ID", "id", 20), ("Summary", "summary", 45), ("Module", "module", 18), ("System", "system", 20),
    ("Preconditions", "preconditions", 40), ("Test Steps", "steps", 60), ("Test Data", "test_data", 30),
    ("Expected Result", "expected_result", 60), ("Type", "type", 11), ("Priority", "priority", 10),
]
POT_COLUMNS = [
    ("Test ID", "id", 20), ("Summary", "summary", 45), ("Module", "module", 18), ("System", "system", 20),
    ("Result", "status", 10), ("Actual Result", "actual_result", 50), ("Screenshot Reference", "evidence", 28),
    ("Reference / Message Numbers", "reference_numbers", 32), ("Bug ID", "bug_id", 14), ("Build", "build", 14),
    ("Notes", "notes", 30),
]
HEADER_FILL = PatternFill("solid", fgColor="29457A")
STATUS_FILLS = {"Pass": "D9F0D9", "Fail": "FAD6D6", "Blocked": "FFEDCC", "Skipped": "EBEBEB", "Not Run": "EBEBEB"}


def as_text(value) -> str:
    """Lists become numbered lines (steps) or bullet lines, so cells read well in Excel and Jira."""
    if isinstance(value, list):
        return "\n".join(f"{n}. {v}" for n, v in enumerate(value, 1))
    return "" if value is None else str(value)


def test_case_row(case: dict) -> dict:
    return {**case, "preconditions": "\n".join(f"- {p}" for p in case.get("preconditions") or []),
            "steps": as_text(case.get("steps"))}


def _add_sheet(wb, title: str, columns: list, rows: list, status_field: str | None = None) -> None:
    ws = wb.create_sheet(title[:31])
    ws.append([header for header, _, _ in columns])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for row in rows:
        ws.append([as_text(row.get(field, "")) for _, field, _ in columns])
    for index, (_, field, width) in enumerate(columns, 1):
        ws.column_dimensions[get_column_letter(index)].width = width
    for line in ws.iter_rows(min_row=2):
        for cell in line:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    if status_field:
        col = [field for _, field, _ in columns].index(status_field)
        for line in ws.iter_rows(min_row=2):
            color = STATUS_FILLS.get(str(line[col].value))
            if color:
                line[col].fill = PatternFill("solid", fgColor=color)
    ws.freeze_panes = "A2"


def write_workbook(path, sheets: list) -> None:
    """sheets: [(title, columns, rows, status_field_or_None)]."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, columns, rows, status_field in sheets:
        _add_sheet(wb, title, columns, rows, status_field)
    tmp = path.with_name(path.name + ".tmp")
    wb.save(tmp)
    tmp.replace(path)


def simple_columns(headers: list, width: int = 30) -> list:
    """Columns for a plain table whose rows are lists: field = column index."""
    return [(h, i, width) for i, h in enumerate(headers)]


def rows_from_lists(rows: list) -> list:
    return [dict(enumerate(r)) for r in rows]
