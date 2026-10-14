"""Async client tests using HTTPX's mock transport; no model or network needed."""
import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx

SCRIPT = Path(__file__).resolve().parents[1] / 'pipeline/generate-responses.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('generate_responses', SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
CLIENT = runner.VLLMClient


class FakeServer:
    def __init__(self, model, count=100, fail_once=False):
        self.model, self.count, self.fail_once = model, count, fail_once
        self.requests = []
        self.active = self.peak = 0

    async def __call__(self, request):
        self.requests.append(request)
        assert request.headers['Authorization'] == 'Bearer test-key'
        if request.url.path.endswith('/models'):
            data = {'data': [{'id': self.model}]}
        elif request.url.path.endswith('/tokenize'):
            data = {'count': self.count, 'max_model_len': 4096, 'tokens': []}
        else:
            if self.fail_once:
                self.fail_once = False
                return httpx.Response(429, json={'error': 'busy'})
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(0.005)
            self.active -= 1
            data = {'id': 'response-1', 'choices': [{'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': 'নমস্কাৰ',
                    'reasoning': 'retained reasoning', 'tool_calls': []}}],
                    'usage': {'prompt_tokens': self.count, 'completion_tokens': 3}}
        return httpx.Response(200, json=data)

    def client(self, *args):
        return CLIENT(*args, transport=httpx.MockTransport(self))


class ResponseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, PIPELINE_LOG_DIR=temp.name)
        env.start()
        self.addCleanup(env.stop)
        original = asyncio.sleep
        async def fast_sleep(seconds):
            await original(0 if seconds >= 1 else seconds)
        sleep = patch.object(asyncio, 'sleep', fast_sleep)
        sleep.start()
        self.addCleanup(sleep.stop)

    async def test_context_budget_and_raw_fields(self):
        server = FakeServer('test/model', count=4090)
        async with server.client('http://localhost:8801/v1', 'test-key') as client:
            result = await client.generate({'question': 'অসমীয়া', 'index': 5}, '',
                server.model, {'max_tokens': 4096, 'seed': 42}, {}, 4096)
        payload = json.loads(server.requests[-1].content)
        self.assertEqual(payload['max_tokens'], 6)
        self.assertEqual(payload['messages'], [{'role': 'user', 'content': 'অসমীয়া'}])
        self.assertEqual(result['generation']['assistant_message']['reasoning'], 'retained reasoning')
        self.assertEqual(result['index'], 5)

    async def test_overlong_prompt_never_generates(self):
        server = FakeServer('test/model', count=4096)
        async with server.client('http://localhost:8801/v1', 'test-key') as client:
            with self.assertRaises(ValueError):
                await client.generate({'question': 'text'}, '', server.model,
                    {'max_tokens': 4096}, {}, 4096)
        self.assertEqual(len(server.requests), 6)

    async def test_retries_transient_errors(self):
        server = FakeServer('test/model', fail_once=True)
        async with server.client('http://localhost:8801/v1', 'test-key') as client:
            # Only suppress retry delay; preserve asynchronous generation yields.
            original = asyncio.sleep
            async def no_delay(seconds):
                await original(0 if seconds >= 1 else seconds)
            with patch.object(runner.asyncio, 'sleep', no_delay):
                await client.generate({'question': 'text'}, 'system', server.model,
                    {'max_tokens': 5}, {}, 4096)
        self.assertEqual(len(server.requests), 4)

    async def test_auth_failure_exhausts_metadata_retries(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(401))
        async with CLIENT('http://localhost:8801/v1', 'test-key', transport=transport) as client:
            with self.assertRaisesRegex(RuntimeError, '401'):
                await client.check_model('test/model')

    async def test_custom_profile_and_retry(self):
        model = 'BhabhaAI/Gajendra-v0.1'
        server = FakeServer(model)
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / 'data/filtered_and_updated/hindi/en_questions.jsonl'
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps({'index': 0, 'question': 'Example?',
                'meta': {'risk_area': 'Hindi-specific'}}) + '\n')
            args = ['--model', model, '--input-dir', str(tmp / 'data'),
                '--output-dir', str(tmp / 'out'), '--regions', 'hindi', '--languages', 'en']
            with patch.dict(os.environ, VLLM_API_KEY='test-key'), patch.object(runner, 'VLLMClient', server.client):
                self.assertEqual(await runner.async_main(args), 0)
                outputs = sorted((tmp / 'out').rglob('*.jsonl'))
                self.assertEqual(len(outputs), 1)
                self.assertEqual(outputs[0].name, 'BhabhaAI--Gajendra-v0.1_turn_1_response.jsonl')
                records = runner.read_rows(outputs[0])
                self.assertEqual([r['generation']['sampling_params']['seed'] for r in records], [42])
                self.assertEqual([r['generation']['turn'] for r in records], [1])
                self.assertEqual(records[0]['generation']['region'], 'hindi')
                self.assertEqual(records[0]['output'], 'নমস্কাৰ')
                before = len(server.requests)
                self.assertEqual(await runner.async_main(args + ['--retry']), 0)
                self.assertEqual(len(server.requests), before + 1)
                with self.assertRaises(FileExistsError):
                    await runner.async_main(args)
                source.write_text('{"index":0,"question":"Changed?"}\n')
                self.assertEqual(await runner.async_main(args + ['--retry']), 0)
                self.assertEqual(len(runner.read_rows(outputs[0])), 1)

    async def test_server_alias_string_and_list_in_deployment(self):
        model = 'BhabhaAI/Gajendra-v0.1'
        for names in ['server-alias', ['server-alias', 'another-alias']]:
            server = FakeServer('server-alias')
            original_load = runner.load_yaml
            def load(path):
                value = original_load(path)
                if str(path).endswith('.deployment.config.yaml'):
                    value['served-model-name'] = names
                return value
            with tempfile.TemporaryDirectory() as directory:
                tmp = Path(directory)
                source = tmp / 'data/filtered_and_updated/hindi/en_questions.jsonl'
                source.parent.mkdir(parents=True)
                source.write_text('{"index":0,"question":"Example?"}\n')
                args = ['--model', model, '--input-dir', str(tmp / 'data'), '--output-dir', str(tmp / 'out'),
                        '--regions', 'hindi', '--languages', 'en']
                with patch.dict(os.environ, VLLM_API_KEY='test-key'), \
                        patch.object(runner, 'VLLMClient', server.client), patch.object(runner, 'load_yaml', load):
                    self.assertEqual(await runner.async_main(args), 0)
                records = runner.read_rows(tmp / 'out/BhabhaAI--Gajendra-v0.1_turn_1_response.jsonl')
                self.assertEqual(records[0]['generation']['model'], 'server-alias')
                self.assertEqual(json.loads(server.requests[-1].content)['model'], 'server-alias')

    async def test_each_generation_turn_has_its_own_file(self):
        model = 'BhabhaAI/Gajendra-v0.1'
        server = FakeServer(model)
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            source = tmp / 'data/filtered_and_updated/hindi/en_questions.jsonl'
            source.parent.mkdir(parents=True)
            source.write_text('{"index":0,"question":"Example?"}\n')
            args = ['--model', model, '--input-dir', str(tmp / 'data'),
                    '--output-dir', str(tmp / 'out'), '--regions', 'hindi', '--languages', 'en', '--turns', '2']
            with patch.dict(os.environ, VLLM_API_KEY='test-key'), patch.object(runner, 'VLLMClient', server.client):
                self.assertEqual(await runner.async_main(args), 0)
                for turn in [1, 2]:
                    path = tmp / 'out' / f'BhabhaAI--Gajendra-v0.1_turn_{turn}_response.jsonl'
                    records = runner.read_rows(path)
                    self.assertEqual(len(records), 1)
                    self.assertEqual(records[0]['generation']['turn'], turn)
                    self.assertEqual(records[0]['generation']['sampling_params']['seed'], 41 + turn)
                before = len(server.requests)
                self.assertEqual(await runner.async_main(args + ['--retry']), 0)
                self.assertEqual(len(server.requests), before + 1)  # Metadata only.

    async def test_thinking_disabled_on_both_endpoints(self):
        server = FakeServer('sarvamai/sarvam-m')
        async with server.client('http://localhost:8823/v1', 'test-key') as client:
            await client.generate({'question': 'text'}, '', server.model,
                {'max_tokens': 20}, {'enable_thinking': False}, 8192)
        for request in server.requests:
            self.assertFalse(json.loads(request.content)['chat_template_kwargs']['enable_thinking'])

    async def test_bounded_concurrency_and_partial_retry(self):
        server = FakeServer('test/model')
        settings = {'served_model': server.model, 'system_prompt': '', 'system_prompt_type': 'empty',
            'sampling': {'max_tokens': 20}, 'context_len': 4096, 'template_kwargs': {}, 'turn': 1}
        rows = [{'index': i, 'question': f'Question {i}'} for i in range(9)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'out.jsonl'
            async with server.client('http://localhost:8801/v1', 'test-key') as client:
                self.assertEqual(await runner.generate_file(client, path, path, rows, settings, False, 2), 0)
                self.assertEqual(server.peak, 2)
                self.assertEqual([r['index'] for r in runner.read_rows(path)], list(range(9)))
                lines = path.read_text().splitlines()
                path.write_text('\n'.join(lines[:3]) + '\n')
                before = len(server.requests)
                self.assertEqual(await runner.generate_file(client, path, path, rows, settings, True, 2), 0)
                self.assertEqual(len(server.requests), before + 12)
                self.assertEqual(len(runner.read_rows(path)), 9)

    async def test_error_retry_and_unprocessed_rows(self):
        server = FakeServer('test/model')
        settings = {'served_model': server.model, 'base_url': 'http://localhost:8801/v1',
            'system_prompt': '', 'system_prompt_type': 'empty', 'sampling': {'max_tokens': 20},
            'context_len': 4096, 'template_kwargs': {}, 'turn': 1}
        rows = [{'index': i, 'question': f'Question {i}'} for i in range(3)]
        failing = True
        async def serve(request):
            if request.url.path.endswith('/chat/completions'):
                question = json.loads(request.content)['messages'][-1]['content']
                if failing and question == 'Question 1': return httpx.Response(500)
            return await server(request)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'out.jsonl'
            async with CLIENT(settings['base_url'], 'test-key', transport=httpx.MockTransport(serve)) as client:
                self.assertEqual(await runner.generate_file(client, path, path, rows, settings, False, 2), 1)
                records = runner.read_rows(path)
                self.assertEqual([r['status'] for r in records], ['SUCCESS', 'ERROR', 'SUCCESS'])
                self.assertEqual(records[1]['generation']['attempts'], 6)
                # Simulate one remaining unprocessed row, alongside one ERROR.
                path.write_text('\n'.join(json.dumps(r) for r in records[:2]) + '\n')
                failing = False
                server.requests.clear()
                self.assertEqual(await runner.generate_file(client, path, path, rows, settings, True, 2), 0)
                self.assertEqual(len(server.requests), 4)
                records = runner.read_rows(path)
                self.assertEqual(len(records), 3)
                self.assertTrue(all(r['status'] == 'SUCCESS' for r in records))
                self.assertEqual(records[1]['generation']['total_attempts'], 7)

    async def test_timeout_extension_is_scoped_to_sample(self):
        server = FakeServer('test/model')
        seen = []
        first = True
        async def serve(request):
            nonlocal first
            question = json.loads(request.content)['messages'][-1]['content']
            seen.append((question, request.extensions['timeout']['read']))
            if question == 'timed' and first:
                first = False
                raise httpx.ReadTimeout('mock timeout', request=request)
            return await server(request)
        async with CLIENT('http://localhost:8801/v1', 'test-key', timeout=120,
                          transport=httpx.MockTransport(serve)) as client:
            await asyncio.gather(*(client.generate({'question': q}, '', 'test/model',
                {'max_tokens': 5}, {}, 4096) for q in ['timed', 'other']))
        self.assertEqual([t for q, t in seen if q == 'timed'], [120, 3000, 3000])
        self.assertTrue(all(t == 120 for q, t in seen if q == 'other'))

    async def test_gemini_native_payload_budget_and_feedback(self):
        requests = []
        blocked = False
        def serve(request):
            requests.append(request)
            self.assertEqual(request.headers['x-goog-api-key'], 'mock-gemini-key')
            if request.method == 'GET':
                value = {'supportedGenerationMethods': ['generateContent'], 'inputTokenLimit': 10000, 'outputTokenLimit': 100}
            elif request.url.path.endswith(':countTokens'):
                value = {'totalTokens': 8190}
            else:
                value = {'promptFeedback': {'blockReason': 'SAFETY'}} if blocked else {
                    'candidates': [{'content': {'parts': [{'text': 'thinking', 'thought': True}, {'text': 'answer'}]},
                                    'finishReason': 'STOP', 'safetyRatings': []}],
                    'usageMetadata': {'promptTokenCount': 8190}, 'modelVersion': 'verified-version'}
            return httpx.Response(200, json=value)
        async with runner.GeminiClient('https://mock/v1beta', 'mock-gemini-key', transport=httpx.MockTransport(serve)) as client:
            await client.check_model('gemini-2.5-flash')
            result = await client.generate({'question': 'text'}, 'instruction', 'gemini-2.5-flash',
                                           {'max_tokens': 4096, 'temperature': 0.6, 'seed': 42}, {}, 8192)
            self.assertEqual(result['output'], 'answer')
            self.assertEqual(result['generation']['assistant_message']['parts'][0]['text'], 'thinking')
            payload = json.loads(requests[-1].content)
            self.assertEqual(payload['generationConfig']['maxOutputTokens'], 2)
            self.assertNotIn('safetySettings', payload)
            self.assertEqual(json.loads(requests[-2].content)['generateContentRequest']['systemInstruction'],
                             {'parts': [{'text': 'instruction'}]})
            blocked = True
            result = await client.generate({'question': 'text'}, '', 'gemini-2.5-flash', {'max_tokens': 5}, {}, 8192)
            self.assertTrue(result['generation']['blocked'])
            self.assertEqual(result['generation']['finish_reason'], 'PROMPT_BLOCKED')


if __name__ == '__main__':
    unittest.main()
