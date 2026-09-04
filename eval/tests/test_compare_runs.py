"""Stdlib-only tests for compare_runs.py. Run directly: python -m eval.tests.test_compare_runs"""
from __future__ import annotations

import sys

from eval.compare_runs import mcnemar_exact_p

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


def test_no_discordant_pairs_is_p_one() -> None:
    check("b=c=0 -> p=1.0 (no evidence either way)", mcnemar_exact_p(0, 0) == 1.0)


def test_symmetric_discordance_is_high_p() -> None:
    p = mcnemar_exact_p(5, 5)
    check("perfectly symmetric discordance (5 vs 5) gives a high p-value", p > 0.5, str(p))


def test_lopsided_discordance_is_low_p() -> None:
    p = mcnemar_exact_p(0, 9)
    check("9-0 lopsided discordance gives a low p-value (real signal)", p < 0.01, str(p))


def test_symmetry_of_arguments() -> None:
    check("mcnemar_exact_p(b, c) == mcnemar_exact_p(c, b)",
          mcnemar_exact_p(2, 7) == mcnemar_exact_p(7, 2))


def test_small_n_never_exceeds_one() -> None:
    for b in range(6):
        for c in range(6):
            p = mcnemar_exact_p(b, c)
            check(f"p in [0,1] for b={b},c={c}", 0.0 <= p <= 1.0, str(p))


def run_tests() -> int:
    test_no_discordant_pairs_is_p_one()
    test_symmetric_discordance_is_high_p()
    test_lopsided_discordance_is_low_p()
    test_symmetry_of_arguments()
    test_small_n_never_exceeds_one()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
