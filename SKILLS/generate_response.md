---
name: surakshaeval-generate-response
description: Generate vLLM or Gemini responses with bounded asyncio concurrency and status-aware retry.
---

# Generate model responses

Create a Conda or uv environment and install [requirements](../README.md#setup).
First run `bash pipeline/run-download-data.sh` with `HF_TOKEN` for an approved
account. It produces the regional source files consumed by this runner.

```bash
bash pipeline/run-generate-responses.sh --model CohereLabs/aya-23-8B \
  --base-url http://127.0.0.1:8804/v1 --regions hindi --languages en --turns 1
bash pipeline/run-generate-responses.sh --model gemini-2.5-flash
```

Read `VLLM_API_KEY` for local serving and `GEMINI_API_KEY` (fallback
`GOOGLE_API_KEY`) for Gemini from the environment. No credentials go in CLI flags,
YAML or logs. vLLM URLs end in `/v1`, Gemini URLs in `/v1beta`. Omit `--base-url`
to use the configured endpoint. `--served-model` selects a vLLM server alias.

`--dry-run` prepares the selection without API calls. `--input-dir` defaults to
repo `data/`; inputs are `filtered_and_updated/<region>/<language>_questions.jsonl`.
Shared settings come from `configs/common.config.yaml`; `--config PATH` selects another
shared configuration. Select profile-supported languages and preserve experiment
sampling/prompts.
Each evaluated-model inference profile contains `n_turns: 1`. Use one generation
turn per question/prompt for experiments; keep
`--turns 1` when passing the option explicitly. Judge scoring rounds are separate.
`--ablations` and `--system-prompt` select
configured prompts. Server-side Jinja formatting and token counting prevent double
formatting. Output caps leave room for prompts; prompts are never truncated.
Gemini retains default safety/thinking behavior and raw candidate/safety metadata.

Results default to `pipeline/output/respones/<model_name>_turn_<N>_response.jsonl` with `/`
replaced by `--` in model filenames. Each turn has a separate file; experiments
use turn 1. Preserve source annotations, region/language/
turn, returned reasoning/tool fields, usage and `SUCCESS`/`ERROR`; never execute
returned tools. Provider blocks are successful generation outcomes with block
metadata. Both backends use shared bounded asyncio concurrency (default 8).

Reuse the same command with `--retry`: skip matching SUCCESS, retry ERROR, and
continue unprocessed items. Keep configuration/selection stable and avoid
concurrent writers. The checkpoint replaces each retried row without duplicates. Turn filenames use
the actual turn index from the profile or --turns override, not a fixed suffix.
Generation has at least five retries (six attempts); a timeout raises the timeout
to 3000 seconds for that sample's subsequent attempts. Log activity under
`logs/model_response/<model>_<date_time>.log`.

See [the pipeline reference](../docs/pipeline.md). Run
`python -m unittest discover -s tests -p 'test_generate_responses.py' -v` for mocked
verification; do not claim live inference from these tests.

## Environment and workflow references

Use [setup_environment.md](setup_environment.md) to create Conda eval-env and
install requirements. Repo-root .env is loaded automatically by Python and shell
entry points; exported variables take precedence. See [the environment template](../.env.example).
For dataset preparation use [download_data.md](download_data.md). For active
Batch inspection/cancellation and partial collection without resubmission use
[batch_management.md](batch_management.md).

## Other provider profiles

[The Fireworks/OpenRouter inventory](../configs/model-access/api/open-weight/README.md)
contains one profile per open-weight eval model for each provider. Only verified
mappings have enabled=true and a model ID; disabled profiles must not be called.
These access configs do not add provider adapters to generate-responses.py.
Use the original inference profile for sampling and n_turns if integrating a
provider client, and preserve provider/deployment identity in experiment results.
