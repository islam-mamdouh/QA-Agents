"""Shared test helpers. No Claude login or network access is needed to run the tests."""
import tempfile
from pathlib import Path


class FakeIncidents:
    def __init__(self):
        self.logged = []

    def log(self, *args):
        self.logged.append(args)


class FakeStore:
    def __init__(self):
        self.incidents = FakeIncidents()


def temp_dir() -> Path:
    return Path(tempfile.mkdtemp())


def base_cfg(runs_dir: Path | None = None) -> dict:
    root = temp_dir()
    return {
        "models": {"main": "main-model", "reviewer": "review-model", "max_tokens": 1000},
        "inputs": {"crs_dir": str(root / "crs"), "knowledge_dir": str(root / "knowledge"), "cr_max_chars": 30000},
        "test_environment": "QA environment",
        "project_context": "test product",
        "knowledge": "",
        "flow": {"max_review_rounds": 2, "max_fire_back": 1, "api_retries": 1, "cases_batch_size": 5,
                 "report_batch_size": 40, "runs_dir": str(runs_dir or temp_dir()), "strict_results": True},
    }
