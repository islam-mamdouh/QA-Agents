import unittest

from tests.helpers import FakeStore, base_cfg
from qa_flow import jira_agent, linear_agent


class JiraTest(unittest.TestCase):
    def test_rich_text_to_plain_text(self):
        adf = {"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "As a user I pay"}]},
            {"type": "bulletList", "content": [{"type": "listItem", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "AC one"}]}]}]}]}
        self.assertEqual(jira_agent.adf_to_text(adf), "As a user I pay\n- AC one")

    def test_fetch_orders_by_dependency(self):
        issues = [
            {"key": "Z-3", "fields": {"summary": "Checkout", "issuelinks": [
                {"type": {"name": "Blocks"}, "inwardIssue": {"key": "Z-1"}}]}},
            {"key": "Z-1", "fields": {"summary": "Cart", "description": "x" * 3000}},
            {"key": "Z-2", "fields": {"summary": "Login", "issuelinks": [
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


class LinearTest(unittest.TestCase):
    def node(self, key, order, blocks=(), blocked_by=()):
        return {"identifier": key, "title": key, "description": "d", "priorityLabel": "High", "sortOrder": order,
                "state": {"name": "Todo"}, "labels": {"nodes": [{"name": "qa"}]}, "project": {"name": "Web"},
                "relations": {"nodes": [{"type": "blocks", "relatedIssue": {"identifier": k}} for k in blocks]},
                "inverseRelations": {"nodes": [{"type": "blocks", "issue": {"identifier": k}} for k in blocked_by]}}

    def run_fetch(self, pages, keys=None):
        calls = []

        def fake(api_key, query, variables):
            calls.append(variables)
            return pages[len(calls) - 1]
        original = linear_agent._post
        linear_agent._post = fake
        try:
            return linear_agent.fetch_stories(base_cfg(source="linear"), FakeStore(), keys), calls
        finally:
            linear_agent._post = original

    def test_pages_relations_and_order(self):
        pages = [
            {"issues": {"nodes": [self.node("ATL-3", 3, blocked_by=["ATL-1"]), self.node("ATL-1", 1, blocks=["ATL-3"])],
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"}}},
            {"issues": {"nodes": [self.node("ATL-2", 2, blocked_by=["ATL-99"])],
                        "pageInfo": {"hasNextPage": False, "endCursor": None}}},
        ]
        out, calls = self.run_fetch(pages)
        self.assertEqual(out["order"], ["ATL-1", "ATL-2", "ATL-3"])
        self.assertEqual(out["stories"]["ATL-3"]["depends_on"], ["ATL-1"])
        self.assertEqual(out["stories"]["ATL-2"]["external_depends_on"], ["ATL-99"])
        self.assertEqual(out["stories"]["ATL-1"]["components"], ["Web"])
        self.assertEqual(calls[1]["after"], "c1")
        self.assertEqual(calls[0]["filter"]["state"], {"name": {"in": ["Todo"]}})

    def test_specific_keys(self):
        pages = [{"issues": {"nodes": [self.node("ATL-5", 1)], "pageInfo": {"hasNextPage": False, "endCursor": None}}}]
        _, calls = self.run_fetch(pages, ["ATL-5", "ATL-7"])
        self.assertEqual(calls[0]["filter"]["number"], {"in": [5, 7]})


if __name__ == "__main__":
    unittest.main()
