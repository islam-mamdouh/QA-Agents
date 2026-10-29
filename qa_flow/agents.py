"""Agents = a prompt file in prompts/ + a model.

Main agents (Opus) write: story_analysis, test_plan, test_cases, report_rows, report_summary.
Reviewer agents (Sonnet) check: reviewer_base.md + review_<stage>.md.
To change what an agent does, edit its prompt file. No code change needed.
"""
import json

from .config import ROOT

PROMPTS = ROOT / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()


def to_json(data) -> str:
    """Compact JSON: no indentation or spaces, which saves input tokens."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def format_issues(issues: list) -> str:
    return "\n".join(f"- [{i['severity']}] {i.get('where', '')}: {i['problem']} -> {i.get('fix', '')}"
                     for i in issues) or "- none"


def validate_review(data: dict) -> None:
    if not isinstance(data.get("issues"), list):
        raise ValueError("'issues' must be a list")
    for issue in data["issues"]:
        if issue.get("severity") not in ("major", "minor") or not issue.get("problem"):
            raise ValueError("every issue needs 'severity' (major|minor) and 'problem'")


class Agents:
    def __init__(self, cfg: dict, llm):
        self.llm = llm
        self.main_model = cfg["models"]["main"]
        self.reviewer_model = cfg["models"]["reviewer"]
        self.context = cfg["project_context"]

    def _system(self, *prompt_names: str) -> str:
        parts = [load_prompt(name) for name in prompt_names]
        if self.context:
            parts.append("## Product context\n" + self.context)
        return "\n\n".join(parts)

    def write(self, role: str, task_input, step: str, previous=None, issues=None, validate=None) -> dict:
        """Main agent produces an output, or revises its previous output using reviewer issues.

        A revision gets only: the input, its last output and the issues. Not the whole
        conversation history, which keeps every round small.
        """
        message = "## Input\n" + to_json(task_input)
        if previous is not None:
            message += ("\n\n## Your previous output\n" + to_json(previous)
                        + "\n\n## Reviewer issues to fix\n" + format_issues(issues or [])
                        + "\n\nFix every major issue and the minor ones that make sense. "
                          "Return the complete corrected JSON.")
        return self.llm.ask_json(self.main_model, self._system(role), message, step, validate)

    def review(self, stage: str, task_input, draft, step: str, previous_issues=None) -> dict:
        message = ("## Source given to the author\n" + to_json(task_input)
                   + "\n\n## Output to review\n" + to_json(draft))
        if previous_issues:
            message += "\n\n## Previously raised issues\n" + format_issues(previous_issues)
        system = self._system("reviewer_base", f"review_{stage}")
        return self.llm.ask_json(self.reviewer_model, system, message, step, validate_review)
