"""
The one definition of this project's source-span offset convention, and the
only place JATS paragraphs get pulled out of an article.

START_HERE.md standing rule 5: labels attach to source spans,
(pmcid, section_id, char_start, char_end), never to chunks. That only holds
if every producer and consumer of an offset agrees on how offsets are
counted. Until 2026-09-05 three files counted them separately (this one,
service/search.py, eval/find_coverage.py), agreeing only by prose assertion,
and they had already drifted: find_coverage silently produced no paragraphs
at all for an abstract written as bare text with no <p> children, where this
module produces one. Every caller now goes through iter_paragraphs.

The convention: paragraphs of a section in document order, joined by a
single "\n", offsets restarting at 0 per section. So for any span this
project emits, `extract_section_text(...)[char_start:char_end]` is the text
it points at.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

SECTION_TAGS = {"abstract": "abstract", "body": "body"}


@dataclass
class ParseError:
    pmcid: str
    reason: str


def _paragraph_texts(node: ET.Element) -> list[str]:
    ps = node.findall(".//p")
    if ps:
        return ["".join(p.itertext()) for p in ps]
    # No <p> children (e.g. some abstracts are a bare <abstract>text</abstract>):
    # fall back to the node's own text as a single "paragraph".
    text = "".join(node.itertext())
    return [text] if text else []


def parse_root(xml_path: Path) -> ET.Element | None:
    """The article root, or None if the file is missing or unparseable. A
    caller that needs both paragraphs and something else off the same
    article (a title, say) parses once with this and passes the root to
    iter_paragraphs_from_root, rather than paying a second parse."""
    try:
        return ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return None


def iter_paragraphs_from_root(root: ET.Element, section: str
                               ) -> Iterator[tuple[str, int, int]]:
    """(text, char_start, char_end) per paragraph of one section, in
    document order. Yields nothing for an unknown or absent section."""
    tag = SECTION_TAGS.get(section)
    if tag is None:
        return
    node = root.find(f".//{tag}")
    if node is None:
        return
    offset = 0
    for text in _paragraph_texts(node):
        yield text, offset, offset + len(text)
        offset += len(text) + 1  # the "\n" extract_section_text joins with


def iter_paragraphs(xml_path: Path, sections: tuple[str, ...] = ("abstract", "body")
                     ) -> Iterator[tuple[str, str, int, int]]:
    """(section, text, char_start, char_end) for every paragraph of the
    named sections. This is the shared entry point: bm25 indexing,
    find_coverage's corpus sweep and service/search.py all read paragraphs
    through here so a span means the same thing to all of them."""
    root = parse_root(xml_path)
    if root is None:
        return
    for section in sections:
        for text, start, end in iter_paragraphs_from_root(root, section):
            yield section, text, start, end


def extract_section_text(xml_path: Path, section: str) -> str | None:
    """The whole section as one string, paragraphs joined by "\\n". None if
    the file is missing, unparseable, or has no such section. This is the
    string every (char_start, char_end) pair indexes into."""
    root = parse_root(xml_path)
    if root is None:
        return None
    tag = SECTION_TAGS.get(section)
    if tag is None or root.find(f".//{tag}") is None:
        return None
    return "\n".join(text for text, _, _ in iter_paragraphs_from_root(root, section))


_PUNCT_MAP = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-",
})


def _normalize(text: str) -> str:
    """Collapse whitespace, fold curly quotes/dashes to their straight ASCII
    forms. Used only to make substring search tolerant of encoding
    differences between a hand-copied quote and the source XML; never used
    to compute offsets directly (see find_quote, which maps back)."""
    return " ".join(text.translate(_PUNCT_MAP).split())


def find_quote(haystack: str, quote: str) -> tuple[int, int] | None:
    """Finds `quote` inside `haystack` tolerant of whitespace/quote-char
    drift, returns (char_start, char_end) as real offsets into the
    *original* haystack, or None if not found. Builds an index map from the
    normalized string back to the original so the returned offsets are
    exact, not approximate."""
    norm_chars: list[str] = []
    index_map: list[int] = []  # index_map[i] = original index of norm_chars[i]
    prev_was_space = True  # so leading whitespace is skipped like _normalize does
    for i, ch in enumerate(haystack):
        mapped = ch.translate(_PUNCT_MAP)
        if mapped.isspace():
            if not prev_was_space:
                norm_chars.append(" ")
                index_map.append(i)
                prev_was_space = True
            continue
        norm_chars.append(mapped)
        index_map.append(i)
        prev_was_space = False
    norm_haystack = "".join(norm_chars).rstrip()
    norm_quote = _normalize(quote)
    pos = norm_haystack.find(norm_quote)
    if pos == -1:
        return None
    start = index_map[pos]
    end_norm_idx = pos + len(norm_quote) - 1
    end = index_map[end_norm_idx] + 1
    return start, end


def load_span_text(xml_dir: Path, pmcid: str, section: str, char_start: int, char_end: int
                    ) -> tuple[str | None, str | None]:
    """Returns (span_text, error). error is None on success; otherwise a short
    machine-readable reason (missing_file, unparseable, no_such_section,
    out_of_range)."""
    xml_path = xml_dir / f"{pmcid}.xml"
    if not xml_path.exists():
        return None, "missing_file"
    section_text = extract_section_text(xml_path, section)
    if section_text is None:
        return None, "no_such_section_or_unparseable"
    if char_start < 0 or char_end > len(section_text) or char_start >= char_end:
        return None, "out_of_range"
    return section_text[char_start:char_end], None
