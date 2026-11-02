"""Step 1 - CR intake. Plain Python, no LLM, no Jira access.

There is no integration with Jira: you copy the Change Request text from Jira by hand into
projects/zatca/crs/<CR-ID>.md (description, acceptance criteria, attachments summary, comments).
The first markdown heading or first line is used as the CR title.
"""
import re
from pathlib import Path

CR_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class IntakeError(Exception):
    pass


def cr_path(crs_dir: str, cr_id: str) -> Path:
    if not CR_ID.match(cr_id or ""):
        raise IntakeError(f"'{cr_id}' is not a valid CR id (letters, digits, - _ . only)")
    return Path(crs_dir) / f"{cr_id}.md"


def clean(text: str) -> str:
    """Normalise pasted text: unify line endings, drop trailing spaces and runs of blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def read_cr(cr_id: str, path: Path, max_chars: int, store) -> dict:
    if not path.exists():
        raise IntakeError(f"CR file not found: {path}\nCopy the CR text from Jira into this file, then run again.")
    text = clean(path.read_text(encoding="utf-8"))
    if len(text) < 20:
        raise IntakeError(f"{path} is (almost) empty. Paste the full CR text into it.")
    if len(text) > max_chars:
        store.incidents.log("01_cr", "data", f"CR text is {len(text)} characters, longer than cr_max_chars",
                            f"trimmed to {max_chars}; raise inputs.cr_max_chars if needed")
        text = text[:max_chars] + "\n...[trimmed]"
    first = next(line for line in text.splitlines() if line.strip())
    title = re.sub(r"^#+\s*", "", first).strip()[:200]
    return {"id": cr_id, "title": title, "text": text, "file": str(path)}
