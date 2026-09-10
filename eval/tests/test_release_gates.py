import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eval.datasets import validate_cases
from eval.judge import GroqJudge, FakeJudge
from eval.baselines._runner import map_claims, answer_from
from eval.score import SystemAnswer, load_coverage_labels, score_groundedness
from eval import score


class ReleaseGates(unittest.TestCase):
    def test_rejected_unreviewed_and_duplicate_cases(self):
        reviewed = {'query_id': 'a', 'validated_by': 'user', 'validation_verdict': 'valid'}
        validate_cases([reviewed])
        for rows in ([], [reviewed, reviewed], [{'query_id': 'a'}],
                     [dict(reviewed, validation_verdict='wrong')]):
            with self.assertRaises(ValueError):
                validate_cases(rows)
        validate_cases([{'query_id': 'a'}], exploratory=True)
        with self.assertRaises(ValueError):
            validate_cases([dict(reviewed, validation_verdict='wrong')], exploratory=True)

    def test_invalid_citation_stays_in_grounding_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text = 'carriers had increased cancer risk'
            (root / 'PMC1.xml').write_text(f'<article><body><p>{text}</p></body></article>')
            span = {'pmcid': 'PMC1', 'section': 'body', 'char_start': 0, 'char_end': len(text)}
            claims = map_claims([{'text': text, 'excerpt_index': 1},
                                 {'text': 'unsupported', 'excerpt_index': 99}], [(span, text)])
            answer = SystemAnswer.from_dict({'case_id': 'a', 'claims': claims})
            result = score_groundedness(answer, FakeJudge(), root)
            self.assertEqual(result.verdict, 'fail')
            self.assertIn('1/2', result.rationale)

    def test_json_boolean_is_not_truthiness(self):
        judge = object.__new__(GroqJudge)
        for value in ('false', 'true', 0, 1, None):
            judge._call = lambda prompt: {'supported': value}
            with self.assertRaises(ValueError):
                judge.grade_claim_groundedness('x', 'y')
            with self.assertRaises(ValueError):
                answer_from({'case_id': 'a'}, {'not_found': value}, [])
        judge._call = lambda prompt: {'supported': False}
        self.assertFalse(judge.grade_claim_groundedness('x', 'y'))

    def test_release_rejects_missing_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'cases.jsonl').write_text(json.dumps({'case_id': 'a', 'validated_by': 'user'})+'\n')
            (p / 'answers.jsonl').write_text('')
            with patch('eval.score.load_split', return_value={}), contextlib.redirect_stderr(io.StringIO()):
                result = score.main(['--cases', str(p/'cases.jsonl'), '--answers', str(p/'answers.jsonl')])
            self.assertEqual(result, 2)

    def test_coverage_labels_reference_real_claims(self):
        answer = SystemAnswer.from_dict({
            'case_id': 'a',
            'claims': [{'text': 'fact', 'cited_pmcid': 'PMC1', 'cited_section': 'body',
                        'cited_char_start': 0, 'cited_char_end': 4}],
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'coverage.jsonl'
            path.write_text(json.dumps({
                'case_id': 'a',
                'units': [{'text': 'fact', 'covered_by_claim': 1, 'critical': True}],
            }) + '\n')
            labels = load_coverage_labels(path, {'a': answer})
            self.assertEqual(labels['a'][0].covered_by_claim, 1)
            for bad in (0, 2, True, '1'):
                path.write_text(json.dumps({
                    'case_id': 'a',
                    'units': [{'text': 'fact', 'covered_by_claim': bad, 'critical': True}],
                }) + '\n')
                with self.assertRaises(ValueError):
                    load_coverage_labels(path, {'a': answer})

    def test_release_requires_coverage_and_accepts_complete_abstention_annotation(self):
        case = {
            'case_id': 'a', 'validated_by': 'user', 'validation_verdict': 'valid',
            'stratum': 'evidence', 'is_negative_case': True, 'query': 'absent?',
            'gold': {'direction': None, 'strength': None, 'has_disagreement': False,
                     'disagreement_note': '', 'expected_not_found': True},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'cases.jsonl').write_text(json.dumps(case) + '\n')
            (root / 'answers.jsonl').write_text(json.dumps({
                'case_id': 'a', 'not_found': True, 'answer_text': 'not found in this corpus',
                'claims': [],
            }) + '\n')
            (root / 'coverage.jsonl').write_text(json.dumps({
                'case_id': 'a', 'units': [],
            }) + '\n')
            base = ['--cases', str(root / 'cases.jsonl'),
                    '--answers', str(root / 'answers.jsonl')]
            with patch('eval.score.load_split', return_value={}), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(score.main(base), 2)
                self.assertEqual(score.main(base + [
                    '--coverage-labels', str(root / 'coverage.jsonl')]), 0)
