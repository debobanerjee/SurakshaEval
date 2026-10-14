"""Verify actual response rubrics, their order, thresholds and runner integration."""
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


class ResponseRubricTests(unittest.TestCase):
    def setUp(self):
        self.config = load_yaml(ROOT / 'configs/rubrics/model_response_judging_rubric.config.yaml')['model_response_evaluation']

    def test_all_harm_specific_rubrics_and_order(self):
        for harm in ['Generic', *self.config['rubric']['specific']]:
            with self.subTest(harm=harm):
                text, rubric = judging.build_rubric(self.config, 'responses', {'meta': {'type_of_harm': harm}})
                groups = [self.config['rubric']['default'], self.config['rubric']['generic']]
                if harm != 'Generic': groups.append(self.config['rubric']['specific'][harm])
                questions = [q for group in groups for q in group['questions']]
                labels = [v for group in groups for v in group['labels']]
                self.assertEqual(text, '\n'.join(f'{i}. {q}' for i, q in enumerate(questions, 1)))
                self.assertEqual(rubric['count'], len(questions))
                self.assertEqual(rubric['labels'], labels)
                answers = ['YES' if label else 'NO' for label in labels]
                self.assertFalse(judging.response_scores(answers, rubric)['harmful_overall'])
                answers[2] = 'NO'  # Non-refusal; only one generic mismatch.
                if harm != 'Generic':
                    answers[7] = 'NO' if answers[7] == 'YES' else 'YES'
                    self.assertTrue(judging.response_scores(answers, rubric)['harmful_specific'])
                    answers[2] = 'YES'
                    self.assertFalse(judging.response_scores(answers, rubric)['harmful_overall'])
        _, rubric = judging.build_rubric(self.config, 'responses', {'type_of_harm': 'Generic'})
        # Three generic mismatches including non-refusal meet threshold 3.
        answers = ['YES', 'YES', 'NO', 'NO', 'YES', 'YES', 'NO']
        self.assertTrue(judging.response_scores(answers, rubric)['harmful_generic'])
        with self.assertRaises(ValueError):
            judging.build_rubric(self.config, 'responses', {'type_of_harm': 'unknown'})

    def test_response_script_reads_generated_file_and_preserves_rounds(self):
        spec = importlib.util.spec_from_file_location('judge_responses_entry', ROOT / 'pipeline/judge-model-responses.py')
        entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
        class Client:
            def __init__(self, *args): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        async def run(client, tasks, role, config, model, sampling, *args):
            self.assertEqual(role, 'responses')
            self.assertEqual([t['round'] for t in tasks], [1, 2, 3])
            self.assertTrue(all(t['rubric']['count'] == 9 for t in tasks))
            self.assertIn('LLM: generated response', tasks[0]['messages'][1]['content'])
            self.assertNotIn('temperature', sampling) if 'gpt-5' in model else self.assertIn('temperature', sampling)
            return 0
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, PIPELINE_LOG_DIR=tmp):
            source = Path(tmp) / 'model_response.jsonl'
            source.write_text('{"index":0,"question":"Example?","output":"generated response","status":"SUCCESS","meta":{"type_of_harm":"Politically sensitive topics"}}\n')
            for profile in (ROOT / 'configs/inference/judge_models/model_response_evaluation').glob('*.yaml'):
                with patch.object(judging, 'JudgeClient', Client), patch.object(judging, 'run_tasks', run):
                    self.assertEqual(entry.main('responses', ['--judge-model', profile.name.removesuffix('_config.yaml'), '--input-file', str(source)]), 0)

    def test_model_selection_uses_turn_in_source_and_judgment_filename(self):
        class Client:
            def __init__(self, *args): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        row = {'index': 0, 'question': 'Example?', 'output': 'response', 'meta': {'type_of_harm': 'Generic'}}
        for turn in [1, 2]:
            async def run(client, tasks, role, config, model, sampling, output, *args):
                self.assertTrue(tasks[0]['source_file'].endswith(f'CohereLabs--aya-23-8B_turn_{turn}_response.jsonl'))
                self.assertEqual(output.name, f'CohereLabs--aya-23-8B_turn_{turn}__gpt-4.1-mini-2025-04-14_judgments.jsonl')
                return 0
            args = ['--model', 'CohereLabs/aya-23-8B']
            if turn == 2: args.extend(['--turn', '2'])
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, PIPELINE_LOG_DIR=tmp), \
                    patch.object(judging, 'JudgeClient', Client), patch.object(judging, 'read_rows', return_value=[row]), \
                    patch.object(judging, 'run_tasks', run):
                self.assertEqual(judging.main('responses', args), 0)


if __name__ == '__main__': unittest.main()
