"""Verify the question runner uses the checked-in safety rubric and judge profiles."""
import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
import judging
from pipeline_common import load_yaml


class QuestionRubricTests(unittest.TestCase):
    def test_exact_question_rubric_and_schema(self):
        config = load_yaml(ROOT / 'configs/rubrics/question_safety_judging_rubric.config.yaml')['safety_question_evaluation']
        text, rubric = judging.build_rubric(config, 'questions', {})
        self.assertEqual(text, config['rubric']['default'][0])
        self.assertEqual(rubric['count'], 8)
        self.assertEqual(rubric['labels'], [1] * 8)
        self.assertEqual(rubric['threshold'], 2)
        answers = [{'YES': 5}] * 8
        import json
        self.assertEqual(judging.parse_answers(json.dumps({'Answer': answers}), 'questions', 8), answers)

    def test_script_renders_configured_rubric_for_each_judge(self):
        script = ROOT / 'pipeline/judge-questions.py'
        spec = importlib.util.spec_from_file_location('judge_questions_entry', script)
        entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
        captured = []
        class Client:
            def __init__(self, *args): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        async def run(client, tasks, role, config, model, sampling, *args):
            self.assertEqual(role, 'questions')
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]['rubric']['count'], 8)
            self.assertIn(config['rubric']['default'][0], tasks[0]['messages'][1]['content'])
            self.assertEqual(tasks[0]['messages'][0]['content'], config['system_prompt']['default'])
            self.assertEqual(sampling.get('temperature'), None if 'gpt-5' in model else 0.6)
            captured.append(model)
            return 0
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, PIPELINE_LOG_DIR=tmp):
            source = Path(tmp) / 'data/filtered_and_updated/hindi/en_questions.jsonl'
            source.parent.mkdir(parents=True)
            source.write_text('{"index":0,"question":"Example?"}\n')
            for profile in (ROOT / 'configs/inference/judge_models/question_evaluation').glob('*.yaml'):
                model = profile.name.removesuffix('_config.yaml')
                with patch.object(judging, 'JudgeClient', Client), patch.object(judging, 'run_tasks', run):
                    self.assertEqual(entry.main('questions', ['--judge-model', model, '--input-dir', str(Path(tmp) / 'data'), '--regions', 'hindi']), 0)
        self.assertEqual(len(captured), 3)


if __name__ == '__main__': unittest.main()
