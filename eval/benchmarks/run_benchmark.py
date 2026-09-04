"""
Phase A2: run this project's own BM25 over a BEIR benchmark and score it
with this project's own IR metrics, against published reference numbers.

The point is not to compete on a leaderboard. It is the check
PROJECT_PLAN.md M1 asks for first and this project skipped: "running your
harness against them tells you whether the harness is broken before you
trust it on your own data." Everything here is the same code the domain
numbers in docs/RESULTS.md came from, pointed at labeled data with a known
answer. If nDCG@10 lands near the published figure, the metric definitions,
the tokenizer, the scoring loop and the qrel join are all approximately
right. If it lands far below, something in that chain is broken and the
domain numbers inherit the problem.

Published reference (Kamalloo et al., "Resources for Brewing BEIR",
arXiv 2306.07471, Table 2; Pyserini multi-field BM25 on the BEIR test
splits). Ours is expected to come in below these, for reasons written down
in docs/DECISION_LOG.md before this was ever run: different k1/b, no
stemming, no stopword removal, single concatenated field.

Usage:
    python run_benchmark.py --dataset scifact
    python run_benchmark.py --dataset nfcorpus --out ../runs/nfcorpus_bm25.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import ir_metrics  # noqa: E402
from bm25 import build_index_from_texts  # noqa: E402
from ir_metrics import QueryResult  # noqa: E402
from loader import load_benchmark  # noqa: E402

# nDCG@10 and Recall@100, from the reference above. Kept here so a run
# prints the comparison instead of leaving it to be looked up later.
REFERENCE = {
    "scifact": {"ndcg@10": 0.665, "recall@100": 0.908},
    "nfcorpus": {"ndcg@10": 0.325, "recall@100": 0.250},
}

# Below this fraction of the reference, the result is a bug signal rather
# than a parameter difference. Committed in the DECISION_LOG entry before
# the first run, so it cannot be moved afterwards to fit the number.
BUG_THRESHOLD_FRACTION = 0.60


def doc_text(doc) -> str:
    """Title and body concatenated into one field. The reference indexes
    them as two equally-weighted fields; this is the simpler thing and the
    difference is accounted for in the prediction."""
    return f"{doc.title} {doc.text}" if doc.title else doc.text


def run(dataset_name: str, top_k: int, limit_queries: int | None) -> tuple[list[QueryResult], dict]:
    data = load_benchmark(dataset_name)
    print(f"{dataset_name}: {data.doc_count} docs, {data.query_count} queries, "
          f"{data.judgment_count} judgments")

    qrels: dict[str, dict[str, int]] = {}
    for j in data.judgments:
        qrels.setdefault(j.query_id, {})[j.doc_id] = j.relevance

    t0 = time.time()
    index = build_index_from_texts([(d.id, doc_text(d)) for d in data.documents.values()])
    build_s = time.time() - t0
    print(f"  indexed in {build_s:.1f}s")

    query_ids = sorted(data.queries)
    if limit_queries:
        query_ids = query_ids[:limit_queries]

    t0 = time.time()
    results = []
    for i, qid in enumerate(query_ids, start=1):
        hits = index.search(data.queries[qid].text, top_k=top_k)
        results.append(QueryResult(
            query_id=qid,
            retrieved=[para.pmcid for para, _score in hits],
            judgments=qrels.get(qid, {}),
        ))
        if i % 50 == 0:
            rate = i / (time.time() - t0)
            print(f"  {i}/{len(query_ids)} queries ({rate:.1f}/s)", flush=True)
    search_s = time.time() - t0

    meta = {
        "dataset": dataset_name, "n_docs": data.doc_count, "n_queries": len(results),
        "top_k": top_k, "index_build_s": round(build_s, 1),
        "search_s": round(search_s, 1), "search_ms_per_query": round(1000 * search_s / len(results), 1),
    }
    return results, meta


def report(dataset_name: str, results: list[QueryResult], meta: dict) -> dict:
    summaries = ir_metrics.evaluate(results, ks=(5, 10, 100), ndcg_k=10)
    print(f"\n  {'metric':14s} {'value':>7s}  {'95% CI':>18s}  {'n':>4s}   reference")
    payload = {"meta": meta, "metrics": {}}
    verdicts = []
    for s in summaries:
        ref = REFERENCE.get(dataset_name, {}).get(s.name)
        ref_str = ""
        if ref is not None:
            delta = s.value - ref
            ref_str = f"   {ref:.3f} (delta {delta:+.3f})"
            verdicts.append((s.name, s.value, ref))
        print(f"  {s.name:14s} {s.value:7.4f}  [{s.ci_low:.4f}, {s.ci_high:.4f}]  "
              f"{s.n:4d}{ref_str}")
        payload["metrics"][s.name] = {
            "value": round(s.value, 4), "ci95": [round(s.ci_low, 4), round(s.ci_high, 4)],
            "n": s.n, "reference": ref,
        }

    print()
    for name, value, ref in verdicts:
        floor = ref * BUG_THRESHOLD_FRACTION
        if value < floor:
            print(f"  *** {name} = {value:.4f} is below {BUG_THRESHOLD_FRACTION:.0%} of the "
                  f"reference ({floor:.4f}). Per the pre-registered threshold this is a bug "
                  f"signal, not a parameter difference. ***")
        else:
            print(f"  {name}: {value / ref:.0%} of reference, above the {BUG_THRESHOLD_FRACTION:.0%} "
                  f"bug threshold.")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="scifact", choices=sorted(REFERENCE))
    parser.add_argument("--top-k", type=int, default=100, help="retrieval depth (recall@100 needs 100)")
    parser.add_argument("--limit-queries", type=int, help="smoke-test mode: only the first N queries")
    parser.add_argument("--out", help="write metrics JSON here")
    args = parser.parse_args(argv)

    results, meta = run(args.dataset, args.top_k, args.limit_queries)
    payload = report(args.dataset, results, meta)

    if args.limit_queries:
        print("\n  (--limit-queries was set: this is a smoke test, not a result to report)")
    elif args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(payload, indent=2))
        print(f"\nWrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
