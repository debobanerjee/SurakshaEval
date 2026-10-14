---
name: surakshaeval-download-data
description: Download the gated SurakshaAI/SurakshaEval dataset and prepare question files consumed by the pipeline.
---

# Download SurakshaEval data

Create and activate [eval-env](setup_environment.md), then run from the code
repository root. Request access on the
[SurakshaAI/SurakshaEval dataset page](https://huggingface.co/datasets/SurakshaAI/SurakshaEval),
provide the required contact information and accept the access conditions.
Use HF_TOKEN belonging to the approved account in the repo-root .env or shell
environment. The downloader reads the variable automatically; no token CLI flag
is accepted and no credentials are saved in manifests.

```bash
bash pipeline/run-download-data.sh
# Optional subset and destination:
bash pipeline/run-download-data.sh --regions hindi assamese --output-dir data
# Select a published branch/tag/commit if needed:
bash pipeline/run-download-data.sh --revision main
```

Default source: SurakshaAI/SurakshaEval. Default destination: repo data/.
`--repo-id` changes the source, --revision is resolved to one commit, and
--regions selects unique regions from configs/common.config.yaml. All requested
regions are validated before writing files. The full release contains 1,484
English/Indic pairs (2,968 prompts); an English question and corresponding Indic
question share their pair ID in one regional context.

The downloader writes:

```text
data/filtered_and_updated/<region>/
├── en_questions.jsonl
├── in-<lang_code>_questions.jsonl
└── download_manifest.json
```

Question rows preserve text verbatim and contain index, pair_id, question,
language, and meta with risk_area, type_of_harm and question_type. The release's
omitted specific_harms and is_unsafe fields are not introduced. Each manifest
records the pinned commit, source path, counts and source/output hashes.
Generation and question judging consume this layout directly.

Existing files are protected. Use --overwrite only when replacing selected
regions deliberately. After selecting another destination, pass its parent data
root as --input-dir to generation and question judging. This script uses
--overwrite rather than the per-sample --retry option used by API runners.

```bash
bash pipeline/run-generate-responses.sh --model CohereLabs/aya-23-8B \
  --regions hindi --languages en --dry-run
```

Logs are stored as `logs/dataset/download_<date_time>.log`, with UTC filename
timestamps. Downloaded data and generated logs are Git-ignored. If access fails,
check account approval and HF_TOKEN; never paste a token into diagnostic output.
See [the pipeline reference](../docs/pipeline.md) for all options and outputs.

```bash
python -m unittest discover -s tests -p 'test_downloads.py' -v
```

Tests mock Hub downloads and do not access the gated dataset.
