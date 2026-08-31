"""
Trivial keyword-match handler for Step 0c. This is not a retriever: it exists
only so the FastAPI service in app.py has real, variable-cost work to do per
request, so the streaming, TTFT, and concurrency measurements it produces are
honest. See docs/DECISION_LOG.md, "Step 0c built as a stub handler, v1
formally dropped." No chunker, no embedder, no vector DB, no LLM.

Two-stage literal keyword search:
  1. Candidate selection: articles whose title contains a query word, ranked
     by how many query words matched. In-memory, over the manifest.
  2. Span extraction: for each candidate in rank order, open its XML off disk
     and return the first body paragraph containing a query word, as a
     (pmcid, section, char_start, char_end) span. Stops at max_matches spans,
     max_scan candidates opened, or a wall-clock deadline, whichever comes
     first. That cap is the backpressure mechanism: an unbounded or
     zero-hit query cannot hang the server indefinitely.
"""
from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "into", "role", "its", "are"}


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
    stopped_reason: str = ""  # max_matches | max_scan | deadline | exhausted | no_query_words


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


def _query_words(query: str) -> list[str]:
    words = [w.lower() for w in _WORD_RE.findall(query)]
    return [w for w in words if len(w) >= 3 and w not in _STOPWORDS]


def _title_candidates(words: list[str], articles: list[ArticleMeta]) -> list[ArticleMeta]:
    """Articles whose title contains any query word, most-matching-words first."""
    scored = []
    for a in articles:
        title_lower = a.title.lower()
        score = sum(1 for w in words if w in title_lower)
        if score > 0:
            scored.append((score, a))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [a for _, a in scored]


def _find_span_in_xml(xml_path: Path, words: list[str]) -> MatchSpan | None:
    """First body paragraph containing a query word, as a source span. Real
    disk I/O and real XML parsing per candidate, which is the point: this is
    what gives the service genuine, variable-cost per-request latency."""
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return None
    body = root.find(".//body")
    if body is None:
        return None
    title_el = root.find(".//article-title")
    title = "".join(title_el.itertext()).strip() if title_el is not None else xml_path.stem

    offset = 0
    for p in body.findall(".//p"):
        text = "".join(p.itertext())
        text_lower = text.lower()
        if any(w in text_lower for w in words):
            return MatchSpan(
                pmcid=xml_path.stem, title=title, section="body",
                char_start=offset, char_end=offset + len(text),
                text=text[:500],
            )
        offset += len(text) + 1
    return None


def search(query: str, articles: list[ArticleMeta], xml_dir: Path, stats: SearchStats, *,
           max_scan: int = 40, max_matches: int = 5,
           deadline_s: float = 5.0) -> Iterator[MatchSpan]:
    """Yields each MatchSpan as it's found, so a caller streaming the response
    can flush the first result as soon as it exists rather than waiting for
    the whole search to finish. Mutates `stats` in place; read it once the
    generator is exhausted to see the result count and why the search
    stopped."""
    words = _query_words(query)
    stats.query_words = words
    if not words:
        stats.stopped_reason = "no_query_words"
        return

    candidates = _title_candidates(words, articles)
    stats.candidates_matched_by_title = len(candidates)

    start = time.monotonic()
    for article in candidates:
        if stats.candidates_scanned >= max_scan:
            stats.stopped_reason = "max_scan"
            return
        if time.monotonic() - start > deadline_s:
            stats.stopped_reason = "deadline"
            return
        stats.candidates_scanned += 1
        span = _find_span_in_xml(xml_dir / f"{article.pmcid}.xml", words)
        if span is not None:
            stats.matches_found += 1
            yield span
            if stats.matches_found >= max_matches:
                stats.stopped_reason = "max_matches"
                return
    stats.stopped_reason = "exhausted"
