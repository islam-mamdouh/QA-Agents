import unittest
from unittest import mock

from tests.helpers import temp_dir
from qa_flow import config

CONFIG = """# test
```yaml
models: {{main: a, reviewer: b}}
test_environment: "QA - ${{TEST_ENV_NAME}}"
flow: {{runs_dir: runs}}
{extra}
project_context: |
  Context line
```
"""


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.folder = temp_dir() / "zatca"
        self.folder.mkdir()
        (self.folder / "config.md").write_text(CONFIG.format(extra=""))
        (self.folder / ".env").write_text("TEST_ENV_NAME=from-folder-env\n")
        self.patch = mock.patch.object(config, "FOLDER", self.folder)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_paths_defaults_and_env(self):
        cfg = config.load_config()
        self.assertEqual(cfg["flow"]["runs_dir"], str((self.folder / "runs").resolve()))
        self.assertEqual(cfg["inputs"]["crs_dir"], str((self.folder / "crs").resolve()))
        self.assertEqual(cfg["test_environment"], "QA - from-folder-env")
        self.assertTrue(cfg["flow"]["strict_results"])
        self.assertEqual(cfg["project_context"], "Context line")
        self.assertEqual(cfg["knowledge"], "")
        self.assertNotIn("jira", cfg)

    def test_knowledge_files_are_loaded_in_order_without_readme(self):
        knowledge = self.folder / "knowledge"
        knowledge.mkdir()
        (knowledge / "README.md").write_text("how to use this folder")
        (knowledge / "b_edi.md").write_text("EDI notes")
        (knowledge / "a_journey.md").write_text("Journey notes")
        self.assertEqual(config.load_config()["knowledge"], "Journey notes\n\nEDI notes")

    def test_models_section_is_required(self):
        (self.folder / "config.md").write_text("```yaml\nflow: {}\n```")
        with self.assertRaises(config.ConfigError):
            config.load_config()

    def test_missing_config(self):
        (self.folder / "config.md").unlink()
        with self.assertRaises(config.ConfigError):
            config.load_config()


if __name__ == "__main__":
    unittest.main()
