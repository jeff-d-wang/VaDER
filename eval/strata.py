"""
Date stratification for the answer set (phase A4).

`docs/RESULTS.md` carries a standing rule: `baseline/no_retrieval` must
**always** be reported per date-stratum (`_pre_cutoff` / `_post_cutoff`),
because "the pooled number conflates retrieval lift with memorization."
PMC full text is in every model's pretraining, so a no-retrieval baseline
scoring well may only mean the model read the paper during training. The
fix `PROJECT_PLAN.md` prescribes is to carve out a post-cutoff slice and
report each stratum separately: "+8 points overall, +31 on post-cutoff
papers" is a far more precise claim than either number alone.

No row in RESULTS.md has ever obeyed that rule. This module is what makes
obeying it possible, and what says out loud when it is not.

A case's year is the EARLIEST publication year among the articles its
answer rests on (its gold spans, or for a negative case the article held
out to make it negative). Earliest, not latest, because the question is
whether the model could have memorized the answer: if any supporting
article predates the cutoff, memorization is on the table, so a case counts
as post-cutoff only when everything it rests on is.

**The cutoff is an assumption, not a fact.** The training cutoff of
`openai/gpt-oss-120b` is not published anywhere this project can cite, so
nothing here hardcodes a claim about it. `--cutoff` defaults to 2024
(post-cutoff means 2025 or later), and the report prints the full year
distribution so any other cutoff can be applied by eye.

Usage:
    python -m eval.strata                     # report the distribution
    python -m eval.strata --cutoff 2023
    python -m eval.strata --annotate          # write earliest_evidence_year into the cases
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).parent
CASES_PATH = EVAL_DIR / "data" / "answer_cases.jsonl"
MANIFEST = EVAL_DIR.parent / "corpus" / "manifest.csv"
SPLIT_PATH = EVAL_DIR / "data" / "dev_held_out_split.csv"

DEFAULT_CUTOFF = 2024

# Below this, a per-stratum pass rate is not a number worth printing: the
# Wilson interval at n<5 spans more than half of [0,1], so the "rate" is
# compatible with almost any truth. Reporting one anyway is how a project
# talks itself into a finding it does not have.
MIN_STRATUM_N = 5

_YEAR = re.compile(r"(19|20)\d{2}")


def load_manifest_years(manifest_path: Path = MANIFEST) -> dict[str, int]:
    years = {}
    with manifest_path.open() as f:
        for row in csv.DictReader(f):
            m = _YEAR.search(row.get("pubdate") or "")
            if m:
                years[row["pmcid"]] = int(m.group(0))
    return years


def case_pmcids(case: dict) -> list[str]:
    """The articles this case's answer rests on. For a negative case that is
    the held-out article: it is the thing whose absence the case asserts,
    and its date is what says whether the model might know it anyway."""
    pmcids = sorted({s["pmcid"] for s in case.get("gold_spans", [])})
    return pmcids or list(case.get("held_out_pmcids", []))


def case_year(case: dict, years: dict[str, int]) -> int | None:
    found = [years[p] for p in case_pmcids(case) if p in years]
    return min(found) if found else None


def stratum(year: int | None, cutoff: int) -> str:
    if year is None:
        return "unknown"
    return "post_cutoff" if year > cutoff else "pre_cutoff"


def load_split(path: Path = SPLIT_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open() as f:
        return {r["case_id"]: r["split"] for r in csv.DictReader(f)}


def load_cases(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--cutoff", type=int, default=DEFAULT_CUTOFF,
                        help=f"post-cutoff means year > this (default {DEFAULT_CUTOFF})")
    parser.add_argument("--annotate", action="store_true",
                        help="write earliest_evidence_year into answer_cases.jsonl")
    args = parser.parse_args(argv)

    cases = load_cases(Path(args.cases))
    years = load_manifest_years()
    split = load_split()

    print(f"{'case':46s} {'split':9s} {'year':>5s}  stratum")
    for case in sorted(cases, key=lambda c: c["case_id"]):
        y = case_year(case, years)
        print(f"{case['case_id']:46s} {split.get(case['case_id'], '?'):9s} "
              f"{y if y else '-':>5}  {stratum(y, args.cutoff)}")

    # The number that decides whether the standing rule is computable at all:
    # non-negative dev cases are what direction/groundedness are scored on.
    scored = [c for c in cases
              if split.get(c["case_id"]) == "dev" and not c["is_negative_case"]]
    counts: dict[str, int] = {}
    for c in scored:
        counts[stratum(case_year(c, years), args.cutoff)] = \
            counts.get(stratum(case_year(c, years), args.cutoff), 0) + 1

    print(f"\nScored stratum sizes (dev, non-negative, n={len(scored)}), cutoff {args.cutoff}:")
    for name in ("pre_cutoff", "post_cutoff", "unknown"):
        n = counts.get(name, 0)
        flag = "" if n >= MIN_STRATUM_N else f"   <- below MIN_STRATUM_N={MIN_STRATUM_N}"
        print(f"  {name:12s} {n:3d}{flag}")

    if counts.get("post_cutoff", 0) < MIN_STRATUM_N:
        print(f"\nRESULTS.md's per-stratum rule is NOT COMPUTABLE on this set. The post-cutoff\n"
              f"stratum holds {counts.get('post_cutoff', 0)} case(s); a pass rate over that is an\n"
              f"anecdote, not a measurement. This is a statement about the eval set, not about\n"
              f"the corpus: {sum(1 for y in years.values() if y > args.cutoff):,} corpus articles\n"
              f"are post-{args.cutoff}, so the material exists and the gap is labeling effort.\n"
              f"Fix by building post-cutoff cases deliberately, not by relaxing the rule.")

    if args.annotate:
        for case in cases:
            case["earliest_evidence_year"] = case_year(case, years)
        with open(args.cases, "w") as f:
            for case in cases:
                f.write(json.dumps(case) + "\n")
        print(f"\nAnnotated {len(cases)} cases with earliest_evidence_year in {args.cases}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
