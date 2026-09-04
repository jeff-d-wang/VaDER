"""
Verify (and where possible, repair) the gold_spans in answer_cases.jsonl
against the real corpus text.

A gold span is a claim: "(pmcid, section, char_start, char_end) supports
this quote." Two ways that claim can be wrong even when char_start/char_end
are in-bounds: the offsets were guessed (round numbers, never checked
against the file) rather than measured, or the article's text shifted
relative to whatever the author had in front of them. Guessed offsets read
as plausible prose either way, which is exactly why they need checking
against the actual XML, not just eyeballed.

Method: `disagreement_note` quotes its sources in single quotes for most
gold spans. For any span whose note contains a quote of least
MIN_QUOTE_LEN chars, this script searches that pmcid's abstract and body
text for the quote (whitespace/curly-quote tolerant, see
corpus_text.find_quote) and, if found, rewrites char_start/char_end (and
section, if the quote turned out to be in the other section) to the quote's
real location. A span whose note has no attributable quote is reported as
NO_QUOTE_TO_VERIFY and left untouched; that's a real limitation, not a
result, see the printed summary.

Usage:
    python -m eval.verify_spans                 # report only
    python -m eval.verify_spans --fix           # rewrite answer_cases.jsonl in place
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common.corpus_text import extract_section_text, find_quote


def expand_to_paragraph(text: str, start: int, end: int) -> tuple[int, int]:
    """Widen an exact quote match to the whole paragraph it's in (paragraphs
    are "\\n"-joined, see corpus_text.extract_section_text). A gold span at
    quote granularity can be a few dozen characters, too narrow to serve as
    a citation target; service/search.py's own spans are whole paragraphs,
    so gold spans match that same granularity."""
    para_start = text.rfind("\n", 0, start) + 1  # rfind returns -1 if absent, +1 -> 0
    newline_pos = text.find("\n", end)
    para_end = newline_pos if newline_pos != -1 else len(text)
    return para_start, para_end

MIN_QUOTE_LEN = 15
CASES_PATH = Path(__file__).parent / "data" / "answer_cases.jsonl"
XML_DIR = Path(__file__).parent.parent / "corpus" / "xml"


def subject_check(span_text: str, case: dict) -> tuple[str, str | None]:
    """Does this span actually talk about the case's subject?

    Added 2026-09-04 after the phase A1 case-validation pass found this
    script had not just missed an error but *created* one. For
    `atm_c7570g_c_risk_class_disagree_001`, the note quoted "up to 60%
    lifetime breast cancer by the age of 70 years". That phrase really is in
    PMC10092731, in a background paragraph about a completely different
    variant (c.7271T>G). The quote search found it, `expand_to_paragraph`
    widened to that paragraph, and `--fix` wrote the offsets in. Every
    individual step worked. The script verified that the quote exists in the
    article and never asked the question that mattered: is this span about
    the variant the case is about?

    Three outcomes, not two, because a strict variant requirement would
    false-positive on legitimate spans: a disagreement case's "the other
    side" span is often about the gene in general (e.g. "ATM pathogenic
    variants show HR 1.32"), which is exactly the contrast the case is
    built on.

      ok            the specific variant notation appears in the span
      gene_only     the gene appears but the variant does not. Legitimate
                    for a general-risk contrast span, a red flag for a span
                    meant to support a variant-specific claim. Needs a human.
      absent        neither appears. Strong signal the span is wrong.
    """
    variant = case.get("variant")
    normalized = " ".join(span_text.split()).lower()
    if variant:
        candidates = [variant]
        if variant[:2] in ("c.", "p."):
            candidates.append(variant[2:])
        for term in candidates:
            if term.lower() in normalized:
                return "ok", term
    gene = case.get("gene")
    if gene and re.search(rf"\b{re.escape(gene)}\b", span_text, re.I):
        return ("gene_only" if variant else "ok"), gene
    return "absent", None


def extract_quotes(note: str) -> list[str]:
    """Candidate quotes to search for, longest first. A note's quote marks
    don't guarantee the enclosed text is byte-exact against the source (one
    real case found here: a note ended a quoted sentence with a period
    where the source had a comma and kept going), so for each quoted block
    this also offers its individual sentences as fallback candidates: a
    quote that fails whole often still matches sentence by sentence.
    Splitting on the quote character (rather than a greedy regex) is what
    makes block extraction correct when a note mixes several short quoted
    terms with one long one: split() alternates
    [outside, quoted, outside, quoted, ...], so odd indices are exactly the
    quoted spans, nothing in between them."""
    blocks = [q for q in note.split("'")[1::2] if len(q) >= MIN_QUOTE_LEN]
    candidates: list[str] = []
    for block in blocks:
        candidates.append(block)
        for sentence in re.split(r"(?<=[.;])\s+", block):
            if len(sentence) >= MIN_QUOTE_LEN and sentence not in candidates:
                candidates.append(sentence)
    return candidates


def load_cases() -> list[dict]:
    with open(CASES_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_cases(cases: list[dict]) -> None:
    with open(CASES_PATH, "w") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")


def verify_case(case: dict, fix: bool) -> list[str]:
    """Returns a list of report lines for this case."""
    lines = []
    note = case["gold"].get("disagreement_note", "")
    quotes = extract_quotes(note)
    for span in case["gold_spans"]:
        pmcid, section = span["pmcid"], span["section"]
        xml_path = XML_DIR / f"{pmcid}.xml"
        if not xml_path.exists():
            lines.append(f"  [MISSING_FILE] {pmcid}")
            continue

        declared_text = extract_section_text(xml_path, section)
        if declared_text is None:
            lines.append(f"  [NO_SUCH_SECTION] {pmcid}/{section}")
            continue

        # Try every quote against both sections of this pmcid; a note can
        # quote a source without saying which section it came from.
        match = None
        for quote in quotes:
            for candidate_section in ("abstract", "body"):
                text = declared_text if candidate_section == section else \
                    extract_section_text(xml_path, candidate_section)
                if text is None:
                    continue
                found = find_quote(text, quote)
                if found:
                    match = (candidate_section, found[0], found[1], quote)
                    break
            if match:
                break

        if match is None:
            in_range = 0 <= span["char_start"] < span["char_end"] <= len(declared_text)
            status = "in range, unverified" if in_range else "OUT OF RANGE"
            lines.append(
                f"  [NO_QUOTE_TO_VERIFY] {pmcid}/{section} "
                f"[{span['char_start']}:{span['char_end']}] ({status})"
            )
            if in_range:
                lines += _subject_lines(declared_text[span["char_start"]:span["char_end"]],
                                        case, pmcid)
            continue

        cand_section, quote_start, quote_end = match[0], match[1], match[2]
        cand_text = declared_text if cand_section == section else extract_section_text(xml_path, cand_section)
        start, end = expand_to_paragraph(cand_text, quote_start, quote_end)
        current = (section, span["char_start"], span["char_end"])
        correct = (cand_section, start, end)
        verdict, _term = subject_check(cand_text[start:end], case)

        if current == correct:
            lines.append(f"  [OK] {pmcid}/{section} [{span['char_start']}:{span['char_end']}]")
        elif verdict == "absent" and fix:
            # The quote matched somewhere that mentions neither the variant
            # nor the gene. Rewriting to it is how this script cemented a
            # wrong span once already; refuse and make a human look.
            lines.append(
                f"  [REFUSED_FIX] {pmcid}: quote found at {cand_section}[{start}:{end}] but that "
                f"span mentions neither {case.get('variant') or ''} nor {case.get('gene')}. "
                f"Left as-is; verify by hand."
            )
        else:
            lines.append(
                f"  [FIXED] {pmcid}: {section}[{span['char_start']}:{span['char_end']}] "
                f"-> {cand_section}[{start}:{end}]"
            )
            if fix:
                span["section"] = cand_section
                span["char_start"] = start
                span["char_end"] = end
        lines += _subject_lines(cand_text[start:end], case, pmcid)
    return lines


def _subject_lines(span_text: str, case: dict, pmcid: str) -> list[str]:
    verdict, term = subject_check(span_text, case)
    if verdict == "ok":
        return []
    if verdict == "gene_only":
        return [f"    [SUBJECT_GENE_ONLY] {pmcid}: span mentions {term} but not "
                f"{case['variant']}. Legitimate for a general-risk contrast span, wrong for a "
                f"variant-specific claim. Needs a human."]
    return [f"    [SUBJECT_ABSENT] {pmcid}: span mentions neither "
            f"{case.get('variant') or '(no variant)'} nor {case.get('gene')}."]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true",
                         help="rewrite answer_cases.jsonl with corrected offsets")
    args = parser.parse_args()

    cases = load_cases()
    counts = {"OK": 0, "FIXED": 0, "REFUSED_FIX": 0, "NO_QUOTE_TO_VERIFY": 0,
              "MISSING_FILE": 0, "NO_SUCH_SECTION": 0,
              "SUBJECT_GENE_ONLY": 0, "SUBJECT_ABSENT": 0}
    for case in cases:
        if not case["gold_spans"]:
            continue
        print(case["case_id"])
        for line in verify_case(case, args.fix):
            print(line)
            for key in counts:
                if f"[{key}]" in line:
                    counts[key] += 1

    if args.fix:
        write_cases(cases)
        print(f"\nRewrote {CASES_PATH}")

    print("\nSummary:", counts)
    if counts["NO_QUOTE_TO_VERIFY"] or counts["MISSING_FILE"] or counts["NO_SUCH_SECTION"]:
        print("Spans above need manual review; this script does not guess without a quote to check against.")
    if counts["SUBJECT_ABSENT"] or counts["SUBJECT_GENE_ONLY"] or counts["REFUSED_FIX"]:
        print("Subject flags above are the check this script lacked until 2026-09-04, when a "
              "case-validation pass found it had repointed a span onto a paragraph about a "
              "different variant. A quote existing in an article does not make it the right quote.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
