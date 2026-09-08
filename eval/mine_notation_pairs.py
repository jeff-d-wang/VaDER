"""
Mine the corpus for pairs of variant notations that name the same variant,
so phase D's exact-identifier failure case can be built from real
equivalences rather than a hand-curated notation table (which would need
dbSNP or similar).

The literature writes these out constantly: `c.68_69delAG (rs80357906)`,
`p.K3326X (rs11571833)`, `5382insC (c.5266dupC)`. A parenthetical like that
is a same-variant equivalence stated by the paper itself. This tool harvests
them, then finds, for each equivalence, corpus paragraphs that mention
exactly ONE of the two forms: those are the gold paragraphs for a paired
retrieval case where the query's identifier either matches the paragraph's
notation or is the equivalent form the paragraph never uses.

Two outputs, one corpus scan each:
  --pairs        : the equivalences, `notation_pairs.csv`
  --candidates <notation_pairs.csv>
                 : gold-paragraph candidates, `notation_case_candidates.csv`

Neither output is an eval case. A human picks rows from the candidates CSV,
writes a question stem, and confirms the paragraph actually answers it
before it goes in `data/identifier_cases.jsonl` (this project's base rate
for unreviewed agent labels is about 50% wrong).

Usage (from repo root):
    python -m eval.mine_notation_pairs --pairs
    python -m eval.mine_notation_pairs --candidates eval/runs/notation_pairs.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from functools import partial
from multiprocessing import Pool
from pathlib import Path

from common.corpus_text import iter_paragraphs
from retrieval.bm25 import tokenize

EVAL_DIR = Path(__file__).parent
XML_DIR = EVAL_DIR.parent / "corpus" / "xml"
MANIFEST = EVAL_DIR.parent / "corpus" / "manifest.csv"
HELD_OUT = EVAL_DIR / "held_out" / "held_out_pmcids.csv"

# One "notation-shaped" token: an rsID, an HGVS c./p./g./m. string, or a
# legacy insertion/deletion name (5382insC, 185delAG).
_TOKEN = r"(?:rs\d{3,}|[cgmp]\.[A-Za-z0-9_>*+\-]{2,30}|\d{2,5}(?:ins|del|dup)[A-Za-z]{0,10})"
PAIR_RE = re.compile(rf"({_TOKEN})\s*\(\s*({_TOKEN})\s*\)")
MIN_GOLD_TOKENS, MAX_GOLD_TOKENS = 25, 400
MAX_PRESENT_DF = 6  # the present form must be rare, or top-10 cannot single out one paragraph


def _kind(form: str) -> str:
    if form.startswith("rs"):
        return "rsid"
    if form[:2] in ("c.", "g.", "m."):
        return "cdna"
    if form.startswith("p."):
        return "protein"
    return "legacy"


def _is_equivalence(a: str, b: str) -> bool:
    """Reject `rs1 (rs2)` and `c.1A>G (c.1A>G)`: an equivalence needs two
    different forms, and two rsIDs are two variants, not two names."""
    if a.lower() == b.lower():
        return False
    return not (a.startswith("rs") and b.startswith("rs"))


def _read_pmcids() -> list[str]:
    with MANIFEST.open() as f:
        return [r["pmcid"] for r in csv.DictReader(f) if r.get("status") == "ok"]


def _held_out() -> set[str]:
    if not HELD_OUT.exists():
        return set()
    with HELD_OUT.open() as f:
        return {r["pmcid"] for r in csv.DictReader(f)}


# ---- pass 1: harvest equivalences -------------------------------------------

def _scan_pairs(pmcid: str) -> list[tuple[str, str, str, str]]:
    out = []
    for section, text, _start, _end in iter_paragraphs(XML_DIR / f"{pmcid}.xml"):
        for m in PAIR_RE.finditer(text):
            a, b = m.group(1), m.group(2)
            if _is_equivalence(a, b):
                out.append((a, b, section, text[max(0, m.start() - 60):m.end() + 60]))
    return [(pmcid, *row) for row in out]


def mine_pairs(out_path: Path) -> None:
    pmcids = _read_pmcids()
    equiv: dict[tuple[str, str], dict] = {}
    with Pool() as pool:
        for i, rows in enumerate(pool.imap_unordered(_scan_pairs, pmcids, chunksize=50), 1):
            if i % 2000 == 0:
                print(f"  {i}/{len(pmcids)}", file=sys.stderr, flush=True)
            for pmcid, a, b, _section, snippet in rows:
                # canonical order: cdna/protein/legacy form first, rsID second
                key = (a, b) if _kind(b) == "rsid" else (b, a)
                rec = equiv.setdefault(key, {"articles": set(), "n": 0, "snippet": snippet})
                rec["articles"].add(pmcid)
                rec["n"] += 1

    rows = [{"pair_id": f"{a}__{b}", "form_a": a, "form_b": b,
             "kind_a": _kind(a), "kind_b": _kind(b),
             "n_mentions": r["n"], "n_articles": len(r["articles"]),
             "example": " ".join(r["snippet"].split())[:200]}
            for (a, b), r in equiv.items()]
    rows.sort(key=lambda r: (-r["n_articles"], -r["n_mentions"], r["pair_id"]))
    _write(out_path, rows)
    print(f"\n{len(rows)} equivalences. Wrote {out_path}")


# ---- pass 2: gold-paragraph candidates -------------------------------------
#
# One combined alternation over every distinct notation form, so a paragraph
# is scanned once, not once per pair. `findall` returns the forms present;
# each pair is then a set membership check. 1,511 pairs x 700k paragraphs is
# a billion regex calls the naive way; this is 700k.

MAX_PAIR_ARTICLES = 12  # skip an equivalence whose forms are too common to single out one paragraph


def _scan_candidates(pmcid: str, big_re: "re.Pattern",
                     pairs: list[tuple[str, str, str]]) -> list[dict]:
    out = []
    for section, text, start, end in iter_paragraphs(XML_DIR / f"{pmcid}.xml"):
        if not (MIN_GOLD_TOKENS <= len(tokenize(text)) <= MAX_GOLD_TOKENS):
            continue
        present_forms = set(big_re.findall(text))
        if not present_forms:
            continue
        for pair_id, form_a, form_b in pairs:
            has_a, has_b = form_a in present_forms, form_b in present_forms
            if has_a == has_b:  # need exactly one form present
                continue
            present, absent = (form_a, form_b) if has_a else (form_b, form_a)
            out.append({"pair_id": pair_id, "form_present": present, "form_absent": absent,
                        "pmcid": pmcid, "section": section,
                        "char_start": start, "char_end": end,
                        "snippet": " ".join(text.split())[:240]})
    return out


def mine_candidates(pairs_csv: Path, out_path: Path) -> None:
    with pairs_csv.open() as f:
        pairs = [(p["pair_id"], p["form_a"], p["form_b"]) for p in csv.DictReader(f)
                 if int(p["n_articles"]) <= MAX_PAIR_ARTICLES]
    forms = sorted({f for _, a, b in pairs for f in (a, b)}, key=len, reverse=True)
    big_re = re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(f) for f in forms)
                        + r")(?![A-Za-z0-9])")
    pmcids = [p for p in _read_pmcids() if p not in _held_out()]
    hits: list[dict] = []
    with Pool() as pool:
        for i, rows in enumerate(
                pool.imap_unordered(partial(_scan_candidates, big_re=big_re, pairs=pairs),
                                    pmcids, chunksize=50), 1):
            if i % 2000 == 0:
                print(f"  {i}/{len(pmcids)}", file=sys.stderr, flush=True)
            hits.extend(rows)

    # df of each present form, across the candidate paragraphs we found
    present_df: dict[str, int] = defaultdict(int)
    for h in hits:
        present_df[h["form_present"]] += 1
    rows = [dict(h, present_df_paragraphs=present_df[h["form_present"]])
            for h in hits if present_df[h["form_present"]] <= MAX_PRESENT_DF]
    rows.sort(key=lambda r: (r["present_df_paragraphs"], r["pair_id"], r["pmcid"]))
    _write(out_path, rows)
    print(f"\n{len(rows)} gold-paragraph candidates (present form in <= {MAX_PRESENT_DF} "
          f"paragraphs). Wrote {out_path}")
    print("Pick rows by hand, write a question stem, confirm the paragraph answers it.")


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print("no rows", file=sys.stderr)
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", action="store_true", help="harvest equivalences")
    parser.add_argument("--candidates", type=Path, metavar="PAIRS_CSV",
                        help="find gold-paragraph candidates for the equivalences in this CSV")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    if args.pairs:
        mine_pairs(args.out or EVAL_DIR / "runs" / "notation_pairs.csv")
    elif args.candidates:
        mine_candidates(args.candidates,
                        args.out or EVAL_DIR / "runs" / "notation_case_candidates.csv")
    else:
        parser.error("pass --pairs or --candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
