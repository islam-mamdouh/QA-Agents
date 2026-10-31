"""Shared test helpers. The Claude and Google libraries are not needed to run the tests."""
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
    return {
        "project": "test",
        "models": {"main": "main-model", "reviewer": "review-model", "max_tokens": 1000},
        "jira": {"base_url": "https://jira", "email": "e", "api_token": "t", "jql": "q",
                 "dependency_link_types": ["blocks"]},
        "google_sheets": {"worksheet_prefix": "T"},
        "project_context": "test product",
        "flow": {"max_review_rounds": 2, "max_fire_back": 1, "api_retries": 1, "analysis_batch_size": 5,
                 "cases_batch_size": 5, "report_batch_size": 40, "runs_dir": str(runs_dir or temp_dir()),
                 "strict_results": True},
    }
