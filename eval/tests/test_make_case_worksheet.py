"""
Tests for make_case_worksheet.py. Stdlib only, same convention as every
other test file in this project (no pytest).

    python -m eval.tests.test_make_case_worksheet
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import eval.make_case_worksheet as mcw

_ABSTRACT = (
    "Carriers of the variant showed a markedly increased risk of disease in this cohort, "
    "with a hazard ratio of 3.4 (95% CI 2.1-5.5). This sentence sits well past the 400th "
    "character of the section, which is exactly where the old kappa worksheet used to cut "
    "the text off, so a test that the full span is rendered has to run past that mark to "
    "mean anything at all. Padding follows to be certain we clear it: "
    + "lorem ipsum dolor sit amet, " * 12
)


def _write_article(xml_dir: Path, pmcid: str, abstract: str) -> None:
    xml_dir.mkdir(parents=True, exist_ok=True)
    (xml_dir / f"{pmcid}.xml").write_text(
        f"<article><front><abstract><p>{abstract}</p></abstract></front></article>"
    )


def _case(case_id: str, ctype: str, spans: list[dict] | None = None) -> dict:
    return {
        "case_id": case_id,
        "stratum": "evidence",
        "is_negative_case": ctype == "negative",
        "gene": "BRCA1", "variant": "c.68_69delAG", "condition": "breast cancer",
        "query": f"query for {case_id}",
        "gold_spans": spans or [],
        "gold": {
            "direction": None if ctype == "negative" else "increased risk",
            "strength": None if ctype == "negative" else "strong",
            "has_disagreement": ctype == "disagreement",
            "disagreement_note": "A says up, B says flat." if ctype == "disagreement" else "",
            "expected_not_found": ctype == "negative",
        },
        "held_out_pmcids": [],
        "notes": f"notes for {case_id}",
        "created_by": "agent:test",
        "created_at_utc": "2026-09-03T00:00:00Z",
    }


class TestSampling(unittest.TestCase):
    def test_takes_one_of_every_type_before_filling_up(self):
        cases = ([_case(f"ord{i}", "ordinary") for i in range(10)]
                 + [_case("neg1", "negative"), _case("dis1", "disagreement")])
        picked = mcw.sample_cases(cases, n=3, seed=0)
        self.assertEqual({mcw.case_type(c) for c in picked},
                         {"ordinary", "negative", "disagreement"})

    def test_is_seeded_and_reproducible(self):
        cases = [_case(f"ord{i}", "ordinary") for i in range(10)]
        a = [c["case_id"] for c in mcw.sample_cases(cases, n=4, seed=7)]
        b = [c["case_id"] for c in mcw.sample_cases(cases, n=4, seed=7)]
        self.assertEqual(a, b)

    def test_never_returns_more_than_n_or_more_than_available(self):
        cases = [_case("ord1", "ordinary"), _case("neg1", "negative")]
        self.assertEqual(len(mcw.sample_cases(cases, n=8, seed=0)), 2)
        self.assertEqual(len(mcw.sample_cases(cases, n=1, seed=0)), 1)

    def test_case_type_matches_the_split_strata(self):
        self.assertEqual(mcw.case_type(_case("a", "negative")), "negative")
        self.assertEqual(mcw.case_type(_case("a", "disagreement")), "disagreement")
        self.assertEqual(mcw.case_type(_case("a", "ordinary")), "ordinary")


class TestRendering(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xml_dir = Path(self.tmp.name) / "xml"
        _write_article(self.xml_dir, "PMC1", _ABSTRACT)

    def tearDown(self):
        self.tmp.cleanup()

    def test_span_text_is_rendered_in_full_not_truncated(self):
        """The regression that matters: docs/DECISION_LOG.md's kappa
        truncation bug. A reviewer graded on less evidence than the judge
        had produced disagreements that were artifacts of the display."""
        span = {"pmcid": "PMC1", "section": "abstract", "char_start": 0, "char_end": len(_ABSTRACT)}
        out = mcw.render_case(_case("ord1", "ordinary", [span]), 1, self.xml_dir)
        self.assertIn("lorem ipsum dolor sit amet", out)
        self.assertIn(_ABSTRACT[-40:], out)
        self.assertGreater(len(out), 500)

    def test_unresolvable_span_is_surfaced_not_silently_skipped(self):
        span = {"pmcid": "PMC_MISSING", "section": "abstract", "char_start": 0, "char_end": 10}
        out = mcw.render_case(_case("ord1", "ordinary", [span]), 1, self.xml_dir)
        self.assertIn("COULD NOT RESOLVE", out)
        self.assertIn("missing_file", out)

    def test_negative_case_renders_the_absence_claim_and_no_span_block(self):
        out = mcw.render_case(_case("neg1", "negative"), 1, self.xml_dir)
        self.assertIn("NO grounding", out)
        self.assertIn("notes for neg1", out)
        self.assertNotIn("Gold spans", out)

    def test_disagreement_case_renders_the_claimed_conflict(self):
        out = mcw.render_case(_case("dis1", "disagreement"), 1, self.xml_dir)
        self.assertIn("A says up, B says flat.", out)

    def test_every_case_gets_verdict_blanks(self):
        for ctype in ("ordinary", "negative", "disagreement"):
            out = mcw.render_case(_case("c1", ctype), 1, self.xml_dir)
            self.assertIn("- **verdict:** ___", out)
            self.assertIn("- **why:** ___", out)


class TestSummarize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ws.md"

    def tearDown(self):
        self.tmp.cleanup()

    def _parse(self, text: str) -> int:
        self.path.write_text(text)
        return mcw.summarize(self.path)

    def test_counts_filled_verdicts(self):
        text = (
            "## Case 1: `a`\n- **verdict:** valid\n- **why:** looks right\n"
            "## Case 2: `b`\n- **verdict:** wrong\n- **why:** span is off topic\n"
            "## Case 3: `c`\n- **verdict:** unsure\n- **why:** need more reading\n"
        )
        self.assertEqual(self._parse(text), 0)

    def test_unfilled_blank_is_not_counted_as_a_verdict(self):
        """A half-finished worksheet must not read as a completed pass."""
        self.path.write_text("## Case 1: `a`\n- **verdict:** ___\n- **why:** ___\n")
        parsed = []
        for line in self.path.read_text().splitlines():
            m = mcw._VERDICT_RE.match(line.strip())
            if m:
                parsed.append(m.group(1).strip())
        self.assertEqual(parsed, ["___"])
        self.assertNotIn("___", mcw.VERDICTS)

    def test_empty_file_is_an_error_not_a_clean_pass(self):
        self.assertEqual(self._parse("nothing here\n"), 1)



class TestStrengthFocus(unittest.TestCase):
    """The strength worksheet uses a different heading format from the case
    worksheet. One parser has to read both, or a filled-in strength review
    silently summarizes as zero cases (which it did on the first run)."""

    def test_parser_reads_both_heading_formats(self):
        case_heading = "## Case 3: `abc`"
        strength_heading = "## 3. `abc`  (dev split)"
        for heading in (case_heading, strength_heading):
            m = mcw._CASE_RE.match(heading)
            self.assertIsNotNone(m, heading)
            self.assertEqual(m.group(1), "abc")

    def test_strength_case_renders_scale_assignment_and_evidence(self):
        tmp = tempfile.TemporaryDirectory()
        xml_dir = Path(tmp.name) / "xml"
        _write_article(xml_dir, "PMC1", _ABSTRACT)
        case = _case("ord1", "ordinary",
                     [{"pmcid": "PMC1", "section": "abstract",
                       "char_start": 0, "char_end": len(_ABSTRACT)}])
        case["gold"]["strength"] = "high"
        case["gold"]["strength_detail"] = "hazard ratio of 3.4"
        case["gold"]["qualifier"] = "conditional on complete loss"
        out = mcw.render_strength_case(case, 1, xml_dir, {"ord1": "dev"})
        self.assertIn("Assigned strength: `high`", out)
        self.assertIn("hazard ratio of 3.4", out)
        self.assertIn("conditional on complete loss", out)
        self.assertIn("hazard ratio of 3.4 (95% CI 2.1-5.5)", out)  # the evidence itself
        self.assertIn("- **verdict:** ___", out)
        tmp.cleanup()


class TestVerdictParsing(unittest.TestCase):
    """The worst bug this file has had. A rater wrote five verdicts as
    "wrong (should be unstated)"; the parser matched only a bare verdict
    word, discarded all five as unparseable, reported them as UNFILLED, and
    printed "valid 6 (100%)" over a real 45% error rate. A summary tool
    that turns corrections into a clean sheet is worse than no tool."""

    def test_bare_verdicts(self):
        for v in mcw.VERDICTS:
            self.assertEqual(mcw._parse_verdict(v), v)

    def test_qualified_verdicts_keep_their_verdict(self):
        for raw, expected in [
            ("wrong (should be unstated)", "wrong"),
            ("wrong (should be moderate)", "wrong"),
            ("wrong (should be low or high)", "wrong"),
            ("valid, though borderline", "valid"),
            ("unsure (need the full paper)", "unsure"),
        ]:
            self.assertEqual(mcw._parse_verdict(raw), expected, raw)

    def test_case_and_markup_insensitive(self):
        self.assertEqual(mcw._parse_verdict("**WRONG** (should be low)"), "wrong")

    def test_unfilled_blank_is_still_not_a_verdict(self):
        self.assertNotIn(mcw._parse_verdict("___"), mcw.VERDICTS)

    def test_a_word_merely_containing_a_verdict_is_not_one(self):
        """"wrongly" must not parse as "wrong"."""
        self.assertNotIn(mcw._parse_verdict("wrongly filed"), mcw.VERDICTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
