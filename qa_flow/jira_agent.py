"""Step 1 - Jira agent. Plain Python, no LLM: fetching and ordering stories needs no AI,
so it costs zero tokens and gives the same result every time.

Output: stories (trimmed, clean text) + dependency order (a story comes after the stories it depends on).
"""
import re

import requests

from .config import require
from .retry import RetryableError, parse_retry_after, retry

STEP = "01_stories"
BASE_FIELDS = ["summary", "description", "status", "priority", "issuelinks", "labels", "components"]
BLOCK_NODES = {"paragraph", "heading", "blockquote", "codeBlock", "tableRow", "rule", "listItem"}


class JiraError(Exception):
    pass


def adf_to_text(node) -> str:
    """Turn Jira's rich-text JSON (Atlassian Document Format) into plain text."""
    out = []

    def walk(n):
        if isinstance(n, list):
            for child in n:
                walk(child)
            return
        if not isinstance(n, dict):
            return
        kind = n.get("type")
        if kind == "text":
            out.append(n.get("text", ""))
            return
        if kind == "hardBreak":
            out.append("\n")
            return
        if kind in ("mention", "emoji", "inlineCard"):
            attrs = n.get("attrs", {})
            out.append(attrs.get("text") or attrs.get("url") or "")
            return
        if kind == "listItem":
            out.append("- ")
        walk(n.get("content", []))
        if kind in ("tableCell", "tableHeader"):
            out.append(" | ")
        if kind in BLOCK_NODES:
            out.append("\n")

    walk(node)
    text = re.sub(r"[ \t]+\n", "\n", "".join(out))
    return re.sub(r"\n{2,}", "\n", text).strip()


def to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return adf_to_text(value)
    if isinstance(value, list):
        return "\n".join(to_text(v) for v in value)
    return str(value).strip()


def _post(url: str, auth, body: dict) -> dict:
    try:
        response = requests.post(url, json=body, auth=auth, timeout=60, headers={"Accept": "application/json"})
    except requests.RequestException as error:
        raise RetryableError(f"Jira connection error: {error}")
    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableError(f"Jira HTTP {response.status_code}", parse_retry_after(response.headers.get("Retry-After")))
    if response.status_code >= 400:
        raise JiraError(f"Jira HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


def _search(cfg: dict, jql: str, fields: list, store) -> list:
    jira = cfg["jira"]
    url = require(cfg, "jira.base_url").rstrip("/") + "/rest/api/3/search/jql"
    auth = (require(cfg, "jira.email"), require(cfg, "jira.api_token"))
    limit = int(jira.get("max_stories", 50))
    issues, page_token = [], None
    while len(issues) < limit:
        body = {"jql": jql, "fields": fields, "maxResults": min(100, limit - len(issues))}
        if page_token:
            body["nextPageToken"] = page_token
        data = retry(lambda: _post(url, auth, body), step=STEP, incidents=store.incidents,
                     attempts=cfg["flow"]["api_retries"])
        issues += data.get("issues", [])
        page_token = data.get("nextPageToken")
        if not page_token or data.get("isLast"):
            break
    return issues[:limit]


def dependency_order(stories: dict, rank: list, store) -> list:
    """Order stories so each one comes after what it depends on; ties keep the Jira rank."""
    remaining, done, order = list(rank), set(), []
    while remaining:
        ready = [k for k in remaining if all(d in done for d in stories[k].get("depends_on", []))]
        if not ready:
            store.incidents.log(STEP, "data", f"dependency cycle between {', '.join(remaining)}",
                                f"cycle broken at {remaining[0]} (Jira rank)")
            ready = [remaining[0]]
        order += ready
        done.update(ready)
        remaining = [k for k in remaining if k not in done]
    return order


def fetch_stories(cfg: dict, store, jql: str | None = None) -> dict:
    jira = cfg["jira"]
    ac_field = jira.get("acceptance_criteria_field") or ""
    fields = BASE_FIELDS + ([ac_field] if ac_field else [])
    max_chars = int(jira.get("description_max_chars", 2500))
    link_types = {t.lower() for t in jira.get("dependency_link_types", ["blocks"])}

    issues = _search(cfg, jql or require(cfg, "jira.jql"), fields, store)
    stories, rank, blocks = {}, [], []

    for issue in issues:
        key, f = issue["key"], issue.get("fields", {})
        description = to_text(f.get("description"))
        if len(description) > max_chars:
            description = description[:max_chars] + " ...[trimmed]"

        depends_on = set()
        for link in f.get("issuelinks") or []:
            link_type = link.get("type", {})
            names = {str(link_type.get(n, "")).lower() for n in ("name", "inward", "outward")}
            if not names & link_types:
                continue
            if "inwardIssue" in link:      # this issue "is blocked by" the other one
                depends_on.add(link["inwardIssue"]["key"])
            elif "outwardIssue" in link:   # this issue "blocks" the other one
                blocks.append((key, link["outwardIssue"]["key"]))

        story = {
            "key": key,
            "summary": f.get("summary", ""),
            "status": (f.get("status") or {}).get("name", ""),
            "priority": (f.get("priority") or {}).get("name", ""),
            "labels": f.get("labels") or [],
            "components": [c.get("name") for c in f.get("components") or []],
            "description": description,
            "acceptance_criteria": to_text(f.get(ac_field)) if ac_field else "",
            "depends_on": sorted(depends_on),
        }
        stories[key] = {k: v for k, v in story.items() if v not in ("", [], None)}  # drop empty fields
        rank.append(key)

    for blocker, blocked in blocks:
        if blocked in stories and blocker not in stories[blocked].get("depends_on", []):
            stories[blocked].setdefault("depends_on", []).append(blocker)

    # Dependencies outside this story set are kept as context but do not affect ordering.
    for story in stories.values():
        deps = story.pop("depends_on", [])
        internal = [d for d in deps if d in stories]
        external = [d for d in deps if d not in stories]
        if internal:
            story["depends_on"] = internal
        if external:
            story["external_depends_on"] = external

    return {"order": dependency_order(stories, rank, store), "stories": stories}
