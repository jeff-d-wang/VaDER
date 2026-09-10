import unittest
from pathlib import Path
from unittest.mock import patch

from eval.generate_grounding_expansion import generate


class GroundingExpansionTests(unittest.TestCase):
    def test_generate_uses_reviewed_span_and_runtime_validation(self):
        rows = [{
            "case_id": "calexp_1",
            "query": "What was reported?",
            "gold_span": {
                "pmcid": "PMC1", "section": "abstract", "char_start": 4, "char_end": 20,
            },
        }]

        def client(prompt, model):
            self.assertIn("reviewed source text", prompt)
            self.assertEqual(model, "model")
            return {
                "direction": "increased", "strength": "unstated", "not_found": False,
                "claims": [{"text": "The value increased", "excerpt_index": 1}],
            }

        with patch("eval.generate_grounding_expansion.load_span_text",
                   return_value=("reviewed source text", None)):
            answers = generate(rows, "model", Path("unused"), client=client)

        self.assertEqual(answers[0]["case_id"], "calexp_1")
        self.assertEqual(answers[0]["answer_text"], "The value increased [1].")
        self.assertEqual(answers[0]["claims"][0]["cited_pmcid"], "PMC1")

    def test_generate_rejects_unresolvable_span_before_model_call(self):
        rows = [{
            "case_id": "calexp_1", "query": "question",
            "gold_span": {"pmcid": "PMC1", "section": "body", "char_start": 0, "char_end": 2},
        }]
        with patch("eval.generate_grounding_expansion.load_span_text",
                   return_value=("", "offset mismatch")):
            with self.assertRaisesRegex(ValueError, "citation does not resolve"):
                generate(rows, "model", Path("unused"), client=lambda *_args, **_kwargs: {})


if __name__ == "__main__":
    unittest.main()
