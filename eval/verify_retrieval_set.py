"""
The standing check on the retrieval set, matching verify_spans.py and
verify_negative_cases.py for the answer set.

The build-time filters in build_retrieval_set.py run once, against the model
output, and then never again. That is not enough on its own. The corpus can
be re-pulled, the tokenizer can change, the offset convention has already
drifted once in this project's history, and the set is grown across several
days in separate runs. Every one of those can leave a row that was valid
when written and is not valid now, and none of them announce themselves.

What each check is for:

  gold spans      Do the offsets still resolve to the same text, checked by
                  content hash? A row whose span no longer resolves is an
                  unanswerable query, and it would score as a retriever
                  failure rather than as the data error it is. The hash and
                  not the length: a span is read by slicing, so it returns
                  the recorded length whenever the section is long enough,
                  and appending a sentence to an article changes the text a
                  row points at without changing its length at all.
  anchors         Still present in the gold paragraph AND in both queries.
                  This is the specificity guarantee the whole set rests on;
                  if it does not hold, the query is not pinned to its
                  paragraph by anything.
  overlap         Does the stored lexical_overlap still recompute to the
                  stored value? It is the number every row's bias caveat is
                  read from, and it depends on the BM25 tokenizer. Change
                  the tokenizer and every stored value silently becomes a
                  claim about code that no longer exists.
  pairing         Exactly two styles per paragraph, no duplicate ids, no two
                  rows with the same query text. The paired style test is
                  only valid on complete pairs.
  held out        No row may cite an article in eval/held_out/. Those files
                  are physically gone from the corpus, so such a query is
                  unanswerable by construction.
  concentration   No article should supply many paragraphs. Queries from one
                  article are correlated, and the per-query bootstrap CI
                  assumes they are not, so concentration silently narrows
                  every interval computed off the set.

Usage:
    python -m eval.verify_retrieval_set
    python -m eval.verify_retrieval_set --cases eval/data/retrieval_cases.jsonl
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

from common.corpus_text import load_span_text
from common.stats import wilson_ci
from eval.build_retrieval_set import (CORPUS_XML, HELD_OUT, STRATA, DEFAULT_OUT,
                                      gold_text_digest, lexical_overlap, normalize)

# More paragraphs than this from one article and its queries are correlated
# enough to matter to the intervals. The builder caps at one paragraph per
# article per stratum, so the ceiling is the number of strata; anything at
# or near that is worth seeing.
MAX_PARAGRAPHS_PER_ARTICLE = 3


def load_rows(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def check(rows: list[dict], xml_dir: Path) -> tuple[list[str], list[str]]:
    """Returns (failures, warnings). A failure means a row is wrong and will
    misreport a number; a warning means the set has a property worth knowing
    before reading one."""
    failures: list[str] = []
    warnings: list[str] = []

    by_paragraph: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    for row in rows:
        by_paragraph[row["paragraph_id"]][row["style"]] = row

    for pid, styles in sorted(by_paragraph.items()):
        if set(styles) != {"lexical", "paraphrased"}:
            failures.append(f"{pid}: styles are {sorted(styles)}, expected both")
            continue
        row = styles["lexical"]
        span = row["gold_span"]
        text, error = load_span_text(xml_dir, span["pmcid"], span["section"],
                                     span["char_start"], span["char_end"])
        if error:
            failures.append(f"{pid}: gold span does not resolve ({error})")
            continue
        stored_digest = row.get("gold_text_sha1")
        if stored_digest is None:
            failures.append(f"{pid}: no gold_text_sha1; this row predates the field and its "
                            f"integrity cannot be checked. Backfill it or rebuild the row")
            continue
        if gold_text_digest(text) != stored_digest:
            failures.append(f"{pid}: gold text hashes to {gold_text_digest(text)}, row records "
                            f"{stored_digest}; the corpus changed under this row")
            continue

        norm_text = normalize(text)
        for anchor in row["anchors"]:
            if normalize(anchor) not in norm_text:
                failures.append(f"{pid}: anchor {anchor!r} is no longer in the gold paragraph")
            for style, r in styles.items():
                if normalize(anchor) not in normalize(r["query"]):
                    failures.append(f"{pid}: {style} query has lost anchor {anchor!r}")

        for style, r in styles.items():
            recomputed = round(lexical_overlap(r["query"], text), 4)
            if abs(recomputed - r["lexical_overlap"]) > 1e-9:
                failures.append(f"{pid}: {style} lexical_overlap is stored as "
                                f"{r['lexical_overlap']} but recomputes to {recomputed}; "
                                f"the stored bias number no longer describes this row")

    ids = [r["query_id"] for r in rows]
    if len(ids) != len(set(ids)):
        failures.append(f"{len(ids) - len(set(ids))} duplicate query_id(s)")
    texts = [normalize(r["query"]) for r in rows]
    if len(texts) != len(set(texts)):
        failures.append(f"{len(texts) - len(set(texts))} duplicate query text(s)")

    if HELD_OUT.exists():
        with open(HELD_OUT) as f:
            held_out = {r["pmcid"] for r in csv.DictReader(f)}
        leaked = sorted({r["gold_span"]["pmcid"] for r in rows
                         if r["gold_span"]["pmcid"] in held_out})
        if leaked:
            failures.append(f"rows cite held-out article(s), which are not in the corpus: "
                            f"{', '.join(leaked)}")

    per_article = collections.Counter(v["lexical"]["gold_span"]["pmcid"]
                                      for v in by_paragraph.values()
                                      if "lexical" in v)
    heavy = [(a, c) for a, c in per_article.items() if c > MAX_PARAGRAPHS_PER_ARTICLE]
    if heavy:
        warnings.append(f"{len(heavy)} article(s) supply more than "
                        f"{MAX_PARAGRAPHS_PER_ARTICLE} paragraphs "
                        f"(most: {max(heavy, key=lambda p: p[1])}); their queries are "
                        f"correlated and the bootstrap CI assumes they are not")
    return failures, warnings


def report(rows: list[dict], xml_dir: Path) -> int:
    by_paragraph = {r["paragraph_id"] for r in rows}
    print(f"{len(rows)} queries over {len(by_paragraph)} paragraphs")

    counts = collections.Counter(r["stratum"] for r in rows
                                 if r["style"] == "lexical")
    print("  paragraphs per stratum: "
          + ", ".join(f"{s}={counts.get(s, 0)}" for s in STRATA))
    empty = [s for s in STRATA if not counts.get(s)]
    if empty:
        print(f"  [note] {len(empty)} stratum/strata not yet generated: {', '.join(empty)}. "
              f"The set is incomplete; per-stratum rows off it are a partial table.")

    years = [r["pub_year"] for r in rows if r["style"] == "lexical"]
    post = sum(1 for y in years if y and y >= 2025)
    print(f"  post-2024 paragraphs: {post} of {len(years)}")

    # Reviewed paragraphs, not rows: a person judges a paragraph and both its
    # queries together, so counting rows would double every verdict.
    seen: dict[str, str | None] = {}
    for r in rows:
        if r["paragraph_id"] not in seen:
            seen[r["paragraph_id"]] = r.get("validation_verdict") if r.get("validated_by") else None
    judged = {p: v for p, v in seen.items() if v}
    wrong = sum(1 for v in judged.values() if v == "wrong")
    print(f"  paragraphs reviewed by a person: {len(judged)} of {len(seen)}")
    if not judged:
        print("  [note] no label here has been read by a person. On this project's measured "
              "base rate, unreviewed agent-written labels run about 50% defective; "
              "run `python -m eval.build_retrieval_set --worksheet 20`.")
    else:
        lo, hi = wilson_ci(wrong, len(judged))
        print(f"  [note] of those reviewed, {wrong} were marked WRONG: {wrong/len(judged):.0%}, "
              f"95% CI [{lo:.0%}, {hi:.0%}]. The unreviewed remainder should be assumed to carry "
              f"the same rate until it is checked.")

    failures, warnings = check(rows, xml_dir)
    for w in warnings:
        print(f"\n  [warn] {w}")
    if failures:
        print(f"\n  {len(failures)} FAILURE(S):")
        for f in failures[:40]:
            print(f"    {f}")
        if len(failures) > 40:
            print(f"    ... and {len(failures) - 40} more")
        return 1
    print("\n  All mechanical checks pass.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--xml-dir", type=Path, default=CORPUS_XML)
    args = parser.parse_args(argv)
    return report(load_rows(args.cases), args.xml_dir)


if __name__ == "__main__":
    sys.exit(main())
