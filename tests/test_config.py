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
        self.folder = temp_dir() / "zatca"
        self.folder.mkdir()
        (self.folder / "config.md").write_text(CONFIG.format(section="jira"))
        (self.folder / ".env").write_text("TEST_SECRET=from-folder-env\n")
        self.patch = mock.patch.object(config, "FOLDER", self.folder)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_paths_are_relative_to_folder_and_env_is_read(self):
        cfg = config.load_config()
        self.assertEqual(cfg["flow"]["runs_dir"], str((self.folder / "runs").resolve()))
        self.assertTrue(cfg["google_sheets"]["service_account_file"].endswith("zatca/secrets/sa.json"))
        self.assertEqual(cfg["jira"]["api_key"], "from-folder-env")
        self.assertTrue(cfg["flow"]["strict_results"])
        self.assertEqual(cfg["project_context"], "Context line")

    def test_jira_section_is_required(self):
        (self.folder / "config.md").write_text(CONFIG.format(section="other"))
        with self.assertRaises(config.ConfigError):
            config.load_config()

    def test_missing_config(self):
        with self.assertRaises(config.ConfigError):
            (self.folder / "config.md").unlink()
            config.load_config()


if __name__ == "__main__":
    unittest.main()
