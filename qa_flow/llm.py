"""Claude API wrapper: retries, prompt caching, JSON parsing and fire-back."""
import json
import re

import anthropic

from .config import anthropic_api_key
from .retry import RetryableError, parse_retry_after, retry


class AgentOutputError(Exception):
    """The agent could not give a usable reply, even after fire-back."""


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


class LLM:
    def __init__(self, cfg: dict, store):
        # api_key=None lets the SDK fall back to the active CLI/OAuth credentials
        # (same resolution the Claude Code CLI harness uses) when config.md has none set.
        self.client = anthropic.Anthropic(api_key=anthropic_api_key(cfg), max_retries=0)
        self.max_tokens = cfg["models"].get("max_tokens", 16000)
        self.retries = cfg["flow"]["api_retries"]
        self.fire_back = cfg["flow"]["max_fire_back"]
        self.store = store

    def _call(self, model: str, system: str, messages: list) -> str:
        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=self.max_tokens,
                # The system prompt (role + product context) is the same on every call of an agent,
                # so it is cached: repeated calls read it at a fraction of the cost.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
            ) as stream:
                message = stream.get_final_message()
        except anthropic.APIConnectionError as error:
            raise RetryableError(f"Claude connection error: {error}")
        except anthropic.APIStatusError as error:
            if error.status_code in (408, 409, 429) or error.status_code >= 500:
                wait = parse_retry_after(error.response.headers.get("retry-after"))
                raise RetryableError(f"Claude API {error.status_code}", wait)
            raise

        self.store.add_usage(model, message.usage)
        if message.stop_reason == "max_tokens":
            raise AgentOutputError(
                "Reply was cut at max_tokens. Lower the batch size in config.md (flow) "
                "or raise models.max_tokens, then resume."
            )
        return "".join(block.text for block in message.content if block.type == "text")

    def ask_json(self, model: str, system: str, user: str, step: str, validate=None) -> dict:
        """Send one request and return the parsed JSON reply.

        Fire-back: if the reply is not valid JSON or fails `validate`, the agent gets its own
        reply back with the problem and is asked to correct it (max_fire_back times).
        """
        messages = [{"role": "user", "content": user}]
        for attempt in range(self.fire_back + 1):
            text = retry(lambda: self._call(model, system, messages),
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
                messages += [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"Your reply could not be used: {problem}. "
                                                "Reply again with ONLY the complete corrected JSON object."},
                ]
