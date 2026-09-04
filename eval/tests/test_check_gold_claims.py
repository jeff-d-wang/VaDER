"""
Tests for check_gold_claims.py. Stdlib only, no pytest.

    python -m eval.tests.test_check_gold_claims
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import eval.check_gold_claims as cgc


def _case(case_id="c1", direction="increased risk", strength="", variant=None,
          spans=None, negative=False):
    return {
        "case_id": case_id, "stratum": "evidence", "is_negative_case": negative,
        "gene": "ATM", "variant": variant, "condition": "breast cancer",
        "query": "q", "gold_spans": spans if spans is not None else [],
        "gold": {"direction": direction, "strength": strength,
                 "has_disagreement": False, "disagreement_note": "",
                 "expected_not_found": negative},
        "held_out_pmcids": [], "notes": "", "created_by": "agent:test",
        "created_at_utc": "2026-09-04T00:00:00Z",
    }


class TestNumberExtraction(unittest.TestCase):
    def test_plain_integers_and_decimals(self):
        self.assertEqual(cgc.numbers_in("HR 1.32 in 296 patients"), {"1.32", "296"})

    def test_comma_thousands_separator_is_stripped(self):
        self.assertEqual(cgc.numbers_in("15,252 carriers"), {"15252"})

    def test_space_thousands_separator_is_stripped(self):
        """PMC XML preserves whatever separator the publisher used. The real
        source for brca_prs_ovarian_risk_ord_001 reads "15 252", while the
        gold label reads "15,252". Both must normalize to the same token or
        the check reports a defect that isn't there."""
        self.assertEqual(cgc.numbers_in("15 252 female BRCA1"), {"15252"})
        self.assertEqual(cgc.numbers_in("15 252 female"), {"15252"})

    def test_percentages_and_ranges_reduce_to_their_numbers(self):
        self.assertEqual(cgc.numbers_in("6% vs 19% risk"), {"6", "19"})
        self.assertEqual(cgc.numbers_in("2.13-21.7-fold"), {"2.13", "21.7"})

    def test_tokenization_gives_number_boundaries_for_free(self):
        """66 must not be credited by a span that only contains 660."""
        self.assertNotIn("66", cgc.numbers_in("660 patients"))

    def test_gene_symbols_do_not_leak_number_tokens(self):
        """Found by these tests: without a letter guard, BRCA1 asserts "1",
        TP53 asserts "53", and a PMCID asserts an eight-digit finding."""
        self.assertEqual(cgc.numbers_in("BRCA1 and BRCA2 carriers"), set())
        self.assertEqual(cgc.numbers_in("TP53 mutation in PMC4150261"), set())
        self.assertEqual(cgc.numbers_in("CHEK2 c.1100delC"), set())

    def test_ordinals_survive_the_letter_guard(self):
        """The guard is on the leading side only: "10th percentile" is a
        real claim and must still be extracted."""
        self.assertEqual(cgc.numbers_in("the 10th percentile"), {"10"})


class TestGoldClaimText(unittest.TestCase):
    def test_variant_notation_is_stripped_before_extraction(self):
        """c.7570G>C carries a position, not a finding. Left in, it would be
        reported missing from every span that names the variant some other
        way."""
        case = _case(variant="c.7570G>C", strength="c.7570G>C confers OR 8.5")
        self.assertEqual(cgc.numbers_in(cgc.gold_claim_text(case)), {"8.5"})

    def test_slashed_gene_symbols_do_not_assert_a_number(self):
        """A false positive caught on the first real run: the leading letter
        guard excludes the 1 of BRCA1, but the 2 of BRCA1/2 is preceded by a
        slash and was reported as an unsupported claim that the source
        "asserts 2"."""
        case = _case(strength="approximately 4-7% of patients carry germline BRCA1/2 mutations")
        self.assertEqual(cgc.numbers_in(cgc.gold_claim_text(case)), {"4", "7"})

    def test_direction_and_strength_are_both_searched(self):
        case = _case(direction="risk up 3-fold", strength="in 296 patients")
        self.assertEqual(cgc.numbers_in(cgc.gold_claim_text(case)), {"3", "296"})


class TestCheckCase(unittest.TestCase):
    # Offsets are computed from this string, never hardcoded: an
    # out-of-range span silently becomes span_error, which would make these
    # tests pass or fail for the wrong reason.
    ABSTRACT = ("From a total of 296 patients we identified 66 who developed a tumour; "
                "47 lymphoid and 19 non-lymphoid were diagnosed.")
    TAIL_START = ABSTRACT.index("47 lymphoid")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xml = Path(self.tmp.name)
        (self.xml / "PMC1.xml").write_text(
            f"<article><front><abstract><p>{self.ABSTRACT}</p></abstract></front></article>"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _span(self, start, end):
        return [{"pmcid": "PMC1", "section": "abstract", "char_start": start, "char_end": end}]

    def test_the_real_regression_numbers_outside_the_cited_span(self):
        """The atm_at_lymphoid_tumor_ord_001 shape: the cohort figures are in
        the abstract, the span starts after them."""
        case = _case(strength="cohort of 296 patients, 66 tumours (47 lymphoid, 19 non-lymphoid)",
                     spans=self._span(self.TAIL_START, len(self.ABSTRACT)))
        result = cgc.check_case(case, self.xml)
        self.assertEqual(result["status"], "missing_numbers")
        self.assertEqual(set(result["missing"]), {"296", "66"})

    def test_span_covering_the_numbers_passes(self):
        case = _case(strength="cohort of 296 patients, 66 tumours (47 lymphoid, 19 non-lymphoid)",
                     spans=self._span(0, len(self.ABSTRACT)))
        self.assertEqual(cgc.check_case(case, self.xml)["status"], "ok")

    def test_gold_with_no_numbers_is_not_silently_ok(self):
        """A distinct status, because "nothing to check" and "checked and
        clean" are different claims and must not be counted together."""
        case = _case(strength="moderate", direction="increased risk",
                     spans=self._span(0, len(self.ABSTRACT)))
        self.assertEqual(cgc.check_case(case, self.xml)["status"], "no_numeric_claim")

    def test_negative_case_is_skipped_not_failed(self):
        self.assertEqual(cgc.check_case(_case(negative=True), self.xml)["status"], "no_spans")

    def test_unresolvable_span_is_reported(self):
        case = _case(strength="296 patients",
                     spans=[{"pmcid": "PMC_MISSING", "section": "abstract",
                             "char_start": 0, "char_end": 10}])
        result = cgc.check_case(case, self.xml)
        self.assertEqual(result["status"], "span_error")
        self.assertTrue(result["errors"])

    def test_a_number_in_any_span_counts(self):
        """A multi-span case may legitimately draw its strength claim from
        across its sources, so a number is credited if it appears in any."""
        case = _case(strength="296 patients",
                     spans=self._span(self.TAIL_START, len(self.ABSTRACT))
                           + self._span(0, self.TAIL_START))
        self.assertEqual(cgc.check_case(case, self.xml)["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
