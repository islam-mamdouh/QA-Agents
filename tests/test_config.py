import unittest
from unittest import mock

from tests.helpers import temp_dir
from qa_flow import config

CONFIG = """# test
```yaml
models: {{main: a, reviewer: b}}
{section}: {{api_key: "${{TEST_SECRET}}"}}
google_sheets: {{service_account_file: ./secrets/sa.json}}
flow: {{runs_dir: runs}}
project_context: |
  Context line
```
"""


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.root = temp_dir()
        (self.root / "zatca").mkdir()
        (self.root / "zatca" / "config.md").write_text(CONFIG.format(section="jira"))
        (self.root / "zatca" / ".env").write_text("TEST_SECRET=from-project-env\n")
        (self.root / "empty").mkdir()
        self.patch = mock.patch.object(config, "PROJECTS", self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_lists_only_folders_with_config(self):
        self.assertEqual(config.project_names(), ["zatca"])

    def test_paths_are_relative_to_project_and_env_is_read(self):
        cfg = config.load_config("zatca")
        self.assertEqual(cfg["flow"]["runs_dir"], str((self.root / "zatca" / "runs").resolve()))
        self.assertTrue(cfg["google_sheets"]["service_account_file"].endswith("zatca/secrets/sa.json"))
        self.assertEqual(cfg["jira"]["api_key"], "from-project-env")
        self.assertTrue(cfg["flow"]["strict_results"])
        self.assertEqual(cfg["project_context"], "Context line")

    def test_jira_section_is_required(self):
        (self.root / "zatca" / "config.md").write_text(CONFIG.format(section="linear"))
        with self.assertRaises(config.ConfigError):
            config.load_config("zatca")

    def test_missing_project(self):
        with self.assertRaises(config.ConfigError):
            config.load_config("nope")


if __name__ == "__main__":
    unittest.main()
