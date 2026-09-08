"""
Phase E: the real retrieval handler behind the streaming service. Replaces
Step 0c's stub keyword matcher (title-prefilter + per-candidate XML scan; see
docs/DECISION_LOG.md, "Step 0c built as a stub handler, v1 formally
dropped"). This is the same BM25-over-structure-aware-chunks path phase D
built and measured (`retrieval/bm25.py`, `retrieval/chunker.py`): one
postings-based index built once at startup, searched per request. No LLM yet
(that is Phase E's generation half, added separately so a load test can
measure the retrieval-only stage before the two are bundled).

Two consequences worth naming, since they change what `SearchStats`' fields
mean without changing the streamed JSON shape (app.py's callers, and every
field name on the wire, are unchanged):

- There is no per-candidate XML scan to cap or time out mid-flight anymore:
  a chunk's text is already in the index. `candidates_matched_by_title` and
  `candidates_scanned` both now report the same number, the size of the
  ranked hit pool the index returned (bounded by `max_scan`), because BM25
  has only one honest "how much did we look at" number where the stub had
  two different ones.
- `max_scan` is repurposed from "candidate files opened" to "how deep into
  the ranked index results to retrieve before truncating to `max_matches`",
  i.e. `BM25Index.search`'s `top_k`. `deadline_s` is still a wall-clock
  guard around the search call, now checked once after a single bounded
  index lookup rather than between many small per-candidate steps.
"""
from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from common.trace import span
from retrieval.bm25 import BM25Index, tokenize


@dataclass
class ArticleMeta:
    pmcid: str
    title: str
    journal: str
    pubdate: str


@dataclass
class MatchSpan:
    pmcid: str
    title: str
    section: str
    char_start: int
    char_end: int
    text: str


@dataclass
class SearchStats:
    query_words: list[str] = field(default_factory=list)
    candidates_matched_by_title: int = 0
    candidates_scanned: int = 0
    matches_found: int = 0
    stopped_reason: str = ""  # max_matches | deadline | exhausted | no_query_words


def load_manifest(manifest_path: Path) -> list[ArticleMeta]:
    """Load the ok rows of corpus/manifest.csv. Returns [] if the manifest
    doesn't exist yet, so the service can start (and report itself unhealthy)
    before the corpus pull has run."""
    if not manifest_path.exists():
        return []
    articles = []
    with open(manifest_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") != "ok":
                continue
            articles.append(ArticleMeta(
                pmcid=row["pmcid"], title=row.get("title", ""),
                journal=row.get("journal", ""), pubdate=row.get("pubdate", ""),
            ))
    return articles


def search(query: str, articles: list[ArticleMeta], stats: SearchStats, *,
           index: BM25Index, max_scan: int = 40, max_matches: int = 5,
           deadline_s: float = 5.0) -> Iterator[MatchSpan]:
    """Yields each MatchSpan as it's found, so a caller streaming the response
    can flush the first result as soon as it exists rather than waiting for
    the whole search to finish. Mutates `stats` in place; read it once the
    generator is exhausted to see the result count and why the search
    stopped. `index` is the corpus's BM25 index, built once at service
    startup (see app.py's lifespan) and searched fresh per request."""
    words = tokenize(query)
    stats.query_words = words
    if not words:
        stats.stopped_reason = "no_query_words"
        return

    t0 = time.monotonic()
    with span("retrieve", retriever="bm25", top_k=max_scan) as s:
        hits = index.search(query, top_k=max_scan)
        s["retrieval.hit_count"] = len(hits)
    stats.candidates_matched_by_title = len(hits)
    stats.candidates_scanned = len(hits)
    if time.monotonic() - t0 > deadline_s:
        stats.stopped_reason = "deadline"
        return

    title_by_pmcid = {a.pmcid: a.title for a in articles}
    for chunk, _score in hits[:max_matches]:
        gold_span = chunk.span()  # {pmcid, section, char_start, char_end}
        stats.matches_found += 1
        yield MatchSpan(
            pmcid=chunk.pmcid, title=title_by_pmcid.get(chunk.pmcid, chunk.pmcid),
            section=gold_span["section"], char_start=gold_span["char_start"],
            char_end=gold_span["char_end"], text=chunk.text[:500],
        )
    stats.stopped_reason = "max_matches" if len(hits) > max_matches else "exhausted"
