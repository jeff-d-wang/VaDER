"""Stdlib-only tests for corpus_text.py and verify_spans.py. Run directly:
    python -m eval.tests.test_verify_spans
"""
from __future__ import annotations

import unittest

import tempfile
from pathlib import Path

from common.corpus_text import extract_section_text, find_quote
from eval.verify_spans import expand_to_paragraph, extract_quotes

SAMPLE_XML = """<article>
  <front><article-meta><abstract>
    <p>First abstract paragraph about BRCA1 and breast cancer risk.</p>
    <p>Second abstract paragraph with more detail on penetrance.</p>
  </abstract></article-meta></front>
  <body>
    <p>Body paragraph one, unrelated content here.</p>
    <p>Body paragraph two mentions the "smoking gun" phrase for testing.</p>
  </body>
</article>
"""

NO_P_XML = """<article>
  <front><article-meta><abstract>Bare abstract text, no child p elements at all.</abstract></article-meta></front>
  <body><p>One body paragraph.</p></body>
</article>
"""


class TestVerifySpans(unittest.TestCase):
    def test_extract_section_text(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "PMC1.xml"
            path.write_text(SAMPLE_XML)
            abstract = extract_section_text(path, "abstract")
            self.assertTrue(abstract == "First abstract paragraph about BRCA1 and breast cancer risk."
                              "\nSecond abstract paragraph with more detail on penetrance.", "%s -- %s" % ("abstract joins paragraphs with newline", repr(abstract)))
            body = extract_section_text(path, "body")
            self.assertTrue(body is not None and "smoking gun" in body, "body extraction finds both paragraphs")
            self.assertIsNone(extract_section_text(path, "references"), "unknown section returns None")

            no_p_path = Path(d) / "PMC2.xml"
            no_p_path.write_text(NO_P_XML)
            bare = extract_section_text(no_p_path, "abstract")
            self.assertTrue(bare == "Bare abstract text, no child p elements at all.", "%s -- %s" % ("bare abstract with no <p> falls back to node text", repr(bare)))

            missing = extract_section_text(Path(d) / "PMC404.xml", "abstract")
            self.assertIsNone(missing, "missing file returns None")

    def test_find_quote(self) -> None:
        haystack = "The gene shows a 'dominant-negative' effect, per the report."
        exact = "dominant-negative"
        r = find_quote(haystack, exact)
        self.assertEqual(r, (18, 35), "%s -- %s" % ("exact substring found", str(r)))
        self.assertEqual(haystack[r[0]:r[1]], exact, "offsets round-trip")

        curly = "The gene shows a ‘dominant‑negative’ effect."  # curly quotes + non-breaking hyphen... actually use en dash
        curly = "Effects were “clearly pathogenic” in this cohort."
        r2 = find_quote(curly, 'clearly pathogenic')
        self.assertIsNotNone(r2, "curly-quote text still matches a straight-quote needle")

        spaced = "Multiple   spaces\nand\ta newline separate these words in the source."
        r3 = find_quote(spaced, "Multiple spaces and a newline separate")
        self.assertIsNotNone(r3, "%s -- %s" % ("whitespace-collapsed needle matches whitespace-irregular haystack", str(r3)))
        if r3:
            self.assertTrue(spaced[r3[0]:r3[1]].split() == "Multiple   spaces\nand\ta newline separate".split(), "mapped offsets land on real text")

        self.assertIsNone(find_quote(haystack, "not in here at all"), "absent quote returns None")

    def test_expand_to_paragraph(self) -> None:
        text = "Para one text.\nPara two has the anchor phrase in it.\nPara three."
        anchor = "anchor phrase"
        i = text.find(anchor)
        s, e = expand_to_paragraph(text, i, i + len(anchor))
        self.assertTrue(text[s:e] == "Para two has the anchor phrase in it.", "%s -- %s" % ("expands to the containing paragraph, not neighbors", repr(text[s:e])))

        # match touching the very start / end of the whole string
        s0, e0 = expand_to_paragraph(text, 0, 5)
        self.assertEqual(s0, 0, "%s -- %s" % ("match at string start doesn't underflow", str(s0)))
        last = text.rfind("Para three")
        s1, e1 = expand_to_paragraph(text, last, len(text))
        self.assertEqual(e1, len(text), "%s -- %s" % ("match at string end extends to len(text)", str(e1)))

        single = "Only one paragraph, no newlines anywhere in it."
        s2, e2 = expand_to_paragraph(single, 5, 8)
        self.assertEqual((s2, e2), (0, len(single)), "single-paragraph text expands to the whole string")

    def test_extract_quotes(self) -> None:
        note = ("Source states 'short' and also 'This is long enough to count as a real quote.'"
                " A second one: 'Another quote long enough to be extracted here too.'")
        quotes = extract_quotes(note)
        self.assertNotIn("short", quotes, "short quote below MIN_QUOTE_LEN excluded")
        self.assertTrue(any("This is long enough" in q for q in quotes) and
              any("Another quote long enough" in q for q in quotes), "%s -- %s" % ("long quotes both extracted", str(quotes)))

        sentence_note = "Reports 'First sentence here is long enough. Second sentence also long enough.'"
        candidates = extract_quotes(sentence_note)
        self.assertTrue(candidates[0] == "First sentence here is long enough. Second sentence also long enough.", "whole block is the first candidate")
        self.assertTrue("First sentence here is long enough." in candidates and
              "Second sentence also long enough." in candidates, "%s -- %s" % ("individual sentences offered as fallback candidates", str(candidates)))

        self.assertEqual(extract_quotes("Plain text, no quotes."), [], "no quotes in a note with no single-quote marks")

    def test_subject_check(self):
        """The check this script lacked until 2026-09-04. The regression it
        guards is real and is in the repo's history: a quote about ATM
        c.7271T>G was located, verified as present, and written in as the gold
        span for a case about ATM c.7570G>C."""
        from eval.verify_spans import subject_check

        case = {"gene": "ATM", "variant": "c.7570G>C"}
        gene_level = {"gene": "BRCA2", "variant": None}

        self.assertTrue(subject_check("ATM c.7570G>C associates with breast cancer", case)[0] == "ok", "span naming the exact variant is ok")

        self.assertTrue(subject_check(
                  "This has previously been demonstrated for ATM c.7271T>G, (p.Val2424Gly), "
                  "having up to 60% lifetime breast cancer by the age of 70 years.", case)[0]
              == "gene_only", "the real regression: right gene, wrong variant, is gene_only not ok")

        self.assertTrue(subject_check("Polygenic risk scores in unselected cohorts.", case)[0] == "absent", "span naming neither is absent")

        self.assertTrue(subject_check("the 7570G>C allele was enriched", case)[0] == "ok", "variant matches without the c. prefix")

        self.assertTrue(subject_check("germline BRCA2 mutation carriers", gene_level)[0] == "ok", "gene-level case (no variant) is ok on a gene mention")

        self.assertTrue(subject_check("the ATMIN cofactor was measured", {"gene": "ATM", "variant": None})[0]
              == "absent", "gene match is whole-word, not a substring")


if __name__ == "__main__":
    unittest.main()
