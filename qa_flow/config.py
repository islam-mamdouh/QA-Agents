"""Loads projects/zatca/config.md (a YAML block inside markdown) and fills ${ENV_VAR} values."""
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
DEFAULT_PROJECT = "zatca"

FLOW_DEFAULTS = {
    "max_review_rounds": 3,
    "max_fire_back": 2,
    "api_retries": 4,
    "analysis_batch_size": 5,
    "cases_batch_size": 3,
    "report_batch_size": 40,
    "runs_dir": "runs",
    "strict_results": True,
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


def project_names() -> list:
    """Projects are folders under projects/ that contain a config.md."""
    return sorted(p.name for p in PROJECTS.glob("*") if (p / "config.md").exists())


def _in_project(folder: Path, value: str) -> str:
    """Relative paths in a project's config.md are relative to that project's folder."""
    path = Path(value).expanduser()
    return str(path if path.is_absolute() else (folder / path).resolve())


def load_config(project: str) -> dict:
    folder = PROJECTS / project
    path = folder / "config.md"
    if not path.exists():
        raise ConfigError(f"{path} not found. Copy {folder / 'config.example.md'} to config.md and fill it in.")
    _load_dotenv(folder / ".env")   # project secrets first, so they win over the shared .env
    _load_dotenv(ROOT / ".env")

    text = path.read_text(encoding="utf-8")
    match = re.search(r"```ya?ml\s*\n(.*?)\n```", text, re.S)
    if not match:
        raise ConfigError(f"No ```yaml block found in {path}")
    cfg = _expand_env(yaml.safe_load(match.group(1)) or {})

    for section in ("models", "jira", "google_sheets"):
        if section not in cfg:
            raise ConfigError(f"Missing section '{section}' in {path}")

    cfg["project"] = project
    cfg["claude_code"] = {"command": "claude", "timeout_seconds": 900, **(cfg.get("claude_code") or {})}
    cfg["flow"] = {**FLOW_DEFAULTS, **(cfg.get("flow") or {})}
    cfg["flow"]["runs_dir"] = _in_project(folder, cfg["flow"]["runs_dir"])
    sheets = cfg["google_sheets"]
    if sheets.get("service_account_file"):
        sheets["service_account_file"] = _in_project(folder, sheets["service_account_file"])
    cfg["project_context"] = (cfg.get("project_context") or "").strip()
    return cfg


def require(cfg: dict, dotted: str):
    """Return a config value or raise a clear error if it is empty."""
    node = cfg
    for part in dotted.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    if node in (None, ""):
        raise ConfigError(f"'{dotted}' is empty in the project's config.md (or its environment variable is not set)")
    return node

