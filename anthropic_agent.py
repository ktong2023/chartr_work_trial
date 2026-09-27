"""Direct Anthropic Messages tool loop. Credentials stay on the controller host."""
import asyncio
import hashlib
import json
import os
import re
import time
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import anthropic
from pydantic import Field
from harbor.agents.base import BaseAgent
from harbor.agents.options import AgentOptions, Env
from harbor.models.agent.context import ModelUsage


class Options(AgentOptions):
    max_turns: Annotated[int, Env("ANTHROPIC_MAX_TURNS", fallback="ANTHROPIC_MAX_TURNS")] = Field(100, ge=1)
    max_tokens: Annotated[int, Env("ANTHROPIC_MAX_TOKENS", fallback="ANTHROPIC_MAX_TOKENS")] = Field(4096, ge=1)
    wall_timeout_sec: float = Field(1170, gt=0)
    api_timeout_sec: float = Field(90, gt=0)
    tool_timeout_sec: float = Field(60, gt=0)
    max_tool_chars: int = Field(50000, ge=256)


class AnthropicAgent(BaseAgent):
    options_model = Options

    def __init__(self, *args, model_name=None, **kwargs):
        super().__init__(*args, model_name=model_name or os.environ.get("ANTHROPIC_MODEL", "claude-opus-5"), **kwargs)
        # Sibling of Harbor's mirrored agent/ directory: never uploaded or mounted.
        self.evidence_dir = Path(self.logs_dir).parent / "controller" / "anthropic"

    @staticmethod
    def name():
        return "anthropic-direct"

    def version(self):
        return "0.2.0"

    async def setup(self, environment):
        pass

    def _redact(self, text):
        for secret in self._secrets:
            text = text.replace(secret, "[REDACTED]")
        return re.sub(r"sk-ant-[A-Za-z0-9_-]+", "[REDACTED]", text)

    def _event(self, kind, **fields):
        event = {"event": kind, "elapsed_sec": round(time.monotonic() - self._started, 6), **fields}
        with (self.evidence_dir / "events.jsonl").open("a") as handle:
            handle.write(self._redact(json.dumps(event, default=str)) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    async def run(self, instruction, environment, context):
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self._started = time.monotonic()
        self._secrets = [v for k, v in os.environ.items() if len(v) >= 8 and
                         any(part in k.upper() for part in ("KEY", "TOKEN", "SECRET", "PASSWORD"))]
        usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self._event("start", instruction=instruction, model=self.model_name, limits=self.options.model_dump(),
                    driver=self.version(), harbor=version("harbor"), sdk=version("anthropic"),
                    adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        reason, validity, turns = "unexpected_error", "evaluation_error", 0
        client = None
        messages = [{"role": "user", "content": instruction}]
        tools = [{"name": "bash", "description": "Run a shell command inside the task environment.",
                  "input_schema": {"type": "object", "properties": {"command": {"type": "string"}},
                                   "required": ["command"], "additionalProperties": False}}]
        try:
            # Only the ordinary Messages API used by the original working adapter.
            # No beta headers, thinking options, caching directives, or gateway features.
            client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"],
                                              timeout=self.options.api_timeout_sec, max_retries=0)
            async with asyncio.timeout(self.options.wall_timeout_sec):
                for turns in range(1, self.options.max_turns + 1):
                    self._event("request", turn=turns, message_count=len(messages))
                    response = await client.messages.create(model=self.model_name, max_tokens=self.options.max_tokens,
                                                            tools=tools, messages=messages)
                    raw = response.model_dump(mode="json")
                    self._event("response", turn=turns, response=raw, request_id=getattr(response, "_request_id", None))
                    for key in usage:
                        usage[key] += raw.get("usage", {}).get(key) or 0
                    if response.stop_reason == "max_tokens":
                        reason, validity = "output_truncated", "valid"
                        break  # Never execute a possibly incomplete tool request.
                    if response.stop_reason in {"end_turn", "stop_sequence", "refusal"}:
                        reason, validity = response.stop_reason, "valid"
                        break
                    calls = [block for block in raw["content"] if block["type"] == "tool_use"]
                    if response.stop_reason != "tool_use" or not calls:
                        reason = "unexpected_stop_reason"
                        break
                    messages.append({"role": "assistant", "content": raw["content"]})
                    results = []
                    for call in calls:
                        args = call.get("input")
                        if call.get("name") != "bash" or not isinstance(args, dict) or set(args) != {"command"} or not isinstance(args["command"], str):
                            result = {"type": "tool_result", "tool_use_id": call["id"],
                                      "content": "Invalid tool call; use bash with a string command.", "is_error": True}
                            self._event("tool_result", turn=turns, result=result)
                            results.append(result)
                            continue
                        self._event("tool_start", turn=turns, tool_use_id=call["id"], command=args["command"])
                        try:
                            # wait_for keeps cancellation responsive; Harbor stops the whole
                            # container before collecting state, including surviving children.
                            command_result = await asyncio.wait_for(environment.exec(command=args["command"]),
                                                                    self.options.tool_timeout_sec)
                        except TimeoutError:
                            reason, validity = "tool_timeout", "valid"
                            self._event("tool_timeout", turn=turns, tool_use_id=call["id"])
                            return
                        stdout, stderr = command_result.stdout or "", command_result.stderr or ""
                        self._event("tool_output", turn=turns, tool_use_id=call["id"], stdout=stdout, stderr=stderr,
                                    exit_code=command_result.return_code)
                        output = f"stdout:\n{stdout}\n\nstderr:\n{stderr}\n\nexit_code: {command_result.return_code}"
                        output = self._redact(output)
                        if len(output) > self.options.max_tool_chars:
                            output = output[:self.options.max_tool_chars] + "\n[Tool output truncated; narrow the command to retrieve missing content.]"
                            self._event("tool_output_truncated", turn=turns, tool_use_id=call["id"])
                        result = {"type": "tool_result", "tool_use_id": call["id"], "content": output,
                                  "is_error": command_result.return_code != 0}
                        self._event("tool_result", turn=turns, result=result)
                        results.append(result)
                    messages.append({"role": "user", "content": results})
                else:
                    reason, validity = "turn_exhaustion", "valid"
        except TimeoutError:
            reason, validity = "wall_timeout", "valid"
        except asyncio.CancelledError:
            reason, validity = "cancelled", "interrupted"
            raise
        except anthropic.APIError as exc:
            reason = "api_error"
            self._event("api_error", error_type=type(exc).__name__, status_code=getattr(exc, "status_code", None),
                        request_id=getattr(exc, "request_id", None))
        except KeyError:
            reason = "missing_credentials"
        except Exception as exc:
            reason = "tool_or_adapter_error"
            self._event("error", error_type=type(exc).__name__)  # Never log exception bodies/headers.
        finally:
            context.n_input_tokens = usage["input_tokens"] + usage["cache_read_input_tokens"] + usage["cache_creation_input_tokens"]
            context.n_output_tokens = usage["output_tokens"]
            context.n_cache_tokens = usage["cache_read_input_tokens"]
            context.model_usage = {self.model_name: ModelUsage(n_input_tokens=context.n_input_tokens,
                                   n_output_tokens=context.n_output_tokens, n_cache_tokens=context.n_cache_tokens)}
            termination = {"reason": reason, "validity": validity, "turns": turns, "usage": usage,
                           "model": self.model_name, "elapsed_sec": round(time.monotonic() - self._started, 6)}
            context.metadata = {**(context.metadata or {}), "anthropic_termination": termination}
            self._event("termination", **termination)
            (self.evidence_dir / "termination.json").write_text(self._redact(json.dumps(termination, indent=2)))
            if client is not None:
                await client.close()
