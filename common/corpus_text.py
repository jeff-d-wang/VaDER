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

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from xml.etree import ElementTree as ET

SECTION_TAGS = {"abstract": "abstract", "body": "body"}


def _paragraph_items(node: ET.Element) -> list[tuple[str, ET.Element | None]]:
    """(text, the <p> element it came from) per paragraph. The element is
    None for the bare-text fallback below, which has no element of its own.

    Everything that needs per-paragraph metadata derives it from this list,
    so metadata cannot drift out of alignment with the offsets: both come
    from one enumeration rather than two that agree by assertion. That is
    the same failure this module was created to end (see the docstring)."""
    ps = node.findall(".//p")
    if ps:
        return [("".join(p.itertext()), p) for p in ps]
    # No <p> children (e.g. some abstracts are a bare <abstract>text</abstract>):
    # fall back to the node's own text as a single "paragraph".
    text = "".join(node.itertext())
    return [(text, None)] if text else []


def _paragraph_texts(node: ET.Element) -> list[str]:
    return [text for text, _ in _paragraph_items(node)]


def _enclosing_sec_title(element: ET.Element | None,
                         parents: dict[ET.Element, ET.Element]) -> str | None:
    """The <title> of the nearest <sec> ancestor, or None. Walks up via an
    explicit parent map because ElementTree elements carry no parent link."""
    current = element
    while current is not None:
        if current.tag == "sec":
            title = current.find("title")
            if title is not None:
                text = " ".join("".join(title.itertext()).split())
                if text:
                    return text
        current = parents.get(current)
    return None


# Every dash shape actually found in the corpus's citation ranges/lists
# ("2-4", "21‑94", "19−21"), plus comma/semicolon and whitespace:
# the punctuation a citation list is built from, never real prose.
_SEP = r",;\-‐‑‒–—−\s"
_SUP_NOTATION_RE = re.compile(rf"^[{_SEP}\[\]()]*$")


def _is_citation_marker(el: ET.Element) -> bool:
    """A JATS bibliographic reference marker: a bare `<xref ref-type="bibr">`,
    or a `<sup>` whose only element children are such xrefs (a superscript
    citation group like "2-4", where the dash is a text node between two
    xrefs, one sometimes empty) AND whose own text and every child's tail
    (both, still inside the closing `</sup>`) are nothing but that
    connector punctuation. Found by inspecting the real corpus: 7,402 of
    7,863 articles carry `ref-type="bibr"`, and it renders inline as bare
    digits with no separator from real prose ("were poor.\\n5\\nCCAs can
    be..."), which a person skimming a worksheet, or a model asked what a
    paragraph reports, can misread as data.

    A sampled 800 articles show the bare-xref shape (a `[1, 2]` or `(3-5)`
    citation list, not wrapped in `<sup>`) outnumbers the `<sup>`-wrapped
    shape 607 files to 153. `_visible_text`/`_strip_citation_sentinels`
    below is what makes the bare shape's surrounding `[...]`/`(...)` also
    disappear, not just the digits.

    The connector-only requirement exists because a `<sup>` can also carry
    a real label alongside its citation, not just citation notation --
    found in the real corpus: `<sup>mut<xref ref-type="bibr">37</xref></sup>`
    (BRCA1mut, a mutation-status label) and `<sup>Revertant
    <xref ref-type="bibr">24</xref></sup>` (a cell-line name). Treating the
    whole `<sup>` as one droppable unit there would silently delete
    "mut"/"Revertant" along with the citation -- a meaning-changing loss in
    exactly the variant-status text this project cares about, not a
    citation cleanup. When the check fails, the `<sup>` is not a marker as
    a whole; `_visible_text` then walks into it normally, and its `<xref>`
    child is still recognized and stripped on its own -- only the real text
    is spared, not the citation number."""
    if el.tag == "xref":
        return el.get("ref-type") == "bibr"
    if el.tag == "sup":
        xrefs = list(el)
        if not xrefs or not all(c.tag == "xref" and c.get("ref-type") == "bibr" for c in xrefs):
            return False
        return all(t is None or _SUP_NOTATION_RE.match(t)
                   for t in [el.text] + [c.tail for c in xrefs])
    return False


_CITATION_SENTINEL = "\x00"
# A `[...]`/`(...)` that holds nothing but sentinels and connector
# punctuation (comma, dash, whitespace) is citation apparatus, not prose --
# e.g. "[1, 2]" or "(3-5)" -- so the bracket goes too, not just the digits.
# The lookahead requires at least one sentinel inside; a bracket with no
# sentinel ("[30S]") or a mix of a sentinel and real words ("[see ref 3]")
# is left alone.
_BRACKETED_MARKER_RE = re.compile(
    rf"\[(?=[{_SEP}{_CITATION_SENTINEL}]*{_CITATION_SENTINEL})[{_SEP}{_CITATION_SENTINEL}]*\]")
_PARENED_MARKER_RE = re.compile(
    rf"\((?=[{_SEP}{_CITATION_SENTINEL}]*{_CITATION_SENTINEL})[{_SEP}{_CITATION_SENTINEL}]*\)")
# A sentinel with no enclosing bracket (the plain <sup> case, or a bare
# xref with no delimiter at all): collapse it and its connector punctuation
# to one space.
_BARE_MARKER_RUN_RE = re.compile(rf"[{_SEP}{_CITATION_SENTINEL}]*{_CITATION_SENTINEL}[{_SEP}{_CITATION_SENTINEL}]*")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,;:])")


def _visible_text(el: ET.Element) -> str:
    """Like `"".join(el.itertext())`, but a citation marker's own subtree is
    replaced with a sentinel (not just dropped) while its `.tail` (the real
    prose immediately after it, an ElementTree element's tail belongs to its
    parent, not to the element) is kept. The sentinel is what lets
    `_strip_citation_sentinels` find and remove an enclosing delimiter that
    belongs to the citation, not the prose."""
    parts = [el.text or ""]
    for child in el:
        if _is_citation_marker(child):
            parts.append(_CITATION_SENTINEL)
        else:
            parts.append(_visible_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _strip_citation_sentinels(text: str) -> str:
    """Second pass over `_visible_text`'s output: remove each citation
    sentinel, and with it a `[...]`/`(...)` that turns out to hold nothing
    but sentinels and connector punctuation, since that bracket is part of
    the citation, not the prose it interrupts."""
    text = _BRACKETED_MARKER_RE.sub("", text)
    text = _PARENED_MARKER_RE.sub("", text)
    text = _BARE_MARKER_RUN_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    return " ".join(text.split())


def clean_paragraph_texts(root: ET.Element, section: str) -> list[str]:
    """Each paragraph's text with citation-marker superscripts stripped and
    whitespace collapsed to single spaces, aligned index for index with
    `iter_paragraphs_from_root`'s yields for the same (root, section).

    **Presentation-only.** Never used to compute an offset, and no stored
    `char_start`/`char_end`/`gold_text_sha1` is read from or checked against
    it: standing rule 5's provenance is unaffected by anything this function
    does. It exists for the two places raw paragraph text reaches a reader
    who is not resolving a span: an LLM asked to write a query or answer
    about a paragraph, and a human worksheet. Both can otherwise treat a
    bibliographic marker as if it were a reported finding."""
    tag = SECTION_TAGS.get(section)
    node = root.find(f".//{tag}") if tag else None
    if node is None:
        return []
    return [_strip_citation_sentinels(_visible_text(p)) if p is not None else " ".join(text.split())
            for text, p in _paragraph_items(node)]


def section_titles_from_root(root: ET.Element, section: str) -> list[str | None]:
    """The enclosing <sec> title for each paragraph of a section, aligned
    index for index with iter_paragraphs_from_root's yields.

    Phase C stratifies the retrieval eval set by section type (methods
    paragraphs retrieve nothing like results paragraphs), and JATS records
    that as a free-text <title>, not an attribute. Returned raw; deciding
    that "Patients and methods" is a methods section is a caller's judgment,
    not this module's convention."""
    tag = SECTION_TAGS.get(section)
    node = root.find(f".//{tag}") if tag else None
    if node is None:
        return []
    parents = {child: parent for parent in node.iter() for child in parent}
    return [_enclosing_sec_title(element, parents) for _, element in _paragraph_items(node)]


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


def spans_overlap(a: dict, b: dict) -> bool:
    """Do two (pmcid, section, char_start, char_end) spans cover any of the
    same source text?

    This is the hit test the retrieval eval set needs: PROJECT_PLAN's rule 5
    attaches gold labels to source spans, never to chunk ids, so "did
    retrieval find it" means "does a returned span overlap a gold span".
    Chunk ids change whenever the chunker changes; source offsets do not,
    which is what makes the chunking ablation computable at all.

    Half-open intervals, so spans that merely touch (one ends exactly where
    the next begins) do NOT overlap. Paragraph offsets in this corpus are
    built by joining on a single separator character, so adjacent paragraphs
    share a boundary; counting that as a hit would credit a retriever for
    returning the paragraph next to the right one."""
    return (a["pmcid"] == b["pmcid"]
            and a["section"] == b["section"]
            and a["char_start"] < b["char_end"]
            and b["char_start"] < a["char_end"])


@dataclass
class Chunk:
    """A retrieval unit that carries provenance back to source offsets.

    START_HERE.md rule 5: a gold label attaches to a source span, never to a
    chunk id, so a chunk must record the spans it was built from. Defined here
    in phase B, before phase D's chunker exists, because this is the one schema
    decision that cannot be retrofitted without a full re-index.

    `source_spans` is a list, not a single span: phase D's structure-aware
    chunker may merge adjacent JATS paragraphs into one chunk, and each of
    those paragraphs is its own (section, char_start, char_end).
    """
    chunk_id: str
    pmcid: str
    text: str
    source_spans: list[dict]  # each: {"section", "char_start", "char_end"}

    def span(self) -> dict:
        """One (pmcid, section, char_start, char_end) covering all source
        spans, for a consumer that needs a single citation span rather than
        the list: the earliest start to the latest end, in the first span's
        section. Only meaningful when every source span is in one section,
        which the phase D chunker guarantees (it never merges across a
        section boundary)."""
        return {"pmcid": self.pmcid, "section": self.source_spans[0]["section"],
                "char_start": min(s["char_start"] for s in self.source_spans),
                "char_end": max(s["char_end"] for s in self.source_spans)}


def chunk_hits_span(chunk: Chunk, gold: dict) -> bool:
    """A chunk is a hit if any of its source spans overlaps the gold span."""
    return any(
        spans_overlap({"pmcid": chunk.pmcid, **s}, gold)
        for s in chunk.source_spans
    )
