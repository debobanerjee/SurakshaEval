"""Inspect and explicitly cancel OpenAI Batch jobs using environment authentication."""
import argparse
import asyncio
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from judging import JudgeClient
from logging_utils import configure_logging
from pipeline_common import positive

ACTIVE = {'validating', 'in_progress', 'finalizing', 'cancelling'}
TERMINAL = {'completed', 'failed', 'expired', 'cancelled'}


def batch_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'batch_[A-Za-z0-9_-]+', value):
        raise ValueError('Expected an OpenAI batch ID beginning with batch_')
    return value


def selected_ids(args, cancelling=False):
    if args.batch_id:
        return list(dict.fromkeys(batch_id(value) for value in args.batch_id))
    if args.state_file:
        state = json.loads(args.state_file.read_text(encoding='utf-8'))
        active = state.get('active_batch')
        if active:
            return [batch_id(active['id'])]
        if not cancelling and state.get('batches'):
            return [batch_id(state['batches'][-1]['id'])]
        raise ValueError('State has no active Batch job; uncertain submissions require provider dashboard inspection')
    return []


def summary(job):
    return {key: job.get(key) for key in ('id', 'status', 'created_at', 'request_counts',
                                         'output_file_id', 'error_file_id')}


async def inspect(client, ids=None, include_finished=False, role=None, page_size=100):
    jobs = []
    if ids:
        for identifier in ids:
            jobs.append(await client.metadata(client.base_url + '/batches/' + batch_id(identifier)))
        return jobs
    after, cursors = None, set()
    while True:
        query = {'limit': page_size}
        if after:
            query['after'] = after
        page = await client.metadata(client.base_url + '/batches?' + urlencode(query))
        entries = page['data']
        for job in entries:
            if (include_finished or job['status'] in ACTIVE) and (not role or (job.get('metadata') or {}).get('role') == role):
                jobs.append(job)
        if not page.get('has_more'):
            break
        after = page.get('last_id') or (entries[-1]['id'] if entries else None)
        if not after or after in cursors:
            raise ValueError('Batch pagination did not advance')
        cursors.add(after)
    return jobs


async def cancel(client, ids, dry_run=False):
    jobs, failures = [], 0
    for identifier in ids:
        identifier = batch_id(identifier)
        try:
            job = await client.metadata(client.base_url + '/batches/' + identifier)
            if job['status'] in TERMINAL or job['status'] == 'cancelling':
                client.logger.info('Batch id=%s status=%s; no cancellation needed', identifier, job['status'])
            elif job['status'] not in ACTIVE:
                raise ValueError('Unrecognized batch status; no cancellation sent')
            elif dry_run:
                client.logger.info('Preview only: would cancel batch id=%s status=%s', identifier, job['status'])
            else:
                client.logger.info('Requesting cancellation for batch id=%s', identifier)
                # Do not blindly retry a mutation after a timeout. Inspect status
                # using the checking script before invoking cancellation again.
                job = await client.request(client.base_url + '/batches/' + identifier + '/cancel', {})
            jobs.append(job)
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            failures += 1
            client.logger.info('Cancellation failed/uncertain for batch id=%s: %s; inspect its status', identifier, exc)
    return jobs, failures


async def async_main(cancelling, argv=None):
    parser = argparse.ArgumentParser(description='Cancel specified OpenAI Batch jobs' if cancelling else 'Inspect OpenAI Batch jobs')
    selection = parser.add_mutually_exclusive_group(required=cancelling)
    selection.add_argument('--batch-id', nargs='+', help='One or more explicit OpenAI batch IDs')
    selection.add_argument('--state-file', type=Path, help='Saved judging .batch_state.json')
    parser.add_argument('--base-url', default='https://api.openai.com/v1')
    parser.add_argument('--timeout', type=positive, default=120)
    if cancelling:
        parser.add_argument('--dry-run', action='store_true', help='Retrieve job statuses but send no cancellation requests')
    else:
        parser.add_argument('--all', action='store_true', help='Include completed/failed/expired/cancelled jobs in listing')
        parser.add_argument('--role', choices=['questions', 'responses'], help='Filter list by SurakshaEval role metadata')
        parser.add_argument('--page-size', type=positive, default=100)
    args = parser.parse_args(argv)
    if not cancelling and args.page_size > 100:
        parser.error('--page-size must be between 1 and 100')
    logger = configure_logging('cancel-batch-jobs' if cancelling else 'check-batch-jobs')
    ids = selected_ids(args, cancelling)
    async with JudgeClient(args.base_url, logger, args.timeout) as client:
        if cancelling:
            jobs, failures = await cancel(client, ids, args.dry_run)
        else:
            jobs = await inspect(client, ids, args.all, args.role, args.page_size)
            failures = 0
        for job in jobs:
            logger.info('Batch id=%s status=%s counts=%s', job['id'], job['status'], job.get('request_counts'))
            print(json.dumps(summary(job), ensure_ascii=False))
    logger.info('Finished batch management; jobs=%d errors=%d', len(jobs), failures)
    return int(failures > 0)


def main(cancelling, argv=None):
    return asyncio.run(async_main(cancelling, argv))
