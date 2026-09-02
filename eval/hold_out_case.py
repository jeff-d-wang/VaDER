"""
Builds a negative case for answer-set property 4 ("says not found in this
corpus"). Physically holds a set of PMCIDs out of corpus/xml/ so nothing in
the corpus grounds that variant-condition pair, without touching
corpus/manifest.csv, the Step 0b pull's immutable reproducibility record.

You are responsible for the judgment call this script does not make:
verifying the PMCID list is COMPLETE, every article in the corpus covering
the pair, before running this. Use find_coverage.py and read the candidates
by hand first (see eval/README.md). This tool does the mechanical part, move
and record, not the verification. Miss an article and the negative case is
silently invalid.

Moves <corpus-dir>/xml/<PMCID>.xml -> <held-out-dir>/xml/<PMCID>.xml and
appends one row per PMCID to <held-out-dir>/held_out_pmcids.csv. Idempotent:
a PMCID already held out under the same pair_id is skipped, not re-recorded.
A PMCID already held out under a DIFFERENT pair_id is refused, one held-out
article should have one owning negative case, not an ambiguous shared one.

Usage:
    python hold_out_case.py --pair-id palb2_pancreatic --gene PALB2 \\
        --condition "pancreatic cancer" --pmcid PMC1234567 --pmcid PMC7654321

    python hold_out_case.py --restore --pair-id palb2_pancreatic

    python hold_out_case.py --list
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

FIELDNAMES = ["pair_id", "pmcid", "gene", "variant", "condition", "held_out_at_utc", "note"]


def _load_registry(registry_path: Path) -> list:
    if not registry_path.exists():
        return []
    with open(registry_path, newline="") as f:
        return list(csv.DictReader(f))


def _write_registry(registry_path: Path, rows: list) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def hold_out(pair_id: str, pmcids: list, gene: str, variant: str, condition: str,
             corpus_dir: Path, held_out_dir: Path, note: str) -> int:
    registry_path = held_out_dir / "held_out_pmcids.csv"
    rows = _load_registry(registry_path)
    by_pmcid = {r["pmcid"]: r for r in rows}
    held_out_xml_dir = held_out_dir / "xml"
    now = datetime.now(timezone.utc).isoformat()

    n_done = 0
    for pmcid in pmcids:
        existing = by_pmcid.get(pmcid)
        if existing is not None:
            if existing["pair_id"] == pair_id:
                print(f"  skip  {pmcid}: already held out under {pair_id}")
            else:
                print(f"  ERROR {pmcid}: already held out under a different pair "
                      f"({existing['pair_id']}), refusing to reassign it to {pair_id}", file=sys.stderr)
            continue

        src = corpus_dir / "xml" / f"{pmcid}.xml"
        if not src.exists():
            print(f"  ERROR {pmcid}: not found at {src}, not held out. Check the pmcid.", file=sys.stderr)
            continue

        held_out_xml_dir.mkdir(parents=True, exist_ok=True)
        dst = held_out_xml_dir / f"{pmcid}.xml"
        src.rename(dst)
        rows.append({"pair_id": pair_id, "pmcid": pmcid, "gene": gene, "variant": variant,
                      "condition": condition, "held_out_at_utc": now, "note": note})
        n_done += 1
        print(f"  held out  {pmcid}  ({gene or ''} {variant or ''} / {condition})".replace("  ", " "))

    _write_registry(registry_path, rows)
    return n_done


def restore(pair_id: str, corpus_dir: Path, held_out_dir: Path) -> int:
    registry_path = held_out_dir / "held_out_pmcids.csv"
    rows = _load_registry(registry_path)
    keep, restored = [], []
    for r in rows:
        if r["pair_id"] != pair_id:
            keep.append(r)
            continue
        src = held_out_dir / "xml" / f"{r['pmcid']}.xml"
        dst = corpus_dir / "xml" / f"{r['pmcid']}.xml"
        if src.exists():
            src.rename(dst)
            print(f"  restored  {r['pmcid']}")
        else:
            print(f"  WARN  {r['pmcid']}: registry says held out but file missing at {src}", file=sys.stderr)
        restored.append(r)
    _write_registry(registry_path, keep)
    return len(restored)


def list_held_out(held_out_dir: Path) -> None:
    rows = _load_registry(held_out_dir / "held_out_pmcids.csv")
    if not rows:
        print("No PMCIDs currently held out.")
        return
    by_pair: dict = {}
    for r in rows:
        by_pair.setdefault(r["pair_id"], []).append(r["pmcid"])
    for pair_id, pmcids in by_pair.items():
        print(f"{pair_id}: {len(pmcids)} pmcid(s): {', '.join(pmcids)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-dir", default=os.environ.get("VADER_CORPUS_DIR", "../corpus"))
    ap.add_argument("--held-out-dir", default="./held_out")
    ap.add_argument("--pair-id", help="an id for this negative case, e.g. palb2_pancreatic")
    ap.add_argument("--pmcid", action="append", default=[], help="repeatable: a PMCID to hold out")
    ap.add_argument("--gene", default="")
    ap.add_argument("--variant", default="")
    ap.add_argument("--condition", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--restore", action="store_true", help="undo: move this pair's PMCIDs back into the corpus")
    ap.add_argument("--list", action="store_true", help="list all currently held-out pairs and exit")
    args = ap.parse_args()

    corpus_dir = Path(args.corpus_dir)
    held_out_dir = Path(args.held_out_dir)

    if args.list:
        list_held_out(held_out_dir)
        return

    if not args.pair_id:
        ap.error("--pair-id is required (unless using --list)")

    if args.restore:
        n = restore(args.pair_id, corpus_dir, held_out_dir)
        print(f"\nRestored {n} pmcid(s) for {args.pair_id}.")
        return

    if not args.pmcid:
        ap.error("need at least one --pmcid to hold out (or use --restore / --list)")
    if not args.condition:
        ap.error("--condition is required, for the registry record")
    if not (args.gene or args.variant):
        ap.error("need --gene or --variant, for the registry record")

    print(f"Holding out {len(args.pmcid)} pmcid(s) for negative case '{args.pair_id}'...")
    n = hold_out(args.pair_id, args.pmcid, args.gene, args.variant, args.condition,
                 corpus_dir, held_out_dir, args.note)
    print(f"\nHeld out {n}/{len(args.pmcid)}. Registry: {held_out_dir / 'held_out_pmcids.csv'}")
    if n < len(args.pmcid):
        print("Some pmcids were skipped or errored, see above. Not all requested holds succeeded.",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
