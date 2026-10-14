"""Offline dashboard portability, escaping and input/output safeguards."""
import base64
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
import generate_safety_dashboard as dashboard


class DashboardTests(unittest.TestCase):
    def fixture(self, directory):
        manifest = {'models': ['model'], 'turn': 3, 'unknown_samples': 1,
                    'methodology': '</script><script>alert(1)</script>',
                    'config': {'regions': ['hindi']}}
        (directory / 'manifest.json').write_text(json.dumps(manifest))
        for name in dashboard.TABLES:
            (directory / f'{name}.csv').write_text('model_path,hindi,Avg\nmodel,,NaN\n')
        for name in dashboard.FIGURES:
            (directory / f'{name}.png').write_bytes(base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aY9kAAAAASUVORK5CYII='))

    def test_portable_payload_escaping_and_missing_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.fixture(directory)
            result = dashboard.build_dashboard(directory, '<Audit>')
            self.assertIn('<title>&lt;Audit&gt;</title>', result)
            match = re.search(r'<script id="audit-data" type="application/json">(.*?)</script>', result, re.S)
            self.assertNotIn('</script>', match[1])
            payload = json.loads(match[1])
            self.assertEqual(payload['metadata']['turn'], 3)
            self.assertIsNone(payload['tables']['rq1_en_pass_rates']['rows'][0]['hindi'])
            self.assertIsNone(payload['tables']['rq1_en_pass_rates']['rows'][0]['Avg'])
            self.assertEqual(base64.b64decode(payload['downloads']['summary']), (directory/'summary.csv').read_bytes())
            self.assertTrue(all(v.startswith('data:image/png;base64,') for v in payload['figures'].values()))
            self.assertNotRegex(result, r'<(?:script|link|img)[^>]+(?:src|href)="https?://')

    def test_generation_overwrite_and_input_protection(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'PIPELINE_LOG_DIR': tmp}):
            directory = Path(tmp)
            self.fixture(directory)
            args = ['--report-dir', tmp]
            self.assertEqual(dashboard.main(args), 0)
            self.assertTrue((directory / 'dashboard.html').is_file())
            with self.assertRaises(FileExistsError):
                dashboard.main(args)
            self.assertEqual(dashboard.main(args + ['--overwrite']), 0)
            with self.assertRaises(ValueError):
                dashboard.main(args + ['--output-file', str(directory / 'summary.csv'), '--overwrite'])

    def test_missing_or_invalid_artifact_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.fixture(directory)
            (directory / 'rq2_harm_type_radars.png').write_bytes(b'not a PNG')
            with self.assertRaisesRegex(ValueError, 'PNG'):
                dashboard.build_dashboard(directory)
            (directory / 'summary.csv').unlink()
            with self.assertRaises(FileNotFoundError):
                dashboard.build_dashboard(directory)


if __name__ == '__main__':
    unittest.main()
