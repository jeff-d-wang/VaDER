"""
Dev/held-out split for answer_cases.jsonl. PROJECT_PLAN.md's statistical
rules say to hold out roughly a third of the answer set from day one,
touched at most three times across the whole project, so a 50-80 case set
run repeatedly over months doesn't quietly become a training set the
project is unknowingly overfitting to.

Stratified by case type (disagreement / negative / ordinary evidence) so
the held-out third isn't accidentally all-one-type at n=19; seeded for
reproducibility, same discipline as the corpus's own uniform-random
sampling (see docs/DECISION_LOG.md, "Corpus re-pull").

Two registries, same pattern as hold_out_case.py's held_out_pmcids.csv:
  - dev_held_out_split.csv: which case_id is in which split. Source of
    truth; assign once, don't silently reassign (see assign_split below).
  - held_out_touches.csv: the audit log. Every time the held-out split is
    actually scored or read for evaluation purposes, score.py appends a
    row here automatically. Nothing *enforces* the "at most three times"
    rule, the log exists so a human (or a review of this file) can.
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

SPLIT_PATH = Path(__file__).parent / "dev_held_out_split.csv"
TOUCHES_PATH = Path(__file__).parent / "held_out_touches.csv"
CASES_PATH = Path(__file__).parent / "answer_cases.jsonl"

HELD_OUT_FRACTION = 1 / 3
MAX_RECOMMENDED_TOUCHES = 3


def case_type(case: dict) -> str:
    if case["stratum"] == "methods_extraction":
        return "methods_extraction"
    if case["is_negative_case"]:
        return "negative"
    if case["gold"].get("has_disagreement"):
        return "disagreement"
    return "ordinary"


def load_cases() -> list[dict]:
    import json
    with open(CASES_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_split() -> dict[str, str]:
    """case_id -> "dev" | "held_out". Empty dict if no split has been
    assigned yet (callers should treat that as "everything is dev", not
    as an error, since a set built before this tool existed is fine)."""
    if not SPLIT_PATH.exists():
        return {}
    with open(SPLIT_PATH, newline="") as f:
        return {row["case_id"]: row["split"] for row in csv.DictReader(f)}


def assign_split(seed: int = 0, fraction: float = HELD_OUT_FRACTION) -> dict[str, str]:
    """Stratified-random assignment, one shot: refuses to run if
    dev_held_out_split.csv already exists and covers every current case,
    same "don't silently reassign" discipline as hold_out_case.py. A case
    added later (not yet in the registry) can be assigned without
    disturbing existing assignments, call this again, only new case_ids
    get placed."""
    cases = load_cases()
    existing = load_split()
    by_type: dict[str, list[str]] = {}
    for c in cases:
        by_type.setdefault(case_type(c), []).append(c["case_id"])

    rows = []
    for typ, ids in by_type.items():
        ids = sorted(ids)  # deterministic order before seeding, same as pull_corpus.py's sampling
        new_ids = [i for i in ids if i not in existing]
        if not new_ids:
            continue
        n_held_out = round(len(ids) * fraction) - sum(
            1 for i in ids if existing.get(i) == "held_out"
        )
        n_held_out = max(0, min(n_held_out, len(new_ids)))
        held_out_new = set(random.Random(seed).sample(new_ids, n_held_out))
        for cid in new_ids:
            rows.append((cid, "held_out" if cid in held_out_new else "dev", typ))

    if not rows and existing:
        print("No new cases to assign; dev_held_out_split.csv is already up to date.")
        return existing

    write_header = not SPLIT_PATH.exists()
    with open(SPLIT_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["case_id", "split", "case_type", "assigned_at_utc", "seed"])
        now = datetime.now(timezone.utc).isoformat()
        for cid, split, typ in rows:
            writer.writerow([cid, split, typ, now, seed])

    return load_split()


def record_touch(reason: str, touched_by: str, n_cases: int, notes: str = "") -> int:
    """Appends one row to held_out_touches.csv, returns the new total touch
    count so the caller can warn if it's over MAX_RECOMMENDED_TOUCHES."""
    write_header = not TOUCHES_PATH.exists()
    with open(TOUCHES_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["touched_at_utc", "reason", "touched_by", "n_cases", "notes"])
        writer.writerow([datetime.now(timezone.utc).isoformat(), reason, touched_by, n_cases, notes])
    return count_touches()


def count_touches() -> int:
    if not TOUCHES_PATH.exists():
        return 0
    with open(TOUCHES_PATH, newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_assign = sub.add_parser("assign", help="stratified-random split assignment")
    p_assign.add_argument("--seed", type=int, default=0)
    p_assign.add_argument("--fraction", type=float, default=HELD_OUT_FRACTION)

    sub.add_parser("list", help="show current split assignments and touch count")

    args = parser.parse_args()
    if args.cmd == "assign":
        split = assign_split(seed=args.seed, fraction=args.fraction)
        counts: dict[str, int] = {}
        for v in split.values():
            counts[v] = counts.get(v, 0) + 1
        print(f"Split assigned: {counts}")
    elif args.cmd == "list":
        split = load_split()
        cases = {c["case_id"]: c for c in load_cases()}
        for cid, s in sorted(split.items(), key=lambda kv: (kv[1], kv[0])):
            typ = case_type(cases[cid]) if cid in cases else "?"
            print(f"  {s:10s} {typ:12s} {cid}")
        n_touches = count_touches()
        warn = "  [WARN: exceeds the recommended 3-touch cap]" if n_touches > MAX_RECOMMENDED_TOUCHES else ""
        print(f"\nHeld-out split has been touched {n_touches} time(s).{warn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
