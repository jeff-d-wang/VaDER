"""
Hand-built Okapi BM25, no ranking library. This is the M1 baseline's
retrieval half (`PROJECT_PLAN.md`'s three-baseline requirement, "BM25-only"),
and also satisfies the project's own rule to implement at least one
component with no library (`START_HERE.md` standing rule 2 / the
"Protecting the learning" section of `PROJECT_PLAN.md`).

Indexes at paragraph granularity (title + abstract + body paragraphs), each
record carrying real provenance, (pmcid, section, char_start, char_end),
using the exact offset convention corpus_text.py already established
(paragraphs joined by "\\n"), so a BM25 hit is a real, citable span, not
just a ranked document id.

Formula: standard Okapi BM25 with the "+1" IDF variant (never negative,
unlike the classic Robertson-Sparck Jones form, which can go negative for a
term that appears in over half the corpus, e.g. "cancer" here):

    score(D, Q) = sum over query terms t of:
        idf(t) * f(t, D) * (k1 + 1) / (f(t, D) + k1 * (1 - b + b * |D| / avgdl))

    idf(t) = ln((N - n(t) + 0.5) / (n(t) + 0.5) + 1)

k1=1.5, b=0.75: the standard textbook defaults (Robertson & Zaragoza 2009),
not tuned against this corpus. Tuning k1/b against the retrieval eval set is
future work once that set (n>=300) exists; not worth doing against 19 cases.
"""
from __future__ import annotations

import math
import pickle
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from corpus_text import extract_section_text

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

    def score(self, query_terms: list[str], i: int) -> float:
        tf = self.term_freqs[i]
        dl = self.doc_lengths[i]
        total = 0.0
        for t in query_terms:
            f = tf.get(t, 0)
            if f == 0:
                continue
            numerator = f * (K1 + 1)
            denominator = f + K1 * (1 - B + B * dl / self.avg_doc_length)
            total += self.idf(t) * numerator / denominator
        return total

    def search(self, query: str, top_k: int = 5) -> list[tuple[Paragraph, float]]:
        terms = tokenize(query)
        scored = [(i, self.score(terms, i)) for i in range(self.n_docs)]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [(self.paragraphs[i], s) for i, s in scored[:top_k]]

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: Path) -> "BM25Index":
        with open(path, "rb") as f:
            return pickle.load(f)


def iter_paragraphs(xml_path: Path, pmcid: str) -> list[Paragraph]:
    """All abstract + body paragraphs for one article, offsets matching
    corpus_text.extract_section_text's "\\n"-join convention exactly (so a
    result here is directly usable as a gold_span-shaped citation)."""
    out = []
    for section in ("abstract", "body"):
        text = extract_section_text(xml_path, section)
        if not text:
            continue
        offset = 0
        for para in text.split("\n"):
            if para.strip():
                out.append(Paragraph(pmcid, section, offset, offset + len(para), para))
            offset += len(para) + 1
    return out


def build_index(xml_dir: Path, pmcids: list[str], min_paragraph_words: int = 5) -> BM25Index:
    paragraphs: list[Paragraph] = []
    for pmcid in pmcids:
        xml_path = xml_dir / f"{pmcid}.xml"
        if not xml_path.exists():
            continue
        for p in iter_paragraphs(xml_path, pmcid):
            if len(tokenize(p.text)) >= min_paragraph_words:
                paragraphs.append(p)

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
