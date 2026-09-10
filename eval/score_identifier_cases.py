"""
Phase D's exit number: BM25 on the exact-identifier failure case.

`data/identifier_cases.jsonl` is a set of PAIRED queries. Each case has a
gold corpus paragraph that names a variant in one notation, and two queries
with the same question stem: `matched` uses the notation the paragraph
contains, `mismatched` uses an equivalent notation the paragraph never uses
(rsID for HGVS, protein-level for cDNA, legacy for current). BM25 is exact
match on tokens, so the prediction is that `matched` recall is near 1.0 and
`mismatched` near 0: `rs80338939` and `c.35delG` are the same variant and
BM25 has no idea.

Same span-overlap scoring as `score_retrieval.py` (a hit is a retrieved
chunk whose source spans overlap the gold span), reused directly.

    python -m eval.score_identifier_cases --index eval/runs/bm25_index.pkl --out eval/runs/identifier_bm25.json
"""
from __future__ import annotations

from eval.datasets import validate_cases

import argparse
import json
import sys
import time
from pathlib import Path

from common.run_meta import file_hash, source_hash, append_run, config_hash, git_sha
from common.stats import wilson_ci
from eval.compare_runs import mcnemar_exact_p
from eval.score_retrieval import check_index_covers_gold, hit_at, rank_of_gold, to_query_result
from retrieval import bm25
from retrieval.bm25 import BM25Index

EVAL_DIR = Path(__file__).parent
DEFAULT_CASES = EVAL_DIR / "data" / "identifier_cases.jsonl"
STYLES = ("matched", "mismatched")


def load_cases(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def arm_recall(cases: list[dict], hits: dict[str, bool], style: str, k: int) -> dict:
    vals = [hits[c["query_id"]] for c in cases if c["style"] == style]
    n, s = len(vals), sum(vals)
    lo, hi = wilson_ci(s, n) if n else (0.0, 0.0)
    return {"value": round(s / n, 4) if n else None, "ci95": [round(lo, 4), round(hi, 4)],
            "n": n, "hits": s}


def paired(cases: list[dict], hits: dict[str, bool], k: int) -> dict:
    by_case: dict[str, dict[str, bool]] = {}
    for c in cases:
        by_case.setdefault(c["case_id"], {})[c["style"]] = hits[c["query_id"]]
    pairs = [v for v in by_case.values() if len(v) == 2]
    b = sum(1 for p in pairs if p["matched"] and not p["mismatched"])
    c_ = sum(1 for p in pairs if p["mismatched"] and not p["matched"])
    return {"n_pairs": len(pairs), "discordant_matched_only": b,
            "discordant_mismatched_only": c_, "mcnemar_p": round(mcnemar_exact_p(b, c_), 4)}


def by_axis(cases: list[dict], hits: dict[str, bool]) -> dict:
    out: dict[str, dict] = {}
    for axis in sorted({c["notation_axis"] for c in cases}):
        sub = [c for c in cases if c["notation_axis"] == axis]
        out[axis] = {s: arm_recall(sub, hits, s, 10) for s in STYLES}
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--index", type=Path, default=EVAL_DIR / "runs" / "bm25_index.pkl")
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--report-k", type=int, default=10)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--exploratory", action="store_true")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    try:
        validate_cases(cases, exploratory=args.exploratory)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{args.cases.name}: {len(cases)} queries over "
          f"{len({c['case_id'] for c in cases})} cases")
    index = BM25Index.load(args.index)
    print(f"{args.index.name}: {index.n_docs} chunks")
    n_missing = check_index_covers_gold(cases, index)
    if n_missing:
        print("Refusing to report: gold spans missing from the index. Rebuild it.", file=sys.stderr)
        return 1

    t0 = time.time()
    hits: dict[str, bool] = {}
    ranks: dict[str, int | None] = {}
    for case in cases:
        found = index.search(case["query"], top_k=args.top_k)
        result = to_query_result(case, [ch for ch, _ in found])
        hits[case["query_id"]] = hit_at(result, args.report_k)
        ranks[case["query_id"]] = rank_of_gold(result)
    search_s = time.time() - t0

    k = args.report_k
    overall = {s: arm_recall(cases, hits, s, k) for s in STYLES}
    pair = paired(cases, hits, k)
    axis = by_axis(cases, hits)

    print(f"\nrecall@{k}  (paired on {pair['n_pairs']} cases)")
    for s in STYLES:
        r = overall[s]
        print(f"  {s:11s} {r['value']:.4f}  [{r['ci95'][0]:.4f}, {r['ci95'][1]:.4f}]  "
              f"n={r['n']}  ({r['hits']}/{r['n']})")
    delta = overall["matched"]["value"] - overall["mismatched"]["value"]
    print(f"  delta       {delta:+.4f}  (discordant matched-only {pair['discordant_matched_only']}, "
          f"mismatched-only {pair['discordant_mismatched_only']}, McNemar exact p={pair['mcnemar_p']:.4f})")

    print(f"\nBy notation axis (recall@{k}):")
    for ax, arms in axis.items():
        print(f"  {ax:16s} matched {arms['matched']['value']}  "
              f"mismatched {arms['mismatched']['value']}  (n={arms['matched']['n']} pairs)")

    config = {"retriever": "bm25", "k1": bm25.K1, "b": bm25.B, "top_k": args.top_k,
              "index": str(args.index), "n_indexed": index.n_docs,
              "cases": str(args.cases), "n_queries": len(cases), "git_sha": git_sha(),
              "cases_sha256": file_hash(args.cases), "index_sha256": file_hash(args.index),
              "source_hash": source_hash(), "report_k": args.report_k, "exploratory": args.exploratory}
    payload = {"config": config, "config_hash": config_hash(config),
               "overall": overall, "paired": pair, "by_axis": axis,
               "per_query": [{"query_id": c["query_id"], "case_id": c["case_id"],
                              "style": c["style"], "notation_axis": c["notation_axis"],
                              "lexical_overlap": c["lexical_overlap"],
                              "hit": hits[c["query_id"]], "rank_of_gold": ranks[c["query_id"]]}
                             for c in cases],
               "meta": {"search_ms_per_query": round(1000 * search_s / max(1, len(cases)), 1)}}
    print(f"\nconfig hash {payload['config_hash']}, git sha {config['git_sha']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2))
        print(f"Wrote {args.out}")
        run_id = append_run(eval_set="identifier", run_config=config, results_path=str(args.out),
                            input_paths={"cases": args.cases, "index": args.index},
                            metrics={f"matched_recall@{k}": overall["matched"]["value"],
                                     f"mismatched_recall@{k}": overall["mismatched"]["value"],
                                     "n_pairs": pair["n_pairs"]})
        print(f"Registered run {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
