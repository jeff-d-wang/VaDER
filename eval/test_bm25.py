"""Stdlib-only tests for bm25.py. Run directly: python test_bm25.py"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from bm25 import BM25Index, build_index, iter_paragraphs, tokenize

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


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


def test_tokenize() -> None:
    toks = tokenize("BRCA1 c.1100delC increases risk (95% CI)")
    check("keeps gene symbol as one token", "brca1" in toks)
    check("keeps HGVS-style dotted token intact", "c.1100delc" in toks, str(toks))
    check("lowercases", all(t == t.lower() for t in toks))


def test_iter_paragraphs_offsets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_corpus(tmp)
        paras = iter_paragraphs(xml_dir / "PMC1.xml", "PMC1")
        check("finds both abstract and body paragraphs", len(paras) == 2, str(paras))
        for p in paras:
            check(f"{p.section} offsets round-trip against real text",
                  p.text == ARTICLES["PMC1"][p.section][p.char_start:p.char_end])


def test_build_index_and_search() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_corpus(tmp)
        index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], min_paragraph_words=3)
        check("index built over all paragraphs across 3 articles", index.n_docs >= 5, str(index.n_docs))

        results = index.search("BRCA1 breast cancer risk", top_k=3)
        check("search returns results", len(results) > 0)
        top_pmcid = results[0][0].pmcid
        check("most BRCA1/breast-cancer-dense paragraph (PMC3) ranks first",
              top_pmcid == "PMC3", f"got {top_pmcid}: {[r[0].pmcid for r in results]}")
        scores = [s for _, s in results]
        check("results sorted descending by score", scores == sorted(scores, reverse=True))

        irrelevant = index.search("diabetes cardiovascular cohort", top_k=3)
        check("unrelated query top hit is the cardiovascular paragraph (PMC2 body)",
              irrelevant[0][0].pmcid == "PMC2", str([r[0].pmcid for r in irrelevant]))

        no_match = index.search("zzzznonexistenttermzzzz", top_k=3)
        check("query with no matching terms returns empty, not garbage", no_match == [])


def test_idf_rarity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_corpus(tmp)
        index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], min_paragraph_words=3)
        # "brca1" appears in some but not all paragraphs; a term in every
        # paragraph should score a lower idf than one in very few.
        common_terms = [t for t, df in index.doc_freq.items() if df == index.n_docs]
        rare_terms = [t for t, df in index.doc_freq.items() if df == 1]
        if common_terms and rare_terms:
            check("a term in every paragraph has lower idf than a term in one",
                  index.idf(common_terms[0]) < index.idf(rare_terms[0]))
        check("idf is never negative (the +1 variant)",
              all(index.idf(t) >= 0 for t in index.doc_freq))


def test_save_load_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_corpus(tmp)
        index = build_index(xml_dir, ["PMC1", "PMC2", "PMC3"], min_paragraph_words=3)
        before = index.search("BRCA1 breast cancer", top_k=3)

        save_path = Path(tmp) / "index.pkl"
        index.save(save_path)
        loaded = BM25Index.load(save_path)
        after = loaded.search("BRCA1 breast cancer", top_k=3)

        check("search results identical after save/load round-trip",
              [(p.pmcid, p.char_start, round(s, 6)) for p, s in before] ==
              [(p.pmcid, p.char_start, round(s, 6)) for p, s in after])


def test_min_paragraph_words_filter() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        xml_dir = make_corpus(tmp)
        loose = build_index(xml_dir, ["PMC1"], min_paragraph_words=0)
        strict = build_index(xml_dir, ["PMC1"], min_paragraph_words=100)
        check("a high min_paragraph_words threshold drops all short paragraphs",
              strict.n_docs == 0 and loose.n_docs > 0, f"loose={loose.n_docs} strict={strict.n_docs}")


def run_tests() -> int:
    test_tokenize()
    test_iter_paragraphs_offsets()
    test_build_index_and_search()
    test_idf_rarity()
    test_save_load_roundtrip()
    test_min_paragraph_words_filter()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
