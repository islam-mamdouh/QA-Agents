"""LLM calls go through the Claude Code CLI (claude -p); subprocess is mocked here."""
import json
import subprocess
import unittest
from unittest import mock

from tests.helpers import base_cfg, temp_dir
from qa_flow import retry as retry_module
from qa_flow.llm import LLM, AgentOutputError, ClaudeCodeError
from qa_flow.store import RunStore


def cli_output(result="", is_error=False, stop_reason="end_turn", status=None):
    out = {"type": "result", "is_error": is_error, "result": result, "stop_reason": stop_reason,
           "api_error_status": status, "total_cost_usd": 0.01,
           "usage": {"input_tokens": 10, "cache_creation_input_tokens": 5,
                     "cache_read_input_tokens": 100, "output_tokens": 20}}
    return subprocess.CompletedProcess(args=[], returncode=1 if is_error else 0, stdout=json.dumps(out), stderr="")


class LLMTest(unittest.TestCase):
    def setUp(self):
        self.store = RunStore(temp_dir() / "run")
        self.llm = LLM(base_cfg(), self.store)
        no_wait = mock.patch.object(retry_module.time, "sleep", lambda seconds: None)
        no_wait.start()
        self.addCleanup(no_wait.stop)

    def test_builds_headless_command_without_api_key(self):
        def fake_run(cmd, **kwargs):
            self.cmd, self.kwargs = cmd, kwargs
            return cli_output('{"ok": true}')
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-should-not-be-used"}):
            llm = LLM(base_cfg(), self.store)
        with mock.patch.object(subprocess, "run", fake_run):
            self.assertEqual(llm.ask_json("main-model", "SYSTEM", "USER", "step"), {"ok": True})
        self.assertEqual(self.cmd[:2], ["claude", "-p"])
        self.assertIn("--system-prompt", self.cmd)
        self.assertEqual(self.cmd[self.cmd.index("--model") + 1], "main-model")
        self.assertEqual(self.cmd[self.cmd.index("--tools") + 1], "")
        self.assertEqual(self.kwargs["input"], "USER")
        self.assertNotIn("ANTHROPIC_API_KEY", self.kwargs["env"])
        self.assertEqual(self.store.state["usage"]["main-model"]["cache_read"], 100)

    def test_fire_back_sends_problem_and_previous_reply(self):
        outputs = [cli_output("not json"), cli_output('{"ok": 1}')]
        prompts = []

        def fake_run(cmd, **kwargs):
            prompts.append(kwargs["input"])
            return outputs[len(prompts) - 1]
        with mock.patch.object(subprocess, "run", fake_run):
            self.assertEqual(self.llm.ask_json("m", "s", "TASK", "step"), {"ok": 1})
        self.assertIn("TASK", prompts[1])
        self.assertIn("not json", prompts[1])
        self.assertEqual(self.store.incidents.count(), 1)

    def test_temporary_error_is_retried(self):
        outputs = [cli_output("Overloaded", is_error=True, status=529), cli_output('{"ok": 2}')]
        n = []

        def fake_run(cmd, **kwargs):
            n.append(1)
            return outputs[len(n) - 1]
        with mock.patch.object(subprocess, "run", fake_run):
            self.assertEqual(self.llm.ask_json("m", "s", "u", "step"), {"ok": 2})
        self.assertEqual(len(n), 2)

    def test_usage_limit_stops_without_retry(self):
        with mock.patch.object(subprocess, "run", lambda cmd, **k: cli_output(
                "Claude usage limit reached. Your limit will reset at 5pm", is_error=True)):
            with self.assertRaises(ClaudeCodeError):
                self.llm.ask_json("m", "s", "u", "step")

    def test_not_logged_in_stops_without_retry(self):
        with mock.patch.object(subprocess, "run", lambda cmd, **k: cli_output(
                "Invalid API key · Please run /login", is_error=True, status=401)):
            with self.assertRaises(ClaudeCodeError):
                self.llm.ask_json("m", "s", "u", "step")

    def test_missing_cli(self):
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError
        with mock.patch.object(subprocess, "run", fake_run):
            with self.assertRaises(ClaudeCodeError):
                self.llm.ask_json("m", "s", "u", "step")

    def test_reply_cut_at_max_tokens(self):
        with mock.patch.object(subprocess, "run", lambda cmd, **k: cli_output("{", stop_reason="max_tokens")):
            with self.assertRaises(AgentOutputError):
                self.llm.ask_json("m", "s", "u", "step")


if __name__ == "__main__":
    unittest.main()
