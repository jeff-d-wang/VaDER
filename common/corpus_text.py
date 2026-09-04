"""
Shared section-text extraction, used by verify_spans.py and score.py (for
pulling the text a citation's (pmcid, section, char_start, char_end) span
actually points at).

Offset convention matches service/search.py's `_find_span_in_xml` exactly:
paragraphs in document order, joined as if by a 1-character separator, so
`extract_section_text(...)[char_start:char_end]` lines up with any span
search.py already returns. This module reconstructs the actual joined
string search.py only accounts for virtually; search.py never needed the
full string, gold-span verification does.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


def extract_section_text(xml_path: Path, section: str) -> str | None:
    """Returns the concatenated section text (paragraphs joined by "\\n", the
    same 1-char-separator convention search.py's offset bookkeeping assumes),
    or None if the file is missing, unparseable, or the section doesn't
    exist in this article."""
    tag = SECTION_TAGS.get(section)
    if tag is None:
        return None
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return None
    node = root.find(f".//{tag}")
    if node is None:
        return None
    return "\n".join(_paragraph_texts(node))


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
