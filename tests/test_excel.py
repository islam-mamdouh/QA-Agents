import unittest

from openpyxl import load_workbook

from tests.helpers import temp_dir
from qa_flow.excel import POT_COLUMNS, TEST_CASE_COLUMNS, test_case_row, write_workbook


class ExcelTest(unittest.TestCase):
    def test_test_cases_sheet_has_jira_columns_and_readable_cells(self):
        path = temp_dir() / "test_cases.xlsx"
        case = {"id": "US-1-TC-001", "summary": "Submit leave request", "module": "Leave",
                "system": "Web portal", "preconditions": ["Employee role", "Leave balance 10 days"],
                "steps": ["Open leave form", "Submit"], "test_data": "2 days",
                "expected_result": "UI: submitted\nDB: status updated", "type": "positive", "priority": "high"}
        write_workbook(path, [("Test Cases", TEST_CASE_COLUMNS, [test_case_row(case)], None)])
        ws = load_workbook(path)["Test Cases"]
        self.assertEqual([c.value for c in ws[1]], ["Test ID", "Summary", "Module", "System", "Preconditions",
                                                    "Test Steps", "Test Data", "Expected Result", "Type", "Priority"])
        row = [c.value for c in ws[2]]
        self.assertEqual(row[4], "- Employee role\n- Leave balance 10 days")
        self.assertEqual(row[5], "1. Open leave form\n2. Submit")
        self.assertEqual(ws.freeze_panes, "A2")

    def test_pot_status_is_coloured(self):
        path = temp_dir() / "pot.xlsx"
        rows = [{"id": "T1", "status": "Pass"}, {"id": "T2", "status": "Fail"}]
        write_workbook(path, [("POT", POT_COLUMNS, rows, "status")])
        ws = load_workbook(path)["POT"]
        self.assertEqual(ws["E2"].fill.fgColor.rgb[-6:], "D9F0D9")
        self.assertEqual(ws["E3"].fill.fgColor.rgb[-6:], "FAD6D6")


if __name__ == "__main__":
    unittest.main()
