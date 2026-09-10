"""Stdlib-only tests for bm25.py. Run directly: python -m retrieval.tests.test_bm25"""
from __future__ import annotations

import math
import random
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from common.corpus_text import Chunk
from retrieval.bm25 import (K1, B, BM25Index, build_index, index_from_chunks,
                            build_index_from_texts, tokenize)
from retrieval.chunker import paragraph_chunks

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


def brute_force_search(index: BM25Index, query: str, top_k: int,
                       k1: float = K1, b: float = B) -> list[tuple[str, float]]:
    """The definition, scored over every chunk with no postings shortcut.
    The gate: index.search must return exactly this ranking."""
    terms = Counter(tokenize(query))
    scored = []
    for i, chunk in enumerate(index.chunks):
        tf = Counter(tokenize(chunk.text))
        dl = sum(tf.values())
        total = 0.0
        for t, qtf in terms.items():
            f = tf.get(t, 0)
            if f == 0:
                continue
            n_t = index.doc_freq.get(t, 0)
            idf = math.log((index.n_docs - n_t + 0.5) / (n_t + 0.5) + 1)
            denom = f + k1 * (1 - b + b * dl / index.avg_doc_length)
            total += qtf * idf * f * (k1 + 1) / denom
        if total > 0:
            scored.append((i, total))
    scored.sort(key=lambda pair: (-pair[1], pair[0]))
    return [(index.chunks[i].chunk_id, s) for i, s in scored[:top_k]]


class TestBm25(unittest.TestCase):
    def test_tokenize(self) -> None:
        toks = tokenize("BRCA1 c.1100delC increases risk (95% CI)")
        self.assertIn("brca1", toks, "keeps gene symbol as one token")
        self.assertIn("c.1100delc", toks, "keeps HGVS-style dotted token intact: %s" % toks)
        self.assertTrue(all(t == t.lower() for t in toks), "lowercases")

    def test_identity_chunker_offsets_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            from common.corpus_text import parse_root
            chunks = paragraph_chunks(parse_root(xml_dir / "PMC1.xml"), "PMC1")
            self.assertEqual(len(chunks), 2, "abstract and body, one chunk each")
            for c in chunks:
                s = c.source_spans[0]
                self.assertEqual(len(c.source_spans), 1, "identity chunker: one span per chunk")
                self.assertEqual(
                    c.text, ARTICLES["PMC1"][s["section"]][s["char_start"]:s["char_end"]],
                    f"{s['section']} offsets round-trip against real text")

    def test_build_index_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], chunker=paragraph_chunks)
            self.assertEqual(index.n_docs, 6, "one chunk per paragraph across 3 two-paragraph articles")

            results = index.search("BRCA1 breast cancer risk", top_k=3)
            self.assertTrue(results, "search returns results")
            self.assertEqual(results[0][0].pmcid, "PMC3",
                             "most BRCA1/breast-cancer-dense paragraph (PMC3) ranks first: "
                             + str([r[0].pmcid for r in results]))
            scores = [s for _, s in results]
            self.assertEqual(scores, sorted(scores, reverse=True), "sorted descending by score")

            irrelevant = index.search("diabetes cardiovascular cohort", top_k=3)
            self.assertEqual(irrelevant[0][0].pmcid, "PMC2",
                             "unrelated query top hit is the cardiovascular paragraph (PMC2)")

            self.assertEqual(index.search("zzzznonexistenttermzzzz", top_k=3), [],
                             "query with no matching terms returns empty, not garbage")

    def test_idf_rarity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = build_index(make_corpus(tmp), ["PMC1", "PMC2", "PMC3"], chunker=paragraph_chunks)
            common_terms = [t for t, df in index.doc_freq.items() if df == index.n_docs]
            rare_terms = [t for t, df in index.doc_freq.items() if df == 1]
            if common_terms and rare_terms:
                self.assertLess(index.idf(common_terms[0]), index.idf(rare_terms[0]),
                                "a term in every chunk has lower idf than a term in one")
            self.assertTrue(all(index.idf(t) >= 0 for t in index.doc_freq),
                            "idf is never negative (the +1 variant)")

    def test_save_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], chunker=paragraph_chunks)
            before = index.search("BRCA1 breast cancer", top_k=3)
            save_path = Path(tmp) / "index.pkl"
            index.save(save_path)
            after = BM25Index.load(save_path).search("BRCA1 breast cancer", top_k=3)
            self.assertEqual([(c.chunk_id, round(s, 6)) for c, s in before],
                             [(c.chunk_id, round(s, 6)) for c, s in after],
                             "search results identical after save/load round-trip")


class TestPostingsMatchesBruteForce(unittest.TestCase):
    """The phase D gate (DECISION_LOG.md, 'BM25 search is a full scan'): the
    postings scan must return the identical ranking to a brute-force score
    over every chunk, on a randomly generated index."""

    VOCAB = "brca1 brca2 tp53 variant carrier cancer risk cohort study rare common".split()

    def random_index(self, rng: random.Random, n_chunks: int) -> BM25Index:
        chunks = []
        for i in range(n_chunks):
            words = [rng.choice(self.VOCAB) for _ in range(rng.randint(3, 25))]
            chunks.append(Chunk(chunk_id=f"c{i}", pmcid=f"PMC{i}", text=" ".join(words),
                                source_spans=[{"section": "body", "char_start": 0, "char_end": 1}]))
        return index_from_chunks(chunks)

    def test_identical_ranking_over_many_random_queries(self) -> None:
        rng = random.Random(0)
        for _ in range(30):
            index = self.random_index(rng, rng.randint(5, 60))
            for _ in range(10):
                query = " ".join(rng.choice(self.VOCAB) for _ in range(rng.randint(1, 4)))
                got = [(c.chunk_id, round(s, 9)) for c, s in index.search(query, top_k=10)]
                want = [(cid, round(s, 9)) for cid, s in brute_force_search(index, query, 10)]
                self.assertEqual(got, want, f"query={query!r}")

    def test_k1_and_b_flow_through_both_paths(self) -> None:
        rng = random.Random(1)
        index = self.random_index(rng, 40)
        for k1, b in ((1.2, 0.75), (2.0, 0.4)):
            got = [(c.chunk_id, round(s, 9)) for c, s in index.search("brca1 variant", 10, k1, b)]
            want = [(cid, round(s, 9))
                    for cid, s in brute_force_search(index, "brca1 variant", 10, k1, b)]
            self.assertEqual(got, want, f"k1={k1} b={b}")


class TestK1AndBAreParameters(unittest.TestCase):
    """k1/b affect scoring only, never the index, so a comparison must not
    need a rebuild."""

    def setUp(self):
        self.index = build_index_from_texts([
            ("d1", "brca1 variant carriers breast cancer risk"),
            ("d2", "brca1 brca1 brca1 variant variant carriers"),
            ("d3", "unrelated zebrafish embryo development study"),
        ])

    def test_defaults_match_the_module_constants(self):
        terms = ["brca1", "variant"]
        self.assertEqual(self.index.score(terms, 0), self.index.score(terms, 0, K1, B))

    def test_k1_changes_the_score(self):
        self.assertNotEqual(round(self.index.score(["brca1"], 1, 1.2, 0.75), 9),
                            round(self.index.score(["brca1"], 1, 1.5, 0.75), 9))

    def test_lower_k1_saturates_repeated_terms_sooner(self):
        """d2 repeats 'brca1' three times, d1 once; a lower k1 narrows the gap."""
        gap12 = self.index.score(["brca1"], 1, 1.2, 0.75) - self.index.score(["brca1"], 0, 1.2, 0.75)
        gap15 = self.index.score(["brca1"], 1, 1.5, 0.75) - self.index.score(["brca1"], 0, 1.5, 0.75)
        self.assertLess(gap12, gap15)

    def test_search_passes_the_parameters_through(self):
        a = self.index.search("brca1 variant", top_k=3, k1=1.2)
        b = self.index.search("brca1 variant", top_k=3, k1=1.5)
        self.assertNotEqual([s for _, s in a], [s for _, s in b])


if __name__ == "__main__":
    unittest.main()


class TestResourceAndCorpusBoundaries(unittest.TestCase):
    def test_expired_deadline_stops_retrieval(self):
        from retrieval.bm25 import build_index_from_texts
        index = build_index_from_texts([('a', 'cancer variant')])
        with self.assertRaises(TimeoutError):
            index.search('cancer', deadline=0)

    def test_exclusion_applies_even_when_xml_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = make_corpus(tmp)
            index = build_index(xml_dir, ['PMC1', 'PMC2'], chunker=paragraph_chunks,
                                excluded_pmcids={'PMC1'})
            self.assertTrue(index.chunks)
            self.assertNotIn('PMC1', {c.pmcid for c in index.chunks})
