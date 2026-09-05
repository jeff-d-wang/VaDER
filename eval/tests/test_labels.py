"""
Tests for labels.py: the controlled vocabularies and the deterministic
grading that replaced an LLM judge on direction and strength.

    python -m eval.tests.test_labels
"""
from __future__ import annotations

import unittest

from eval.labels import (DIRECTIONS, STRENGTHS, grade_direction, grade_strength,
                         majority_class_baseline, normalize_direction, normalize_strength)


class TestNormalization(unittest.TestCase):
    def test_vocabulary_values_pass_through(self):
        for d in DIRECTIONS:
            self.assertEqual(normalize_direction(d), d)
        for s in STRENGTHS:
            self.assertEqual(normalize_strength(s), s)

    def test_the_two_spellings_that_caused_this_redesign_unify(self):
        """The real defect: 'mixed' and 'mixed_evidence' were two gold
        strings for one concept."""
        self.assertEqual(normalize_direction("mixed"), "mixed")
        self.assertEqual(normalize_direction("mixed_evidence"), "mixed")
        self.assertEqual(normalize_direction("mixed evidence"), "mixed")

    def test_case_and_whitespace_insensitive(self):
        self.assertEqual(normalize_direction("  INCREASED  "), "increased")

    def test_off_vocabulary_returns_none_rather_than_guessing(self):
        """A near-miss must not be quietly accepted; accepting synonyms one
        at a time rebuilds the free-text problem this replaced."""
        self.assertIsNone(normalize_direction("elevated in some cohorts"))
        self.assertIsNone(normalize_direction("pathogenic increases risk"))
        self.assertIsNone(normalize_strength("substantial protective effect observed"))


class TestGradeDirection(unittest.TestCase):
    def test_exact_match_passes(self):
        self.assertEqual(grade_direction("increased", "increased")[0], "pass")

    def test_alias_still_passes(self):
        self.assertEqual(grade_direction("mixed", "mixed_evidence")[0], "pass")

    def test_mismatch_fails(self):
        self.assertEqual(grade_direction("increased", "none")[0], "fail")

    def test_no_partial_credit_for_a_categorical_property(self):
        for gold in DIRECTIONS:
            for ans in DIRECTIONS:
                self.assertIn(grade_direction(gold, ans)[0], ("pass", "fail"))

    def test_off_vocabulary_answer_fails_and_says_so(self):
        verdict, why = grade_direction("increased", "probably higher, hard to say")
        self.assertEqual(verdict, "fail")
        self.assertIn("off-vocabulary", why)

    def test_bad_gold_blames_the_case_not_the_system(self):
        verdict, why = grade_direction("pathogenic increases risk", "increased")
        self.assertEqual(verdict, "fail")
        self.assertIn("fix the case", why)


class TestGradeStrength(unittest.TestCase):
    def test_exact_match_passes(self):
        self.assertEqual(grade_strength("high", "high")[0], "pass")

    def test_one_tier_off_on_the_ordinal_scale_is_partial(self):
        self.assertEqual(grade_strength("high", "moderate")[0], "partial")
        self.assertEqual(grade_strength("low", "moderate")[0], "partial")

    def test_two_tiers_off_fails(self):
        self.assertEqual(grade_strength("high", "low")[0], "fail")

    def test_off_scale_values_are_categorical_never_partial(self):
        """disputed/unstated/none are not points on low<moderate<high, so
        missing them is a miss, not a near miss."""
        self.assertEqual(grade_strength("disputed", "moderate")[0], "fail")
        self.assertEqual(grade_strength("unstated", "low")[0], "fail")
        self.assertEqual(grade_strength("none", "low")[0], "fail")

    def test_a_real_migrated_case_shape(self):
        """atm_at_lymphoid gold was a cohort description; under the new
        scheme it is `high`, and the cohort text lives unscored in
        strength_detail."""
        self.assertEqual(grade_strength("high", "high")[0], "pass")
        self.assertEqual(grade_strength("high", "substantial protective effect")[0], "fail")


class TestMajorityClassBaseline(unittest.TestCase):
    def test_reports_the_trivial_score_to_read_results_against(self):
        value, rate, n = majority_class_baseline(["increased"] * 8 + ["mixed"] * 3)
        self.assertEqual(value, "increased")
        self.assertAlmostEqual(rate, 8 / 11)
        self.assertEqual(n, 11)

    def test_ignores_unlabelled_cases(self):
        value, rate, n = majority_class_baseline(["increased", None, "increased"])
        self.assertEqual((value, n), ("increased", 2))
        self.assertAlmostEqual(rate, 1.0)

    def test_empty_is_not_a_crash(self):
        self.assertEqual(majority_class_baseline([None, None]), (None, 0.0, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
