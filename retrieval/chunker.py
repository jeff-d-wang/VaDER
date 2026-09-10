"""
The phase D structure-aware JATS chunker: raw article paragraphs in, a list
of `common.corpus_text.Chunk` out, each carrying provenance back to source
offsets so a span-attached gold label still resolves after a re-chunk
(START_HERE.md rule 5).

Design, logged in docs/DECISION_LOG.md ("the phase D structure-aware JATS
chunker") before this file existed:

  - Merge consecutive paragraphs that share a section ("abstract" / "body")
    AND an enclosing <sec> title, stopping a chunk when the next paragraph
    would take it past TARGET_TOKENS.
  - Never merge across a section boundary or a <sec>-title change.
  - Do not split a paragraph. One paragraph over the target lands alone in
    its own oversized chunk. ponytail: no intra-paragraph splitting; add a
    sentence splitter in M6 if the chunking ablation needs one.
  - Drop chunks under MIN_TOKENS and paragraphs under a boilerplate <sec>
    title (acknowledgements, funding, ethics, ...), the same exclusion list
    eval/build_retrieval_set.py uses.

Tokens are counted with retrieval.bm25.tokenize, the same tokenizer the
index and every retrieval number already use, so "350 tokens" means the same
thing here as it does to BM25.

`paragraph_chunks` is the identity chunker: one Chunk per raw paragraph, no
merging. Benchmarks (one doc per chunk) and M6's raw-paragraph baseline need
it. `build_index` in retrieval/bm25.py takes whichever of the two as a
parameter.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from common.corpus_text import (Chunk, iter_paragraphs_from_root,
                                section_titles_from_root)
from retrieval.bm25 import tokenize

SECTIONS = ("abstract", "body")
TARGET_TOKENS = 350
MIN_TOKENS = 5

# Substring match against the normalized (lowercased) <sec> title. A
# paragraph under one of these is dropped before chunking. Same list as
# eval/build_retrieval_set.py's boilerplate exclusion.
BOILERPLATE_TITLES = (
    "acknowledg", "funding", "ethic", "competing interest", "conflict of interest",
    "data availability", "abbreviation", "author contribution", "supplementary",
)


def _is_boilerplate(title: str | None) -> bool:
    if not title:
        return False
    low = title.lower()
    return any(key in low for key in BOILERPLATE_TITLES)


def _make_chunk(pmcid: str, section: str, run: list[tuple[str, int, int]]) -> Chunk | None:
    """Build one Chunk from a run of (text, char_start, char_end) paragraphs,
    or None if the merged text is under MIN_TOKENS. Each paragraph stays its
    own source_spans entry so a whole-paragraph gold span matches exactly."""
    text = "\n".join(t for t, _, _ in run)
    if len(tokenize(text)) < MIN_TOKENS:
        return None
    start, end = run[0][1], run[-1][2]
    return Chunk(
        chunk_id=f"{pmcid}:{section}:{start}-{end}",
        pmcid=pmcid,
        text=text,
        source_spans=[{"section": section, "char_start": s, "char_end": e}
                      for _, s, e in run],
    )


def chunk_article(root: ET.Element, pmcid: str) -> list[Chunk]:
    """Structure-aware chunks for one parsed article."""
    chunks: list[Chunk] = []
    for section in SECTIONS:
        paragraphs = list(iter_paragraphs_from_root(root, section))
        titles = section_titles_from_root(root, section)
        run: list[tuple[str, int, int]] = []
        run_key: tuple[str, str | None] | None = None
        run_tokens = 0
        for (text, start, end), title in zip(paragraphs, titles):
            if _is_boilerplate(title):
                if run:
                    chunk = _make_chunk(pmcid, section, run)
                    if chunk:
                        chunks.append(chunk)
                run, run_key, run_tokens = [], None, 0
                continue
            n = len(tokenize(text))
            key = (section, title)
            if run and (key != run_key or run_tokens + n > TARGET_TOKENS):
                chunk = _make_chunk(pmcid, section, run)
                if chunk:
                    chunks.append(chunk)
                run, run_tokens = [], 0
            run.append((text, start, end))
            run_key = key
            run_tokens += n
        if run:
            chunk = _make_chunk(pmcid, section, run)
            if chunk:
                chunks.append(chunk)
    return chunks


def paragraph_chunks(root: ET.Element, pmcid: str) -> list[Chunk]:
    """Identity chunker: one Chunk per raw paragraph, no merging, no boilerplate
    filter (benchmark corpora have no <sec> structure to filter on)."""
    chunks: list[Chunk] = []
    for section in SECTIONS:
        for text, start, end in iter_paragraphs_from_root(root, section):
            chunk = _make_chunk(pmcid, section, [(text, start, end)])
            if chunk:
                chunks.append(chunk)
    return chunks
