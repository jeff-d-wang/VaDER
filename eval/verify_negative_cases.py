"""
Re-check every negative case's central claim: that the corpus contains no
grounding for its variant-condition pair.

Why this exists. Negative cases (property 4, "says not found in this
corpus") used to be built by searching a handful of variant notations,
finding nothing, and declaring the pair absent. The phase A1 validation
pass showed why that fails: `palb2_c1592del4_pancreatic_neg_001` searched
`c.1592del4`, a notation that does not exist in the literature (the real
Finnish founder variant is `c.1592delT`), found nothing, and asserted an
absence that three corpus articles flatly contradict. A search that finds
nothing is suggestive of absence, never proof of it, because notation space
is unbounded and prose descriptions escape any notation list.

The rebuilt cases invert that logic. Each one names a variant that appeared
in exactly ONE corpus article, and that article has been held out
(`hold_out_case.py`). Absence is therefore true by construction. What this
script does is confirm the construction still holds:

  1. the variant notation appears in zero remaining corpus articles, and
  2. the article the case claims to have held out really is held out.

Both are cheap and mechanical, which is the point: the old cases rested on
an agent's report of what it had searched, and these rest on a check anyone
can rerun in ten seconds.

What it still cannot prove: that no article discusses the same variant
under a different name. That residual is unavoidable by any keyword method
and is why hold-out, not search, is what makes the case sound. The check
here is a regression guard on the construction, not an independent proof of
absence.

Usage:
    python verify_negative_cases.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from multiprocessing import Pool
from pathlib import Path

from corpus_text import extract_section_text

EVAL_DIR = Path(__file__).parent
CASES_PATH = EVAL_DIR / "answer_cases.jsonl"
XML_DIR = EVAL_DIR.parent / "corpus" / "xml"
MANIFEST = EVAL_DIR.parent / "corpus" / "manifest.csv"
REGISTRY = EVAL_DIR / "held_out" / "held_out_pmcids.csv"

_PATTERNS: list[tuple[str, re.Pattern]] = []
_XML_DIR = XML_DIR


def _init(patterns, xml_dir):
    global _PATTERNS, _XML_DIR
    _PATTERNS = [(cid, re.compile(re.escape(v), re.I)) for cid, v in patterns]
    _XML_DIR = xml_dir


def _scan(pmcid: str) -> list[tuple[str, str]]:
    path = _XML_DIR / f"{pmcid}.xml"
    if not path.exists():
        return []
    hits = []
    for section in ("abstract", "body"):
        text = extract_section_text(path, section)
        if not text:
            continue
        for case_id, pattern in _PATTERNS:
            if pattern.search(text):
                hits.append((case_id, pmcid))
    return hits


def load_registry() -> set[str]:
    if not REGISTRY.exists():
        return set()
    with REGISTRY.open() as f:
        return {row["pmcid"] for row in csv.DictReader(f)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--xml-dir", default=str(XML_DIR))
    args = parser.parse_args(argv)

    with Path(args.cases).open() as f:
        cases = [json.loads(line) for line in f if line.strip()]
    negatives = [c for c in cases if c["is_negative_case"]]
    if not negatives:
        print("No negative cases in the set.")
        return 0

    patterns = [(c["case_id"], c["variant"]) for c in negatives if c.get("variant")]
    no_variant = [c["case_id"] for c in negatives if not c.get("variant")]

    with MANIFEST.open() as f:
        pmcids = [r["pmcid"] for r in csv.DictReader(f) if r.get("status") == "ok"]
    found: dict[str, list[str]] = {case_id: [] for case_id, _ in patterns}
    xml_dir = Path(args.xml_dir)
    with Pool(initializer=_init, initargs=(patterns, xml_dir)) as pool:
        for hits in pool.imap_unordered(_scan, pmcids, chunksize=50):
            for case_id, pmcid in hits:
                found[case_id].append(pmcid)

    registry = load_registry()
    failures = 0
    for case in negatives:
        case_id = case["case_id"]
        problems = []
        grounding = found.get(case_id, [])
        if grounding:
            problems.append(f"variant {case['variant']} still appears in "
                            f"{len(grounding)} article(s): {', '.join(sorted(grounding)[:5])}")
        for pmcid in case.get("held_out_pmcids", []):
            if pmcid not in registry:
                problems.append(f"claims to hold out {pmcid}, not in held_out registry")
            if (xml_dir / f"{pmcid}.xml").exists():
                problems.append(f"{pmcid} is still present in the corpus")
        if case.get("construction") != "hold_out":
            problems.append("not built by hold-out; absence rests on a failed search, which is "
                            "not proof (see this module's docstring)")
        if problems:
            failures += 1
            print(f"[FAIL] {case_id}")
            for p in problems:
                print(f"    {p}")
        else:
            print(f"[ok]   {case_id}: {case['variant']} absent, {case['held_out_pmcids']} held out")

    if no_variant:
        print(f"\n{len(no_variant)} negative case(s) have no variant to check: "
              f"{', '.join(no_variant)}")

    print(f"\n{len(negatives) - failures}/{len(negatives)} negative cases verified.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
