"""Stdlib-only tests for compare_runs.py. Run directly: python -m eval.tests.test_compare_runs"""
from __future__ import annotations

import unittest

from eval.compare_runs import mcnemar_exact_p


class TestCompareRuns(unittest.TestCase):
    def test_no_discordant_pairs_is_p_one(self) -> None:
        self.assertEqual(mcnemar_exact_p(0, 0), 1.0, "b=c=0 -> p=1.0 (no evidence either way)")

    def test_symmetric_discordance_is_high_p(self) -> None:
        p = mcnemar_exact_p(5, 5)
        self.assertTrue(p > 0.5, "%s -- %s" % ("perfectly symmetric discordance (5 vs 5) gives a high p-value", str(p)))

    def test_lopsided_discordance_is_low_p(self) -> None:
        p = mcnemar_exact_p(0, 9)
        self.assertTrue(p < 0.01, "%s -- %s" % ("9-0 lopsided discordance gives a low p-value (real signal)", str(p)))

    def test_symmetry_of_arguments(self) -> None:
        self.assertEqual(mcnemar_exact_p(2, 7), mcnemar_exact_p(7, 2), "mcnemar_exact_p(b, c) == mcnemar_exact_p(c, b)")

    def test_small_n_never_exceeds_one(self) -> None:
        for b in range(6):
            for c in range(6):
                p = mcnemar_exact_p(b, c)
                self.assertTrue(0.0 <= p <= 1.0, "%s -- %s" % (f"p in [0,1] for b={b},c={c}", str(p)))


if __name__ == "__main__":
    unittest.main()
