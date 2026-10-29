"""Google Sheets output.

Design phase: Gaps (questions for the team) and Traceability (requirements -> test cases).
Report phase: Results, Summary, Quality, Traceability (with results) and Gaps.
"""
from .config import require
from .retry import RetryableError, retry
from .traceability import GAP_COLUMNS, MATRIX_COLUMNS

RESULT_COLUMNS = [
    ("Test Case ID", "id"), ("Story", "story"), ("Title", "title"), ("Priority", "priority"),
    ("Type", "type"), ("Status", "status"), ("Expected Result", "expected"),
    ("Actual Result", "actual_result"), ("Severity", "severity"), ("Defect Summary", "defect_summary"),
    ("Bug ID", "bug_id"), ("Root Cause", "root_cause"), ("Bug Status", "bug_status"),
    ("Recommendation", "recommendation"),
]
STATUS_COLORS = {  # light background colors for the Status column
    "Pass": {"red": 0.85, "green": 0.94, "blue": 0.85},
    "Fail": {"red": 0.98, "green": 0.84, "blue": 0.84},
    "Blocked": {"red": 1.0, "green": 0.93, "blue": 0.80},
    "Skipped": {"red": 0.92, "green": 0.92, "blue": 0.92},
    "Not Run": {"red": 0.92, "green": 0.92, "blue": 0.92},
}
HEADER_STYLE = {"textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                "backgroundColor": {"red": 0.16, "green": 0.27, "blue": 0.45}}


def _fresh_sheet(spreadsheet, title: str, rows: int, cols: int):
    """Create the tab, or clear it if it exists (so resuming this step is safe)."""
    import gspread
    try:
        ws = spreadsheet.worksheet(title)
        ws.clear()
        ws.resize(rows=rows, cols=cols)
        return ws
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def _summary_values(summary: dict, stats: dict) -> list:
    values = [["Test Execution Summary", ""], ["", ""],
              ["Total test cases", stats["total"]], ["Executed", stats["executed"]], ["Pass rate", stats["pass_rate"]]]
    values += [[status, count] for status, count in stats["by_status"].items()]
    values += [["", ""], ["Executive summary", summary.get("executive_summary", "")],
               ["Quality assessment", summary.get("quality_assessment", "")], ["", ""], ["Exit criteria", "Met"]]
    values += [[e.get("criterion", ""), f"{e.get('met', '')} {e.get('note', '')}".strip()]
               for e in summary.get("exit_criteria", [])]
    values += [["", ""], ["Key risks", "\n".join(summary.get("key_risks", []))],
               ["Recommendations", "\n".join(summary.get("recommendations", []))],
               ["Improvement actions", "\n".join(summary.get("improvement_actions", []))], ["", ""],
               ["Story", "Pass / Fail / Blocked / Skipped / Not Run"]]
    values += [[story, " / ".join(str(v) for v in counts.values())] for story, counts in stats["per_story"].items()]
    return values


GAP_HEADERS = ["Gap ID", "Story", "Question", "Status", "Answer", "Raised"]


def _table(spreadsheet, title: str, header: list, body: list, widths: list) -> list:
    """Write a simple table tab (header row styled, frozen, wrapped text). Returns format requests."""
    ws = _fresh_sheet(spreadsheet, title, len(body) + 1, len(header))
    ws.update(range_name="A1", values=[header] + [[str(v) for v in row] for row in body])
    ws.format("1:1", HEADER_STYLE)
    ws.freeze(rows=1)
    requests = [{"repeatCell": {
        "range": {"sheetId": ws.id, "startRowIndex": 1},
        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}}]
    requests += [{"updateDimensionProperties": {
        "range": {"sheetId": ws.id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
        "properties": {"pixelSize": w}, "fields": "pixelSize"}} for i, w in enumerate(widths)]
    return requests


def _trace_tabs(spreadsheet, prefix: str, run_id: str, gaps: list, matrix: list) -> list:
    requests = _table(spreadsheet, f"{prefix} Traceability {run_id}", [h for h, _ in MATRIX_COLUMNS],
                      [[row.get(f, "") for _, f in MATRIX_COLUMNS] for row in matrix],
                      [90, 240, 100, 90, 90, 260, 60, 60, 60, 60, 120, 80, 170])
    requests += _table(spreadsheet, f"{prefix} Gaps {run_id}", GAP_HEADERS,
                       [[g.get(c, "") for c in GAP_COLUMNS] for g in gaps] or [["none", "", "", "", "", ""]],
                       [110, 90, 420, 90, 300, 100])
    return requests


def _quality_values(quality: dict) -> tuple:
    """Rows for the Quality tab, plus the row numbers of the section titles (for bold formatting)."""
    values, titles = [], []

    def section(title: str, header: list, body: list):
        titles.append(len(values))
        values.append([title, "", "", "", ""])
        values.append(header + [""] * (5 - len(header)))
        values.extend([[str(c) for c in row] + [""] * (5 - len(row)) for row in body] or [["none", "", "", "", ""]])
        values.append([""] * 5)

    section("Quality KPIs", ["KPI", "Value", "What it means"],
            [[k["kpi"], k["value"], k["meaning"]] for k in quality["kpis"]])
    section("Pareto - failed cases by story", ["Story", "Failed", "%", "Cumulative %", "Vital few (80%)"],
            [[p["item"], p["count"], p["percent"], p["cumulative"], p["vital"]] for p in quality["pareto_by_story"]])
    section("Pareto - failed cases by root cause", ["Root cause", "Failed", "%", "Cumulative %", "Vital few (80%)"],
            [[p["item"], p["count"], p["percent"], p["cumulative"], p["vital"]] for p in quality["pareto_by_root_cause"]])
    section("Failed cases by severity", ["Severity", "Count"], [[s["severity"], s["count"]] for s in quality["severity"]])
    return values, titles


def _write(cfg: dict, run_id: str, rows: list, summary: dict, stats: dict, quality: dict,
           gaps: list, matrix: list) -> str:
    import gspread
    try:
        client = gspread.service_account(filename=require(cfg, "google_sheets.service_account_file"))
        spreadsheet = client.open_by_key(require(cfg, "google_sheets.spreadsheet_id"))
        prefix = cfg["google_sheets"].get("worksheet_prefix", "QA")

        # Results tab
        results = _fresh_sheet(spreadsheet, f"{prefix} Results {run_id}", len(rows) + 1, len(RESULT_COLUMNS))
        values = [[h for h, _ in RESULT_COLUMNS]] + [[str(r.get(f, "")) for _, f in RESULT_COLUMNS] for r in rows]
        results.update(range_name="A1", values=values)
        results.format("1:1", HEADER_STYLE)
        results.freeze(rows=1)
        status_col = [f for _, f in RESULT_COLUMNS].index("status")
        requests = [{"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [{"sheetId": results.id, "startRowIndex": 1, "startColumnIndex": status_col,
                        "endColumnIndex": status_col + 1}],
            "booleanRule": {"condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": status}]},
                            "format": {"backgroundColor": color}}}}} for status, color in STATUS_COLORS.items()]
        requests.append({"repeatCell": {
            "range": {"sheetId": results.id, "startRowIndex": 1},
            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}})
        widths = [130, 90, 260, 80, 90, 80, 260, 260, 80, 240, 90, 110, 90, 240]
        requests += [{"updateDimensionProperties": {
            "range": {"sheetId": results.id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}} for i, w in enumerate(widths)]

        # Summary tab
        summary_values = _summary_values(summary, stats)
        summary_ws = _fresh_sheet(spreadsheet, f"{prefix} Summary {run_id}", len(summary_values), 2)
        summary_ws.update(range_name="A1", values=summary_values)
        summary_ws.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})
        summary_ws.format("A:A", {"textFormat": {"bold": True}})
        requests += [
            {"updateDimensionProperties": {"range": {"sheetId": summary_ws.id, "dimension": "COLUMNS",
                                                     "startIndex": 0, "endIndex": 1},
                                           "properties": {"pixelSize": 220}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": summary_ws.id, "dimension": "COLUMNS",
                                                     "startIndex": 1, "endIndex": 2},
                                           "properties": {"pixelSize": 600}, "fields": "pixelSize"}},
            {"repeatCell": {"range": {"sheetId": summary_ws.id},
                            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
        ]
        # Quality tab: KPIs, Pareto tables and severity distribution
        quality_values, titles = _quality_values(quality)
        quality_ws = _fresh_sheet(spreadsheet, f"{prefix} Quality {run_id}", len(quality_values), 5)
        quality_ws.update(range_name="A1", values=quality_values)
        for t in titles:
            quality_ws.format(f"{t + 1}:{t + 1}", {"textFormat": {"bold": True, "fontSize": 12}})
            quality_ws.format(f"A{t + 2}:E{t + 2}", HEADER_STYLE)
        requests += [{"updateDimensionProperties": {
            "range": {"sheetId": quality_ws.id, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}} for i, w in enumerate([240, 90, 380, 110, 120])]

        requests += _trace_tabs(spreadsheet, prefix, run_id, gaps, matrix)
        spreadsheet.batch_update({"requests": requests})
        return f"{spreadsheet.url}#gid={results.id}"
    except gspread.exceptions.APIError as error:
        status = getattr(error.response, "status_code", 0)
        if status == 429 or status >= 500:
            raise RetryableError(f"Google Sheets HTTP {status}")
        raise


def _open(cfg: dict):
    import gspread
    client = gspread.service_account(filename=require(cfg, "google_sheets.service_account_file"))
    return client.open_by_key(require(cfg, "google_sheets.spreadsheet_id"))


def _sheets_errors(fn):
    """Turn temporary Google errors (429, 5xx) into retryable ones."""
    import gspread
    try:
        return fn()
    except gspread.exceptions.APIError as error:
        status = getattr(error.response, "status_code", 0)
        if status == 429 or status >= 500:
            raise RetryableError(f"Google Sheets HTTP {status}")
        raise


def publish_design(cfg: dict, store, gaps: list, matrix: list) -> str:
    """End of design: share the requirement gaps and the coverage before testing starts."""
    def write():
        spreadsheet = _open(cfg)
        prefix = cfg["google_sheets"].get("worksheet_prefix", "QA")
        spreadsheet.batch_update({"requests": _trace_tabs(spreadsheet, prefix, store.dir.name, gaps, matrix)})
        return f"{spreadsheet.url}#gid={spreadsheet.worksheet(f'{prefix} Gaps {store.dir.name}').id}"
    return retry(lambda: _sheets_errors(write), step="04_design_sheets", incidents=store.incidents,
                 attempts=cfg["flow"]["api_retries"])


def publish_table(cfg: dict, store, title: str, header: list, body: list, widths: list, step: str) -> str:
    """Write one table tab (used by the monthly report)."""
    def write():
        spreadsheet = _open(cfg)
        spreadsheet.batch_update({"requests": _table(spreadsheet, title, header, body, widths)})
        return f"{spreadsheet.url}#gid={spreadsheet.worksheet(title).id}"
    return retry(lambda: _sheets_errors(write), step=step, incidents=store.incidents,
                 attempts=cfg["flow"]["api_retries"])


def publish(cfg: dict, store, rows: list, summary: dict, stats: dict, quality: dict, gaps: list, matrix: list) -> str:
    return retry(lambda: _write(cfg, store.dir.name, rows, summary, stats, quality, gaps, matrix),
                 step="07_google_sheets", incidents=store.incidents, attempts=cfg["flow"]["api_retries"])
