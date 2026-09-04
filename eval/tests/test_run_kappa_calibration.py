"""Stdlib-only tests for run_kappa_calibration.py. Run directly:
python -m eval.tests.test_run_kappa_calibration"""
from __future__ import annotations

import sys

from eval.run_kappa_calibration import parse_worksheet

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


SAMPLE = """# Kappa calibration worksheet

## case_one
Some prose here, not a verdict line.
**Your verdicts (pass/partial/fail):**
- direction: pass
- groundedness: Partial
- says_not_found (should NOT have refused): fail
- disagreement: fail (the system missed the conflict entirely, presenting only one side)

---

## case_two
- says_not_found: ___

---

## case_three
- direction: PASS
- disagreement: fail
"""


def test_parses_verdicts_per_case() -> None:
    result = parse_worksheet(SAMPLE)
    check("case_one parsed", "case_one" in result)
    check("direction verdict parsed as pass", result["case_one"]["direction"] == "pass")
    check("verdict lowercased regardless of input case",
          result["case_one"]["groundedness"] == "partial")
    check("says_not_found aliased to not_found", result["case_one"]["not_found"] == "fail")


def test_blank_verdict_excluded() -> None:
    result = parse_worksheet(SAMPLE)
    check("case_two present but with no verdicts (blank was skipped)",
          "case_two" in result and "not_found" not in result["case_two"])


def test_uppercase_verdict_normalized() -> None:
    result = parse_worksheet(SAMPLE)
    check("PASS (uppercase) normalized to pass", result["case_three"]["direction"] == "pass")


def test_prose_lines_ignored() -> None:
    result = parse_worksheet(SAMPLE)
    check("only 4 real verdicts on case_one, prose line didn't get parsed as a 5th",
          len(result["case_one"]) == 4, str(result["case_one"]))


def test_trailing_rationale_after_verdict_still_parses() -> None:
    # Regression: an earlier version of _VERDICT_LINE required end-of-line
    # right after the verdict word, so any annotated verdict ("fail
    # (explanation)") was silently dropped, undercounting real worksheets
    # by a large margin. See DECISION_LOG.md.
    result = parse_worksheet(SAMPLE)
    check("verdict with a trailing rationale in parens still parsed",
          result["case_one"].get("disagreement") == "fail", str(result["case_one"]))


def test_empty_worksheet_returns_empty() -> None:
    check("no case headers -> empty result", parse_worksheet("no case headers here") == {})


def run_tests() -> int:
    test_parses_verdicts_per_case()
    test_blank_verdict_excluded()
    test_uppercase_verdict_normalized()
    test_prose_lines_ignored()
    test_trailing_rationale_after_verdict_still_parses()
    test_empty_worksheet_returns_empty()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
