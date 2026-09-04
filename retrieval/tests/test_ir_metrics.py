"""
Tests for ir_metrics.py. Stdlib only, no pytest, same convention as every
other test file here.

The nDCG expectations below are computed by hand in the docstrings rather
than copied from another implementation, on purpose: the point of this
module is to be a metric definition this project can defend line by line,
and a test that asserts "matches whatever the library said" defends nothing.

    python -m retrieval.tests.test_ir_metrics
"""
from __future__ import annotations

import math
import unittest

from retrieval import ir_metrics as m
from retrieval.ir_metrics import QueryResult


def _qr(retrieved, judgments, query_id="q1"):
    return QueryResult(query_id=query_id, retrieved=retrieved, judgments=judgments)


class TestRecall(unittest.TestCase):
    def test_counts_relevant_in_top_k_over_all_relevant(self):
        r = _qr(["a", "b", "c"], {"b": 1, "c": 2, "d": 1})
        self.assertAlmostEqual(m.recall_at_k(r, 3), 2 / 3)
        self.assertAlmostEqual(m.recall_at_k(r, 2), 1 / 3)
        self.assertAlmostEqual(m.recall_at_k(r, 1), 0.0)

    def test_graded_relevance_is_binary_for_recall(self):
        """A relevance-2 doc counts once, not twice."""
        r = _qr(["a"], {"a": 2})
        self.assertAlmostEqual(m.recall_at_k(r, 1), 1.0)

    def test_k_beyond_the_ranking_does_not_crash_or_inflate(self):
        r = _qr(["a"], {"a": 1, "b": 1})
        self.assertAlmostEqual(m.recall_at_k(r, 100), 0.5)

    def test_query_with_no_relevant_docs_is_undefined_not_zero(self):
        """Scoring it 0 would drag the mean down for a query no system could
        ever get right; scoring it 1 would inflate it. Neither is honest."""
        self.assertIsNone(m.recall_at_k(_qr(["a"], {"a": 0}), 10))
        self.assertIsNone(m.recall_at_k(_qr(["a"], {}), 10))


class TestReciprocalRank(unittest.TestCase):
    def test_is_one_over_the_first_relevant_rank_one_indexed(self):
        self.assertAlmostEqual(m.reciprocal_rank(_qr(["a", "b"], {"a": 1})), 1.0)
        self.assertAlmostEqual(m.reciprocal_rank(_qr(["a", "b"], {"b": 1})), 0.5)
        self.assertAlmostEqual(m.reciprocal_rank(_qr(["a", "b", "c"], {"c": 1})), 1 / 3)

    def test_zero_when_nothing_relevant_was_retrieved(self):
        self.assertAlmostEqual(m.reciprocal_rank(_qr(["a"], {"z": 1})), 0.0)

    def test_cutoff_hides_a_relevant_doc_past_k(self):
        r = _qr(["a", "b", "c"], {"c": 1})
        self.assertAlmostEqual(m.reciprocal_rank(r, k=2), 0.0)
        self.assertAlmostEqual(m.reciprocal_rank(r, k=3), 1 / 3)


class TestDCG(unittest.TestCase):
    def test_rank_one_is_undiscounted(self):
        """log2(1 + 1) = 1, so the first position divides by exactly 1."""
        self.assertAlmostEqual(m.dcg([3.0]), 3.0)

    def test_discount_matches_the_written_formula(self):
        """gains [1, 1] -> 1/log2(2) + 1/log2(3) = 1 + 0.6309297."""
        self.assertAlmostEqual(m.dcg([1.0, 1.0]), 1 + 1 / math.log2(3))


class TestNDCG(unittest.TestCase):
    def test_worked_example(self):
        """retrieved [a, b, c], judged {b:1, c:2, d:1}, k=3.

          gains  = [0, 1, 2]
          DCG    = 0/log2(2) + 1/log2(3) + 2/log2(4)
                 = 0 + 0.6309297 + 1.0          = 1.6309297
          ideal  = [2, 1, 1]  (d is judged but never retrieved; it still
                               belongs in the ideal ranking)
          IDCG   = 2/1 + 1/log2(3) + 1/2        = 3.1309297
          nDCG@3 = 1.6309297 / 3.1309297        = 0.5209...
        """
        r = _qr(["a", "b", "c"], {"b": 1, "c": 2, "d": 1})
        expected = (1 / math.log2(3) + 1.0) / (2.0 + 1 / math.log2(3) + 0.5)
        self.assertAlmostEqual(m.ndcg_at_k(r, 3), expected)
        self.assertAlmostEqual(m.ndcg_at_k(r, 3), 0.520906, places=5)

    def test_perfect_ranking_scores_one(self):
        r = _qr(["c", "b", "d"], {"b": 1, "c": 2, "d": 1})
        self.assertAlmostEqual(m.ndcg_at_k(r, 3), 1.0)

    def test_graded_relevance_rewards_putting_the_2_first(self):
        judgments = {"x": 2, "y": 1}
        better = m.ndcg_at_k(_qr(["x", "y"], judgments), 2)
        worse = m.ndcg_at_k(_qr(["y", "x"], judgments), 2)
        self.assertGreater(better, worse)
        self.assertAlmostEqual(better, 1.0)

    def test_unjudged_docs_count_as_zero_gain(self):
        """The standard BEIR treatment, and a real limitation worth having a
        test name for: a good-but-unjudged result is penalized."""
        r = _qr(["unjudged", "b"], {"b": 1})
        self.assertAlmostEqual(m.ndcg_at_k(r, 2), (1 / math.log2(3)) / 1.0)

    def test_undefined_when_no_relevant_docs_exist(self):
        self.assertIsNone(m.ndcg_at_k(_qr(["a"], {"a": 0}), 10))

    def test_idcg_is_capped_at_k_not_computed_over_all_judgments(self):
        """With 3 relevant docs and k=1, a system that puts one at rank 1 is
        perfect at that depth. Computing IDCG over all 3 would wrongly score
        it 0.46 and make nDCG@1 unattainable by any system."""
        r = _qr(["a"], {"a": 1, "b": 1, "c": 1})
        self.assertAlmostEqual(m.ndcg_at_k(r, 1), 1.0)


class TestAggregation(unittest.TestCase):
    def test_mean_drops_undefined_queries_and_reports_the_real_n(self):
        mean, n = m.mean_ignoring_none([1.0, None, 0.0, None])
        self.assertAlmostEqual(mean, 0.5)
        self.assertEqual(n, 2)

    def test_all_undefined_is_n_zero_not_a_crash(self):
        mean, n = m.mean_ignoring_none([None, None])
        self.assertEqual((mean, n), (0.0, 0))

    def test_bootstrap_is_seeded_and_brackets_the_mean(self):
        values = [0.0, 0.25, 0.5, 0.75, 1.0] * 20
        lo1, hi1 = m.bootstrap_ci(values, n_resamples=500, seed=3)
        lo2, hi2 = m.bootstrap_ci(values, n_resamples=500, seed=3)
        self.assertEqual((lo1, hi1), (lo2, hi2))
        self.assertLess(lo1, 0.5)
        self.assertGreater(hi1, 0.5)

    def test_bootstrap_on_a_constant_has_zero_width(self):
        lo, hi = m.bootstrap_ci([0.7] * 30, n_resamples=200, seed=0)
        self.assertAlmostEqual(lo, 0.7)
        self.assertAlmostEqual(hi, 0.7)

    def test_evaluate_reports_every_metric_with_an_n_and_an_interval(self):
        results = [
            _qr(["a", "b"], {"a": 1}, "q1"),
            _qr(["c", "d"], {"d": 2}, "q2"),
            _qr(["e"], {}, "q3"),  # no relevant docs: undefined for recall/ndcg
        ]
        summaries = {s.name: s for s in m.evaluate(results, ks=(1, 10), ndcg_k=10)}
        self.assertEqual(set(summaries), {"recall@1", "recall@10", "ndcg@10", "mrr"})
        self.assertEqual(summaries["recall@10"].n, 2)  # q3 excluded
        self.assertEqual(summaries["mrr"].n, 3)        # mrr is defined for q3 (scores 0)
        self.assertAlmostEqual(summaries["recall@10"].value, 1.0)
        self.assertAlmostEqual(summaries["mrr"].value, (1.0 + 0.5 + 0.0) / 3)
        for s in summaries.values():
            self.assertLessEqual(s.ci_low, s.value + 1e-9)
            self.assertGreaterEqual(s.ci_high, s.value - 1e-9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
