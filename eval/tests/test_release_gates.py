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
from eval.score import SystemAnswer, score_groundedness
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
