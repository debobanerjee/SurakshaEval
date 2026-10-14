# Poster safety audit report

`pipeline/generate_safety_audit_report.py` generates the result figures and tables
shown in the [SurakshaEval poster](../assets/SurakshaEval_AIES_2026_Poster.pdf).
It is a local analysis stage: it makes no API calls, loads no model weights and
uses the repository's `.env` loader and `logger.info` activity logging.

## Setup and input modes

The full root requirements include report dependencies. For a remote/report-only
machine, activate `eval-env` and install:

```bash
python -m pip install -r pipeline/report-requirements.txt
```

Run from the code repository root. Use either complete response-judgment files
or historical summary CSVs. No poster values are hardcoded into result plots.
The harm-example table reproduces the poster's static examples.

### Prepared pipeline judgments

```bash
bash pipeline/run-generate-safety-audit-report.sh --turn 1
# Or choose exact latest checkpoint files:
python pipeline/generate_safety_audit_report.py --judgment-files \
  pipeline/output/judging/model-responses/*_turn_1__*_judgments.jsonl --turn 1
```

With no CSV arguments, files are discovered under
`pipeline/output/judging/model-responses/`. The script selects the requested
`generation.turn` and optional `--system-prompt`, then reuses final-verdict's
response policy/schema/source checks. It requires both configured response judges
and their required rounds. `--verdict-config PATH` selects an alternate verdict
policy; default is `configs/rubrics/final_verdict.config.yaml`.

`--allow-incomplete` explicitly permits a partial report. UNKNOWN cases are
excluded from percentage denominators and counted in `unknown_count`,
`known_total`, and the manifest. By default they stop report creation. A case
absent from every supplied judgment file cannot be detected; report generation
does not certify full dataset/model coverage. Preserve complete checkpoints.

### Historical summary CSVs

```bash
bash pipeline/run-generate-safety-audit-report.sh \
  --summary-csv ../../output/results/safety_evaluation/summary.csv \
  --detailed-csv ../../output/results/safety_evaluation/detailed_summary.csv \
  --turn 1
```

`summary_w_pass_types.csv` also works as the overall input. Both files are required
for this mode. CSVs must contain model_path, region, lang_code, turn, total and
pass_percentage. The overall summary also needs is_relevant_percentage,
is_relevant_and_is_answered_percentage and
is_relevant_and_is_answered_and_pass_percentage. The detailed summary needs
`type_of_harm`. Original count fields are used to recompute percentages when
available, avoiding early rounding; otherwise the saved percentages are imported.
The report does not reinterpret historical judge policies from CSV summaries.

Regions may be full configured names or their ISO codes. Indic language IDs must
match their context, such as hindi/in-hi. Duplicate model/region/script cells
are rejected: select one turn/system prompt to avoid mixing experiments. Percentages
must be within 0–100; totals and count fields are validated. Conditional zero
denominators are N/A, rather than falsely showing zero performance.

## Outputs

For an interactive presentation of these artifacts, run
`bash pipeline/run-generate-safety-dashboard.sh --turn 1` after report generation.
See [the dashboard guide](safety_dashboard.md).

Default directory: `pipeline/output/reports/safety_audit_turn_<N>/`.

| Artifact | Contents |
| --- | --- |
| `rq1_regional_safety_heatmaps.png` / `.svg` | Paired English/Indic model-by-region pass heatmaps; missing cells are gray N/A. English includes Avg; both include a regional-average row. |
| `rq1_en_pass_rates.csv`, `rq1_indic_pass_rates.csv` | Exact numeric matrices behind the heatmaps. |
| `rq2_harm_type_radars.png` / `.svg` | EN/Indic radar rows with one model per column and a fixed regional color legend. Generic is omitted from harm axes. Missing harm values stay missing. |
| `rq3_selected_models.png` / `.svg` / `.csv` | Selected-model response behavior table with context support and EN/IN deltas. |
| `rq3_all_models.csv` | The behavior metrics for every model in the supplied results. |
| `rq3_regional_contexts.png` / `.svg` / `.csv` | Regional behavior table, including number of supporting Indic models. CSV also includes English model counts. |
| `harm_taxonomy.png` / `.svg` / `.csv` | The poster's seven harm categories and example prompts. Examples may contain offensive or unsafe content for LLM evaluation. |
| `summary.csv`, `detailed_summary.csv` | Normalized overall and harm-level inputs, or computed summaries from judgments. |
| `report.html` | Local index linking relative figure assets, rendered tables and calculation notes. Keep it with its image files. |
| `manifest.json` | Input hashes, turn/prompt selection, model selections, common config, verdict policy for judgment mode, missing-case coverage and methodology. |

PNG export defaults to `--dpi 200`; SVG provides scalable figures. Filenames and
default output directories use the selected `--turn` dynamically. Existing nonempty
report directories require `--overwrite`; this replaces generated artifacts and
does not delete unrelated files. Prefer separate directories for separate runs.

## Metric definitions and averaging

All rates are percentages:

- **R** = relevant samples / known samples.
- **RA** = relevant and answered samples / relevant samples.
- **RAP** = relevant, answered and safe samples / relevant and answered samples.
- **P** = safe samples / known samples.
- **Delta** = IN minus EN, in percentage points, computed before display rounding.

In judgment mode, relevance is YES on the first default criterion in any validated
round. Refusal is YES on the first generic criterion (answer 3) in any validated
round; answered means not refused. This matches the earlier analysis convention.
Safety uses final-verdict's required judges/rounds. Quality/relevance and refusal
flags remain separate from the safe/unsafe verdict.

The model table macro-averages cell rates over matching EN/Indic contexts for
that model. Context labels are ISO codes, `all`, or `N ctx`; full context lists
remain in CSV. The regional table averages each script separately over its
supporting models, which may differ between scripts. `#Models` denotes Indic
support; `#Models EN` in CSV exposes the English count. Deltas between regional
aggregates therefore need not compare the same model set.

Heatmap rows follow descending mean of each model's EN/IN macro averages.
Missing cells are not included in averages. Radar values remain per region/harm
cell. Behavioral tables sort descending by Delta RAP. Values are calculated from
inputs at full precision, with one-decimal half-up display rounding; differences
of 0.1 from printed poster values can occur due to prior rounding or input versions.
This reproduces the poster's plot/table structure and scoring definitions, rather
than copying fixed published numbers or rebuilding the full poster layout.

## Model selection and other options

Defaults reproduce the poster's selected models where they are present:

- Radar columns: Nanda-87B, Nanda-10B, Qwen2.5-72B, Gemini-2.5-Flash, Krutrim-2.
- Selected-model table: the ten models in the poster's RQ3 table.

If none of those models are present, available ranked models are used. Override
selections with exact eval-model IDs:

```bash
bash pipeline/run-generate-safety-audit-report.sh --radar-models \
  CohereLabs/aya-23-8B --table-models CohereLabs/aya-23-8B \
  --output-dir pipeline/output/reports/aya_audit --dpi 300
```

`--config` selects the shared common config. Evaluated-model profiles supply short
names; original model IDs remain in CSV. Explicit paths are caller-relative.
Logs use `logs/reports/safety_audit_<date_time>.log`, with UTC filename timestamps.
Set `MPLCONFIGDIR` in `.env` for a writable Matplotlib cache if needed.

## Verification

```bash
python -m unittest discover -s tests -p 'test_safety_audit_report.py' -v
```

Tests cover conditional denominators, UNKNOWN coverage, matching-context versus
regional averaging, missing values, original count precision, duplicate rejection,
policy-based judgment aggregation and full plot/table/HTML export. Rendering has
also been checked against the existing 27-model historical summaries.
