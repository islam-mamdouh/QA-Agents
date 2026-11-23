"""Step 1 - user story intake. Plain Python, no LLM, no tracker access.

There is no integration with Jira, Azure DevOps or any other tracker: you copy the user story
text by hand into workspace/stories/<STORY-ID>.md (description, acceptance criteria, business
rules, attachment notes, comments).
The first markdown heading or first line is used as the story title.
"""
import re
from pathlib import Path

STORY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class IntakeError(Exception):
    pass


def story_path(stories_dir: str, story_id: str) -> Path:
    if not STORY_ID.match(story_id or ""):
        raise IntakeError(f"'{story_id}' is not a valid story id (letters, digits, - _ . only)")
    return Path(stories_dir) / f"{story_id}.md"


def clean(text: str) -> str:
    """Normalise pasted text: unify line endings, drop trailing spaces and runs of blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def read_story(story_id: str, path: Path, max_chars: int, store) -> dict:
    if not path.exists():
        raise IntakeError(f"Story file not found: {path}\nCopy the user story text into this file, then run again.")
    text = clean(path.read_text(encoding="utf-8"))
    if len(text) < 20:
        raise IntakeError(f"{path} is (almost) empty. Paste the full story text into it.")
    if len(text) > max_chars:
        store.incidents.log("01_story", "data", f"story text is {len(text)} characters, longer than story_max_chars",
                            f"trimmed to {max_chars}; raise inputs.story_max_chars if needed")
        text = text[:max_chars] + "\n...[trimmed]"
    first = next(line for line in text.splitlines() if line.strip())
    title = re.sub(r"^#+\s*", "", first).strip()[:200]
    return {"id": story_id, "title": title, "text": text, "file": str(path)}
