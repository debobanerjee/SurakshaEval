---
name: surakshaeval-judge-model-responses
description: Run responses judging using role-specific rubrics with async or OpenAI Batch requests.
---

# Judge evaluated-model responses

Create a Conda or uv environment and install [requirements](../README.md#setup).
Set OPENAI_API_KEY in the environment. Never pass secrets in arguments or store
them in configs/logs. Work from the repository root.

```bash
bash pipeline/run-judge-model-responses.sh --model CohereLabs/aya-23-8B
bash pipeline/run-judge-model-responses.sh --model CohereLabs/aya-23-8B --mode batch --batch-action submit
bash pipeline/run-judge-model-responses.sh --model CohereLabs/aya-23-8B --mode batch --batch-action collect --retry
```

Read the generated model aggregate from pipeline/output/respones/ via --model,
or select --input-file. Generation turn defaults to 1; --turn N with --model
selects another turn. Default judgment names are
`<model>_turn_<N>__<judge>_judgments.jsonl`, with judge rounds stored on rows.
Load the response judge/rubric profile and append default,
generic and harm-specific criteria in that order. Validate uppercase YES/NO strings
and the full answer count. Preserve refusal and mismatch-threshold scores. The
final-verdict stage requires two safe rounds per configured judge by default.

Shared paths/regions come from configs/common.config.yaml. Select --judge-model from
the corresponding role's profiles. String None sampling
values mean no override. Both modes share rubric rendering and validation.
--dry-run performs no API requests. Async concurrency defaults to 8. --rounds
overrides the role/profile round count; keep final-verdict expected rounds aligned.

Use --retry to skip matching SUCCESS, retry ERROR and process unprocessed samples.
At most five attempts per sample per run/cycle are permitted. Explicit retries
allow another cycle; collecting an active Batch retains its current budget.
Use `--batch-action collect-only --retry` to collect partial results without
submitting replacements after cancellation; see the Batch management guide.
Retain original inputs and .batch_state.json until collection finishes; custom_id
maps unordered results, including null-response error rows that are saved as
ERROR and retried. Exit 2 means pending. Missing/blocked responses and
invalid/failed judge outputs remain ERROR and cannot become safe verdicts.
Checkpoints keep one latest record per item and cumulative attempt counts.

Logs use `logs/judge/<judge>_eval_models_<model>_<date_time>.log`. Derive final verdicts only
once the required judges and rounds are present; missing evidence yields UNKNOWN.
See [rubrics and final verdicts](../docs/pipeline.md) and
[the final-verdict guide](final_verdict.md).

```bash
python -m unittest discover -s tests -p 'test_judge_model_responses.py' -v
python -m unittest discover -s tests -p 'test_judging.py' -v
```

Tests use mocked traffic. They do not perform paid judging calls.

## Environment and workflow references

Use [setup_environment.md](setup_environment.md) to create Conda eval-env and
install requirements. Repo-root .env is loaded automatically by Python and shell
entry points; exported variables take precedence. See [the environment template](../.env.example).
For dataset preparation use [download_data.md](download_data.md). For active
Batch inspection/cancellation and partial collection without resubmission use
[batch_management.md](batch_management.md).
