"""Mocked Hub downloads and log/wrapper checks; never download model weights."""
import importlib.util
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from logging_utils import configure_logging
from pipeline_common import read_rows


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / 'pipeline' / f'{name}.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        env = patch.dict(os.environ, HF_TOKEN='mock-hf-token', PIPELINE_LOG_DIR=str(self.path / 'logs'))
        env.start(); self.addCleanup(env.stop)

    def test_dataset_conversion_commit_hashes_and_protection(self):
        runner = load('download-data')
        source = self.path / 'pairs.jsonl'
        source.write_text(json.dumps({'id': 'hindi-0', 'index': 0, 'region': 'hindi', 'language': 'hi',
            'question_en': 'Example?', 'question_indic': 'उदाहरण?', 'risk_area': 'Hindi-specific',
            'type_of_harm': 'Generic', 'question_type': ''}, ensure_ascii=False) + '\n')
        with patch.object(runner, 'download_sources', return_value=('commit-123', {'hindi': source})) as download:
            args = ['--regions', 'hindi', '--output-dir', str(self.path / 'data')]
            self.assertEqual(runner.main(args), 0)
            self.assertEqual(download.call_args.args[3], 'mock-hf-token')
            directory = self.path / 'data/filtered_and_updated/hindi'
            english = read_rows(directory / 'en_questions.jsonl')[0]
            indic = read_rows(directory / 'in-hi_questions.jsonl')[0]
            self.assertEqual(english['pair_id'], indic['pair_id'])
            self.assertEqual(indic['question'], 'उदाहरण?')
            self.assertEqual(indic['meta']['question_type'], '')
            self.assertNotIn('is_unsafe', indic)
            manifest = json.loads((directory / 'download_manifest.json').read_text())
            self.assertEqual(manifest['revision'], 'commit-123')
            import hashlib
            self.assertEqual(manifest['outputs']['en_questions.jsonl'], hashlib.sha256((directory / 'en_questions.jsonl').read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError): runner.main(args)
            source.write_text('{"invalid":true}\n')
            with self.assertRaises(ValueError): runner.main(args + ['--overwrite'])
            self.assertEqual(read_rows(directory / 'en_questions.jsonl')[0], english)

    def test_checkpoint_pinning_env_auth_and_directory_identity(self):
        runner = load('download-checkpoint')
        calls = []
        hub = ModuleType('huggingface_hub')
        errors = ModuleType('huggingface_hub.errors')
        errors.HfHubHTTPError = type('HfHubHTTPError', (Exception,), {})
        class API:
            def __init__(self, token): self.token = token
            def model_info(self, model, revision):
                calls.append(('info', model, revision, self.token))
                return SimpleNamespace(sha='fixed-commit')
        def snapshot(**kwargs):
            calls.append(('snapshot', kwargs))
            manifest = json.loads((Path(kwargs['local_dir']) / runner.MANIFEST).read_text())
            self.assertEqual(manifest['commit'], 'fixed-commit')
            (Path(kwargs['local_dir']) / 'config.json').write_text('{}')
        hub.HfApi, hub.snapshot_download = API, snapshot
        destination = self.path / 'checkpoint with spaces'
        with patch.dict(sys.modules, {'huggingface_hub': hub, 'huggingface_hub.errors': errors}):
            self.assertEqual(runner.main(['org/model', str(destination)]), 0)
            self.assertEqual(calls[1][1]['revision'], 'fixed-commit')
            self.assertEqual(calls[1][1]['token'], 'mock-hf-token')
            self.assertEqual(runner.main(['org/model', str(destination)]), 0)
            self.assertEqual(calls[2][2], 'fixed-commit')
            with self.assertRaises(ValueError): runner.main(['other/model', str(destination)])
            other = self.path / 'occupied'; other.mkdir(); (other / 'file').write_text('existing')
            with self.assertRaises(ValueError): runner.main(['org/model', str(other)])

    def test_log_layout_and_no_credentials(self):
        cases = [('download-data', None, None, 'dataset/download_'),
                 ('generate-responses', 'org/model', None, 'model_response/org--model_'),
                 ('judge-questions', 'judge', None, 'judge/judge_questions_'),
                 ('judge-model-responses', 'judge', 'org/model', 'judge/judge_eval_models_org--model_'),
                 ('deployment', 'org/model', None, 'deployment/org--model_'),
                 ('download-checkpoint', 'org/model', None, 'checkpoints/org--model_')]
        for task, model, evaluated, prefix in cases:
            logger = configure_logging(task, model, evaluated)
            logger.info('Mock activity completed')
            handler = next(h for h in logger.handlers if isinstance(h, logging.FileHandler))
            path = Path(handler.baseFilename)
            self.assertTrue(str(path.relative_to(self.path / 'logs')).startswith(prefix))
            self.assertNotIn('mock-hf-token', path.read_text())

    def test_wrappers_help_and_shell_syntax(self):
        for path in sorted((ROOT / 'pipeline').glob('*.sh')):
            subprocess.run(['bash', '-n', str(path)], check=True)
            if path.name == 'run-deployment.sh': continue
            result = subprocess.run(['bash', str(path), '--help'], env={**os.environ, 'PYTHON_BIN': sys.executable},
                capture_output=True, text=True, check=True)
            self.assertIn('usage:', result.stdout)
            self.assertNotIn('--resume', result.stdout)
            if any(name in path.name for name in ('generate-responses', 'judge-questions', 'judge-model-responses')):
                self.assertIn('--retry', result.stdout)


if __name__ == '__main__': unittest.main()
