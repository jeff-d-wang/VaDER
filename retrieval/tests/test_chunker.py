"""Stdlib-only tests for the phase D structure-aware chunker.
Run directly: python -m retrieval.tests.test_chunker
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from common.corpus_text import extract_section_text, parse_root
from retrieval.chunker import TARGET_TOKENS, chunk_article, paragraph_chunks

# A body with two sibling <sec>s and a boilerplate one, plus an abstract.
BIG_PARA = " ".join(["token"] * (TARGET_TOKENS + 40))  # one paragraph over the target

XML = f"""<article>
  <front><article-meta><abstract>
    <p>This abstract describes a study of BRCA1 variants in a breast cancer cohort.</p>
  </abstract></article-meta></front>
  <body>
    <sec><title>Methods</title>
      <p>Patients were recruited from three centres over a four year enrolment window.</p>
      <p>Sequencing was performed on a targeted panel covering the relevant genes here.</p>
    </sec>
    <sec><title>Results</title>
      <p>The variant was found in twelve of two hundred sequenced tumour samples total.</p>
      <p>{BIG_PARA}</p>
    </sec>
    <sec><title>Acknowledgements</title>
      <p>We thank the study funders and participating clinicians for their support here.</p>
    </sec>
  </body>
</article>
"""


class TestChunker(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "PMC1.xml"
        self.path.write_text(XML)
        self.root = parse_root(self.path)
        self.chunks = chunk_article(self.root, "PMC1")

    def tearDown(self):
        self._tmp.cleanup()

    def test_chunk_text_is_a_verbatim_slice_of_the_section(self):
        """chunk.text must equal section_text[first_start:last_end], the
        invariant that lets a gold offset resolve after a re-chunk."""
        by_section = {"abstract": extract_section_text(self.path, "abstract"),
                      "body": extract_section_text(self.path, "body")}
        for chunk in self.chunks:
            section = chunk.source_spans[0]["section"]
            start = chunk.source_spans[0]["char_start"]
            end = chunk.source_spans[-1]["char_end"]
            self.assertEqual(by_section[section][start:end], chunk.text, chunk.chunk_id)
            # and each individual paragraph span still resolves
            for s in chunk.source_spans:
                self.assertIn(by_section[section][s["char_start"]:s["char_end"]], chunk.text)

    def test_no_chunk_crosses_a_section_boundary(self):
        for chunk in self.chunks:
            sections = {s["section"] for s in chunk.source_spans}
            self.assertEqual(len(sections), 1, f"{chunk.chunk_id} spans {sections}")

    def test_methods_and_results_do_not_merge_across_the_sec_boundary(self):
        methods = [c for c in self.chunks if "recruited from three centres" in c.text]
        results = [c for c in self.chunks if "twelve of two hundred" in c.text]
        self.assertEqual(len(methods), 1)
        self.assertEqual(len(results), 1)
        self.assertIsNot(methods[0], results[0])
        self.assertNotIn("twelve of two hundred", methods[0].text,
                         "a Results paragraph leaked into a Methods chunk")

    def test_the_two_methods_paragraphs_merge_into_one_chunk(self):
        methods = [c for c in self.chunks if "recruited from three centres" in c.text]
        self.assertEqual(len(methods), 1)
        self.assertIn("targeted panel", methods[0].text, "second Methods paragraph did not merge in")
        self.assertEqual(len(methods[0].source_spans), 2, "one span per merged paragraph")

    def test_an_oversized_paragraph_survives_whole_and_alone(self):
        big = [c for c in self.chunks if "token token token" in c.text]
        self.assertEqual(len(big), 1, "the over-target paragraph is one chunk, not split")
        self.assertEqual(len(big[0].source_spans), 1, "and nothing merged onto it")
        self.assertNotIn("twelve of two hundred", big[0].text)

    def test_boilerplate_section_is_dropped(self):
        self.assertFalse(any("thank the study funders" in c.text for c in self.chunks),
                         "an Acknowledgements paragraph was chunked")

    def test_abstract_is_its_own_chunk(self):
        abstract = [c for c in self.chunks if c.source_spans[0]["section"] == "abstract"]
        self.assertEqual(len(abstract), 1)
        self.assertIn("This abstract describes", abstract[0].text)

    def test_identity_chunker_is_one_chunk_per_paragraph(self):
        ident = paragraph_chunks(self.root, "PMC1")
        # abstract(1) + methods(2) + results(2) + acks(1) = 6; identity chunker
        # has no boilerplate filter.
        self.assertEqual(len(ident), 6)
        self.assertTrue(all(len(c.source_spans) == 1 for c in ident))


if __name__ == "__main__":
    unittest.main()
