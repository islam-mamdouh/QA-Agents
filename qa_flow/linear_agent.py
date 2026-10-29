"""Step 1 - Linear agent. Plain Python, no LLM, same output as the Jira agent:
stories (trimmed, clean text) + dependency order.

Filters come from the `linear` section of the project's config.md:
team key, active cycle only, state names and labels.
"""
import requests

from .config import require
from .jira_agent import dependency_order
from .retry import RetryableError, parse_retry_after, retry

STEP = "01_stories"
URL = "https://api.linear.app/graphql"

QUERY = """
query Issues($filter: IssueFilter, $first: Int, $after: String) {
  issues(filter: $filter, first: $first, after: $after) {
    nodes {
      identifier title description priorityLabel sortOrder
      state { name }
      labels { nodes { name } }
      project { name }
      relations { nodes { type relatedIssue { identifier } } }
      inverseRelations { nodes { type issue { identifier } } }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""


class LinearError(Exception):
    pass


def _post(api_key: str, query: str, variables: dict) -> dict:
    try:
        response = requests.post(URL, json={"query": query, "variables": variables}, timeout=60,
                                 headers={"Authorization": api_key, "Content-Type": "application/json"})
    except requests.RequestException as error:
        raise RetryableError(f"Linear connection error: {error}")
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableError(f"Linear HTTP {response.status_code}", parse_retry_after(response.headers.get("Retry-After")))
    if response.status_code >= 400:
        raise LinearError(f"Linear HTTP {response.status_code}: {response.text[:300]}")
    body = response.json()
    if body.get("errors"):
        raise LinearError(f"Linear error: {body['errors'][0].get('message', body['errors'])}")
    return body["data"]


def build_filter(linear: dict) -> dict:
    flt = {"team": {"key": {"eq": require({"linear": linear}, "linear.team_key")}}}
    if linear.get("active_cycle_only", True):
        flt["cycle"] = {"isActive": {"eq": True}}
    if linear.get("states"):
        flt["state"] = {"name": {"in": linear["states"]}}
    if linear.get("labels"):
        flt["labels"] = {"some": {"name": {"in": linear["labels"]}}}
    return flt


def check_login(cfg: dict) -> None:
    _post(require(cfg, "linear.api_key"), "query { viewer { id } }", {})


def fetch_stories(cfg: dict, store, keys: list | None = None) -> dict:
    """keys: optional issue identifiers (e.g. ["ATL-12", "ATL-15"]) instead of the config filter."""
    linear = cfg["linear"]
    api_key = require(cfg, "linear.api_key")
    limit = int(linear.get("max_stories", 50))
    max_chars = int(linear.get("description_max_chars", 2500))
    flt = {"number": {"in": [int(k.split("-")[-1]) for k in keys]},
           "team": {"key": {"eq": require(cfg, "linear.team_key")}}} if keys else build_filter(linear)

    nodes, after = [], None
    while len(nodes) < limit:
        variables = {"filter": flt, "first": min(50, limit - len(nodes)), "after": after}
        data = retry(lambda: _post(api_key, QUERY, variables), step=STEP, incidents=store.incidents,
                     attempts=cfg["flow"]["api_retries"])
        page = data["issues"]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    nodes = sorted(nodes[:limit], key=lambda n: n.get("sortOrder") or 0)  # board order

    stories, rank, blocks = {}, [], []
    for n in nodes:
        key = n["identifier"]
        description = (n.get("description") or "").strip()
        if len(description) > max_chars:
            description = description[:max_chars] + " ...[trimmed]"

        depends_on = set()
        for rel in (n.get("relations") or {}).get("nodes", []):          # this issue blocks the other
            if rel.get("type") == "blocks":
                blocks.append((key, rel["relatedIssue"]["identifier"]))
        for rel in (n.get("inverseRelations") or {}).get("nodes", []):   # the other issue blocks this one
            if rel.get("type") == "blocks":
                depends_on.add(rel["issue"]["identifier"])

        story = {
            "key": key,
            "summary": n.get("title", ""),
            "status": (n.get("state") or {}).get("name", ""),
            "priority": n.get("priorityLabel", ""),
            "labels": [l["name"] for l in (n.get("labels") or {}).get("nodes", [])],
            "components": [n["project"]["name"]] if n.get("project") else [],
            "description": description,
            "depends_on": sorted(depends_on),
        }
        stories[key] = {k: v for k, v in story.items() if v not in ("", [], None, "No priority")}
        rank.append(key)

    for blocker, blocked in blocks:
        if blocked in stories and blocker not in stories[blocked].get("depends_on", []):
            stories[blocked].setdefault("depends_on", []).append(blocker)

    for story in stories.values():
        deps = story.pop("depends_on", [])
        internal = [d for d in deps if d in stories]
        external = [d for d in deps if d not in stories]
        if internal:
            story["depends_on"] = internal
        if external:
            story["external_depends_on"] = external

    return {"order": dependency_order(stories, rank, store), "stories": stories}
