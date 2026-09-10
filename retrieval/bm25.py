"""
Hand-built Okapi BM25, no ranking library. This is the M1 baseline's
retrieval half (`PROJECT_PLAN.md`'s three-baseline requirement, "BM25-only").

**The index unit is a `common.corpus_text.Chunk`** (phase D). A chunk carries
`source_spans`, a list of `(section, char_start, char_end)` back into the
source article, using the exact offset convention `corpus_text.py` owns
(paragraphs joined by "\\n"), so a BM25 hit is a real, citable span.
The raw-paragraph index of earlier phases is now just the identity chunker
(`retrieval.chunker.paragraph_chunks`): one chunk per paragraph, one span each.

Formula: standard Okapi BM25 with the "+1" IDF variant (never negative,
unlike the classic Robertson-Sparck Jones form, which can go negative for a
term that appears in over half the corpus, e.g. "cancer" here):

    score(D, Q) = sum over query terms t of:
        qtf(t) * idf(t) * f(t, D) * (k1 + 1) / (f(t, D) + k1 * (1 - b + b * |D| / avgdl))

    idf(t) = ln((N - n(t) + 0.5) / (n(t) + 0.5) + 1)

k1 and b are parameters, defaulting to k1=1.5, b=0.75, and `search` / `score`
take overrides so a comparison needs no re-indexing.

**Search is a postings scan** (phase D, per `DECISION_LOG.md` "BM25 search is
a full scan"). The index stores `postings: term -> [(chunk_idx, tf)]` rather
than a `Counter` per chunk, and `search` iterates only the postings of the
query terms, accumulating into a dict. A chunk containing no query term
scores 0 and was discarded by the old full scan too, so the ranking is
identical; memory drops because there is no per-chunk `Counter`. The
`test_bm25.py` gate asserts the identical ranking against a brute-force BM25.
"""
from __future__ import annotations

import math
import pickle
import re
import time
import heapq
from array import array
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from common.corpus_text import Chunk, parse_root

_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-.]*")  # keeps "c.1100delC", "BRCA1" etc. as one token

K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


@dataclass
class BM25Index:
    chunks: list[Chunk]
    # term -> a flat array of interleaved (chunk_idx, term_freq, chunk_idx, ...).
    # A list of (int, int) tuples costs about 64 bytes an entry in CPython; the
    # array costs 8.
    postings: dict[str, "array"]
    doc_lengths: list[int] # token count per chunk, same order as chunks
    avg_doc_length: float
    n_docs: int
    doc_freq: dict[str, int] = field(default_factory=dict)  # term -> #chunks containing it

    def idf(self, term: str) -> float:
        n_t = self.doc_freq.get(term, 0)
        return math.log((self.n_docs - n_t + 0.5) / (n_t + 0.5) + 1)

    def _term_freq(self, term: str, i: int) -> int:
        """tf of `term` in chunk `i`, read off the postings array. Linear in
        that term's document frequency; used only by `score` (a test and
        ad-hoc helper). `search` never calls it, it accumulates over postings
        directly."""
        plist = self.postings.get(term, ())
        for j in range(0, len(plist), 2):
            if plist[j] == i:
                return plist[j + 1]
        return 0

    def score(self, query_terms: list[str], i: int, k1: float = K1, b: float = B) -> float:
        dl = self.doc_lengths[i]
        total = 0.0
        for t, qtf in Counter(query_terms).items():
            f = self._term_freq(t, i)
            if f == 0:
                continue
            numerator = f * (k1 + 1)
            denominator = f + k1 * (1 - b + b * dl / self.avg_doc_length)
            total += qtf * self.idf(t) * numerator / denominator
        return total

    def search(self, query: str, top_k: int = 5,
               k1: float = K1, b: float = B, *, deadline: float | None = None) -> list[tuple[Chunk, float]]:
        """k1/b are scoring-time parameters, so a sweep reuses one index."""
        scores: dict[int, float] = {}
        if top_k < 1:
            raise ValueError("top_k must be positive")
        for t, qtf in Counter(tokenize(query)).items():
            plist = self.postings.get(t)
            if not plist:
                continue
            idf = self.idf(t)
            for j in range(0, len(plist), 2):
                if deadline is not None and j % 2048 == 0 and time.monotonic() >= deadline:
                    raise TimeoutError("retrieval deadline exceeded")
                i, f = plist[j], plist[j + 1]
                dl = self.doc_lengths[i]
                denominator = f + k1 * (1 - b + b * dl / self.avg_doc_length)
                scores[i] = scores.get(i, 0.0) + qtf * idf * f * (k1 + 1) / denominator
        # Tie-break on ascending chunk index, matching the old full scan's
        # stable sort over range(n_docs). Without the secondary key the dict's
        # insertion order (first query term's postings first) would break ties
        # differently and the identical-ranking gate could fail on equal scores.
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("retrieval deadline exceeded")
        ranked = heapq.nsmallest(top_k, scores.items(), key=lambda pair: (-pair[1], pair[0]))
        return [(self.chunks[i], s) for i, s in ranked[:top_k]]

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: Path) -> "BM25Index":
        """A pickle records the module path of every class inside it, so an
        index built before a module moved raises a bare ModuleNotFoundError
        that says nothing about what to do. Caught here and turned into the
        instruction: rebuild. The index is git-ignored and regenerable in
        about a minute, so rebuilding is always the right answer."""
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                f"{path} was pickled against a module layout that no longer exists "
                f"({exc}). Rebuild it: see eval/README.md, 'bm25.py: hand-built retrieval'."
            ) from exc


def index_from_chunks(chunks: list[Chunk]) -> BM25Index:
    """Build the postings index from chunks.

    Split out from `build_index` so the identical formula can be pointed at
    something other than this project's own corpus. That is what makes the
    harness validation in `benchmarks/run_benchmark.py` meaningful: SciFact
    and NFCorpus are scored by exactly this code."""
    flat: dict[str, list[int]] = {}
    doc_lengths: list[int] = []
    for i, chunk in enumerate(chunks):
        tf = Counter(tokenize(chunk.text))
        doc_lengths.append(sum(tf.values()))
        for term, count in tf.items():
            flat.setdefault(term, []).extend((i, count))
    postings = {term: array("i", pairs) for term, pairs in flat.items()}
    n_docs = len(chunks)
    avg_doc_length = sum(doc_lengths) / n_docs if n_docs else 0.0
    doc_freq = {term: len(p) // 2 for term, p in postings.items()}
    return BM25Index(chunks=chunks, postings=postings, doc_lengths=doc_lengths,
                     avg_doc_length=avg_doc_length, n_docs=n_docs, doc_freq=doc_freq)


def build_index(xml_dir: Path, pmcids: list[str], chunker=None, *,
                excluded_pmcids: set[str] | None = None) -> BM25Index:
    """Chunk every article with `chunker` (default: the phase D structure-aware
    chunker) and index the result. Pass `retrieval.chunker.paragraph_chunks`
    for the raw-paragraph (identity) index."""
    from retrieval.chunker import chunk_article  # local: chunker imports tokenize from here
    chunker = chunker or chunk_article
    chunks: list[Chunk] = []
    for pmcid in pmcids:
        if pmcid in (excluded_pmcids or ()):
            continue
        root = parse_root(xml_dir / f"{pmcid}.xml")
        if root is None:
            continue
        chunks.extend(chunker(root, pmcid))
    return index_from_chunks(chunks)


def build_index_from_texts(docs: list[tuple[str, str]]) -> BM25Index:
    """Index (doc_id, text) pairs as whole documents, one Chunk each.

    For a benchmark corpus there is no section structure and no char-offset
    provenance to preserve, so `source_spans` is degenerate by design: one
    span, section "doc", offsets spanning the whole text. Kept rather than
    made optional so there is exactly one index type and a benchmark hit and
    a corpus hit are the same shape."""
    chunks = [Chunk(chunk_id=doc_id, pmcid=doc_id, text=text,
                    source_spans=[{"section": "doc", "char_start": 0, "char_end": len(text)}])
              for doc_id, text in docs]
    return index_from_chunks(chunks)
