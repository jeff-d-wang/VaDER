"""Stdlib-only tests for make_kappa_worksheet.py. Run directly:
python test_make_kappa_worksheet.py"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from make_kappa_worksheet import format_case
from score import Claim, SystemAnswer

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


EVIDENCE_DISAGREEMENT_CASE = {
    "case_id": "ev1", "is_negative_case": False,
    "query": "does X cause Y?",
    "gold": {
        "direction": "increased risk", "strength": "moderate",
        "has_disagreement": True, "disagreement_note": "Study A says yes, Study B says no.",
    },
}

EVIDENCE_PLAIN_CASE = {
    "case_id": "ev2", "is_negative_case": False,
    "query": "does A cause B?",
    "gold": {"direction": "increased risk", "strength": "high", "has_disagreement": False,
              "disagreement_note": ""},
}

NEGATIVE_CASE = {
    "case_id": "neg1", "is_negative_case": True,
    "query": "does Z cause W?",
    "gold": {"direction": None, "strength": None, "has_disagreement": False,
              "disagreement_note": "", "expected_not_found": True},
}

XML_TEMPLATE = """<article><front><article-meta><abstract><p>{abstract}</p></abstract>
</article-meta></front><body><p>{body}</p></body></article>
"""


def make_xml_dir(tmp: str) -> Path:
    xml_dir = Path(tmp)
    (xml_dir / "PMC1.xml").write_text(XML_TEMPLATE.format(
        abstract="A causes B strongly, confirmed in this cohort study.", body="unrelated"))
    return xml_dir


def test_negative_case_shows_only_says_not_found() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(case_id="neg1", not_found=True, answer_text="not found in this corpus.")
        section = format_case(NEGATIVE_CASE, answer, xml_dir)
        check("negative case shows the says_not_found blank", "says_not_found: ___" in section)
        check("negative case does NOT show direction/groundedness blanks",
              "direction: ___" not in section and "groundedness: ___" not in section)
        check("negative case does not show a gold direction line",
              "Gold direction:" not in section)


def test_disagreement_case_shows_extra_line() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(case_id="ev1", direction="x", answer_text="answer", claims=[])
        section = format_case(EVIDENCE_DISAGREEMENT_CASE, answer, xml_dir)
        check("disagreement case shows the disagreement blank", "- disagreement: ___" in section)
        check("disagreement case shows the gold disagreement note",
              "Study A says yes, Study B says no." in section)


def test_plain_evidence_case_omits_disagreement_line() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(case_id="ev2", direction="x", answer_text="answer", claims=[])
        section = format_case(EVIDENCE_PLAIN_CASE, answer, xml_dir)
        check("no-disagreement evidence case omits the disagreement blank",
              "- disagreement: ___" not in section)
        check("still shows direction and groundedness blanks",
              "direction: ___" in section and "groundedness: ___" in section)


def test_claims_resolved_to_real_source_text() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        claim = Claim("A causes B", "PMC1", "abstract", 0, 20)
        answer = SystemAnswer(case_id="ev2", direction="x", answer_text="answer", claims=[claim])
        section = format_case(EVIDENCE_PLAIN_CASE, answer, xml_dir)
        check("resolved claim shows real source text, not a placeholder",
              "A causes B strongly" in section, section)


def test_unresolvable_claim_shown_not_hidden() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        claim = Claim("fabricated", "PMC_MISSING", "abstract", 0, 20)
        answer = SystemAnswer(case_id="ev2", direction="x", answer_text="answer", claims=[claim])
        section = format_case(EVIDENCE_PLAIN_CASE, answer, xml_dir)
        check("an unresolvable citation is surfaced in the worksheet, not silently dropped",
              "does not resolve" in section, section)


def run_tests() -> int:
    test_negative_case_shows_only_says_not_found()
    test_disagreement_case_shows_extra_line()
    test_plain_evidence_case_omits_disagreement_line()
    test_claims_resolved_to_real_source_text()
    test_unresolvable_claim_shown_not_hidden()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
