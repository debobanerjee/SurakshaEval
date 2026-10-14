"""Deterministic verdict policies: three question judges, two response judges."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pipeline'))
from judging import build_rubric
from pipeline_common import load_yaml
spec = importlib.util.spec_from_file_location('final_verdict', ROOT / 'pipeline/final-verdict.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


class VerdictTests(unittest.TestCase):
    def rows(self, role):
        self.policy = load_yaml(ROOT / 'configs/rubrics/final_verdict.config.yaml')[role]
        name = 'question_safety_judging_rubric' if role == 'questions' else 'model_response_judging_rubric'
        section = 'safety_question_evaluation' if role == 'questions' else 'model_response_evaluation'
        self.config = load_yaml(ROOT / 'configs/rubrics' / f'{name}.config.yaml')[section]
        _, rubric = build_rubric(self.config, role, {'meta': {'type_of_harm': 'Politically sensitive topics'}})
        answers = [{'YES': 5}] * 8 if role == 'questions' else ['YES' if l else 'NO' for l in rubric['labels']]
        return [{'question': 'example', 'output': 'response', 'meta': {'type_of_harm': 'Politically sensitive topics'},
            'status': 'SUCCESS', 'judging': {'role': role, 'judge_model': judge, 'judge_round': round_no,
                'source_file': 'source', 'source_row': 0, 'status': 'SUCCESS', 'rubric': rubric,
                'answers': copy.deepcopy(answers)}}
            for judge in self.policy['judges'] for round_no in range(1, self.policy['rounds'] + 1)]

    def evaluate(self, rows, role):
        return runner.verdicts(rows, role, self.policy, self.config)[0]['final_verdict']['verdict']

    def test_three_question_judges_confidence_and_votes(self):
        rows = self.rows('questions')
        self.assertEqual(len(rows), 3)
        self.assertEqual(self.evaluate(rows, 'questions'), 'UNSAFE')
        rows[0]['judging']['answers'][0] = {'YES': 4}
        rows[1]['judging']['answers'][0] = {'NO': 5}
        self.assertEqual(self.evaluate(rows, 'questions'), 'UNSAFE')
        rows[0]['judging']['answers'][0] = {'YES': 3}
        self.assertEqual(self.evaluate(rows, 'questions'), 'SAFE')
        self.assertEqual(self.evaluate(rows[:-1], 'questions'), 'UNKNOWN')
        rows[2]['judging']['status'] = 'ERROR'
        self.assertEqual(self.evaluate(rows, 'questions'), 'UNKNOWN')

    def test_two_response_judges_safe_rounds_and_error(self):
        rows = self.rows('responses')
        self.assertEqual(len(rows), 6)
        self.assertEqual(self.evaluate(rows, 'responses'), 'SAFE')
        rows[0]['judging']['answers'][2] = 'NO'  # No refusal.
        rows[0]['judging']['answers'][7] = 'NO'  # Harm-specific mismatch.
        self.assertEqual(self.evaluate(rows, 'responses'), 'SAFE')
        rows[1]['judging']['answers'] = list(rows[0]['judging']['answers'])
        self.assertEqual(self.evaluate(rows, 'responses'), 'UNSAFE')
        rows[1]['judging']['status'] = 'ERROR'
        self.assertEqual(self.evaluate(rows, 'responses'), 'UNKNOWN')

    def test_changed_question_rubric_text_is_unknown(self):
        rows = self.rows('questions')
        self.config['rubric']['default'][0] += '\nChanged criterion wording.'
        self.assertEqual(self.evaluate(rows, 'questions'), 'UNKNOWN')

    def test_conflicting_sources_and_duplicates(self):
        rows = self.rows('questions')
        rows[0]['question'] = 'changed'
        self.assertEqual(self.evaluate(rows, 'questions'), 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.evaluate(rows + [rows[0]], 'questions')


if __name__ == '__main__': unittest.main()
