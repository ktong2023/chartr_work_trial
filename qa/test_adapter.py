"""No-network adapter checks: every model response is mocked."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import anthropic
import httpx
from harbor.models.agent.context import AgentContext
from anthropic_agent import AnthropicAgent


def response(stop='end_turn', content=None):
    return anthropic.types.Message(id='msg_mock', type='message', role='assistant', model='mock-opus',
        content=content or [{'type':'text','text':'Done'}], stop_reason=stop, stop_sequence=None,
        usage={'input_tokens':10,'output_tokens':5,'cache_read_input_tokens':3,'cache_creation_input_tokens':2})


def tool(name='bash', args=None):
    return response('tool_use', [{'type':'tool_use','id':'tool_mock','name':name,'input':args or {'command':'clinic patients'}}])


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.logs = Path(self.tmp.name) / 'agent'
        self.client = SimpleNamespace(messages=SimpleNamespace(create=AsyncMock()), close=AsyncMock())
        self.environment = SimpleNamespace(exec=AsyncMock(return_value=SimpleNamespace(stdout='ok', stderr='', return_code=0)))
        self.context = AgentContext()
        self.patch_client = patch('anthropic_agent.anthropic.AsyncAnthropic', return_value=self.client)
        self.constructor = self.patch_client.start()
        self.addCleanup(self.patch_client.stop)
        self.patch_env = patch.dict(os.environ, {'ANTHROPIC_API_KEY':'sk-ant-offline-test-secret'})
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)

    async def run_agent(self, responses, **options):
        self.client.messages.create.side_effect = responses
        agent = AnthropicAgent(logs_dir=self.logs, **options)
        await agent.run('Test instruction', self.environment, self.context)
        return self.read_termination(), self.read_events()

    def read_termination(self):
        return json.loads((Path(self.tmp.name)/'controller/anthropic/termination.json').read_text())

    def read_events(self):
        return [json.loads(x) for x in (Path(self.tmp.name)/'controller/anthropic/events.jsonl').read_text().splitlines()]

    async def test_tool_loop_usage_and_config(self):
        term, events = await self.run_agent([tool(), response()], model_name='org-opus', max_tokens=321)
        self.assertEqual(term['reason'],'end_turn')
        self.assertEqual(term['validity'],'valid')
        self.assertEqual(self.context.n_input_tokens,30)
        self.assertEqual(self.context.n_output_tokens,10)
        self.assertEqual(self.context.n_cache_tokens,6)
        first = self.client.messages.create.call_args_list[0].kwargs
        self.assertEqual(set(first), {'model','max_tokens','tools','messages','thinking','cache_control'})
        self.assertEqual(first['thinking'], {'type': 'adaptive', 'display': 'summarized'})
        self.assertEqual(first['cache_control'], {'type': 'ephemeral'})
        self.assertEqual(first['model'],'org-opus')
        self.assertEqual(first['max_tokens'],321)
        self.assertTrue(any(e['event']=='tool_output' for e in events))
        self.assertFalse(self.logs.exists())
        self.client.close.assert_awaited_once()

    async def test_turn_exhaustion(self):
        term, _ = await self.run_agent([tool()], max_turns=1)
        self.assertEqual(term['reason'],'turn_exhaustion')
        self.assertEqual(term['validity'],'valid')

    async def test_output_truncation_no_partial_tool_execution(self):
        truncated = tool(); truncated.stop_reason='max_tokens'
        term, _ = await self.run_agent([truncated])
        self.assertEqual(term['reason'],'output_truncated')
        self.environment.exec.assert_not_awaited()

    async def test_tool_error_feedback_and_output_truncation(self):
        self.environment.exec.return_value = SimpleNamespace(stdout='x'*2000, stderr='invalid request', return_code=2)
        term, events = await self.run_agent([tool(),response()], max_tool_chars=256)
        results = [e['result'] for e in events if e['event']=='tool_result']
        self.assertTrue(results[0]['is_error'])
        self.assertIn('truncated',results[0]['content'])
        self.assertEqual(term['reason'],'end_turn')

    async def test_invalid_tool_feedback(self):
        _, events = await self.run_agent([tool('unknown'), response()])
        self.environment.exec.assert_not_awaited()
        self.assertTrue(next(e for e in events if e['event']=='tool_result')['result']['is_error'])

    async def test_api_error_is_invalid_and_redacted(self):
        self.client.messages.create.side_effect = anthropic.APIConnectionError(request=httpx.Request('POST','https://example.invalid'))
        agent = AnthropicAgent(logs_dir=self.logs, api_retry_delays=(0, 0))
        await agent.run('sk-ant-offline-test-secret',self.environment,self.context)
        self.assertEqual(self.client.messages.create.await_count, 3)
        self.assertEqual(self.read_termination()['validity'],'evaluation_error')
        self.assertEqual(self.read_termination()['reason'],'api_error')
        self.assertNotIn('sk-ant-offline-test-secret',json.dumps(self.read_events()))

    async def test_transient_api_error_is_retried_and_logged(self):
        error = anthropic.APIConnectionError(request=httpx.Request('POST', 'https://example.invalid'))
        term, events = await self.run_agent([error, response()], api_retry_delays=(0,))
        self.assertEqual((term['reason'], term['validity']), ('end_turn', 'valid'))
        self.assertEqual([e['error_type'] for e in events if e['event'] == 'api_retry'], ['APIConnectionError'])

    async def test_missing_credentials_is_invalid_without_api_call(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': ''}):
            agent = AnthropicAgent(logs_dir=self.logs)
            await agent.run('Test', self.environment, self.context)
        self.assertEqual((self.read_termination()['reason'], self.read_termination()['validity']),
                         ('missing_credentials', 'evaluation_error'))
        self.constructor.assert_not_called()

    async def test_adaptive_thinking_can_be_disabled(self):
        await self.run_agent([response()], adaptive_thinking=False)
        self.assertNotIn('thinking', self.client.messages.create.call_args_list[0].kwargs)

    async def test_tool_infrastructure_error(self):
        self.environment.exec.side_effect = RuntimeError('secret body must not be logged')
        term, events = await self.run_agent([tool()])
        self.assertEqual(term['validity'],'evaluation_error')
        self.assertNotIn('secret body',json.dumps(events))

    async def test_tool_timeout(self):
        async def slow(**kwargs):
            await asyncio.sleep(2)
        self.environment.exec.side_effect=slow
        term, _ = await self.run_agent([tool()], tool_timeout_sec=.01)
        self.assertEqual(term['reason'],'tool_timeout')

    async def test_wall_timeout_nonblocking(self):
        async def slow(**kwargs):
            await asyncio.sleep(2)
        self.client.messages.create.side_effect=slow
        agent=AnthropicAgent(logs_dir=self.logs,wall_timeout_sec=.02)
        work=asyncio.create_task(agent.run('Test',self.environment,self.context))
        await asyncio.sleep(.005)
        self.assertFalse(work.done())
        await work
        self.assertEqual(self.read_termination()['reason'],'wall_timeout')

    async def test_cancellation_persists_and_propagates(self):
        started=asyncio.Event()
        async def slow(**kwargs):
            started.set()
            await asyncio.sleep(2)
        self.client.messages.create.side_effect=slow
        agent=AnthropicAgent(logs_dir=self.logs)
        work=asyncio.create_task(agent.run('Test',self.environment,self.context))
        await started.wait()
        work.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await work
        self.assertEqual(self.read_termination()['reason'],'cancelled')
        self.assertEqual(self.read_termination()['validity'],'interrupted')

    def test_environment_defaults_and_import_path(self):
        with patch.dict(os.environ, {'ANTHROPIC_MODEL':'environment-opus','ANTHROPIC_MAX_TURNS':'7'}):
            agent=AnthropicAgent(logs_dir=self.logs)
            self.assertEqual(agent.model_name,'environment-opus')
            self.assertEqual(agent.options.max_turns,7)
        from harbor.agents.factory import AgentFactory
        from harbor.models.trial.config import AgentConfig
        agent=AgentFactory.create_agent_from_config(AgentConfig(import_path='anthropic_agent:AnthropicAgent'), logs_dir=self.logs)
        self.assertIsInstance(agent,AnthropicAgent)


if __name__ == '__main__':
    unittest.main()
