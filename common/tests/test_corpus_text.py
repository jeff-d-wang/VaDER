"""
The offset convention has exactly one owner (common/corpus_text.py) and
three consumers. This is the check that they agree, which until 2026-09-05
was only asserted in prose in four docstrings while find_coverage quietly
disagreed about bare-text abstracts.

The invariant, for every span this project can emit:

    extract_section_text(xml, section)[char_start:char_end] == that span's text
"""
from __future__ import annotations

import tempfile
import unittest
from xml.etree import ElementTree as ET
from pathlib import Path

from common.corpus_text import (Chunk, chunk_hits_span, clean_paragraph_texts,
                                extract_section_text, iter_paragraphs, iter_paragraphs_from_root,
                                parse_root, section_titles_from_root, spans_overlap)

WITH_PARAGRAPHS = """<article>
  <front><article-meta><title-group><article-title>A Title</article-title></title-group></article-meta></front>
  <abstract><p>First abstract paragraph.</p><p>Second one.</p></abstract>
  <body><p>Body para one mentions BRCA1.</p><p>Body para two.</p><p>Third body para.</p></body>
</article>"""

# An abstract written as bare text, no <p> children. This is the shape the
# old find_coverage._extract_paragraphs dropped on the floor.
BARE_ABSTRACT = """<article>
  <abstract>Bare abstract text with no paragraph tags.</abstract>
  <body><p>Body para.</p></body>
</article>"""


def write(tmp: str, xml: str) -> Path:
    path = Path(tmp) / "PMC1.xml"
    path.write_text(xml)
    return path


class TestOffsetConvention(unittest.TestCase):
    def test_offsets_index_back_into_the_section_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, WITH_PARAGRAPHS)
            for section, text, start, end in iter_paragraphs(path):
                whole = extract_section_text(path, section)
                self.assertEqual(whole[start:end], text,
                                 f"{section} span [{start}:{end}] does not index back to its text")

    def test_sections_are_counted_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, WITH_PARAGRAPHS)
            firsts = {s: start for s, _, start, _ in reversed(list(iter_paragraphs(path)))}
            self.assertEqual(firsts["abstract"], 0)
            self.assertEqual(firsts["body"], 0, "body offsets must restart at 0, not continue the abstract")

    def test_bare_text_abstract_is_one_paragraph_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, BARE_ABSTRACT)
            abstracts = [t for s, t, _, _ in iter_paragraphs(path) if s == "abstract"]
            self.assertEqual(abstracts, ["Bare abstract text with no paragraph tags."])

    def test_missing_or_unparseable_file_yields_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(parse_root(Path(tmp) / "nope.xml"))
            self.assertEqual(list(iter_paragraphs(Path(tmp) / "nope.xml")), [])
            broken = write(tmp, "<article><body><p>unclosed")
            self.assertEqual(list(iter_paragraphs(broken)), [])


class TestConsumersAgree(unittest.TestCase):
    """bm25 and find_coverage each turn paragraphs into their own span type;
    both must land on the same offsets as corpus_text.py's own convention.

    service/search.py used to be a third independent consumer (its own
    per-candidate XML scan, `_find_span_in_xml`) and had its own agreement
    test here. Phase E replaced that scan with retrieval.bm25/chunker
    directly (docs/DECISION_LOG.md, the phase E service rewrite): the
    service no longer computes a span itself, it reads `Chunk.span()` off
    the same index `test_bm25_spans_resolve` below already checks. A
    dedicated service-vs-bm25 agreement test would now be asserting that
    one piece of code agrees with itself, so it was removed rather than
    updated to hit the same function twice."""

    def test_bm25_spans_resolve(self):
        from retrieval.chunker import paragraph_chunks  # bm25 indexes what this yields
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, WITH_PARAGRAPHS)
            chunks = paragraph_chunks(parse_root(path), "PMC1")
            self.assertTrue(chunks)
            for c in chunks:
                s = c.source_spans[0]
                whole = extract_section_text(path, s["section"])
                self.assertEqual(whole[s["char_start"]:s["char_end"]], c.text)

    def test_find_coverage_spans_resolve(self):
        from eval.find_coverage import _extract_paragraphs
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, WITH_PARAGRAPHS)
            paras = _extract_paragraphs(path)
            self.assertTrue(paras)
            for section, text, start, end in paras:
                self.assertEqual(extract_section_text(path, section)[start:end], text)



class TestCleanParagraphTexts(unittest.TestCase):
    """Real shapes, pulled from PMC9218467 while diagnosing this: a single
    citation ("<sup>\\n<xref ref-type=\"bibr\">1</xref>\\n</sup>", the newline
    is real pretty-print whitespace already in the XML) and a range
    ("2–4", where the middle xref is empty and the dash is a bare text
    node between two xrefs)."""

    XML = """<article>
  <abstract><p>Rare cancers.<sup>
<xref ref-type="bibr" rid="b1">1</xref>
</sup> They occur late.<sup><xref ref-type="bibr" rid="b2">2</xref><xref ref-type="bibr" rid="b3" />–<xref ref-type="bibr" rid="b4">4</xref></sup> Stage 4 disease is common.<sup>2</sup></p></abstract>
  <body><p>Second para, no citations.</p></body>
</article>"""

    def test_citation_superscripts_are_stripped_and_whitespace_collapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, self.XML)
            root = parse_root(path)
            cleaned = clean_paragraph_texts(root, "abstract")
            self.assertEqual(
                cleaned[0],
                "Rare cancers. They occur late. Stage 4 disease is common.2")

    def test_offsets_and_raw_text_are_unaffected(self):
        """The whole point: this is presentation-only. iter_paragraphs_from_root
        and extract_section_text must still see the raw text, citation markers
        and pretty-print whitespace included, so no stored offset moves."""
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, self.XML)
            root = parse_root(path)
            raw = list(iter_paragraphs_from_root(root, "abstract"))[0][0]
            self.assertIn("1", raw)
            self.assertIn("\n", raw)
            whole = extract_section_text(path, "abstract")
            self.assertEqual(whole[:len(raw)], raw)

    def test_a_bare_sup_with_no_xref_is_left_alone(self):
        """"<sup>2</sup>" with no <xref> child could be a real superscript
        (an exponent, a chemical formula) rather than a citation marker; only
        a sup whose element children are ALL bibr xrefs is stripped."""
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, self.XML)
            root = parse_root(path)
            cleaned = clean_paragraph_texts(root, "abstract")
            self.assertTrue(cleaned[0].endswith("common.2"))

    def test_aligned_with_paragraphs_from_root_and_bare_text_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, BARE_ABSTRACT)
            root = parse_root(path)
            cleaned = clean_paragraph_texts(root, "abstract")
            self.assertEqual(cleaned, ["Bare abstract text with no paragraph tags."])


class TestCleanParagraphTextsBareXrefLists(unittest.TestCase):
    """The <sup>-wrapped shape above turns out to be the minority: sampling
    800 corpus articles, 607 carry a bare (non-sup) xref citation list, only
    153 the sup-wrapped one. A bare xref inside "[...]" or "(...)" needs the
    brackets removed too, not just the digits, or the result is a dangling
    "[]" or "(-)" that reads worse than the citation did. Real shapes, pulled
    from PMC10859687, PMC5883065, PMC8410541."""

    XML = """<article>
  <abstract><p>Ribosome biogenesis is a process [<xref rid="r1" ref-type="bibr">1</xref>].
It involves polymerases [<xref rid="r2" ref-type="bibr">2</xref>, <xref rid="r3" ref-type="bibr">3</xref>, <xref rid="r4" ref-type="bibr">4</xref>].
S1P is generated via two kinases (<xref rid="r5" ref-type="bibr">3</xref>–<xref rid="r6" ref-type="bibr">5</xref>). Prior work (<xref rid="r7" ref-type="bibr">1</xref>, <xref rid="r8" ref-type="bibr">2</xref>) showed this.
The 30S ribosomal subunit [rRNA] assembles first.</p></abstract>
  <body><p>Second para, no citations.</p></body>
</article>"""

    def cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, self.XML)
            root = parse_root(path)
            return clean_paragraph_texts(root, "abstract")[0]

    def test_single_bracketed_bare_xref_removes_the_brackets(self):
        self.assertIn("a process. It involves", self.cleaned())

    def test_comma_separated_bracketed_list_removes_the_brackets(self):
        self.assertIn("It involves polymerases. S1P is generated", self.cleaned())

    def test_dash_range_in_parens_removes_the_parens(self):
        self.assertIn("via two kinases. Prior work", self.cleaned())

    def test_comma_separated_parens_removes_the_parens(self):
        self.assertIn("Prior work showed this.", self.cleaned())

    def test_bracket_with_no_marker_inside_is_left_alone(self):
        """"[rRNA]" has no xref child at all: not a citation, don't touch it."""
        self.assertIn("[rRNA]", self.cleaned())


class TestCleanParagraphTextsRealLabelInsideSup(unittest.TestCase):
    """A <sup> can carry a real label alongside its citation, not just
    citation notation. Real shapes, pulled from PMC8849557 (a mutation-status
    label used throughout the paper: "BRCA1mut" means something different
    from "BRCA1") and PMC8211653 (a cell-line name). Treating the whole
    <sup> as one droppable unit, as the sup-wrapped case alone does, would
    silently delete "mut"/"Revertant" along with the citation number -- a
    meaning-changing loss in exactly the variant-status text this project
    cares about."""

    XML = """<article>
  <abstract><p>TNBCs in BRCA1<sup>mut</sup>37</p></abstract>
  <body><p>TNBCs in BRCA1<sup>mut<xref rid="R37" ref-type="bibr">37</xref></sup>, and PALB2<sup>mut<xref rid="R38" ref-type="bibr">38</xref></sup> carriers. CAPAN1<sup>Revertant <xref ref-type="bibr" rid="CR24">24</xref></sup>. Fig. 1<sup><xref rid="a" ref-type="bibr">1</xref></sup> shows this.</p></body>
</article>"""

    def cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, self.XML)
            root = parse_root(path)
            return clean_paragraph_texts(root, "body")[0]

    def test_real_label_sharing_a_sup_with_a_citation_survives(self):
        text = self.cleaned()
        self.assertIn("BRCA1mut", text)
        self.assertIn("PALB2mut", text)

    def test_the_citation_number_is_still_removed_from_that_label(self):
        text = self.cleaned()
        self.assertNotIn("mut37", text)
        self.assertNotIn("mut38", text)

    def test_a_real_word_label_also_survives(self):
        self.assertIn("Revertant", self.cleaned())

    def test_formatted_label_inside_sup_survives(self):
        self.XML = ('<article><body><p>BRCA1<sup><italic>mut</italic>'
                    '<xref ref-type="bibr">37</xref></sup> carriers.</p></body></article>')
        self.assertEqual(self.cleaned(), "BRCA1mut carriers.")

    def test_pure_sup_wrapped_citation_still_disappears_completely(self):
        """Regression check: this fix must not weaken the plain case (no
        real text sharing the <sup>) that TestCleanParagraphTexts covers."""
        self.assertIn("Fig. 1 shows", self.cleaned())


class TestSpansOverlap(unittest.TestCase):
    @staticmethod
    def _s(start, end, pmcid="PMC1", section="abstract"):
        return {"pmcid": pmcid, "section": section, "char_start": start, "char_end": end}

    def test_partial_overlap_counts(self):
        self.assertTrue(spans_overlap(self._s(0, 100), self._s(50, 150)))

    def test_containment_counts_either_way(self):
        self.assertTrue(spans_overlap(self._s(0, 100), self._s(10, 20)))
        self.assertTrue(spans_overlap(self._s(10, 20), self._s(0, 100)))

    def test_disjoint_does_not(self):
        self.assertFalse(spans_overlap(self._s(0, 50), self._s(60, 100)))

    def test_touching_spans_do_not_overlap(self):
        """Adjacent paragraphs share a boundary because section text is
        joined on one separator char. Counting that as a hit would credit a
        retriever for returning the paragraph next to the right one."""
        self.assertFalse(spans_overlap(self._s(0, 50), self._s(50, 100)))

    def test_different_article_or_section_never_overlaps(self):
        self.assertFalse(spans_overlap(self._s(0, 100), self._s(0, 100, pmcid="PMC2")))
        self.assertFalse(spans_overlap(self._s(0, 100), self._s(0, 100, section="body")))


NESTED_SECS = """<article>
  <abstract><p>Abstract para.</p></abstract>
  <body>
    <sec><title>Introduction</title><p>Intro para.</p></sec>
    <sec><title>Patients and methods</title>
      <p>Methods para.</p>
      <sec><title>Statistical analysis</title><p>Stats para.</p></sec>
    </sec>
    <p>An orphan paragraph in no sec at all.</p>
  </body>
</article>"""


class TestSectionTitles(unittest.TestCase):
    def titles(self, section):
        return section_titles_from_root(ET.fromstring(NESTED_SECS), section)

    def test_aligned_with_the_paragraph_enumeration(self):
        root = ET.fromstring(NESTED_SECS)
        paragraphs = list(iter_paragraphs_from_root(root, "body"))
        self.assertEqual(len(paragraphs), len(self.titles("body")),
                         "titles must be index-for-index with the offsets they describe")

    def test_nearest_enclosing_sec_wins(self):
        self.assertEqual(self.titles("body"),
                         ["Introduction", "Patients and methods", "Statistical analysis", None])

    def test_no_sec_structure_gives_none(self):
        self.assertEqual(self.titles("abstract"), [None])

    def test_absent_section_gives_empty_list(self):
        self.assertEqual(section_titles_from_root(ET.fromstring(NESTED_SECS), "nope"), [])


class TestChunkProvenance(unittest.TestCase):
    """A Chunk carries the source spans it was built from, and is a retrieval
    hit if any of them overlaps the gold span. This is the phase B schema that
    cannot be retrofitted without a re-index."""

    @staticmethod
    def _gold(start, end, pmcid="PMC1", section="body"):
        return {"pmcid": pmcid, "section": section, "char_start": start, "char_end": end}

    def test_hit_when_one_source_span_overlaps_gold(self):
        chunk = Chunk(chunk_id="PMC1:body:0-2", pmcid="PMC1", text="para0 para1",
                      source_spans=[{"section": "body", "char_start": 0, "char_end": 50},
                                    {"section": "body", "char_start": 51, "char_end": 90}])
        self.assertTrue(chunk_hits_span(chunk, self._gold(60, 80)))   # overlaps span 2
        self.assertTrue(chunk_hits_span(chunk, self._gold(10, 20)))   # overlaps span 1

    def test_miss_when_no_source_span_overlaps(self):
        chunk = Chunk(chunk_id="PMC1:body:0", pmcid="PMC1", text="para0",
                      source_spans=[{"section": "body", "char_start": 0, "char_end": 50}])
        self.assertFalse(chunk_hits_span(chunk, self._gold(50, 90)))          # touches, disjoint
        self.assertFalse(chunk_hits_span(chunk, self._gold(10, 20, section="abstract")))
        self.assertFalse(chunk_hits_span(chunk, self._gold(10, 20, pmcid="PMC2")))


if __name__ == "__main__":
    unittest.main()
