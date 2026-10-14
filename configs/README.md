# Evaluation configuration

[common.config.yaml](common.config.yaml) contains shared settings for the prepared evaluation
pipeline. Model profiles, judge profiles, rubrics, access settings and deployment
settings live in separate directories so a run can select just what it needs.
See [the repository README](../README.md) for setup and runnable examples.

## Shared config fields

| Field | Current value or structure | Role in the prepared pipeline |
| --- | --- | --- |
| `input_dir` | `data` | Default data root for generation and question judging, resolved against the code repository root. Dataset download also defaults to repo `data/`; use its `--output-dir` to select another destination. |
| `output_dir` | `output` | Retained shared research setting. Prepared generation/judging runners use their explicit `pipeline/output/...` defaults, rather than this field. Use their output CLI arguments to redirect results. |
| `regions` | Ten regional context names | Default regions to download or process. `--regions` selects a subset where supported. |
| `language_codes` | Region-to-language mapping | Identifies Indic question files, such as `hindi: in-hi`. English question files use `en`. |
| `risk_area2id` | Regional risk-area-to-ID mapping | Retained benchmark annotation mapping for analysis; current judging runners preserve source risk-area metadata. |
| `type_of_harm2id` | Harm-name-to-ID mapping | Benchmark category mapping, including Generic and seven specific harm types. Response judging selects its rubric using the source harm name. |
| `harm_shortform` | Harm-name-to-abbreviation mapping | Retained shorthand for analysis and reporting. |

Moving this file under `configs/` does not make data paths relative to this
directory. Generation and question judging still resolve default paths against
the repository root. Explicit CLI paths are relative to the calling directory.
The workspace's original research `config.yaml` is a separate file.

Generation turns are defined by `eval_models.<model_id>.n_turns` in each model
inference profile, with `1` for all configured models. The runner defaults to one
when the field is absent; `--turns` overrides the selected profile. Shared config
has no generation-turn or serving settings. Serving settings such as dtype, tensor
parallelism, sequence limits and GPU memory utilization are defined in the selected
per-model vLLM deployment YAML.

## Other configuration directories

| Directory | Contents and detail reference |
| --- | --- |
| `inference/eval_models/` | One evaluated-model profile per file: `n_turns: 1`, sampling, supported languages and system prompts. |
| `inference/judge_models/question_evaluation/` | The three question judges and their provider sampling settings. |
| `inference/judge_models/model_response_evaluation/` | The two response judges, sampling settings and evaluation rounds. |
| `rubrics/` | Question and response criteria plus final-verdict policy. See [the rubric README](rubrics/README.md) for all fields, schemas, thresholds and voting examples. |
| `custom_chat_templates/` | Five custom Indic templates. See [the template README](custom_chat_templates/README.md) for supported inputs and provenance. |
| `model-access/local/open-weight/vllm/` | Native per-model vLLM deployment YAMLs. See [deployment guidance](../SKILLS/deployment.md) and [the port mapping](../docs/vllm_ports.md). |
| `model-access/api/proprietary/google/` | Gemini API profiles. See [the context audit](../docs/context_length_audit.md) for the configured retired Gemini ID. |
| `model-access/api/open-weight/` | 23 profiles per provider, including verified mappings and disabled placeholders. See [the provider inventory](model-access/api/open-weight/README.md) and [the main README](../README.md#hosted-api-access-for-open-weight-models). |

Dataset download, generation and both judging scripts accept `--config PATH` for
an alternate shared config. In contrast, `run-deployment.sh --config` selects a
native deployment config, and `final-verdict.py --config` selects the final-verdict
policy. The latter does not replace the judging rubrics. Credentials always come
from environment variables, including automatically loaded repo-root `.env`,
rather than these YAML files. See [environment setup](../SKILLS/setup_environment.md).
