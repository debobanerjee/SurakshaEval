---
name: surakshaeval-judge-questions
description: Run questions judging using role-specific rubrics with async or OpenAI Batch requests.
---

# Judge questions

Create a Conda or uv environment and install [requirements](../README.md#setup).
Set OPENAI_API_KEY in the environment. Never pass secrets in arguments or store
them in configs/logs. Work from the repository root.

```bash
bash pipeline/run-judge-questions.sh --regions hindi --language en
bash pipeline/run-judge-questions.sh --regions hindi --language en --mode batch --batch-action submit
bash pipeline/run-judge-questions.sh --regions hindi --language en --mode batch --batch-action collect --retry
```

Load the question rubric and question judge profile. Preserve all eight criteria
and validate YES/NO confidence objects (integer 1–5), in their configured order.
Judging retains raw answers; final-verdict.py applies the explicit confidence ≥4
and two-judge-vote policy from configs/rubrics/final_verdict.config.yaml.

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
maps unordered results. Exit 2 means pending. Invalid/failed judge outputs remain ERROR and cannot become safe verdicts.
The saved rubric includes exact question criteria text so changed wording cannot
reuse old answers in final-verdict.
Checkpoints keep one latest record per item and cumulative attempt counts.

Logs use `logs/judge/<judge>_questions_<date_time>.log`. Derive final verdicts only
once the required judges and rounds are present; missing evidence yields UNKNOWN.
See [rubrics and final verdicts](../docs/pipeline.md) and
[the final-verdict guide](final_verdict.md).

```bash
python -m unittest discover -s tests -p 'test_judge_questions.py' -v
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
