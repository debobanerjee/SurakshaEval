---
name: surakshaeval-safety-audit-report
description: Generate SurakshaEval poster plots and tables from response judgments or summary CSVs using the safety audit report pipeline.
---

# Generate the poster plots and tables

Use this workflow to produce the SurakshaEval poster's regional safety heatmaps,
harm-category radars, response-behavior tables and harm-taxonomy table. Run commands
from the root of the code repository, `github_repo_prep/SurakshaEval/` in the
preparation workspace. Use the existing
[report generator](../pipeline/generate_safety_audit_report.py) and
[shell launcher](../pipeline/run-generate-safety-audit-report.sh).

## Prepare the environment and choose inputs

Activate `eval-env` following [environment setup](setup_environment.md). If the
full requirements are already installed, no additional setup is needed. For a
report-only environment:

```bash
conda activate eval-env
python -m pip install -r pipeline/report-requirements.txt
```

The repository-root `.env` is loaded; plotting requires no API key. Select one
experiment turn and, when inputs contain multiple prompt variants, select one
with `--system-prompt`. Choose either response-judge checkpoints or historical
summary CSVs; these input modes are mutually exclusive.

### Response-judge checkpoints

With no input paths, the generator discovers files under
`pipeline/output/judging/model-responses/`:

```bash
turn=1
bash pipeline/run-generate-safety-audit-report.sh --turn "$turn"
```

To restrict the report to specific model checkpoints:

```bash
turn=1
python pipeline/generate_safety_audit_report.py --turn "$turn" \
  --judgment-files pipeline/output/judging/model-responses/CohereLabs--aya-23-8B_turn_${turn}__*_judgments.jsonl
```

Use the latest checkpoint files. This mode reuses the response policy from
`configs/rubrics/final_verdict.config.yaml`, requiring its configured judges and
rounds. `--verdict-config PATH` selects an alternate policy. It aggregates existing
judgments locally; it does not submit new judging requests.

### Historical summary CSVs

Provide both the overall and harm-level summaries. From the preparation workspace's
code repo, the existing research results are located two directories above:

```bash
turn=1
bash pipeline/run-generate-safety-audit-report.sh --turn "$turn" \
  --summary-csv ../../output/results/safety_evaluation/summary.csv \
  --detailed-csv ../../output/results/safety_evaluation/detailed_summary.csv
```

For a standalone clone, supply your own CSV paths. `summary_w_pass_types.csv` also
works as the overall input. CSV mode uses the historical scoring results and
recomputes rates from original counts when available. Consult
[the report reference](../docs/safety_audit_report.md) for required CSV fields.

## Preserve scoring and coverage

- Keep **R = relevant / known**, **RA = answered / relevant**,
  **RAP = safe / relevant answered**, and **P = safe / known**. These are percentages;
  delta is Indic minus English in percentage points.
- Model behavior averages compare matching English/Indic contexts. Regional
  behavior averages use supporting models separately for each script.
- Keep missing cells and zero conditional denominators as N/A. Default judgment
  mode rejects UNKNOWN; use `--allow-incomplete` only for an explicitly partial
  report and retain its unknown-case counts. Samples missing from every input
  cannot be detected by this analysis.
- Keep one turn/prompt variant per report. Duplicate summary cells or conflicting
  source identities need corrected inputs before rerunning.

## Select models and export figures

Defaults select the poster's radar/table models where available. Use exact
evaluated-model IDs for custom selections; for example:

```bash
turn=1
bash pipeline/run-generate-safety-audit-report.sh --turn "$turn" \
  --radar-models CohereLabs/aya-23-8B \
  --table-models CohereLabs/aya-23-8B \
  --output-dir pipeline/output/reports/aya_audit --dpi 300
```

Use the same CSV arguments with these selection options when using historical
results. Default output is `pipeline/output/reports/safety_audit_turn_<N>/`;
`--output-dir PATH` changes it. Existing nonempty output requires `--overwrite`.
The default PNG resolution is 200 DPI; SVG provides scalable figures.

| Output | Contents |
| --- | --- |
| `rq1_regional_safety_heatmaps.png` / `.svg` | Paired English/Indic regional pass-rate heatmaps |
| `rq2_harm_type_radars.png` / `.svg` | Seven specific harm categories, by model and regional context |
| `rq3_selected_models.png` / `.svg` / `.csv` | Selected-model response behavior and deltas |
| `rq3_regional_contexts.png` / `.svg` / `.csv` | Regional response behavior and model coverage |
| `harm_taxonomy.png` / `.svg` / `.csv` | Poster harm categories and example prompts |
| `rq1_en_pass_rates.csv`, `rq1_indic_pass_rates.csv` | Heatmap matrices |
| `rq3_all_models.csv` | Behavior metrics for every included model |
| `summary.csv`, `detailed_summary.csv` | Normalized report inputs |
| `report.html`, `manifest.json` | Figure index, calculation notes, input hashes and policy metadata |

## Check results and hand off

Open `report.html` alongside its image files. Inspect labels, legends, layout,
English/Indic colors and model/context coverage. Compare table metrics with the
source CSVs and check turn/prompt selection and unknown-case counts in
`manifest.json`. Values are calculated from inputs; small differences from the
printed poster may reflect input versions or historical rounding.

If changing report code, run its focused tests:

```bash
python -m unittest discover -s tests -p 'test_safety_audit_report.py' -v
```

Activities are logged to `logs/reports/safety_audit_<date_time>.log`, using UTC
filename timestamps. For Matplotlib cache permission failures, set `MPLCONFIGDIR`
to a writable directory in `.env`. For missing inputs or invalid CSVs, correct
the paths/schema; for UNKNOWN judgments, complete the required judging evidence
or explicitly generate a partial report.

If a dashboard is requested, use [the dashboard workflow](safety_dashboard.md)
after generating the plots and tables:

```bash
turn=1
bash pipeline/run-generate-safety-dashboard.sh --turn "$turn"
```

For a custom report directory, pass that directory using `--report-dir PATH`.
Report the output location and any remaining coverage limitations to the user.
