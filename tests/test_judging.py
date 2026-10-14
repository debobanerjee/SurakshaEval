"""Tests for question and response judging in async and Batch modes; no paid calls."""
import asyncio
import copy
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from judging import JudgeClient, parse_answers, run_tasks
from judging_batch import run_batch
from pipeline_common import read_rows


def tasks_for(role, count=3):
    rubric = {'count': 1, 'labels': [1], 'threshold': 2} if role == 'questions' else {
        'count': 2, 'labels': [1, 0], 'groups': {
            'default': {'labels': [1], 'threshold': 1},
            'generic': {'labels': [0], 'threshold': 1}}}
    return [{'row': {'index': i, 'question': f'question {i}', 'output': f'response {i}',
                     'meta': {'type_of_harm': 'Generic'}},
             'round': 1, 'region': 'hindi', 'source_file': 'source.jsonl', 'source_row': i,
             'rubric': rubric, 'messages': [{'role': 'user', 'content': str(i)}], 'skip_reason': None}
            for i in range(count)]


def reply(role):
    answers = [{'YES': 5}] if role == 'questions' else ['YES', 'NO']
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'Answer': answers})}}]}


class JudgingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'judge.jsonl'
        self.logger = logging.getLogger('test-judging')
        env = patch.dict(os.environ, OPENAI_API_KEY='mock-environment-key')
        env.start(); self.addCleanup(env.stop)
        original = asyncio.sleep
        async def fast_sleep(_):
            await original(0)
        sleep = patch.object(asyncio, 'sleep', fast_sleep)
        sleep.start(); self.addCleanup(sleep.stop)

    async def check_async(self, role):
        tasks = tasks_for(role)
        requests = []
        failing = True
        def serve(request):
            self.assertEqual(request.headers['Authorization'], 'Bearer mock-environment-key')
            index = int(json.loads(request.content)['messages'][0]['content'])
            requests.append(index)
            return httpx.Response(500) if index == 1 and failing else httpx.Response(200, json=reply(role))
        async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
            self.assertEqual(await run_tasks(client, tasks[:2], role, {}, 'judge', {}, self.output, False, 2, self.logger), 1)
            self.assertEqual(requests.count(1), 5)
            self.assertEqual([r['status'] for r in read_rows(self.output)], ['SUCCESS', 'ERROR'])
            # Matching successful sample is skipped; ERROR and new sample are processed.
            failing = False
            requests.clear()
            self.assertEqual(await run_tasks(client, tasks, role, {}, 'judge', {}, self.output, True, 2, self.logger), 0)
            self.assertEqual(sorted(requests), [1, 2])
            records = read_rows(self.output)
            self.assertEqual(len(records), 3)
            self.assertTrue(all(r['status'] == 'SUCCESS' for r in records))
            self.assertEqual(records[1]['judging']['total_attempts'], 6)
            requests.clear()
            await run_tasks(client, tasks, role, {}, 'judge', {}, self.output, True, 2, self.logger)
            self.assertEqual(requests, [])
            changed = copy.deepcopy(tasks)
            changed[1]['row']['output'] = 'regenerated response'
            await run_tasks(client, changed, role, {}, 'judge', {}, self.output, True, 2, self.logger)
            self.assertEqual(requests, [1])
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                await run_tasks(client, changed, role, {}, 'other-judge', {}, self.output, True, 2, self.logger)
            with self.assertRaises(FileExistsError):
                await run_tasks(client, tasks, role, {}, 'judge', {}, self.output, False, 2, self.logger)

    async def test_question_judging_retry(self):
        await self.check_async('questions')

    async def test_model_response_judging_retry(self):
        await self.check_async('responses')

    async def check_batch(self, role):
        tasks = tasks_for(role)
        indices, submissions = [], []
        failing = True
        async def upload(client, path):
            indices[:] = [int(r['custom_id'][5:]) for r in read_rows(path)]
            submissions.append(list(indices))
            return 'file-input'
        def serve(request):
            if request.method == 'POST':
                body = json.loads(request.content)
                self.assertEqual(body['endpoint'], '/v1/chat/completions')
                return httpx.Response(200, json={'id': f'batch-{len(submissions)}'})
            if '/batches/' in request.url.path:
                return httpx.Response(200, json={'status': 'completed', 'output_file_id': 'file-output'})
            entries = [{'custom_id': f'task-{i}',
                'error': {'code': 'batch_expired'} if i == 1 and failing else None,
                'response': None if i == 1 and failing else {'status_code': 200, 'body': reply(role)}}
                for i in reversed(indices)]
            return httpx.Response(200, text='\n'.join(json.dumps(e) for e in entries))
        with patch('judging_batch.upload_file', upload):
            async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
                self.assertEqual(await run_batch(client, tasks, role, {}, 'judge', {}, self.output, False, 'run', 1, 20, self.logger), 1)
                self.assertEqual(submissions, [[0, 1, 2], [1], [1], [1], [1]])
                self.assertEqual([r['status'] for r in read_rows(self.output)], ['SUCCESS', 'ERROR', 'SUCCESS'])
                failing = False
                self.assertEqual(await run_batch(client, tasks, role, {}, 'judge', {}, self.output, True, 'run', 1, 20, self.logger), 0)
                self.assertEqual(submissions[-1], [1])
                self.assertEqual(read_rows(self.output)[1]['judging']['total_attempts'], 6)
                count = len(submissions)
                self.assertEqual(await run_batch(client, tasks, role, {}, 'judge', {}, self.output, True, 'run', 1, 20, self.logger), 0)
                self.assertEqual(len(submissions), count)
                self.assertEqual(len(read_rows(self.output)), 3)

    async def test_question_batch_retry(self):
        await self.check_batch('questions')

    async def test_model_response_batch_retry(self):
        await self.check_batch('responses')

    async def test_unavailable_response_is_error_then_retried(self):
        tasks = tasks_for('responses', 1)
        tasks[0]['skip_reason'] = 'generation_error'
        seen = []
        def serve(request):
            seen.append(request)
            return httpx.Response(200, json=reply('responses'))
        async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
            self.assertEqual(await run_tasks(client, tasks, 'responses', {}, 'judge', {}, self.output, False, 1, self.logger), 1)
            self.assertEqual(seen, [])
            tasks[0]['skip_reason'] = None
            self.assertEqual(await run_tasks(client, tasks, 'responses', {}, 'judge', {}, self.output, True, 1, self.logger), 0)
            self.assertEqual(len(seen), 1)

    async def test_invalid_schema_uses_five_attempts(self):
        requests = []
        def serve(request):
            requests.append(request)
            result = reply('questions')
            result['choices'][0]['message']['content'] = '{"Answer":[{"YES":true}]}'
            return httpx.Response(200, json=result)
        async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
            self.assertEqual(await run_tasks(client, tasks_for('questions', 1), 'questions', {}, 'judge', {}, self.output, False, 1, self.logger), 1)
        self.assertEqual(len(requests), 5)
        self.assertIn('raw_response', read_rows(self.output)[0]['judging'])

    async def test_pending_batch_collect_preserves_attempt_budget(self):
        tasks = tasks_for('questions', 1)
        submissions = []
        ready = False
        async def upload(client, path):
            submissions.append(read_rows(path))
            return 'input'
        def serve(request):
            if request.method == 'POST':
                return httpx.Response(200, json={'id': f'batch-{len(submissions)}'})
            if '/batches/' in request.url.path:
                return httpx.Response(200, json={'status': 'completed' if ready else 'in_progress',
                                                 'output_file_id': 'output' if ready else None})
            return httpx.Response(200, text=json.dumps({'custom_id': 'task-0', 'response': {'status_code': 500, 'body': {}}}))
        with patch('judging_batch.upload_file', upload):
            async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
                self.assertEqual(await run_batch(client, tasks, 'questions', {}, 'judge', {}, self.output, False, 'submit', 1, 20, self.logger), 2)
                self.assertEqual(await run_batch(client, tasks, 'questions', {}, 'judge', {}, self.output, True, 'collect', 1, 20, self.logger), 2)
                self.assertEqual(len(submissions), 1)
                changed = copy.deepcopy(tasks); changed[0]['row']['question'] = 'changed'
                with self.assertRaisesRegex(ValueError, 'changed'):
                    await run_batch(client, changed, 'questions', {}, 'judge', {}, self.output, True, 'collect', 1, 20, self.logger)
                with self.assertRaisesRegex(ValueError, 'pending Batch'):
                    await run_tasks(client, tasks, 'questions', {}, 'judge', {}, self.output, True, 1, self.logger)
                ready = True
                for _ in range(4):
                    self.assertEqual(await run_batch(client, tasks, 'questions', {}, 'judge', {}, self.output, True, 'collect', 1, 20, self.logger), 2)
                self.assertEqual(await run_batch(client, tasks, 'questions', {}, 'judge', {}, self.output, True, 'collect', 1, 20, self.logger), 1)
                self.assertEqual(len(submissions), 5)
                self.assertEqual(read_rows(self.output)[0]['judging']['attempts'], 5)

    async def test_collect_only_keeps_partial_results_without_resubmitting(self):
        tasks = tasks_for('questions', 2)
        submissions = []
        async def upload(client, path):
            submissions.append(read_rows(path)); return 'input'
        def serve(request):
            if request.method == 'POST': return httpx.Response(200, json={'id': 'batch_partial'})
            if '/batches/' in request.url.path:
                return httpx.Response(200, json={'status': 'cancelled', 'output_file_id': 'output'})
            return httpx.Response(200, text=json.dumps({'custom_id': 'task-0', 'response': {'status_code': 200, 'body': reply('questions')}}))
        with patch('judging_batch.upload_file', upload):
            async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
                self.assertEqual(await run_batch(client, tasks, 'questions', {}, 'judge', {}, self.output, False, 'submit', 1, 20, self.logger), 2)
                self.assertEqual(await run_batch(client, tasks, 'questions', {}, 'judge', {}, self.output, True, 'collect-only', 1, 20, self.logger), 1)
                self.assertEqual(len(submissions), 1)
                self.assertEqual([r['status'] for r in read_rows(self.output)], ['SUCCESS', 'ERROR'])

    def test_answer_schemas(self):
        with self.assertRaises(ValueError):
            parse_answers('{"Answer":["yes"]}', 'responses', 1)
        with self.assertRaises(ValueError):
            parse_answers('{"Answer":[{"YES":6}]}', 'questions', 1)


if __name__ == '__main__':
    unittest.main()
