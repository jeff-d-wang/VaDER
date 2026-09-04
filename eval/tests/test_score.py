"""Stdlib-only tests for score.py, using judge.FakeJudge (no network, no API
key needed). Run directly: python -m eval.tests.test_score

These test the scorer's own branching logic (bucket thresholds, N/A
handling, negative-case special-casing), not judgment quality: FakeJudge's
crude word-overlap heuristic is not a real groundedness judge, see
judge.py's docstring.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import json

import eval.score as score
import eval.split as split_mod
from eval.judge import FakeJudge
from eval.score import Claim, SystemAnswer, score_case, summarize, wilson_ci

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


XML_TEMPLATE = """<article>
  <front><article-meta><abstract>
    <p>{abstract}</p>
  </abstract></article-meta></front>
  <body><p>{body}</p></body>
</article>
"""

EVIDENCE_CASE = {
    "case_id": "ev1", "stratum": "evidence", "is_negative_case": False,
    "gene": "BRCA1", "variant": None, "condition": "breast cancer",
    "query": "What does the literature say about BRCA1 and breast cancer risk?",
    "gold_spans": [{"pmcid": "PMC1", "section": "abstract", "char_start": 0, "char_end": 60}],
    "gold": {
        "direction": "pathogenic increases risk", "strength": "high",
        "has_disagreement": True,
        "disagreement_note": "Study A found elevated risk in carriers; Study B found no significant association in a different cohort.",
        "expected_not_found": False,
    },
}

NEGATIVE_CASE = {
    "case_id": "neg1", "stratum": "evidence", "is_negative_case": True,
    "gene": "PALB2", "variant": "c.1del", "condition": "pancreatic cancer",
    "query": "What does the literature say about PALB2 c.1del and pancreatic cancer?",
    "gold_spans": [],
    "gold": {"direction": None, "strength": None, "has_disagreement": False,
              "disagreement_note": "", "expected_not_found": True},
}

METHODS_CASE = {
    "case_id": "meth1", "stratum": "methods_extraction",
    "query": "What genome build did this study use?",
    "gold": {"expected_value": "GRCh38", "expected_pmcids": ["PMC1"]},
}


def make_xml_dir(tmp: str, abstract="BRCA1 pathogenic variants increase breast cancer risk substantially in carriers.",
                  body="Unrelated body text.") -> Path:
    xml_dir = Path(tmp)
    (xml_dir / "PMC1.xml").write_text(XML_TEMPLATE.format(abstract=abstract, body=body))
    return xml_dir


def test_evidence_pass_case() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(
            case_id="ev1", direction="pathogenic, increases risk", strength="high",
            not_found=False,
            answer_text="Study A and Study B disagree: Study A found elevated risk while Study B found no significant association.",
            claims=[Claim(
                text="BRCA1 pathogenic variants increase breast cancer risk",
                cited_pmcid="PMC1", cited_section="abstract", cited_char_start=0, cited_char_end=60,
            )],
        )
        result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
        check("direction scored", result.direction is not None)
        check("direction passes on matching claim", result.direction.verdict in ("pass", "partial"),
              result.direction.rationale)
        check("groundedness scored", result.groundedness is not None)
        check("groundedness passes: claim text overlaps cited span",
              result.groundedness.verdict == "pass", result.groundedness.rationale)
        check("disagreement scored (gold.has_disagreement True)", result.disagreement is not None)
        check("disagreement passes: answer states conflict + overlaps note",
              result.disagreement.verdict == "pass", result.disagreement.rationale)
        check("not_found scored as reverse/extended check", result.not_found is not None)
        check("not_found passes: system did not refuse", result.not_found.verdict == "pass")
        check("not_found note flags this as the extended check", result.not_found.note == "extended_check")


def test_evidence_no_claims_fails_groundedness() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(case_id="ev1", direction="pathogenic", not_found=False, claims=[])
        result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
        check("no claims -> groundedness fails, not silently N/A",
              result.groundedness.verdict == "fail" and result.groundedness.note == "empty_claims")


def test_evidence_wrong_refusal_fails_not_found() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(case_id="ev1", answer_text="This is not found in this corpus.", not_found=True)
        result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
        check("wrongly refusing an answerable case fails not_found",
              result.not_found.verdict == "fail", result.not_found.rationale)


def test_negative_case_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(case_id="neg1", not_found=True,
                               answer_text="This variant is not found in this corpus.")
        result = score_case(NEGATIVE_CASE, answer, FakeJudge(), xml_dir)
        check("negative case: direction is N/A", result.direction is None)
        check("negative case: disagreement is N/A", result.disagreement is None)
        check("negative case: groundedness is N/A when no claims made", result.groundedness is None)
        check("negative case: not_found passes on correct refusal", result.not_found.verdict == "pass")


def test_negative_case_fabrication_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        answer = SystemAnswer(case_id="neg1", not_found=False,
                               answer_text="This variant is associated with increased risk.",
                               claims=[Claim("fabricated claim", "PMC1", "abstract", 0, 20)])
        result = score_case(NEGATIVE_CASE, answer, FakeJudge(), xml_dir)
        check("negative case: fabricated answer fails not_found",
              result.not_found.verdict == "fail", result.not_found.rationale)
        check("negative case: groundedness still scored since claims were (wrongly) made",
              result.groundedness is not None)


def test_groundedness_bucketing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        good_claim = Claim("BRCA1 pathogenic variants increase breast cancer risk",
                            "PMC1", "abstract", 0, 80)
        bad_claim = Claim("completely unrelated statement about zebrafish migration patterns",
                           "PMC1", "abstract", 0, 80)
        # 1/1 supported -> pass
        a1 = SystemAnswer(case_id="ev1", direction="x", claims=[good_claim])
        r1 = score_case(EVIDENCE_CASE, a1, FakeJudge(), xml_dir)
        check("1/1 grounded claims -> pass", r1.groundedness.verdict == "pass")

        # 1/3 supported -> fail (33%)
        a2 = SystemAnswer(case_id="ev1", direction="x", claims=[good_claim, bad_claim, bad_claim])
        r2 = score_case(EVIDENCE_CASE, a2, FakeJudge(), xml_dir)
        check("1/3 grounded claims -> fail", r2.groundedness.verdict == "fail", r2.groundedness.rationale)


def test_groundedness_unresolvable_citation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        claim = Claim("some claim text here", "PMC_DOES_NOT_EXIST", "abstract", 0, 10)
        answer = SystemAnswer(case_id="ev1", claims=[claim])
        result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
        check("citation to a missing article counts as unsupported, not a crash",
              result.groundedness.verdict == "fail")
        check("rationale names the unresolvable citation", "missing_file" in result.groundedness.rationale)


def test_methods_extraction() -> None:
    correct = SystemAnswer(case_id="meth1", parameter_value="GRCh38", cited_pmcid="PMC1")
    wrong_value = SystemAnswer(case_id="meth1", parameter_value="GRCh37", cited_pmcid="PMC1")
    wrong_cite = SystemAnswer(case_id="meth1", parameter_value="GRCh38", cited_pmcid="PMC999")

    r_correct = score_case(METHODS_CASE, correct, FakeJudge(), Path("."))
    check("methods: correct value+citation both pass",
          r_correct.parameter_accuracy.verdict == "pass" and r_correct.citation.verdict == "pass")
    check("methods: direction/groundedness/disagreement all N/A for this stratum",
          r_correct.direction is None and r_correct.groundedness is None and r_correct.disagreement is None)

    r_wrong_value = score_case(METHODS_CASE, wrong_value, FakeJudge(), Path("."))
    check("methods: wrong parameter value fails, citation still passes",
          r_wrong_value.parameter_accuracy.verdict == "fail" and r_wrong_value.citation.verdict == "pass")

    r_wrong_cite = score_case(METHODS_CASE, wrong_cite, FakeJudge(), Path("."))
    check("methods: wrong citation fails independently of parameter value",
          r_wrong_cite.citation.verdict == "fail")


def test_summarize_excludes_na_from_denominator() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_xml_dir(tmp)
        neg_answer = SystemAnswer(case_id="neg1", not_found=True)
        ev_answer = SystemAnswer(case_id="ev1", direction="pathogenic",
                                  claims=[Claim("BRCA1 pathogenic variants increase breast cancer risk",
                                                "PMC1", "abstract", 0, 80)])
        scores = [
            score_case(NEGATIVE_CASE, neg_answer, FakeJudge(), xml_dir),
            score_case(EVIDENCE_CASE, ev_answer, FakeJudge(), xml_dir),
        ]
        summary = summarize(scores)
        check("direction summary only counts the 1 case where it applied",
              summary["direction"]["n"] == 1, str(summary.get("direction")))
        check("not_found summary counts both cases (applies to both strata)",
              summary["not_found"]["n"] == 2, str(summary.get("not_found")))


def test_wilson_ci() -> None:
    low, high = wilson_ci(0, 0)
    check("n=0 doesn't divide by zero", (low, high) == (0.0, 0.0))

    low, high = wilson_ci(4, 4)
    check("4/4 interval stays within [0,1], doesn't blow up to >1",
          0.0 <= low <= high <= 1.0 and high == 1.0, str((low, high)))
    check("4/4 interval is still wide (small n, honest uncertainty)", low < 0.6, str(low))

    low, high = wilson_ci(0, 4)
    check("0/4 interval stays within [0,1], doesn't go below 0",
          0.0 <= low <= high <= 1.0 and low == 0.0, str((low, high)))

    low, high = wilson_ci(150, 300)
    check("large n: interval tight around 0.5", high - low < 0.15, str((low, high)))
    check("large n: point estimate inside its own interval", low <= 0.5 <= high)


def test_held_out_default_excludes_it() -> None:
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        xml_dir = make_xml_dir(tmp)
        cases_path = tmp_path / "cases.jsonl"
        with open(cases_path, "w") as f:
            f.write(json.dumps(EVIDENCE_CASE) + "\n")
            f.write(json.dumps(NEGATIVE_CASE) + "\n")
        answers_path = tmp_path / "answers.jsonl"
        with open(answers_path, "w") as f:
            f.write(json.dumps({"case_id": "ev1", "not_found": False, "claims": []}) + "\n")
            f.write(json.dumps({"case_id": "neg1", "not_found": True}) + "\n")

        split_mod.CASES_PATH = cases_path
        split_mod.SPLIT_PATH = tmp_path / "split.csv"
        split_mod.TOUCHES_PATH = tmp_path / "touches.csv"
        with open(split_mod.SPLIT_PATH, "w") as f:
            f.write("case_id,split,case_type,assigned_at_utc,seed\n")
            f.write("ev1,dev,ordinary,2026-01-01T00:00:00Z,0\n")
            f.write("neg1,held_out,negative,2026-01-01T00:00:00Z,0\n")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = score.main(["--answers", str(answers_path), "--judge", "fake",
                              "--cases", str(cases_path), "--xml-dir", str(xml_dir)])
        check("exit code 0 on default (exclude) run", rc == 0)
        check("only the dev case (ev1) was scored, held-out case excluded",
              "Scored 1/1 cases" in buf.getvalue(), buf.getvalue())
        check("no touch recorded on the default exclude path", split_mod.count_touches() == 0)

        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            rc2 = score.main(["--answers", str(answers_path), "--judge", "fake",
                               "--cases", str(cases_path), "--xml-dir", str(xml_dir),
                               "--held-out", "only", "--touch-reason", "unit test"])
        check("exit code 0 on --held-out only run", rc2 == 0)
        check("only the held-out case (neg1) was scored",
              "Scored 1/1 cases" in buf2.getvalue(), buf2.getvalue())
        check("a touch WAS recorded when --held-out only was used", split_mod.count_touches() == 1)


def test_held_out_requires_touch_reason() -> None:
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        answers_path = tmp_path / "answers.jsonl"
        answers_path.write_text("")
        cases_path = tmp_path / "cases.jsonl"
        cases_path.write_text("")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = score.main(["--answers", str(answers_path), "--cases", str(cases_path),
                              "--held-out", "include"])
        check("refuses --held-out include without --touch-reason", rc != 0)
        check("error message explains why", "touch-reason" in buf.getvalue(), buf.getvalue())


def run_tests() -> int:
    test_evidence_pass_case()
    test_evidence_no_claims_fails_groundedness()
    test_evidence_wrong_refusal_fails_not_found()
    test_negative_case_pass()
    test_negative_case_fabrication_fails()
    test_groundedness_bucketing()
    test_groundedness_unresolvable_citation()
    test_methods_extraction()
    test_summarize_excludes_na_from_denominator()
    test_wilson_ci()
    test_held_out_default_excludes_it()
    test_held_out_requires_touch_reason()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
