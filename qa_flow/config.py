"""Loads projects/zatca/config.md (a YAML block inside markdown) and fills ${ENV_VAR} values.

No credentials are needed: agents run through the Claude Code login, CR text is pasted into files
by hand (no Jira integration) and all deliverables are local Excel / markdown files.
"""
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "projects" / "zatca"   # config.md, crs/, knowledge/, runs/ for the ZATCA customs project

FLOW_DEFAULTS = {
    "max_review_rounds": 3,
    "max_fire_back": 2,
    "api_retries": 4,
    "cases_batch_size": 4,       # CR requirements per test-case-writing call
    "report_batch_size": 40,
    "runs_dir": "runs",
    "strict_results": True,
}
INPUT_DEFAULTS = {
    "crs_dir": "crs",            # one text file per CR: crs/<CR-ID>.md
    "knowledge_dir": "knowledge",  # *.md system knowledge given to every agent (keep it short)
    "cr_max_chars": 30000,
}


class ConfigError(Exception):
    pass


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from .env without overriding real environment variables."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _expand_env(value):
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)
    return value


def _in_folder(value: str) -> str:
    """Relative paths in config.md are relative to projects/zatca/."""
    path = Path(value).expanduser()
    return str(path if path.is_absolute() else (FOLDER / path).resolve())


def load_knowledge(folder: str) -> str:
    """All *.md files in the knowledge folder (except README.md), joined, in name order."""
    path = Path(folder)
    if not path.is_dir():
        return ""
    parts = [f.read_text(encoding="utf-8").strip() for f in sorted(path.glob("*.md"))
             if f.name.lower() != "readme.md"]
    return "\n\n".join(p for p in parts if p)


def load_config() -> dict:
    path = FOLDER / "config.md"
    if not path.exists():
        raise ConfigError(f"{path} not found. Copy {FOLDER / 'config.example.md'} to config.md and fill it in.")
    _load_dotenv(FOLDER / ".env")
    _load_dotenv(ROOT / ".env")

    text = path.read_text(encoding="utf-8")
    match = re.search(r"```ya?ml\s*\n(.*?)\n```", text, re.S)
    if not match:
        raise ConfigError(f"No ```yaml block found in {path}")
    cfg = _expand_env(yaml.safe_load(match.group(1)) or {})
    if "models" not in cfg:
        raise ConfigError(f"Missing section 'models' in {path}")

    cfg["claude_code"] = {"command": "claude", "timeout_seconds": 900, **(cfg.get("claude_code") or {})}
    cfg["flow"] = {**FLOW_DEFAULTS, **(cfg.get("flow") or {})}
    cfg["flow"]["runs_dir"] = _in_folder(cfg["flow"]["runs_dir"])
    cfg["inputs"] = {**INPUT_DEFAULTS, **(cfg.get("inputs") or {})}
    for key in ("crs_dir", "knowledge_dir"):
        cfg["inputs"][key] = _in_folder(cfg["inputs"][key])
    cfg["test_environment"] = str(cfg.get("test_environment") or "QA environment").strip()
    cfg["project_context"] = (cfg.get("project_context") or "").strip()
    cfg["knowledge"] = load_knowledge(cfg["inputs"]["knowledge_dir"])
    return cfg


def require(cfg: dict, dotted: str):
    """Return a config value or raise a clear error if it is empty."""
    node = cfg
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    if node in (None, ""):
        raise ConfigError(f"'{dotted}' is empty in projects/zatca/config.md")
    return node
