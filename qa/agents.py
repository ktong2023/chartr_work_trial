"""Private no-credit Harbor probes. Never copied into evaluated images."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

import anthropic
import httpx
from harbor.agents.base import BaseAgent
from anthropic_agent import AnthropicAgent


class BoundaryProbe(BaseAgent):
    @staticmethod
    def name():
        return "boundary-probe"

    def version(self):
        return "1"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
        result = await environment.exec(command=r'''python - <<'PY'
import json, os, pathlib, urllib.request, urllib.error
for path in ('/tests','/solution','/state','/app/fixture.json','/app/store.py',
             '/app/grade.py','/var/run/docker.sock','/app/chartr_task1_conceptual_framework_v0_1.md'):
    assert not pathlib.Path(path).exists(), path
assert not any('ANTHROPIC' in k for k in os.environ)
for route in ('reset','admin','export','grade','records/S01'):
    try:
        urllib.request.urlopen(urllib.request.Request('http://clinic:8000/'+route,data=b'{}',
                              headers={'Content-Type':'application/json'}))
        raise AssertionError('Unexpected writable route: '+route)
    except urllib.error.HTTPError as error:
        assert error.code == 400
pathlib.Path('/evidence').mkdir(exist_ok=True)
pathlib.Path('/evidence/snapshot.json').write_text('{"forged":true}')
pathlib.Path('/logs/artifacts/evidence').mkdir(parents=True,exist_ok=True)
pathlib.Path('/logs/artifacts/evidence/snapshot.json').write_text('{"forged":true}')
print('Private files, admin routes, source writes, credentials and Docker socket inaccessible; forgery planted.')
PY''')
        controller = Path(self.logs_dir).parent / "controller"
        controller.mkdir(exist_ok=True)
        (controller / "boundary-probe.json").write_text(json.dumps({
            "exit_code": result.return_code, "stdout": result.stdout, "stderr": result.stderr}, indent=2))
        if result.return_code:
            raise RuntimeError("Boundary probe failed")


class MockAPIError(AnthropicAgent):
    async def run(self, instruction, environment, context):
        client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(side_effect=
            anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.invalid")))), close=AsyncMock())
        with patch("anthropic_agent.anthropic.AsyncAnthropic", return_value=client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-offline-test-only"}):
            await super().run(instruction, environment, context)


class MockBudget(AnthropicAgent):
    async def run(self, instruction, environment, context):
        response = anthropic.types.Message(
            id="msg_offline", type="message", role="assistant", model="mock-opus",
            content=[{"type": "tool_use", "id": "tool_offline", "name": "bash",
                      "input": {"command": "clinic patients"}}], stop_reason="tool_use", stop_sequence=None,
            usage={"input_tokens": 10, "output_tokens": 5})
        client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock(return_value=response)), close=AsyncMock())
        with patch("anthropic_agent.anthropic.AsyncAnthropic", return_value=client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-offline-test-only"}):
            await super().run(instruction, environment, context)
