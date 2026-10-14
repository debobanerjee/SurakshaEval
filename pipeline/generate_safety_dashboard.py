#!/usr/bin/env python
"""Build a portable, offline dashboard from generated safety audit artifacts."""
import argparse
import base64
import csv
import html
import json
import logging
import math
from pathlib import Path
import sys

from environment import load_environment
from logging_utils import configure_logging

load_environment()
ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger('safety-dashboard')
TABLES = ('rq1_en_pass_rates', 'rq1_indic_pass_rates', 'rq3_all_models',
          'rq3_selected_models', 'rq3_regional_contexts', 'harm_taxonomy', 'summary', 'detailed_summary')
FIGURES = ('rq1_regional_safety_heatmaps', 'rq2_harm_type_radars',
           'rq3_selected_models', 'rq3_regional_contexts', 'harm_taxonomy')


def read_table(path):
    """Keep identifiers as strings and numeric missing values as JSON null."""
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        if not columns or len(columns) != len(set(columns)):
            raise ValueError(f'Invalid CSV header: {path.name}')
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'Malformed CSV row: {path.name}')
            converted = {}
            for key, value in row.items():
                if key in {'model_path', 'region', 'contexts', 'lang_code', 'script',
                           'type_of_harm', 'system_prompt', 'Harm type', 'Example safety prompt'}:
                    converted[key] = value
                    continue
                try:
                    number = float(value)
                    converted[key] = number if math.isfinite(number) else None
                except ValueError:
                    converted[key] = None if value.strip().lower() in {'', 'n/a', 'nan'} else value
            rows.append(converted)
    return {'columns': columns, 'rows': rows}


def build_dashboard(report_dir, title='SurakshaEval · Safety audit'):
    manifest = json.loads((report_dir / 'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or not isinstance(manifest.get('models'), list):
        raise ValueError('Invalid audit manifest: expected models list')
    tables, downloads, figures = {}, {}, {}
    for name in TABLES:
        path = report_dir / f'{name}.csv'
        LOG.info('Loading table %s', path.name)
        tables[name] = read_table(path)
        downloads[name] = base64.b64encode(path.read_bytes()).decode('ascii')
    for name in FIGURES:
        path = report_dir / f'{name}.png'
        LOG.info('Embedding plot %s', path.name)
        raw = path.read_bytes()
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError(f'Expected PNG image: {path.name}')
        figures[name] = 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')
    config = manifest.get('config', {})
    regions = config.get('regions') or [c for c in tables['rq1_en_pass_rates']['columns'] if c not in {'model_path', 'Avg'}]
    metadata = {key: manifest.get(key) for key in ('created_at', 'input_mode', 'turn',
                'system_prompt', 'unknown_samples', 'allow_incomplete', 'methodology', 'models')}
    payload = {'metadata': metadata, 'regions': regions, 'tables': tables,
               'downloads': downloads, 'figures': figures}
    # A data script must not permit HTML closing tags from model names or prompts.
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (Path(__file__).parent / 'templates/safety_dashboard.html').read_text(encoding='utf-8')
    return template.replace('__DASHBOARD_TITLE__', html.escape(title)).replace('__DASHBOARD_DATA__', encoded)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-dir', type=Path, help='Audit directory containing manifest.json, CSVs and PNGs')
    parser.add_argument('--turn', type=int, default=1, help='Select default audit directory (default: 1)')
    parser.add_argument('--output-file', type=Path, help='Default: <report-dir>/dashboard.html')
    parser.add_argument('--title', default='SurakshaEval · Safety audit')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args(argv)
    if args.turn < 1:
        parser.error('--turn must be positive')
    configure_logging('safety-dashboard')
    directory = args.report_dir or ROOT / 'pipeline/output/reports' / f'safety_audit_turn_{args.turn}'
    output = args.output_file or directory / 'dashboard.html'
    if output.exists() and not args.overwrite:
        raise FileExistsError(f'{output} exists; use --overwrite')
    # Avoid overwriting any input artifact, even when --overwrite is supplied.
    if output.resolve() in {(directory / name).resolve() for name in
                            ['manifest.json', 'report.html'] + [f'{n}.csv' for n in TABLES] +
                            [f'{n}.{suffix}' for n in FIGURES for suffix in ('png', 'svg')]}:
        raise ValueError('Dashboard output must not overwrite audit input artifacts')
    LOG.info('Building dashboard from %s', directory)
    content = build_dashboard(directory, args.title)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
    LOG.info('Dashboard ready: %s (%.2f MB); open directly in a browser', output, output.stat().st_size / 1e6)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        LOG.error('%s', exc)
        sys.exit(1)
