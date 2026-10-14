"""Batch inspection/cancellation tests use only mocked API requests."""
import asyncio
import argparse
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
from batch_management import cancel, inspect, selected_ids
from judging import JudgeClient


class BatchManagementTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.logger = logging.getLogger('test-batch-management')
        env = patch.dict(os.environ, OPENAI_API_KEY='mock-key')
        env.start(); self.addCleanup(env.stop)

    async def test_listing_follows_pages_and_filters_active_roles(self):
        seen = []
        def serve(request):
            seen.append(request)
            self.assertEqual(request.headers['Authorization'], 'Bearer mock-key')
            if request.url.params.get('after'):
                self.assertEqual(request.url.params['after'], 'batch_finished')
                value = {'data': [{'id': 'batch_response', 'status': 'cancelling', 'metadata': {'role': 'responses'}},
                                  {'id': 'batch_question', 'status': 'in_progress', 'metadata': {'role': 'questions'}}], 'has_more': False}
            else:
                value = {'data': [{'id': 'batch_finished', 'status': 'completed', 'metadata': None}],
                         'has_more': True, 'last_id': 'batch_finished'}
            return httpx.Response(200, json=value)
        async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
            jobs = await inspect(client, role='responses', page_size=1)
            self.assertEqual([job['id'] for job in jobs], ['batch_response'])
            self.assertEqual(len(seen), 2)
            self.assertEqual(seen[0].url.params['limit'], '1')

    async def test_all_listing_includes_finished_jobs(self):
        jobs = [{'id': 'batch_finished', 'status': 'completed'}, {'id': 'batch_active', 'status': 'in_progress'}]
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'data': jobs, 'has_more': False}))
        async with JudgeClient('https://mock/v1', self.logger, transport=transport) as client:
            self.assertEqual(len(await inspect(client)), 1)
            self.assertEqual(len(await inspect(client, include_finished=True)), 2)

    async def test_repeated_pagination_cursor_fails_instead_of_looping(self):
        calls = []
        def serve(request):
            calls.append(request)
            return httpx.Response(200, json={'data': [{'id': 'batch_same', 'status': 'completed'}],
                                            'has_more': True, 'last_id': 'batch_same'})
        async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
            with self.assertRaisesRegex(ValueError, 'did not advance'):
                await inspect(client)
        self.assertEqual(len(calls), 2)

    async def test_explicit_id_reports_finished_job(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'id': 'batch_done', 'status': 'completed'}))
        async with JudgeClient('https://mock/v1', self.logger, transport=transport) as client:
            self.assertEqual((await inspect(client, ['batch_done']))[0]['status'], 'completed')

    async def test_cancel_only_selected_active_jobs(self):
        mutations = []
        def serve(request):
            identifier = request.url.path.split('/')[3]
            if request.method == 'POST':
                mutations.append(identifier)
                return httpx.Response(200, json={'id': identifier, 'status': 'cancelling'})
            status = {'batch_active': 'in_progress', 'batch_done': 'completed', 'batch_cancelling': 'cancelling'}[identifier]
            return httpx.Response(200, json={'id': identifier, 'status': status})
        async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
            jobs, errors = await cancel(client, ['batch_active', 'batch_done', 'batch_cancelling'])
            self.assertEqual(errors, 0)
            self.assertEqual(mutations, ['batch_active'])
            self.assertEqual([j['status'] for j in jobs], ['cancelling', 'completed', 'cancelling'])
            mutations.clear()
            await cancel(client, ['batch_active'], dry_run=True)
            self.assertEqual(mutations, [])

    async def test_cancel_timeout_does_not_repeat_mutation(self):
        mutations = []
        def serve(request):
            if request.method == 'POST':
                mutations.append(request)
                raise httpx.ReadTimeout('mock timeout', request=request)
            return httpx.Response(200, json={'id': 'batch_active', 'status': 'in_progress'})
        async with JudgeClient('https://mock/v1', self.logger, transport=httpx.MockTransport(serve)) as client:
            _, errors = await cancel(client, ['batch_active'])
            self.assertEqual(errors, 1)
            self.assertEqual(len(mutations), 1)

    def test_state_selection_and_invalid_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'state.json'
            path.write_text(json.dumps({'active_batch': {'id': 'batch_active'}, 'batches': []}))
            args = argparse.Namespace(batch_id=None, state_file=path)
            self.assertEqual(selected_ids(args, True), ['batch_active'])
            path.write_text(json.dumps({'active_batch': None, 'batches': [{'id': 'batch_latest'}]}))
            self.assertEqual(selected_ids(args), ['batch_latest'])
            with self.assertRaisesRegex(ValueError, 'no active'):
                selected_ids(args, True)
            args = argparse.Namespace(batch_id=['batch_a', 'batch_a'], state_file=None)
            self.assertEqual(selected_ids(args), ['batch_a'])
            args.batch_id = ['batch_a/../../other']
            with self.assertRaises(ValueError): selected_ids(args)


if __name__ == '__main__': unittest.main()
