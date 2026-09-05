"""Stdlib-only tests for kappa.py. Every expected value below was hand-
derived from the Cohen's kappa formula (po, pe, (po-pe)/(1-pe)), then cross-
checked against the function's own output, not copied from an external
reference. Run directly: python -m eval.tests.test_kappa"""
from __future__ import annotations

import unittest

import math

from eval.kappa import cohens_kappa, interpret, kappa_report

def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) < tol


class TestKappa(unittest.TestCase):
    def test_perfect_agreement(self) -> None:
        a = ["pass", "fail", "partial", "pass", "fail"]
        self.assertTrue(close(cohens_kappa(a, a, False), 1.0), "perfect agreement -> kappa = 1.0 (unweighted)")
        self.assertTrue(close(cohens_kappa(a, a, True), 1.0), "perfect agreement -> kappa = 1.0 (weighted)")

    def test_hand_derived_extreme_disagreement_only(self) -> None:
        # po=0.75, pe=0.5 -> kappa=0.5. Hand-derived: see module docstring note
        # in kappa.py; only pass/fail appear (no partial), so weighted ==
        # unweighted here (the pass-fail distance is the max possible weight-0
        # case either way).
        a = ["pass", "pass", "fail", "fail"]
        b = ["pass", "fail", "fail", "fail"]
        self.assertTrue(close(cohens_kappa(a, b, False), 0.5), "%s -- %s" % ("hand-derived po=0.75/pe=0.5 case -> unweighted kappa = 0.5", str(cohens_kappa(a, b, False))))
        self.assertTrue(close(cohens_kappa(a, b, True), 0.5), "%s -- %s" % ("same case, weighted == unweighted when only the extreme categories disagree", str(cohens_kappa(a, b, True))))

    def test_hand_derived_partial_disagreement(self) -> None:
        # Includes a pass-vs-partial near-miss. Hand-derived: po_w=0.875,
        # pe_w=0.5625 -> kappa_w=5/7 (0.71428...); po=0.75, pe=0.3125 ->
        # kappa=0.63636... (see PR/commit description for the full derivation).
        a = ["pass", "pass", "partial", "fail"]
        b = ["partial", "pass", "partial", "fail"]
        k_unweighted = cohens_kappa(a, b, False)
        k_weighted = cohens_kappa(a, b, True)
        self.assertTrue(close(k_unweighted, 7 / 11), "%s -- %s" % ("unweighted kappa matches hand derivation (7/11 = 0.6364)", str(k_unweighted)))
        self.assertTrue(close(k_weighted, 5 / 7), "%s -- %s" % ("weighted kappa matches hand derivation (5/7 = 0.7143)", str(k_weighted)))
        self.assertTrue(k_weighted > k_unweighted, "weighted kappa is higher than unweighted here (a near-miss costs less)")

    def test_degenerate_no_variation(self) -> None:
        k = cohens_kappa(["pass"] * 5, ["pass"] * 5, False)
        self.assertTrue(math.isnan(k), "both raters always pick the same single category -> NaN, not a fake 1.0 or crash")

    def test_length_mismatch_raises(self) -> None:
        try:
            cohens_kappa(["pass", "fail"], ["pass"], False)
            self.assertTrue(False, "mismatched-length rating lists raise")
        except ValueError:
            self.assertTrue(True, "mismatched-length rating lists raise")

    def test_empty_raises(self) -> None:
        try:
            cohens_kappa([], [], False)
            self.assertTrue(False, "empty rating lists raise rather than silently returning 0")
        except ValueError:
            self.assertTrue(True, "empty rating lists raise rather than silently returning 0")

    def test_interpret_bands(self) -> None:
        self.assertTrue(interpret(-0.1) == "no better than chance / slight", "negative/near-zero kappa reads as the lowest band")
        self.assertEqual(interpret(0.9), "almost perfect", "kappa 0.9 reads as almost perfect")
        self.assertEqual(interpret(0.5), "moderate", "kappa 0.5 reads as moderate")

    def test_kappa_report_lists_disagreement_indices(self) -> None:
        a = ["pass", "pass", "fail"]
        b = ["pass", "fail", "fail"]
        report = kappa_report(a, b, "judge", "human")
        self.assertIn("[1]", report, "%s -- %s" % ("report names the disagreement index", report))
        self.assertTrue("unweighted kappa" in report and "weighted kappa" in report, "report includes both kappa values")


if __name__ == "__main__":
    unittest.main()
