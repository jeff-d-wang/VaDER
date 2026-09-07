"""
Hand-built Okapi BM25, no ranking library. This is the M1 baseline's
retrieval half (`PROJECT_PLAN.md`'s three-baseline requirement, "BM25-only"),
and also satisfies the project's own rule to implement at least one
component with no library (`START_HERE.md` standing rule 2 / the
"Protecting the learning" section of `PROJECT_PLAN.md`).

Indexes at paragraph granularity (abstract and body paragraphs; the title
is not indexed), each record carrying real provenance,
(pmcid, section, char_start, char_end),
using the exact offset convention corpus_text.py already established
(paragraphs joined by "\\n"), so a BM25 hit is a real, citable span, not
just a ranked document id.

Formula: standard Okapi BM25 with the "+1" IDF variant (never negative,
unlike the classic Robertson-Sparck Jones form, which can go negative for a
term that appears in over half the corpus, e.g. "cancer" here):

    score(D, Q) = sum over query terms t of:
        idf(t) * f(t, D) * (k1 + 1) / (f(t, D) + k1 * (1 - b + b * |D| / avgdl))

    idf(t) = ln((N - n(t) + 0.5) / (n(t) + 0.5) + 1)

k1 and b are parameters, defaulting to k1=1.5, b=0.75, and `search` takes
overrides so a comparison needs no re-indexing (they affect scoring only,
never the index).

**On the defaults.** Robertson & Zaragoza (2009) give k1 as a RANGE, usually
1.2 to 2.0, with b=0.75. This module's docstring previously called k1=1.5
"the standard textbook default", which was too strong: the widely deployed
single default, in Lucene and Elasticsearch, is k1=1.2. Corrected 2026-09-06
after the user asked whether 1.2 had ever been tried. It had not. See
docs/DECISION_LOG.md, "does k1=1.2 beat k1=1.5", for what the comparison
found and why it was run against BEIR rather than against this project's own
domain set.
"""
from __future__ import annotations

import math
import pickle
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from common.corpus_text import iter_paragraphs as _iter_paragraphs

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-.]*")  # keeps "c.1100delC", "BRCA1" etc. as one token

K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


@dataclass
class Paragraph:
    pmcid: str
    section: str
    char_start: int
    char_end: int
    text: str


@dataclass
class BM25Index:
    paragraphs: list[Paragraph]
    doc_freq: dict[str, int]          # term -> number of paragraphs containing it
    term_freqs: list[Counter]         # per-paragraph term counts, same order as paragraphs
    doc_lengths: list[int]            # token count per paragraph
    avg_doc_length: float
    n_docs: int

    def idf(self, term: str) -> float:
        n_t = self.doc_freq.get(term, 0)
        return math.log((self.n_docs - n_t + 0.5) / (n_t + 0.5) + 1)

    def score(self, query_terms: list[str], i: int, k1: float = K1, b: float = B) -> float:
        tf = self.term_freqs[i]
        dl = self.doc_lengths[i]
        total = 0.0
        for t in query_terms:
            f = tf.get(t, 0)
            if f == 0:
                continue
            numerator = f * (k1 + 1)
            denominator = f + k1 * (1 - b + b * dl / self.avg_doc_length)
            total += self.idf(t) * numerator / denominator
        return total

    def search(self, query: str, top_k: int = 5,
               k1: float = K1, b: float = B) -> list[tuple[Paragraph, float]]:
        """k1/b are scoring-time parameters, so a sweep reuses one index."""
        terms = tokenize(query)
        scored = [(i, self.score(terms, i, k1, b)) for i in range(self.n_docs)]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [(self.paragraphs[i], s) for i, s in scored[:top_k]]

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: Path) -> "BM25Index":
        """A pickle records the module path of every class inside it, so an
        index built before this module moved (eval/bm25.py to
        retrieval/bm25.py, 2026-09-04) raises a bare ModuleNotFoundError
        that says nothing about what to do. Caught here and turned into the
        instruction: rebuild. The index is git-ignored and regenerable in
        about 100 seconds, so rebuilding is always the right answer."""
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"{path} was pickled against a module layout that no longer exists "
                f"({exc}). Rebuild it: see eval/README.md, 'bm25.py: hand-built retrieval'."
            ) from exc


def iter_paragraphs(xml_path: Path, pmcid: str) -> list[Paragraph]:
    """All abstract + body paragraphs for one article, tagged with the pmcid,
    so a hit here is directly usable as a gold_span-shaped citation. Offsets
    come from common.corpus_text, which owns the convention."""
    return [Paragraph(pmcid, section, start, end, text)
            for section, text, start, end in _iter_paragraphs(xml_path)
            if text.strip()]


def index_from_paragraphs(paragraphs: list[Paragraph]) -> BM25Index:
    """The scoring-side half of index construction, split out from
    build_index so the identical formula can be pointed at something other
    than this project's own corpus. That is what makes the harness
    validation in benchmarks/run_benchmark.py meaningful: SciFact and
    NFCorpus are scored by exactly this code, not by a reimplementation of
    it that could agree with the reference while the real one disagrees."""
    term_freqs = [Counter(tokenize(p.text)) for p in paragraphs]
    doc_lengths = [sum(tf.values()) for tf in term_freqs]
    doc_freq: dict[str, int] = {}
    for tf in term_freqs:
        for term in tf:
            doc_freq[term] = doc_freq.get(term, 0) + 1
    n_docs = len(paragraphs)
    avg_doc_length = sum(doc_lengths) / n_docs if n_docs else 0.0

    return BM25Index(
        paragraphs=paragraphs, doc_freq=doc_freq, term_freqs=term_freqs,
        doc_lengths=doc_lengths, avg_doc_length=avg_doc_length, n_docs=n_docs,
    )


def build_index(xml_dir: Path, pmcids: list[str], min_paragraph_words: int = 5) -> BM25Index:
    paragraphs: list[Paragraph] = []
    for pmcid in pmcids:
        xml_path = xml_dir / f"{pmcid}.xml"
        if not xml_path.exists():
            continue
        for p in iter_paragraphs(xml_path, pmcid):
            if len(tokenize(p.text)) >= min_paragraph_words:
                paragraphs.append(p)
    return index_from_paragraphs(paragraphs)


def build_index_from_texts(docs: list[tuple[str, str]]) -> BM25Index:
    """Index (doc_id, text) pairs as whole documents, one Paragraph each.

    For a benchmark corpus there is no section structure and no char-offset
    provenance to preserve, so those fields are degenerate by design:
    `section` is "doc" and the offsets span the whole text. They are kept
    rather than made optional so there is exactly one index type in this
    project, and so a benchmark hit and a corpus hit are the same shape."""
    paragraphs = [Paragraph(doc_id, "doc", 0, len(text), text) for doc_id, text in docs]
    return index_from_paragraphs(paragraphs)
