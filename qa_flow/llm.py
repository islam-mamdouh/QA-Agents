"""Claude through the Claude Code harness (your Claude login / subscription, no API key).

Every agent call runs `claude -p` in headless mode:
  - your agent prompt replaces Claude Code's default system prompt (--system-prompt)
  - all tools, MCP servers and settings are switched off: the agent only reads and writes text
  - the input is sent on stdin, the reply comes back as JSON (--output-format json)
On top of that: retries, JSON parsing and fire-back.
"""
import json
import os
import re
import subprocess

from .retry import RetryableError, retry


class AgentOutputError(Exception):
    """The agent could not give a usable reply, even after fire-back."""


class ClaudeCodeError(Exception):
    """A problem that a retry will not fix (login, usage limit, missing CLI)."""


def parse_json(text: str):
    """Take the JSON object out of a reply (tolerates ```json fences and text around it)."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in the reply")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON: {error}") from None


def _child_env(max_tokens: int) -> dict:
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)   # make sure your Claude login is used, not an API key
    env.pop("CLAUDECODE", None)          # allow running from inside a Claude Code session
    env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(max_tokens)
    return env


class LLM:
    def __init__(self, cfg: dict, store):
        cc = cfg.get("claude_code") or {}
        self.command = cc.get("command", "claude")
        self.timeout = int(cc.get("timeout_seconds", 900))
        self.env = _child_env(int(cfg["models"].get("max_tokens", 16000)))
        self.retries = cfg["flow"]["api_retries"]
        self.fire_back = cfg["flow"]["max_fire_back"]
        self.store = store

    def _call(self, model: str, system: str, prompt: str) -> str:
        cmd = [self.command, "-p",
               "--model", model,
               "--system-prompt", system,
               "--output-format", "json",
               "--tools", "",                  # no tools: pure text in, text out
               "--strict-mcp-config",          # no MCP servers
               "--setting-sources", "",        # ignore user/project settings, hooks, CLAUDE.md
               "--no-session-persistence"]     # do not save these calls as sessions
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                  encoding="utf-8", timeout=self.timeout, env=self.env)
        except FileNotFoundError:
            raise ClaudeCodeError(f"'{self.command}' not found. Install Claude Code or set claude_code.command in the project's config.md")
        except subprocess.TimeoutExpired:
            raise RetryableError(f"Claude Code call took longer than {self.timeout}s")

        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise RetryableError(f"Claude Code exit {proc.returncode}: {(proc.stderr or proc.stdout)[:200]}")

        if out.get("usage"):
            self.store.add_usage(model, out["usage"], out.get("total_cost_usd", 0))
        if out.get("is_error"):
            message, status = str(out.get("result", "")), out.get("api_error_status")
            low = message.lower()
            if "usage limit" in low or "limit reached" in low or "limit will reset" in low:
                raise ClaudeCodeError(f"Claude usage limit reached: {message}. Resume after it resets.")
            if "log in" in low or "login" in low or "authentication" in low or status in (401, 403):
                raise ClaudeCodeError(f"Claude Code is not logged in: {message}. Run `claude` and /login.")
            raise RetryableError(f"Claude Code error {status or ''}: {message[:200]}")
        if out.get("stop_reason") == "max_tokens":
            raise AgentOutputError("Reply was cut at max_tokens. Lower the batch size in config.md (flow) "
                                   "or raise models.max_tokens, then resume.")
        return out.get("result", "")

    def ask_json(self, model: str, system: str, user: str, step: str, validate=None) -> dict:
        """Send one request and return the parsed JSON reply.

        Fire-back: if the reply is not valid JSON or fails `validate`, the agent gets the task
        again together with its own reply and the problem, and is asked to correct it.
        """
        prompt = user
        for attempt in range(self.fire_back + 1):
            text = retry(lambda: self._call(model, system, prompt),
                         step=step, incidents=self.store.incidents, attempts=self.retries)
            try:
                data = parse_json(text)
                if validate:
                    validate(data)
                return data
            except ValueError as problem:
                if attempt == self.fire_back:
                    raise AgentOutputError(f"{step}: unusable reply after {attempt + 1} tries: {problem}")
                self.store.incidents.log(step, "fire_back", str(problem), "sent back to the agent to fix")
                prompt = (f"{user}\n\n## Your previous reply\n{text}\n\n## Problem\n"
                          f"Your previous reply could not be used: {problem}. "
                          "Reply again with ONLY the complete corrected JSON object.")
