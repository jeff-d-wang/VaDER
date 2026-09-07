"""Stdlib-only tests for bm25.py. Run directly: python -m retrieval.tests.test_bm25"""
from __future__ import annotations

import unittest

import tempfile
from pathlib import Path

from retrieval.bm25 import BM25Index, build_index, iter_paragraphs, tokenize

ARTICLES = {
    "PMC1": {
        "abstract": "BRCA1 pathogenic variants increase breast cancer risk substantially in carriers.",
        "body": "Unrelated background about study methodology and statistical approach used here.",
    },
    "PMC2": {
        "abstract": "This study examines cardiovascular disease outcomes in a large cohort.",
        "body": "BRCA1 and BRCA2 mutation carriers were excluded from this cardiovascular cohort. Cancer was not the focus. Diabetes risk was assessed separately in a different population entirely.",
    },
    "PMC3": {
        "abstract": "BRCA1 BRCA1 BRCA1 breast cancer risk breast cancer risk elevated substantially, high confidence finding here.",
        "body": "Filler paragraph about unrelated topic to pad this article's total length considerably beyond the others.",
    },
}

XML_TEMPLATE = """<article>
  <front><article-meta><abstract><p>{abstract}</p></abstract></article-meta></front>
  <body><p>{body}</p></body>
</article>
"""


def make_corpus(tmp: str) -> Path:
    xml_dir = Path(tmp)
    for pmcid, sections in ARTICLES.items():
        (xml_dir / f"{pmcid}.xml").write_text(
            XML_TEMPLATE.format(abstract=sections["abstract"], body=sections["body"])
        )
    return xml_dir


class TestBm25(unittest.TestCase):
    def test_tokenize(self) -> None:
        toks = tokenize("BRCA1 c.1100delC increases risk (95% CI)")
        self.assertIn("brca1", toks, "keeps gene symbol as one token")
        self.assertIn("c.1100delc", toks, "%s -- %s" % ("keeps HGVS-style dotted token intact", str(toks)))
        self.assertTrue(all(t == t.lower() for t in toks), "lowercases")

    def test_iter_paragraphs_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            paras = iter_paragraphs(xml_dir / "PMC1.xml", "PMC1")
            self.assertEqual(len(paras), 2, "%s -- %s" % ("finds both abstract and body paragraphs", str(paras)))
            for p in paras:
                self.assertTrue(p.text == ARTICLES["PMC1"][p.section][p.char_start:p.char_end], f"{p.section} offsets round-trip against real text")

    def test_build_index_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], min_paragraph_words=3)
            self.assertTrue(index.n_docs >= 5, "%s -- %s" % ("index built over all paragraphs across 3 articles", str(index.n_docs)))

            results = index.search("BRCA1 breast cancer risk", top_k=3)
            self.assertTrue(len(results) > 0, "search returns results")
            top_pmcid = results[0][0].pmcid
            self.assertTrue(top_pmcid == "PMC3", "%s -- %s" % ("most BRCA1/breast-cancer-dense paragraph (PMC3) ranks first", f"got {top_pmcid}: {[r[0].pmcid for r in results]}"))
            scores = [s for _, s in results]
            self.assertEqual(scores, sorted(scores, reverse=True), "results sorted descending by score")

            irrelevant = index.search("diabetes cardiovascular cohort", top_k=3)
            self.assertTrue(irrelevant[0][0].pmcid == "PMC2", "%s -- %s" % ("unrelated query top hit is the cardiovascular paragraph (PMC2 body)", str([r[0].pmcid for r in irrelevant])))

            no_match = index.search("zzzznonexistenttermzzzz", top_k=3)
            self.assertEqual(no_match, [], "query with no matching terms returns empty, not garbage")

    def test_idf_rarity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], min_paragraph_words=3)
            # "brca1" appears in some but not all paragraphs; a term in every
            # paragraph should score a lower idf than one in very few.
            common_terms = [t for t, df in index.doc_freq.items() if df == index.n_docs]
            rare_terms = [t for t, df in index.doc_freq.items() if df == 1]
            if common_terms and rare_terms:
                self.assertTrue(index.idf(common_terms[0]) < index.idf(rare_terms[0]), "a term in every paragraph has lower idf than a term in one")
            self.assertTrue(all(index.idf(t) >= 0 for t in index.doc_freq), "idf is never negative (the +1 variant)")

    def test_save_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], min_paragraph_words=3)
            before = index.search("BRCA1 breast cancer", top_k=3)

            save_path = Path(tmp) / "index.pkl"
            index.save(save_path)
            loaded = BM25Index.load(save_path)
            after = loaded.search("BRCA1 breast cancer", top_k=3)

            self.assertTrue([(p.pmcid, p.char_start, round(s, 6)) for p, s in before] ==
                  [(p.pmcid, p.char_start, round(s, 6)) for p, s in after], "search results identical after save/load round-trip")

    def test_min_paragraph_words_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            loose = build_index(xml_dir, ["PMC1"], min_paragraph_words=0)
            strict = build_index(xml_dir, ["PMC1"], min_paragraph_words=100)
            self.assertTrue(strict.n_docs == 0 and loose.n_docs > 0, "%s -- %s" % ("a high min_paragraph_words threshold drops all short paragraphs", f"loose={loose.n_docs} strict={strict.n_docs}"))


if __name__ == "__main__":
    unittest.main()


class TestK1AndBAreParameters(unittest.TestCase):
    """k1/b affect scoring only, never the index, so a comparison must not
    need a rebuild. Added 2026-09-06 with the k1=1.2 comparison."""

    def setUp(self):
        from retrieval.bm25 import build_index_from_texts
        self.index = build_index_from_texts([
            ("d1", "brca1 variant carriers breast cancer risk"),
            ("d2", "brca1 brca1 brca1 variant variant carriers"),
            ("d3", "unrelated zebrafish embryo development study"),
        ])

    def test_defaults_match_the_module_constants(self):
        from retrieval.bm25 import B, K1
        terms = ["brca1", "variant"]
        self.assertEqual(self.index.score(terms, 0),
                         self.index.score(terms, 0, K1, B))

    def test_k1_changes_the_score(self):
        terms = ["brca1"]
        self.assertNotEqual(round(self.index.score(terms, 1, 1.2, 0.75), 9),
                            round(self.index.score(terms, 1, 1.5, 0.75), 9))

    def test_lower_k1_saturates_repeated_terms_sooner(self):
        """The whole point of k1: it caps how much a repeated term keeps
        adding. d2 repeats "brca1" three times, d1 once, so a lower k1 should
        narrow the gap between them."""
        terms = ["brca1"]
        gap12 = self.index.score(terms, 1, 1.2, 0.75) - self.index.score(terms, 0, 1.2, 0.75)
        gap15 = self.index.score(terms, 1, 1.5, 0.75) - self.index.score(terms, 0, 1.5, 0.75)
        self.assertLess(gap12, gap15)

    def test_search_passes_the_parameters_through(self):
        a = self.index.search("brca1 variant", top_k=3, k1=1.2)
        b = self.index.search("brca1 variant", top_k=3, k1=1.5)
        self.assertNotEqual([s for _, s in a], [s for _, s in b])
