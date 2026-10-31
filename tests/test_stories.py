import unittest

from tests.helpers import FakeStore, base_cfg
from qa_flow import jira_agent


class JiraTest(unittest.TestCase):
    def test_rich_text_to_plain_text(self):
        adf = {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "As a taxpayer I issue an invoice"}]},
            {"type": "bulletList", "content": [{"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "AC one"}]}]}]}]}
        self.assertEqual(jira_agent.adf_to_text(adf), "As a taxpayer I issue an invoice\n- AC one")

    def test_fetch_orders_by_dependency(self):
        issues = [
            {"key": "Z-3", "fields": {"summary": "Report simplified invoice", "issuelinks": [
                {"type": {"name": "Blocks"}, "inwardIssue": {"key": "Z-1"}}]}},
            {"key": "Z-1", "fields": {"summary": "Generate invoice QR code", "description": "x" * 3000}},
            {"key": "Z-2", "fields": {"summary": "Onboard device (CSID)", "issuelinks": [
                {"type": {"name": "Blocks"}, "inwardIssue": {"key": "Z-99"}}]}},
        ]
        original = jira_agent._post
        jira_agent._post = lambda url, auth, body: {"issues": issues, "isLast": True}
        try:
            out = jira_agent.fetch_stories(base_cfg(), FakeStore())
        finally:
            jira_agent._post = original
        self.assertLess(out["order"].index("Z-1"), out["order"].index("Z-3"))
        self.assertEqual(out["stories"]["Z-3"]["depends_on"], ["Z-1"])
        self.assertEqual(out["stories"]["Z-2"]["external_depends_on"], ["Z-99"])
        self.assertTrue(out["stories"]["Z-1"]["description"].endswith("...[trimmed]"))

    def test_dependency_cycle_is_broken_and_logged(self):
        store = FakeStore()
        order = jira_agent.dependency_order({"A": {"depends_on": ["B"]}, "B": {"depends_on": ["A"]}}, ["A", "B"], store)
        self.assertEqual(sorted(order), ["A", "B"])
        self.assertEqual(len(store.incidents.logged), 1)


if __name__ == "__main__":
    unittest.main()
