# Safety audit dashboard

`pipeline/generate_safety_dashboard.py` turns an existing safety audit directory
into a polished, self-contained HTML dashboard. Generate the audit first using
[the report script](safety_audit_report.md). No API calls or new inference are made.

From the code repository root, with your environment activated:

```bash
bash pipeline/run-generate-safety-dashboard.sh --turn 1
# Select a custom audit directory and destination:
python pipeline/generate_safety_dashboard.py \
  --report-dir pipeline/output/reports/safety_audit_turn_1 \
  --output-file pipeline/output/reports/safety_dashboard.html
```

Open `pipeline/output/reports/safety_audit_turn_1/dashboard.html` directly in a
browser. Figures, data and CSV downloads are embedded; you can share just that
HTML file. It uses no external JavaScript, fonts, or web services. The dataset
link is optional external navigation. JavaScript must be enabled for the interface.

The dashboard provides:

- Responsive layout, section navigation, and light/dark themes.
- Counts of models, represented contexts, experiment turn, and unknown cases.
- Original poster heatmaps, radars, and behavior figures with expandable previews
  and PNG downloads.
- Searchable pass-rate tables with English/Indic and regional-context selectors.
- Searchable, sortable all-model behavior tables with metric selection and CSV downloads.
- Regional behavior, harm taxonomy, coverage notes and calculation methodology.

Plot images reflect the complete report; table filters do not regenerate them.
N/A remains missing, rather than zero. Deltas are Indic minus English in
percentage points. Tables display one decimal place; CSV downloads preserve the
original exports. The dashboard does not calculate an overall leaderboard score.
Read model context support and the methodology before comparing rates.

The input must contain `manifest.json`, all eight CSVs, and the five PNGs produced
by the audit script. `--turn N` selects the default source directory only; the
displayed turn always comes from the manifest. `--report-dir PATH` selects another
source, `--output-file PATH` changes the destination, and `--title TEXT` changes
the browser title. Existing output requires `--overwrite`; source artifacts are
protected even with that flag. Embedded data can make the HTML several megabytes.

The shared `.env` loader is applied. Activities use `logger.info` and are logged
to `logs/reports/safety_dashboard_<date_time>.log`, with UTC filename timestamps.
No new Python packages are needed beyond the lightweight pipeline requirements.
