---
name: surakshaeval-safety-dashboard
description: Generate a self-contained interactive SurakshaEval dashboard from existing safety audit plots, CSV tables and manifest metadata.
---

# Generate the safety audit dashboard

Use [generate_safety_dashboard.py](../pipeline/generate_safety_dashboard.py) and
[its launcher](../pipeline/run-generate-safety-dashboard.sh) to build an offline
HTML dashboard. Run commands from the code repository root,
`github_repo_prep/SurakshaEval/` in the preparation workspace.

## Prepare the inputs

Activate `eval-env` following [environment setup](setup_environment.md). The
dashboard uses the lightweight `pipeline/requirements.txt` dependencies and the
shared repository-root `.env` loader. No API key is needed for generation.

Select an existing audit directory containing `manifest.json`, all eight CSVs
and five PNG figures produced by the
[plots and tables workflow](safety_audit_report.md). If artifacts are missing,
generate that report using the intended inputs and experiment turn before building
the dashboard. Dashboard generation itself makes no API calls or model inference.

## Generate the dashboard

For the default audit directory:

```bash
turn=1
bash pipeline/run-generate-safety-dashboard.sh --turn "$turn"
```

Input: `pipeline/output/reports/safety_audit_turn_<N>/`.
Output: `pipeline/output/reports/safety_audit_turn_<N>/dashboard.html`.

For a custom report directory and destination:

```bash
python pipeline/generate_safety_dashboard.py \
  --report-dir pipeline/output/reports/aya_audit \
  --output-file pipeline/output/reports/aya_dashboard.html \
  --title "SurakshaEval · Aya safety audit"
```

`--turn` selects the default input directory; it does not change the experiment
data. The displayed turn comes from the manifest. Explicit paths are relative to
the working directory. `--title` changes the browser tab title.

When refreshing an existing dashboard, use the same command with `--overwrite`.
Audit source artifacts remain protected from being used as the output filename.
The generator embeds plots and table data, so the HTML may be several megabytes.

## Verify the result

Open the generated HTML directly in a browser with JavaScript enabled. Verify:

- Navigation between overview, regional safety, harm analysis, response behavior,
  and methodology; light/dark theme and narrow-screen layout.
- Model searches, English/Indic selection, regional-context filters, metric
  selection and numeric column sorting.
- Expanded figure previews, PNG downloads and full CSV downloads.
- Model/context counts, experiment turn, unknown-case coverage and methodology
  against the audit inputs.

Filters affect tables; the embedded plots retain the complete audit results.
Preserve N/A values, conditional metric definitions and coverage notes. Deltas
are Indic minus English in percentage points. Displayed table values use one
decimal; downloaded CSVs retain the original exported precision.

If changing dashboard code, run:

```bash
python -m unittest discover -s tests -p 'test_safety_dashboard.py' -v
```

## Troubleshooting and handoff

Read `logs/reports/safety_dashboard_<date_time>.log` for generation failures;
filename timestamps are UTC. Missing artifacts require a complete report export.
Invalid PNG/CSV/manifest inputs require corrected or regenerated report artifacts.
Existing output requires another destination or `--overwrite`.

Share the generated HTML file on its own: it embeds figures, tables and downloads,
and requires no server or external scripts/fonts. Report the output path and any
coverage limitations. If browser inspection is unavailable, state that visual and
interaction checks were not performed. Publishing or uploading is a separate task.
See [the dashboard reference](../docs/safety_dashboard.md) for full options.
