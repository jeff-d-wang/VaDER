"""
Find HGVS variant notations that appear in very few corpus articles, as
candidates for hold-out negative cases.

This is the provenance of the negative cases in `answer_cases.jsonl`. They
say they were found "by mining every HGVS notation in the corpus and keeping
those with document frequency 1"; this is that mining step, kept in the repo
so the claim is reproducible rather than asserted.

**Why hold-out candidates have to be rare.** Guessing famous founder
variants does not work. BRCA1 185delAG appears in 89 corpus articles, CHEK2
I157T in 70, BRCA2 6174delT in 73. Holding those out would remove a large,
topically central slice of the corpus and silently change every other
measurement in the project. A variant appearing in exactly one article can
be removed without distorting anything.

**Read this before trusting the `gene` column.** The first version of this
script assigned each variant the first gene symbol appearing anywhere in the
same paragraph. Checking 8 shortlisted candidates against the source text
found 4 were wrong: `c.2502_2503insA` is ATM (not BRCA2, which merely
appeared earlier in the sentence), `c.1919C>A` is PMS2 (not PALB2),
`c.5890A>G` is ATM (not BRCA1), `c.334C>T` is RAD51D/BARD1 (not BRCA1).
Proximity is not attribution. That is the same defect class the phase A1
validation pass found in the hand-built eval cases (docs/DECISION_LOG.md),
reproduced by a fresh tool within the hour, which is decent evidence it is a
property of the task rather than of one careless agent.

The attribution here is now nearest-preceding-symbol within a short window,
which matches how these are actually written ("ATM: c.2502_2503insA",
"BRCA2 c.9275A>G", "PMS2 (c.1919C>A)"), and it reports the distance so a
weak match is visible. **It is still a hint, not a finding.** Confirm every
candidate by reading the source before building a case on it.

Usage (from eval/):
    python mine_rare_variants.py --max-df 1
    python mine_rare_variants.py --max-df 2 --condition "ovarian cancer"
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

from corpus_text import extract_section_text

EVAL_DIR = Path(__file__).parent
XML_DIR = EVAL_DIR.parent / "corpus" / "xml"
MANIFEST = EVAL_DIR.parent / "corpus" / "manifest.csv"

HGVS = re.compile(
    r"\bc\.\d+(?:[+-]\d+)?(?:_\d+(?:[+-]\d+)?)?"
    r"(?:[ACGT]+>[ACGT]+|del[ACGT]*|dup[ACGT]*|ins[ACGT]+|delins[ACGT]+)"
)
GENES = ("BRCA1", "BRCA2", "PALB2", "ATM", "CHEK2", "TP53", "RAD51C", "RAD51D",
         "BRIP1", "BARD1", "PMS2", "MLH1", "MSH2", "MSH6", "MUTYH", "PTEN")
CONDITIONS = ("breast cancer", "ovarian cancer", "pancreatic cancer", "prostate cancer",
              "colorectal cancer", "endometrial cancer")

# How far back to look for the gene symbol a variant belongs to. Wide enough
# for "BRCA2 (NM_000059.4) c.9275A>G", narrow enough that the previous
# sentence's gene does not win.
ATTRIBUTION_WINDOW = 60


def attribute_gene(paragraph: str, match_start: int) -> tuple[str | None, int]:
    """Nearest gene symbol *preceding* the variant within ATTRIBUTION_WINDOW.
    Returns (gene, distance), or (None, -1) when nothing is close enough.

    Preceding rather than nearest-either-side on purpose: the convention in
    this literature is gene-then-variant, and a following symbol is usually
    the next item in a list, which is exactly how the first version of this
    script misattributed 4 of 8 candidates."""
    window_start = max(0, match_start - ATTRIBUTION_WINDOW)
    window = paragraph[window_start:match_start]
    best, best_distance = None, -1
    for gene in GENES:
        for m in re.finditer(rf"\b{gene}\b", window):
            distance = len(window) - m.end()
            if best is None or distance < best_distance:
                best, best_distance = gene, distance
    return best, best_distance


def _scan(pmcid: str) -> tuple[str, list[tuple[str, str | None, int, str]]]:
    path = XML_DIR / f"{pmcid}.xml"
    if not path.exists():
        return pmcid, []
    found = []
    for section in ("abstract", "body"):
        text = extract_section_text(path, section)
        if not text:
            continue
        for para in text.split("\n"):
            lowered = para.lower()
            conditions = [c for c in CONDITIONS if c in lowered]
            if not conditions:
                continue
            for m in HGVS.finditer(para):
                gene, distance = attribute_gene(para, m.start())
                found.append((m.group(0), gene, distance, conditions[0]))
    return pmcid, found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-df", type=int, default=1,
                        help="only report notations appearing in at most this many articles")
    parser.add_argument("--condition", help="restrict to one condition")
    parser.add_argument("--out", help="write candidates as CSV here")
    args = parser.parse_args(argv)

    with MANIFEST.open() as f:
        pmcids = [r["pmcid"] for r in csv.DictReader(f) if r.get("status") == "ok"]

    variant_articles: dict[str, set[str]] = defaultdict(set)
    detail: dict[tuple[str, str], tuple[str | None, int, str]] = {}
    with Pool() as pool:
        for i, (pmcid, found) in enumerate(pool.imap_unordered(_scan, pmcids, chunksize=50), 1):
            if i % 2000 == 0:
                print(f"  {i}/{len(pmcids)}", file=sys.stderr, flush=True)
            for variant, gene, distance, condition in found:
                variant_articles[variant].add(pmcid)
                detail.setdefault((variant, pmcid), (gene, distance, condition))

    rows = []
    for (variant, pmcid), (gene, distance, condition) in sorted(detail.items()):
        df = len(variant_articles[variant])
        if df > args.max_df:
            continue
        if args.condition and condition != args.condition:
            continue
        rows.append({"variant": variant, "gene_hint": gene or "UNKNOWN",
                     "gene_distance_chars": distance, "condition": condition,
                     "df": df, "pmcid": pmcid})

    # Unattributed rows (distance -1) sort LAST, not first: a candidate with
    # no gene symbol near it is the least useful, and a naive ascending sort
    # on distance puts exactly the wrong rows at the top of the screen.
    rows.sort(key=lambda r: (r["df"],
                             r["gene_distance_chars"] if r["gene_distance_chars"] >= 0 else 10**6,
                             r["variant"]))
    print(f"\n{len(rows)} candidate(s) with df <= {args.max_df}\n")
    print(f"{'variant':24} {'gene?':8} {'dist':>4}  {'condition':19} {'df':>3}  pmcid")
    for r in rows:
        print(f"{r['variant']:24} {r['gene_hint']:8} {r['gene_distance_chars']:4d}  "
              f"{r['condition']:19} {r['df']:3d}  {r['pmcid']}")

    if args.out:
        with open(args.out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])) if rows else None
            if writer:
                writer.writeheader()
                writer.writerows(rows)
        print(f"\nWrote {args.out}")

    print("\nThe gene column is a HINT from nearest-preceding-symbol matching, not a finding. "
          "An earlier version of this attribution was wrong for 4 of 8 checked candidates. "
          "Read the source for any candidate before building a case on it, and confirm the "
          "notation's true document frequency with verify_negative_cases.py after holding out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
