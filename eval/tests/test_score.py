"""Stdlib-only tests for score.py, using judge.FakeJudge (no network, no API
key needed). Run directly: python -m eval.tests.test_score

These test the scorer's own branching logic (bucket thresholds, N/A
handling, negative-case special-casing), not judgment quality: FakeJudge's
crude word-overlap heuristic is not a real groundedness judge, see
judge.py's docstring.
"""
from __future__ import annotations

import unittest

import tempfile
from pathlib import Path

import json

import eval.score as score
import eval.split as split_mod
from eval.judge import FakeJudge
from eval.score import Claim, SystemAnswer, score_case, summarize, wilson_ci

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
        "direction": "increased", "strength": "high",
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

def make_xml_dir(tmp: str, abstract="BRCA1 pathogenic variants increase breast cancer risk substantially in carriers.",
                  body="Unrelated body text.") -> Path:
    xml_dir = Path(tmp)
    (xml_dir / "PMC1.xml").write_text(XML_TEMPLATE.format(abstract=abstract, body=body))
    return xml_dir


class TestScore(unittest.TestCase):
    def test_evidence_pass_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            answer = SystemAnswer(
                case_id="ev1", direction="increased", strength="high",
                not_found=False,
                answer_text="Study A and Study B disagree: Study A found elevated risk while Study B found no significant association.",
                claims=[Claim(
                    text="BRCA1 pathogenic variants increase breast cancer risk",
                    cited_pmcid="PMC1", cited_section="abstract", cited_char_start=0, cited_char_end=60,
                )],
            )
            result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
            self.assertIsNotNone(result.direction, "direction scored")
            self.assertTrue(result.direction.verdict in ("pass", "partial"), "%s -- %s" % ("direction passes on matching claim", result.direction.rationale))
            self.assertIsNotNone(result.groundedness, "groundedness scored")
            self.assertTrue(result.groundedness.verdict == "pass", "%s -- %s" % ("groundedness passes: claim text overlaps cited span", result.groundedness.rationale))
            self.assertIsNotNone(result.disagreement, "disagreement scored (gold.has_disagreement True)")
            self.assertTrue(result.disagreement.verdict == "pass", "%s -- %s" % ("disagreement passes: answer states conflict + overlaps note", result.disagreement.rationale))
            self.assertIsNotNone(result.not_found, "not_found scored as reverse/extended check")
            self.assertEqual(result.not_found.verdict, "pass", "not_found passes: system did not refuse")
            self.assertEqual(result.not_found.note, "extended_check", "not_found note flags this as the extended check")

    def test_evidence_no_claims_fails_groundedness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            answer = SystemAnswer(case_id="ev1", direction="increased", not_found=False, claims=[])
            result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
            self.assertTrue(result.groundedness.verdict == "fail" and result.groundedness.note == "empty_claims", "no claims -> groundedness fails, not silently N/A")

    def test_evidence_wrong_refusal_fails_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            answer = SystemAnswer(case_id="ev1", answer_text="This is not found in this corpus.", not_found=True)
            result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
            self.assertTrue(result.not_found.verdict == "fail", "%s -- %s" % ("wrongly refusing an answerable case fails not_found", result.not_found.rationale))

    def test_negative_case_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            answer = SystemAnswer(case_id="neg1", not_found=True,
                                   answer_text="This variant is not found in this corpus.")
            result = score_case(NEGATIVE_CASE, answer, FakeJudge(), xml_dir)
            self.assertIsNone(result.direction, "negative case: direction is N/A")
            self.assertIsNone(result.disagreement, "negative case: disagreement is N/A")
            self.assertIsNone(result.groundedness, "negative case: groundedness is N/A when no claims made")
            self.assertEqual(result.not_found.verdict, "pass", "negative case: not_found passes on correct refusal")

    def test_negative_case_fabrication_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            answer = SystemAnswer(case_id="neg1", not_found=False,
                                   answer_text="This variant is associated with increased risk.",
                                   claims=[Claim("fabricated claim", "PMC1", "abstract", 0, 20)])
            result = score_case(NEGATIVE_CASE, answer, FakeJudge(), xml_dir)
            self.assertTrue(result.not_found.verdict == "fail", "%s -- %s" % ("negative case: fabricated answer fails not_found", result.not_found.rationale))
            self.assertIsNotNone(result.groundedness, "negative case: groundedness still scored since claims were (wrongly) made")

    def test_groundedness_bucketing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            good_claim = Claim("BRCA1 pathogenic variants increase breast cancer risk",
                                "PMC1", "abstract", 0, 80)
            bad_claim = Claim("completely unrelated statement about zebrafish migration patterns",
                               "PMC1", "abstract", 0, 80)
            # 1/1 supported -> pass
            a1 = SystemAnswer(case_id="ev1", direction="increased", claims=[good_claim])
            r1 = score_case(EVIDENCE_CASE, a1, FakeJudge(), xml_dir)
            self.assertEqual(r1.groundedness.verdict, "pass", "1/1 grounded claims -> pass")

            # 1/3 supported -> fail (33%)
            a2 = SystemAnswer(case_id="ev1", direction="increased", claims=[good_claim, bad_claim, bad_claim])
            r2 = score_case(EVIDENCE_CASE, a2, FakeJudge(), xml_dir)
            self.assertTrue(r2.groundedness.verdict == "fail", "%s -- %s" % ("1/3 grounded claims -> fail", r2.groundedness.rationale))

    def test_groundedness_unresolvable_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            claim = Claim("some claim text here", "PMC_DOES_NOT_EXIST", "abstract", 0, 10)
            answer = SystemAnswer(case_id="ev1", claims=[claim])
            result = score_case(EVIDENCE_CASE, answer, FakeJudge(), xml_dir)
            self.assertTrue(result.groundedness.verdict == "fail", "citation to a missing article counts as unsupported, not a crash")
            self.assertIn("missing_file", result.groundedness.rationale, "rationale names the unresolvable citation")

    def test_summarize_excludes_na_from_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_xml_dir(tmp)
            neg_answer = SystemAnswer(case_id="neg1", not_found=True)
            ev_answer = SystemAnswer(case_id="ev1", direction="increased",
                                      claims=[Claim("BRCA1 pathogenic variants increase breast cancer risk",
                                                    "PMC1", "abstract", 0, 80)])
            scores = [
                score_case(NEGATIVE_CASE, neg_answer, FakeJudge(), xml_dir),
                score_case(EVIDENCE_CASE, ev_answer, FakeJudge(), xml_dir),
            ]
            summary = summarize(scores)
            self.assertTrue(summary["direction"]["n"] == 1, "%s -- %s" % ("direction summary only counts the 1 case where it applied", str(summary.get("direction"))))
            self.assertTrue(summary["not_found"]["n"] == 2, "%s -- %s" % ("not_found summary counts both cases (applies to both strata)", str(summary.get("not_found"))))

    def test_wilson_ci(self) -> None:
        low, high = wilson_ci(0, 0)
        self.assertEqual((low, high), (0.0, 0.0), "n=0 doesn't divide by zero")

        low, high = wilson_ci(4, 4)
        self.assertTrue(0.0 <= low <= high <= 1.0 and high == 1.0, "%s -- %s" % ("4/4 interval stays within [0,1], doesn't blow up to >1", str((low, high))))
        self.assertTrue(low < 0.6, "%s -- %s" % ("4/4 interval is still wide (small n, honest uncertainty)", str(low)))

        low, high = wilson_ci(0, 4)
        self.assertTrue(0.0 <= low <= high <= 1.0 and low == 0.0, "%s -- %s" % ("0/4 interval stays within [0,1], doesn't go below 0", str((low, high))))

        low, high = wilson_ci(150, 300)
        self.assertTrue(high - low < 0.15, "%s -- %s" % ("large n: interval tight around 0.5", str((low, high))))
        self.assertTrue(low <= 0.5 <= high, "large n: point estimate inside its own interval")

    def test_held_out_default_excludes_it(self) -> None:
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
                rc = score.main(["--answers", str(answers_path), "--judge", "fake", "--exploratory",
                                  "--cases", str(cases_path), "--xml-dir", str(xml_dir)])
            self.assertEqual(rc, 0, "exit code 0 on default (exclude) run")
            self.assertTrue("Scored 1/1 cases" in buf.getvalue(), "%s -- %s" % ("only the dev case (ev1) was scored, held-out case excluded", buf.getvalue()))
            self.assertEqual(split_mod.count_touches(), 0, "no touch recorded on the default exclude path")

            buf2 = io.StringIO()
            with contextlib.redirect_stdout(buf2):
                rc2 = score.main(["--answers", str(answers_path), "--judge", "fake", "--exploratory",
                                   "--cases", str(cases_path), "--xml-dir", str(xml_dir),
                                   "--held-out", "only", "--touch-reason", "unit test"])
            self.assertEqual(rc2, 0, "exit code 0 on --held-out only run")
            self.assertTrue("Scored 1/1 cases" in buf2.getvalue(), "%s -- %s" % ("only the held-out case (neg1) was scored", buf2.getvalue()))
            self.assertEqual(split_mod.count_touches(), 1, "a touch WAS recorded when --held-out only was used")

    def test_held_out_requires_touch_reason(self) -> None:
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
            self.assertNotEqual(rc, 0, "refuses --held-out include without --touch-reason")
            self.assertIn("touch-reason", buf.getvalue(), "%s -- %s" % ("error message explains why", buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
