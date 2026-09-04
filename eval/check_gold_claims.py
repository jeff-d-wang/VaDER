"""
Does a case's gold label assert numbers that its own gold spans don't
contain?

Written 2026-09-04, after the phase A1 validation pass found this exact
defect in 2 of 8 cases (docs/DECISION_LOG.md, "half the gold set is
defective"):

  atm_at_lymphoid_tumor_ord_001   gold strength asserts "296 ... patients,
                                  66 ... 47 lymphoid, 19 non-lymphoid".
                                  Those figures are in PMC3170966's
                                  abstract at roughly 380-700. The gold
                                  span starts at 617.
  brca_prs_ovarian_risk_ord_001   gold strength asserts "15,252 BRCA1 and
                                  8,211 BRCA2 carriers". Those are in
                                  PMC5408990's abstract at roughly 816. The
                                  gold span starts at 1057.

Both are the same shape and both are catchable with arithmetic, no LLM and
no judgment: pull every number out of the gold label, pull every number out
of the text the gold spans actually point at, and report the difference.
That is all this does.

It is a PRECISION tool, not a recall tool. A missing number is strong
evidence of a real problem. A clean result proves only that the numbers
line up: `brca_prs_ovarian_risk_ord_001`'s other defect, attributing a
BRCA2-only finding to BRCA1 and BRCA2 both, involves no numbers at all and
this script cannot see it. Numeric drift is the cheap half of citation
drift, not the whole of it.

Usage:
    python -m eval.check_gold_claims                  # all cases
    python -m eval.check_gold_claims --case-id foo    # one case
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common.corpus_text import load_span_text

CASES_PATH = Path(__file__).parent / "data" / "answer_cases.jsonl"
XML_DIR = Path(__file__).parent.parent / "corpus" / "xml"

# Digits separated by a comma, ordinary space, non-breaking space, thin
# space or narrow no-break space are one number. Journals use all of these
# as thousands separators, and PMC XML preserves whichever the publisher
# chose: the source of 15,252 above literally reads "15 252".
_THOUSANDS = re.compile(r"(?<=\d)[,    ](?=\d)")
# Not preceded by a letter, digit or dot. The letter guard is what keeps
# gene symbols out of the claim set: without it BRCA1 yields the token "1",
# TP53 yields "53", and a PMCID yields a phantom eight-digit claim. The dot
# guard stops the ".11" of "4.11" from also matching as its own number.
_NUMBER = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?")


def numbers_in(text: str) -> set[str]:
    """Number tokens, thousands separators removed and trailing zeros in
    decimals left alone. Returning a set of tokens rather than doing
    substring search is what gives correct boundaries for free: "66" cannot
    match inside "660", because tokenization already split them."""
    return set(_NUMBER.findall(_THOUSANDS.sub("", text)))


# Gene symbols written with a slashed suffix: BRCA1/2, MSH2/6. The leading
# letter guard in _NUMBER already excludes the "1" of BRCA1, but the "2" of
# BRCA1/2 is preceded by a slash and slips through as a claim that the
# source "asserts 2". Found as a false positive on the first real run.
_GENE_SYMBOL = re.compile(r"\b[A-Z]{2,}\d+(?:/\d+)*\b")


def gold_claim_text(case: dict) -> str:
    """The parts of a gold label that make factual assertions, with the
    things that carry digits without asserting anything removed first: the
    variant notation (`c.1592delT`, `c.7570G>C` are positions, not
    findings) and gene symbols (`BRCA1/2`, `TP53`)."""
    parts = [str(case["gold"].get("direction") or ""), str(case["gold"].get("strength") or "")]
    text = " ".join(parts)
    variant = case.get("variant")
    if variant:
        text = text.replace(variant, " ")
    return _GENE_SYMBOL.sub(" ", text)


def span_text_for(case: dict, xml_dir: Path) -> tuple[str, list[str]]:
    """All of this case's gold spans, concatenated. A number is credited if
    it appears in ANY of them: a multi-span case is allowed to draw its
    strength claim from across its sources."""
    chunks, errors = [], []
    for span in case["gold_spans"]:
        text, err = load_span_text(xml_dir, span["pmcid"], span["section"],
                                   span["char_start"], span["char_end"])
        if err is not None:
            errors.append(f"{span['pmcid']}/{span['section']}: {err}")
        else:
            chunks.append(text)
    return "\n".join(chunks), errors


def check_case(case: dict, xml_dir: Path = XML_DIR) -> dict:
    """Returns a result dict; `status` is one of:
       ok, missing_numbers, no_numeric_claim, no_spans, span_error."""
    if case["is_negative_case"] or not case["gold_spans"]:
        return {"case_id": case["case_id"], "status": "no_spans", "missing": []}

    text, errors = span_text_for(case, xml_dir)
    if errors and not text:
        return {"case_id": case["case_id"], "status": "span_error", "missing": [],
                "errors": errors}

    claimed = numbers_in(gold_claim_text(case))
    if not claimed:
        return {"case_id": case["case_id"], "status": "no_numeric_claim", "missing": []}

    present = numbers_in(text)
    missing = sorted(claimed - present, key=lambda s: (-len(s), s))
    return {
        "case_id": case["case_id"],
        "status": "missing_numbers" if missing else "ok",
        "missing": missing,
        "claimed": sorted(claimed),
        "errors": errors,
    }


def load_cases(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--xml-dir", default=str(XML_DIR))
    parser.add_argument("--case-id", help="check just this one case")
    args = parser.parse_args(argv)

    cases = load_cases(Path(args.cases))
    if args.case_id:
        cases = [c for c in cases if c["case_id"] == args.case_id]
        if not cases:
            print(f"No such case: {args.case_id}", file=sys.stderr)
            return 1

    counts: dict[str, int] = {}
    flagged = []
    for case in cases:
        result = check_case(case, Path(args.xml_dir))
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if result["status"] in ("missing_numbers", "span_error"):
            flagged.append(result)

    for result in flagged:
        print(f"[{result['status'].upper()}] {result['case_id']}")
        if result["missing"]:
            print(f"    gold asserts {', '.join(result['missing'])} "
                  f"— absent from every gold span")
        for err in result.get("errors", []):
            print(f"    unresolvable span: {err}")

    print(f"\nSummary: {counts}")
    if not flagged:
        print("No numeric drift found. Note what that does and does not mean: the numbers line "
              "up, which says nothing about attribution (whose result a figure is) or about "
              "claims with no numbers in them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
