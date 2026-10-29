"""Run folder = the checkpoint. Everything needed to resume a run lives in runs/<run-id>/.

runs/<run-id>/
  state.json        step status, review round, token usage
  artifacts/*.json  output of every finished step (and the latest draft of a running review loop)
  incidents.md      incident log
  *.md / *.csv      human readable outputs
"""
import json
import os
from datetime import datetime
from pathlib import Path

from .incidents import Incidents


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write_atomic(path: Path, text: str) -> None:
    """Write to a temp file then rename, so a crash never leaves a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class RunStore:
    def __init__(self, run_dir: Path):
        self.dir = Path(run_dir)
        self.artifacts = self.dir / "artifacts"
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.incidents = Incidents(self.dir / "incidents.md")
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        else:
            self.state = {"run_id": self.dir.name, "created": now(), "phase": "design",
                          "status": "new", "steps": {}, "usage": {}}
            self._save()

    # ---- opening runs -------------------------------------------------
    @classmethod
    def create(cls, runs_dir) -> "RunStore":
        return cls(Path(runs_dir) / datetime.now().strftime("%Y%m%d-%H%M%S"))

    @classmethod
    def open(cls, runs_dir, run_id: str | None = None) -> "RunStore":
        runs_dir = Path(runs_dir)
        if run_id:
            path = runs_dir / run_id
        else:
            runs = sorted(p for p in runs_dir.glob("*") if (p / "state.json").exists()) if runs_dir.exists() else []
            if not runs:
                raise FileNotFoundError(f"No runs found in {runs_dir}/")
            path = runs[-1]
        if not (path / "state.json").exists():
            raise FileNotFoundError(f"Run not found: {path}")
        return cls(path)

    # ---- state ----------------------------------------------------------
    def _save(self) -> None:
        write_atomic(self.state_path, json.dumps(self.state, ensure_ascii=False, indent=2))

    def set(self, **fields) -> None:
        self.state.update(fields)
        self._save()

    def step(self, key: str) -> dict:
        return self.state["steps"].get(key, {})

    def update_step(self, key: str, **fields) -> None:
        step = self.state["steps"].setdefault(key, {})
        step.update(fields, updated=now())
        self._save()

    def is_done(self, key: str) -> bool:
        return self.step(key).get("status") == "done"

    def reset_steps(self, prefix: str) -> None:
        self.state["steps"] = {k: v for k, v in self.state["steps"].items() if not k.startswith(prefix)}
        self._save()

    def add_usage(self, model: str, usage) -> None:
        totals = self.state["usage"].setdefault(model, {"calls": 0, "input": 0, "output": 0, "cache_read": 0})
        totals["calls"] += 1
        totals["input"] += getattr(usage, "input_tokens", 0) or 0
        totals["output"] += getattr(usage, "output_tokens", 0) or 0
        totals["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        self._save()

    # ---- artifacts ------------------------------------------------------
    def save(self, name: str, data) -> None:
        write_atomic(self.artifacts / f"{name}.json", json.dumps(data, ensure_ascii=False, indent=1))

    def load(self, name: str):
        path = self.artifacts / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def write_text(self, filename: str, text: str) -> Path:
        path = self.dir / filename
        write_atomic(path, text)
        return path
