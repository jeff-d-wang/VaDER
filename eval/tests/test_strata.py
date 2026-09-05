"""
Tests for strata.py (phase A4 date stratification). Stdlib only.

    python -m eval.tests.test_strata
"""
from __future__ import annotations

import unittest

from eval.strata import case_pmcids, case_year, stratum

YEARS = {"PMC_OLD": 2014, "PMC_MID": 2021, "PMC_NEW": 2026}


def _case(spans=(), held_out=(), negative=False):
    return {
        "case_id": "c1", "is_negative_case": negative,
        "gold_spans": [{"pmcid": p, "section": "abstract", "char_start": 0, "char_end": 1}
                       for p in spans],
        "held_out_pmcids": list(held_out),
    }


class TestCasePmcids(unittest.TestCase):
    def test_uses_gold_spans_when_present(self):
        self.assertEqual(case_pmcids(_case(spans=["PMC_OLD", "PMC_NEW"])), ["PMC_NEW", "PMC_OLD"])

    def test_deduplicates_multiple_spans_in_one_article(self):
        self.assertEqual(case_pmcids(_case(spans=["PMC_OLD", "PMC_OLD"])), ["PMC_OLD"])

    def test_falls_back_to_held_out_article_for_a_negative_case(self):
        """A negative case has no gold spans. The held-out article is the
        thing whose absence it asserts, and its date is what says whether
        the model might know it from pretraining anyway."""
        self.assertEqual(case_pmcids(_case(held_out=["PMC_NEW"], negative=True)), ["PMC_NEW"])


class TestCaseYear(unittest.TestCase):
    def test_takes_the_earliest_supporting_article(self):
        """Earliest, not latest: if ANY supporting article predates the
        cutoff, memorization is on the table, so the case cannot count as
        post-cutoff."""
        self.assertEqual(case_year(_case(spans=["PMC_OLD", "PMC_NEW"]), YEARS), 2014)

    def test_none_when_no_article_has_a_known_year(self):
        self.assertIsNone(case_year(_case(spans=["PMC_MISSING"]), YEARS))

    def test_ignores_articles_missing_from_the_manifest(self):
        self.assertEqual(case_year(_case(spans=["PMC_MISSING", "PMC_MID"]), YEARS), 2021)


class TestStratum(unittest.TestCase):
    def test_boundary_year_is_pre_cutoff(self):
        """post_cutoff means strictly after the cutoff year, so a 2024 paper
        against a 2024 cutoff is pre-cutoff, the conservative reading."""
        self.assertEqual(stratum(2024, 2024), "pre_cutoff")
        self.assertEqual(stratum(2025, 2024), "post_cutoff")

    def test_unknown_year_is_its_own_bucket_not_silently_pre(self):
        self.assertEqual(stratum(None, 2024), "unknown")

    def test_a_mixed_age_case_lands_pre_cutoff(self):
        case = _case(spans=["PMC_OLD", "PMC_NEW"])
        self.assertEqual(stratum(case_year(case, YEARS), 2024), "pre_cutoff")


if __name__ == "__main__":
    unittest.main(verbosity=2)
