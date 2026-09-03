"""Stdlib-only tests for kappa.py. Every expected value below was hand-
derived from the Cohen's kappa formula (po, pe, (po-pe)/(1-pe)), then cross-
checked against the function's own output, not copied from an external
reference. Run directly: python test_kappa.py"""
from __future__ import annotations

import math
import sys

from kappa import cohens_kappa, interpret, kappa_report

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) < tol


def test_perfect_agreement() -> None:
    a = ["pass", "fail", "partial", "pass", "fail"]
    check("perfect agreement -> kappa = 1.0 (unweighted)", close(cohens_kappa(a, a, False), 1.0))
    check("perfect agreement -> kappa = 1.0 (weighted)", close(cohens_kappa(a, a, True), 1.0))


def test_hand_derived_extreme_disagreement_only() -> None:
    # po=0.75, pe=0.5 -> kappa=0.5. Hand-derived: see module docstring note
    # in kappa.py; only pass/fail appear (no partial), so weighted ==
    # unweighted here (the pass-fail distance is the max possible weight-0
    # case either way).
    a = ["pass", "pass", "fail", "fail"]
    b = ["pass", "fail", "fail", "fail"]
    check("hand-derived po=0.75/pe=0.5 case -> unweighted kappa = 0.5",
          close(cohens_kappa(a, b, False), 0.5), str(cohens_kappa(a, b, False)))
    check("same case, weighted == unweighted when only the extreme categories disagree",
          close(cohens_kappa(a, b, True), 0.5), str(cohens_kappa(a, b, True)))


def test_hand_derived_partial_disagreement() -> None:
    # Includes a pass-vs-partial near-miss. Hand-derived: po_w=0.875,
    # pe_w=0.5625 -> kappa_w=5/7 (0.71428...); po=0.75, pe=0.3125 ->
    # kappa=0.63636... (see PR/commit description for the full derivation).
    a = ["pass", "pass", "partial", "fail"]
    b = ["partial", "pass", "partial", "fail"]
    k_unweighted = cohens_kappa(a, b, False)
    k_weighted = cohens_kappa(a, b, True)
    check("unweighted kappa matches hand derivation (7/11 = 0.6364)",
          close(k_unweighted, 7 / 11), str(k_unweighted))
    check("weighted kappa matches hand derivation (5/7 = 0.7143)",
          close(k_weighted, 5 / 7), str(k_weighted))
    check("weighted kappa is higher than unweighted here (a near-miss costs less)",
          k_weighted > k_unweighted)


def test_degenerate_no_variation() -> None:
    k = cohens_kappa(["pass"] * 5, ["pass"] * 5, False)
    check("both raters always pick the same single category -> NaN, not a fake 1.0 or crash",
          math.isnan(k))


def test_length_mismatch_raises() -> None:
    try:
        cohens_kappa(["pass", "fail"], ["pass"], False)
        check("mismatched-length rating lists raise", False)
    except ValueError:
        check("mismatched-length rating lists raise", True)


def test_empty_raises() -> None:
    try:
        cohens_kappa([], [], False)
        check("empty rating lists raise rather than silently returning 0", False)
    except ValueError:
        check("empty rating lists raise rather than silently returning 0", True)


def test_interpret_bands() -> None:
    check("negative/near-zero kappa reads as the lowest band", interpret(-0.1) == "no better than chance / slight")
    check("kappa 0.9 reads as almost perfect", interpret(0.9) == "almost perfect")
    check("kappa 0.5 reads as moderate", interpret(0.5) == "moderate")


def test_kappa_report_lists_disagreement_indices() -> None:
    a = ["pass", "pass", "fail"]
    b = ["pass", "fail", "fail"]
    report = kappa_report(a, b, "judge", "human")
    check("report names the disagreement index", "[1]" in report, report)
    check("report includes both kappa values", "unweighted kappa" in report and "weighted kappa" in report)


def run_tests() -> int:
    test_perfect_agreement()
    test_hand_derived_extreme_disagreement_only()
    test_hand_derived_partial_disagreement()
    test_degenerate_no_variation()
    test_length_mismatch_raises()
    test_empty_raises()
    test_interpret_bands()
    test_kappa_report_lists_disagreement_indices()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
