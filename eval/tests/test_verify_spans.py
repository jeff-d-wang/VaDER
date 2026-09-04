"""Stdlib-only tests for corpus_text.py and verify_spans.py. Run directly:
    python -m eval.tests.test_verify_spans
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from common.corpus_text import extract_section_text, find_quote
from eval.verify_spans import expand_to_paragraph, extract_quotes

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


SAMPLE_XML = """<article>
  <front><article-meta><abstract>
    <p>First abstract paragraph about BRCA1 and breast cancer risk.</p>
    <p>Second abstract paragraph with more detail on penetrance.</p>
  </abstract></article-meta></front>
  <body>
    <p>Body paragraph one, unrelated content here.</p>
    <p>Body paragraph two mentions the "smoking gun" phrase for testing.</p>
  </body>
</article>
"""

NO_P_XML = """<article>
  <front><article-meta><abstract>Bare abstract text, no child p elements at all.</abstract></article-meta></front>
  <body><p>One body paragraph.</p></body>
</article>
"""


def test_extract_section_text() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "PMC1.xml"
        path.write_text(SAMPLE_XML)
        abstract = extract_section_text(path, "abstract")
        check("abstract joins paragraphs with newline",
              abstract == "First abstract paragraph about BRCA1 and breast cancer risk."
                          "\nSecond abstract paragraph with more detail on penetrance.",
              repr(abstract))
        body = extract_section_text(path, "body")
        check("body extraction finds both paragraphs", body is not None and "smoking gun" in body)
        check("unknown section returns None", extract_section_text(path, "references") is None)

        no_p_path = Path(d) / "PMC2.xml"
        no_p_path.write_text(NO_P_XML)
        bare = extract_section_text(no_p_path, "abstract")
        check("bare abstract with no <p> falls back to node text",
              bare == "Bare abstract text, no child p elements at all.", repr(bare))

        missing = extract_section_text(Path(d) / "PMC404.xml", "abstract")
        check("missing file returns None", missing is None)


def test_find_quote() -> None:
    haystack = "The gene shows a 'dominant-negative' effect, per the report."
    exact = "dominant-negative"
    r = find_quote(haystack, exact)
    check("exact substring found", r == (18, 35), str(r))
    check("offsets round-trip", haystack[r[0]:r[1]] == exact)

    curly = "The gene shows a ‘dominant‑negative’ effect."  # curly quotes + non-breaking hyphen... actually use en dash
    curly = "Effects were “clearly pathogenic” in this cohort."
    r2 = find_quote(curly, 'clearly pathogenic')
    check("curly-quote text still matches a straight-quote needle", r2 is not None)

    spaced = "Multiple   spaces\nand\ta newline separate these words in the source."
    r3 = find_quote(spaced, "Multiple spaces and a newline separate")
    check("whitespace-collapsed needle matches whitespace-irregular haystack", r3 is not None, str(r3))
    if r3:
        check("mapped offsets land on real text",
              spaced[r3[0]:r3[1]].split() == "Multiple   spaces\nand\ta newline separate".split())

    check("absent quote returns None", find_quote(haystack, "not in here at all") is None)


def test_expand_to_paragraph() -> None:
    text = "Para one text.\nPara two has the anchor phrase in it.\nPara three."
    anchor = "anchor phrase"
    i = text.find(anchor)
    s, e = expand_to_paragraph(text, i, i + len(anchor))
    check("expands to the containing paragraph, not neighbors",
          text[s:e] == "Para two has the anchor phrase in it.", repr(text[s:e]))

    # match touching the very start / end of the whole string
    s0, e0 = expand_to_paragraph(text, 0, 5)
    check("match at string start doesn't underflow", s0 == 0, str(s0))
    last = text.rfind("Para three")
    s1, e1 = expand_to_paragraph(text, last, len(text))
    check("match at string end extends to len(text)", e1 == len(text), str(e1))

    single = "Only one paragraph, no newlines anywhere in it."
    s2, e2 = expand_to_paragraph(single, 5, 8)
    check("single-paragraph text expands to the whole string", (s2, e2) == (0, len(single)))


def test_extract_quotes() -> None:
    note = ("Source states 'short' and also 'This is long enough to count as a real quote.'"
            " A second one: 'Another quote long enough to be extracted here too.'")
    quotes = extract_quotes(note)
    check("short quote below MIN_QUOTE_LEN excluded", "short" not in quotes)
    check("long quotes both extracted",
          any("This is long enough" in q for q in quotes) and
          any("Another quote long enough" in q for q in quotes),
          str(quotes))

    sentence_note = "Reports 'First sentence here is long enough. Second sentence also long enough.'"
    candidates = extract_quotes(sentence_note)
    check("whole block is the first candidate",
          candidates[0] == "First sentence here is long enough. Second sentence also long enough.")
    check("individual sentences offered as fallback candidates",
          "First sentence here is long enough." in candidates and
          "Second sentence also long enough." in candidates,
          str(candidates))

    check("no quotes in a note with no single-quote marks", extract_quotes("Plain text, no quotes.") == [])


def test_subject_check():
    """The check this script lacked until 2026-09-04. The regression it
    guards is real and is in the repo's history: a quote about ATM
    c.7271T>G was located, verified as present, and written in as the gold
    span for a case about ATM c.7570G>C."""
    from eval.verify_spans import subject_check

    case = {"gene": "ATM", "variant": "c.7570G>C"}
    gene_level = {"gene": "BRCA2", "variant": None}

    check("span naming the exact variant is ok",
          subject_check("ATM c.7570G>C associates with breast cancer", case)[0] == "ok")

    check("the real regression: right gene, wrong variant, is gene_only not ok",
          subject_check(
              "This has previously been demonstrated for ATM c.7271T>G, (p.Val2424Gly), "
              "having up to 60% lifetime breast cancer by the age of 70 years.", case)[0]
          == "gene_only")

    check("span naming neither is absent",
          subject_check("Polygenic risk scores in unselected cohorts.", case)[0] == "absent")

    check("variant matches without the c. prefix",
          subject_check("the 7570G>C allele was enriched", case)[0] == "ok")

    check("gene-level case (no variant) is ok on a gene mention",
          subject_check("germline BRCA2 mutation carriers", gene_level)[0] == "ok")

    check("gene match is whole-word, not a substring",
          subject_check("the ATMIN cofactor was measured", {"gene": "ATM", "variant": None})[0]
          == "absent")


def run_tests() -> int:
    test_extract_section_text()
    test_find_quote()
    test_expand_to_paragraph()
    test_extract_quotes()
    test_subject_check()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
