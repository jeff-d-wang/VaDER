"""
The shared baseline scaffolding (eval/baselines/_runner.py). Two things are
worth a check here and neither had one before:

  - map_claims resolves a model's excerpt number back to a real source span,
    and drops a citation to an excerpt that does not exist. That is the only
    thing standing between a model hallucinating an offset and a gold-span
    citation, and it is the code path every groundedness number depends on.
  - bm25_only and oracle_spans must use the SAME prompt. Their whole reason
    to exist is that context is the only variable between them. This used to
    be two copies and a comment asking nicely.
"""
from __future__ import annotations

import unittest

from eval.baselines import bm25_only, no_retrieval, oracle_spans
from eval.baselines._runner import (EXCERPT_PROMPT, answer_from, format_excerpts,
                                    map_claims)

SPAN_A = {"pmcid": "PMC1", "section": "body", "char_start": 10, "char_end": 40}
SPAN_B = {"pmcid": "PMC2", "section": "abstract", "char_start": 0, "char_end": 25}
EXCERPTS = [(SPAN_A, "First excerpt text."), (SPAN_B, "Second excerpt text.")]


class TestPromptIsShared(unittest.TestCase):
    def test_the_two_excerpt_baselines_use_one_prompt(self):
        self.assertIs(bm25_only.EXCERPT_PROMPT, oracle_spans.EXCERPT_PROMPT)
        self.assertIs(bm25_only.EXCERPT_PROMPT, EXCERPT_PROMPT)

    def test_every_baseline_asks_for_the_same_vocabulary(self):
        """A baseline that offers the model a different set of direction
        values is not comparable with the others, and labels.py would grade
        the difference as an off-vocabulary failure by the model."""
        from eval.labels import DIRECTIONS, STRENGTHS
        for prompt in (EXCERPT_PROMPT, no_retrieval.NO_CONTEXT_PROMPT):
            for value in DIRECTIONS + STRENGTHS:
                self.assertIn(value, prompt)


class TestMapClaims(unittest.TestCase):
    def test_resolves_excerpt_index_to_the_real_span(self):
        claims = map_claims([{"text": "a claim", "excerpt_index": 2}], EXCERPTS)
        self.assertEqual(claims, [{
            "text": "a claim", "cited_pmcid": "PMC2", "cited_section": "abstract",
            "cited_char_start": 0, "cited_char_end": 25,
        }])

    def test_preserves_a_claim_with_an_invalid_citation(self):
        for bad in (0, 3, -1, None, "1", 1.0, True):
            claim = map_claims([{"text": "x", "excerpt_index": bad}], EXCERPTS)[0]
            self.assertEqual(claim["text"], "x")
            self.assertEqual(claim["cited_pmcid"], "")

    def test_keeps_the_good_claims_when_one_is_bad(self):
        claims = map_claims(
            [{"text": "ok", "excerpt_index": 1}, {"text": "bad", "excerpt_index": 99}], EXCERPTS)
        self.assertEqual([c["text"] for c in claims], ["ok", "bad"])

    def test_no_claims_at_all_is_an_empty_list_not_a_crash(self):
        self.assertEqual(map_claims(None, EXCERPTS), [])
        self.assertEqual(map_claims([], EXCERPTS), [])


class TestFormatting(unittest.TestCase):
    def test_excerpts_are_numbered_from_one(self):
        text = format_excerpts(EXCERPTS)
        self.assertTrue(text.startswith("[1] (from PMC1, body) First excerpt text."))
        self.assertIn("[2] (from PMC2, abstract) Second excerpt text.", text)

    def test_answer_from_tolerates_a_model_omitting_fields(self):
        answer = answer_from({"case_id": "c1"}, {}, [])
        self.assertEqual(answer["case_id"], "c1")
        self.assertIsNone(answer["direction"])
        self.assertFalse(answer["not_found"])
        self.assertEqual(answer["claims"], [])


if __name__ == "__main__":
    unittest.main()
