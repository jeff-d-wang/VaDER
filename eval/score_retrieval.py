"""
Phase C's exit number: run a retriever over the n>=300 retrieval set and
report recall@k, MRR and nDCG@10 with intervals.

Three things here are not just plumbing.

**A hit is a span overlap, not an id match.** Gold is a source span, per
standing rule 5, so "did retrieval find it" means "does a returned span
cover any of the same source text". That is what lets phase D re-chunk the
corpus and score against this same set without relabelling anything: chunk
ids change, source offsets do not.

**The lexical-bias contrast is paired.** Every paragraph produced two
queries, one reusing its wording and one paraphrased, so the two styles run
on identical gold. The gap between them, tested with McNemar on the same
items, is the measured size of the bias that would otherwise be a caveat on
every row.

**The single-gold hole rate is measured, not assumed.** Another paragraph
may answer a query as well as the gold one and scores as a miss.
`--measure-holes` puts an LLM on the top non-gold hits of a sample and
reports how often that happens, with a CI. Recall off this set is a lower
bound by exactly that much.

Usage:
    python -m eval.score_retrieval --index runs/bm25_index.pkl --out runs/retrieval_bm25.json
    python -m eval.score_retrieval --index runs/bm25_index.pkl --measure-holes 40
"""
from __future__ import annotations

from eval.datasets import validate_cases

import argparse
import json
import random
import sys
import time
from pathlib import Path

from common.corpus_text import Chunk, chunk_hits_span
from common.run_meta import file_hash, source_hash, append_run, config_hash, git_sha
from common.stats import wilson_ci
from eval.compare_runs import mcnemar_exact_p
from common.llm_client import DEFAULT_MODEL, groq_chat_json
from retrieval import bm25, ir_metrics
from retrieval.bm25 import BM25Index
from retrieval.ir_metrics import QueryResult

EVAL_DIR = Path(__file__).parent
DEFAULT_CASES = EVAL_DIR / "data" / "retrieval_cases.jsonl"

GOLD_ID = "GOLD"  # the one judged doc id; see to_query_result

MIN_STRATUM_N = 5  # same floor eval/strata.py uses: below this, report nothing

HOLE_PROMPT = """You are auditing a retrieval evaluation set.

The set assumes exactly ONE paragraph in the corpus answers each query. This checks whether that
assumption holds: if some OTHER paragraph answers the query just as well, the set is scoring a
correct retrieval as a miss.

Query:
{query}

The paragraph the set treats as the only correct answer:
\"\"\"{gold}\"\"\"

A different paragraph the retriever returned:
\"\"\"{candidate}\"\"\"

Does the different paragraph answer the query on its own, well enough that a user would be
satisfied with it? Being on the same topic is not enough; it must answer this specific question.

Respond with strict JSON:
{{"answers_the_query": true or false, "why": "one short sentence"}}"""


def load_cases(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def span_key(span: dict) -> str:
    """Identity of a span, as a string, for exact lookups.

    Both offsets, not just the start. Keying on the start alone looks
    equivalent and is not: a paragraph's FIRST fragment shares its start, so
    a start-only key reports an index of sentence fragments as covering
    every gold span it shreds. That is precisely the index this project was
    scoring against until 2026-09-05, so the weaker key would have hidden
    the thing the check exists to find. (Caught by
    test_a_fragment_of_the_gold_paragraph_does_not_count_as_covering_it,
    which failed against the first version of this.)"""
    return "{pmcid}:{section}:{char_start}-{char_end}".format(**span)


def check_index_covers_gold(cases: list[dict], index: BM25Index) -> int:
    """Every gold paragraph must actually be in the index, or the query is
    unanswerable and its miss says nothing about the retriever.

    This exists because it already happened. The index is a pickle, a cached
    artifact rather than code, so the 2026-09-05 audit that unified this
    project's paragraph convention fixed every producer and consumer and left
    the cache alone. The stale pickle held 436,834 records built by an
    extractor that split paragraphs on newlines: 2,273 sentence fragments for
    one article the current convention reads as 186 paragraphs. Scored against
    it, this set still produced entirely plausible numbers, because a fragment
    inside the gold paragraph does overlap it. Plausible numbers off the wrong
    index are the failure mode worth an explicit check.

    The key match is against each chunk's individual `source_spans` entries,
    not the merged chunk span. The phase D chunker keeps every merged
    paragraph as its own span entry and never splits a paragraph, so a
    whole-paragraph gold span still matches one entry exactly, and the exact
    match (not overlap) is what keeps the fragment-index detection working."""
    keys = {span_key({"pmcid": chunk.pmcid, **s})
            for chunk in index.chunks for s in chunk.source_spans}
    missing = [c for c in cases if span_key(c["gold_span"]) not in keys]
    if missing:
        examples = ", ".join(sorted({m["gold_span"]["pmcid"] for m in missing})[:5])
        print(f"\n*** {len(missing)} of {len(cases)} gold spans are NOT in this index "
              f"({examples}). Those queries cannot be answered and their misses are "
              f"meaningless. The index is stale: rebuild it (see eval/README.md, "
              f"'The retrieval set'). ***", file=sys.stderr)
    return len(missing)


def to_query_result(case: dict, hits: list[Chunk]) -> QueryResult:
    """One query's ranking, in the shape ir_metrics scores.

    The trick worth understanding: every retrieved chunk that overlaps gold
    (any of its source spans) is relabelled to the single id GOLD, and
    judgments is {GOLD: 1}. That makes the total relevant count 1, which is
    what recall's denominator has to be when the set has exactly one gold
    span. Judging retrieved ids directly instead would make the denominator
    "however many relevant things we happened to return", and recall would
    come out 1.0 for everyone.

    Only the FIRST overlapping hit keeps the id; later ones are dropped from
    the ranking. Two chunks can both overlap gold (a merge that split a
    neighbourhood two ways), and leaving both in would let a query score
    recall@k = 2.0 against a denominator of 1. A non-gold chunk keeps its own
    `chunk_id`."""
    retrieved: list[str] = []
    gold_seen = False
    for chunk in hits:
        if chunk_hits_span(chunk, case["gold_span"]):
            if gold_seen:
                continue
            gold_seen = True
            retrieved.append(GOLD_ID)
        else:
            retrieved.append(chunk.chunk_id)
    return QueryResult(query_id=case["query_id"], retrieved=retrieved, judgments={GOLD_ID: 1})


def hit_at(result: QueryResult, k: int) -> bool:
    return GOLD_ID in result.retrieved[:k]


def rank_of_gold(result: QueryResult) -> int | None:
    """1-indexed rank of the gold span, or None if it was never retrieved.

    Persisted per query in the run output because every hit@k, the paired
    style test and any later slice are all derivable from it, and retrieval
    over 436k paragraphs costs about nine minutes per pass. Re-running the
    retriever to ask a different question of the same ranking is the kind of
    waste that quietly discourages asking."""
    return result.retrieved.index(GOLD_ID) + 1 if GOLD_ID in result.retrieved else None


def summarize(label: str, results: list[QueryResult], ndcg_k: int) -> dict:
    summaries = ir_metrics.evaluate(results, ks=(1, 5, 10, 100), ndcg_k=ndcg_k)
    print(f"\n{label}  (n={len(results)})")
    print(f"  {'metric':14s} {'value':>7s}  {'95% CI':>18s}  {'n':>4s}")
    metrics = {}
    for s in summaries:
        print(f"  {s.name:14s} {s.value:7.4f}  [{s.ci_low:.4f}, {s.ci_high:.4f}]  {s.n:4d}")
        metrics[s.name] = {"value": round(s.value, 4),
                           "ci95": [round(s.ci_low, 4), round(s.ci_high, 4)], "n": s.n}
    return metrics


def paired_style_test(cases: list[dict], results: dict[str, QueryResult], k: int) -> dict | None:
    """McNemar on recall@k between the two query styles, over paragraphs that
    produced both. Binary hit/miss on identical gold, so the exact test
    applies directly and no bootstrap is needed."""
    by_paragraph: dict[str, dict[str, bool]] = {}
    for case in cases:
        result = results.get(case["query_id"])
        if result is not None:
            by_paragraph.setdefault(case["paragraph_id"], {})[case["style"]] = hit_at(result, k)
    pairs = [v for v in by_paragraph.values() if len(v) == 2]
    if not pairs:
        return None
    # b: lexical hit where paraphrased missed. c: the reverse.
    b = sum(1 for p in pairs if p["lexical"] and not p["paraphrased"])
    c = sum(1 for p in pairs if p["paraphrased"] and not p["lexical"])
    lex = sum(1 for p in pairs if p["lexical"]) / len(pairs)
    para = sum(1 for p in pairs if p["paraphrased"]) / len(pairs)
    p_value = mcnemar_exact_p(b, c)
    print(f"\nLexical bias, paired on {len(pairs)} paragraphs (recall@{k}):")
    print(f"  lexical      {lex:.4f}")
    print(f"  paraphrased  {para:.4f}")
    print(f"  delta        {lex - para:+.4f}  (discordant {b}/{c}, McNemar exact p={p_value:.3f})")
    return {"n_pairs": len(pairs), "k": k, "lexical": round(lex, 4),
            "paraphrased": round(para, 4), "delta": round(lex - para, 4),
            "discordant_b": b, "discordant_c": c, "mcnemar_p": round(p_value, 4)}


def by_stratum(cases: list[dict], results: dict[str, QueryResult], k: int) -> dict:
    """recall@k per section stratum, with a Wilson interval. Refuses to
    report a stratum under MIN_STRATUM_N, the same floor eval/strata.py
    applies: a rate on 3 items is not a rate."""
    buckets: dict[str, list[bool]] = {}
    for case in cases:
        result = results.get(case["query_id"])
        if result is not None:
            buckets.setdefault(case["stratum"], []).append(hit_at(result, k))
    print(f"\nBy section stratum (recall@{k}):")
    out = {}
    for stratum, hits in sorted(buckets.items()):
        n, successes = len(hits), sum(hits)
        if n < MIN_STRATUM_N:
            print(f"  {stratum:14s} n={n}, below the n={MIN_STRATUM_N} floor, not reported")
            continue
        lo, hi = wilson_ci(successes, n)
        print(f"  {stratum:14s} {successes / n:.4f}  [{lo:.4f}, {hi:.4f}]  n={n}")
        out[stratum] = {"value": round(successes / n, 4),
                        "ci95": [round(lo, 4), round(hi, 4)], "n": n}
    return out


def sample_one_query_per_paragraph(cases: list[dict], n: int, seed: int) -> list[dict]:
    """Distinct paragraphs, one query each.

    Sampling queries directly would draw both styles of the same paragraph,
    and those two ask about the SAME fact against the SAME gold span. They
    are one observation, not two, and counting them as two would narrow the
    hole rate's interval on evidence that does not exist. Which style gets
    picked is random, so both are represented across the sample."""
    by_paragraph: dict[str, list[dict]] = {}
    for case in cases:
        by_paragraph.setdefault(case["paragraph_id"], []).append(case)
    rng = random.Random(seed)
    ids = sorted(by_paragraph)
    rng.shuffle(ids)
    return [rng.choice(by_paragraph[pid]) for pid in ids[:n]]


OVERLAP_BANDS = ((0.0, 0.5), (0.5, 0.65), (0.65, 0.8), (0.8, 0.9), (0.9, 1.01))


def by_overlap(cases: list[dict], results: dict[str, QueryResult], k: int) -> dict:
    """recall@k against the query's lexical overlap with its gold paragraph,
    with the two styles split out inside each band.

    This is the table that makes the headline paired result interpretable,
    and it answers a question the paired test cannot. The paired test says
    wording-reusing queries beat paraphrased ones. This says **why**: recall
    rises monotonically with overlap, and inside a fixed overlap band the
    style label adds almost nothing. So `style` is a manipulation that moves
    `lexical_overlap`, and overlap is what the retriever actually responds
    to. The practical consequence is that later ablations should condition on
    the per-row overlap number, not on the style label, which is a coarse
    proxy for it.

    Read the bands with their `n` in view: the styles are unequally
    represented inside each one by construction (a paraphrase rarely reaches
    0.9 overlap, a wording-reusing query rarely falls below 0.5), so a
    within-band comparison at small n is suggestive, not decisive."""
    print(f"\nBy lexical overlap with the gold paragraph (recall@{k}):")
    out = {}
    for lo, hi in OVERLAP_BANDS:
        band = [c for c in cases
                if lo <= c["lexical_overlap"] < hi and c["query_id"] in results]
        if not band:
            continue
        hits = sum(hit_at(results[c["query_id"]], k) for c in band)
        ci_lo, ci_hi = wilson_ci(hits, len(band))
        per_style = []
        for style in ("lexical", "paraphrased"):
            sub = [c for c in band if c["style"] == style]
            if len(sub) >= MIN_STRATUM_N:
                h = sum(hit_at(results[c["query_id"]], k) for c in sub)
                per_style.append(f"{style} {h / len(sub):.3f} (n={len(sub)})")
            else:
                per_style.append(f"{style} n={len(sub)}")
        print(f"  [{lo:.2f},{hi:.2f})  {hits / len(band):.3f}  "
              f"[{ci_lo:.3f}, {ci_hi:.3f}]  n={len(band):3d}   " + ",  ".join(per_style))
        out[f"{lo:.2f}-{hi:.2f}"] = {"value": round(hits / len(band), 4),
                                     "ci95": [round(ci_lo, 4), round(ci_hi, 4)], "n": len(band)}
    return out


def measure_holes(cases: list[dict], results: dict[str, QueryResult], index: BM25Index,
                  sample_n: int, top_n: int, model: str, seed: int) -> dict:
    """How often does a non-gold paragraph also answer the query?

    This is the number that says how much of the miss rate is the retriever
    and how much is the set's own single-gold assumption. Reported as a
    standing caveat on every row scored off this set, per the phase C design
    decision, rather than left as an unquantified worry."""
    # Keyed by chunk_id, so both the gold chunk and each candidate come out of
    # the index the retriever actually searched, not off disk a second time.
    by_id = {chunk.chunk_id: chunk for chunk in index.chunks}
    sampled = sample_one_query_per_paragraph(cases, sample_n, seed)
    holes, judged, details = 0, 0, []
    for i, case in enumerate(sampled, start=1):
        result = results.get(case["query_id"])
        if result is None:
            continue
        gold = next((c for c in index.chunks if chunk_hits_span(c, case["gold_span"])), None)
        if gold is None:
            continue
        candidates = [doc_id for doc_id in result.retrieved[:top_n] if doc_id != GOLD_ID]
        judged += 1
        for doc_id in candidates:
            chunk = by_id.get(doc_id)
            if chunk is None:
                continue
            verdict = groq_chat_json(HOLE_PROMPT.format(
                query=case["query"], gold=gold.text, candidate=chunk.text), model=model)
            if verdict.get("answers_the_query"):
                holes += 1
                details.append({"query_id": case["query_id"], "other": doc_id,
                                "why": verdict.get("why", "")})
                break  # one unjudged-relevant hit is enough to call this query holed
        if i % 10 == 0:
            print(f"  holes: {i}/{len(sampled)} queries, {holes} found", flush=True)

    lo, hi = wilson_ci(holes, judged) if judged else (0.0, 0.0)
    rate = holes / judged if judged else 0.0
    print(f"\nSingle-gold hole rate: {rate:.4f} [{lo:.4f}, {hi:.4f}] n={judged} "
          f"(top-{top_n} non-gold hits judged)")
    print(f"  Read every recall number off this set as a LOWER BOUND by roughly this much.")
    return {"value": round(rate, 4), "ci95": [round(lo, 4), round(hi, 4)], "n": judged,
            "top_n_judged": top_n, "model": model, "examples": details[:10]}




def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--index", type=Path, default=EVAL_DIR / "runs" / "bm25_index.pkl")
    parser.add_argument("--top-k", type=int, default=100, help="retrieval depth; recall@100 needs 100")
    parser.add_argument("--report-k", type=int, default=10, help="k for the paired and per-stratum tests")
    parser.add_argument("--out", type=Path, help="write metrics JSON here")
    parser.add_argument("--measure-holes", type=int, metavar="N",
                        help="LLM-judge the top non-gold hits of N sampled queries")
    parser.add_argument("--hole-top-n", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--allow-missing-gold", action="store_true",
                        help="report anyway when gold spans are absent from the index "
                             "(they will score as misses that mean nothing)")
    parser.add_argument("--exploratory", action="store_true")
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    try:
        validate_cases(cases, exploratory=args.exploratory)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{args.cases}: {len(cases)} queries over "
          f"{len({c['paragraph_id'] for c in cases})} paragraphs")
    index = BM25Index.load(args.index)
    print(f"{args.index}: {index.n_docs} paragraphs indexed")
    n_missing = check_index_covers_gold(cases, index)
    if n_missing and not args.allow_missing_gold:
        print("Refusing to report a number off an index that does not contain the gold spans. "
              "Pass --allow-missing-gold to override.", file=sys.stderr)
        return 1

    t0 = time.time()
    results: dict[str, QueryResult] = {}
    for i, case in enumerate(cases, start=1):
        hits = index.search(case["query"], top_k=args.top_k)
        results[case["query_id"]] = to_query_result(case, [p for p, _score in hits])
        if i % 50 == 0:
            print(f"  {i}/{len(cases)} queries ({i / (time.time() - t0):.2f}/s)", flush=True)
    search_s = time.time() - t0

    ordered = [results[c["query_id"]] for c in cases]
    # What a RESULTS.md row off this run has to name: the retriever's
    # parameters, the index it searched, and the case file, so two rows with
    # the same hash really did measure the same thing. Timings are excluded,
    # they vary run to run and would make every hash unique.
    config = {"retriever": "bm25", "k1": bm25.K1, "b": bm25.B, "top_k": args.top_k,
              "index": str(args.index), "n_indexed": index.n_docs,
              "cases": str(args.cases), "n_queries": len(cases), "git_sha": git_sha(),
              "cases_sha256": file_hash(args.cases), "index_sha256": file_hash(args.index),
              "source_hash": source_hash(), "report_k": args.report_k, "exploratory": args.exploratory}
    payload = {
        "config": config, "config_hash": config_hash(config),
        "meta": {"cases": str(args.cases), "n_queries": len(cases),
                 "n_paragraphs": len({c["paragraph_id"] for c in cases}),
                 "index": str(args.index), "n_indexed": index.n_docs, "top_k": args.top_k,
                 "gold_spans_missing_from_index": n_missing,
                 "search_ms_per_query": round(1000 * search_s / max(1, len(cases)), 1)},
        "overall": summarize("Overall", ordered, args.report_k),
        "by_style": {}, "by_stratum": {}, "by_overlap": {},
        "lexical_bias": None, "holes": None,
        "per_query": [{"query_id": c["query_id"], "paragraph_id": c["paragraph_id"],
                       "style": c["style"], "stratum": c["stratum"],
                       "lexical_overlap": c["lexical_overlap"],
                       "rank_of_gold": rank_of_gold(results[c["query_id"]])}
                      for c in cases],
    }
    for style in sorted({c["style"] for c in cases}):
        subset = [results[c["query_id"]] for c in cases if c["style"] == style]
        payload["by_style"][style] = summarize(f"Style: {style}", subset, args.report_k)

    payload["lexical_bias"] = paired_style_test(cases, results, args.report_k)
    payload["by_stratum"] = by_stratum(cases, results, args.report_k)
    payload["by_overlap"] = by_overlap(cases, results, args.report_k)

    if args.measure_holes:
        payload["holes"] = measure_holes(cases, results, index, args.measure_holes,
                                         args.hole_top_n, args.model, args.seed)

    print(f"\nconfig hash {payload['config_hash']}, git sha {config['git_sha']}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2))
        print(f"Wrote {args.out}")
        overall = payload["overall"]
        run_id = append_run(
            eval_set="retrieval", run_config=config, results_path=str(args.out),
            input_paths={"cases": args.cases, "index": args.index},
            metrics={f"recall@{args.report_k}": overall.get(f"recall@{args.report_k}"),
                     "mrr": overall.get("mrr"), "n_queries": len(cases)})
        print(f"Registered run {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
