---
name: surakshaeval-batch-management
description: Inspect running OpenAI Batch jobs and cancel explicitly selected jobs while preserving local judging state.
---

# Check and cancel Batch jobs

Activate [eval-env](setup_environment.md). Put OPENAI_API_KEY in the repo-root
.env or exported environment. Scripts inherit the key without credential flags.
Use the same account/project that created the judging batch.

```bash
# List active jobs, following all pages; optionally select the evaluation role.
bash pipeline/run-check-batch-jobs.sh
bash pipeline/run-check-batch-jobs.sh --role responses
# Inspect specific jobs or the job tracked by a judging state file.
bash pipeline/run-check-batch-jobs.sh --batch-id batch_YOUR_ID
bash pipeline/run-check-batch-jobs.sh --state-file path/to/judgments.batch_state.json
# Include completed/failed/expired/cancelled jobs in account-wide listing.
bash pipeline/run-check-batch-jobs.sh --all
```

The default listing includes validating, in_progress, finalizing and cancelling.
It lists accessible jobs, including unrelated jobs unless --role filters them.
Explicit IDs show their status even when finished; a state file selects its active
job or most recent submitted job for inspection. Output is one JSON summary per
job on stdout; logger.info activity goes to stderr and
`logs/judge/check_batch_jobs_<date_time>.log`. --page-size is 1–100 (default 100).

```bash
# Preview retrieves status but sends no cancel request.
bash pipeline/run-cancel-batch-jobs.sh --batch-id batch_YOUR_ID --dry-run
# Cancel exactly the selected job(s).
bash pipeline/run-cancel-batch-jobs.sh --batch-id batch_YOUR_ID
bash pipeline/run-cancel-batch-jobs.sh --state-file path/to/judgments.batch_state.json
```

Cancellation requires explicit --batch-id or --state-file. There is no automatic
cancel-all operation. Finished jobs and jobs already cancelling are left alone.
A state-based cancellation requires an active job; uncertain submissions without
an ID must be resolved through the provider dashboard. Cancellation logs use
`logs/judge/cancel_batch_jobs_<date_time>.log`. Failed/uncertain requests return exit
1; inspect status before attempting another cancellation after a timeout.

Stop any local `--batch-action run` poller before cancelling, so it cannot
resubmit remaining work. Ctrl+C stops local polling; the remote job keeps running
until cancelled. Cancellation can take up to 10 minutes, with status cancelling,
and may leave partial results. See the official
[Batch cancellation reference](https://developers.openai.com/api/reference/resources/batches/methods/cancel).
Do not delete request files or .batch_state.json before collecting partial results.
The management scripts do not modify judging checkpoints or state.

To collect completed items **without submitting another batch**, use the original
judge selection/settings with --batch-action collect-only:

```bash
bash pipeline/run-judge-model-responses.sh --model CohereLabs/aya-23-8B \
  --mode batch --batch-action collect-only --retry
# Question judging supports the same collect-only action.
```

Exit 2 means the job is still pending/cancelling; rerun collection later. Exit 1
means ERROR/unprocessed judgments remain; those are not safe verdicts. Normal
collect or run actions can resubmit failed/unprocessed items, so use them only
when intentionally restarting work. Preserve attempt budgets and original inputs
while a job is active. See [the pipeline reference](../docs/pipeline.md#openai-batch)
and [OpenAI listing reference](https://developers.openai.com/api/reference/resources/batches/methods/list).
