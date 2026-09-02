# Results

One row per measured number, ever. This is the file an interview question gets answered from.
"What's your p95 latency," "what does one query cost," "what's your retrieval recall" should all
be a lookup here, not a re-derivation. Append, don't overwrite; if a number changes, add a new row
rather than editing the old one, so the history of how a metric moved stays visible.

**Three things every row needs** (the third is new in v3):

1. **Git SHA.** An untagged number is not reproducible, including to yourself in three months.
2. **Config hash.** Which chunker/embedder/index/retriever/reranker/model/prompt produced it.
3. **An interval, not just a point estimate.** A bare `0.74` is a claim the data may not support.
   Report a 95% CI (bootstrap is fine) and the `n` it came from. This is the single most common
   way a project like this fools itself.

**Which eval set?** Every row must say. The two sets have very different power:

- **`retrieval` set (n >= 300)**: automatically scored, labels attached to source spans. Retrieval
  ablations live here; a roughly 3-point delta is detectable.
- **`answer` set (n approximately 50-80, with a held-out third)**: hand-labeled end-to-end quality.
  Only large effects are visible. Say so in the Notes rather than over-reading a small delta.

**Comparisons are paired.** When a row exists to be compared against another row, both configs
ran on the same items. Record the paired test result (McNemar or paired bootstrap) in Notes, not
just the two marginal rates.

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-08-31 | 0c | n/a (server load test) | `latency/p95_ms` | 30.0 | [27.2, 35.8] | 60 | `stub-c401c89faf18` | `4bb2b5e` | concurrency=1 baseline; stub keyword-match handler, not a RAG quality number, see notes below the table |
| 2026-08-31 | 0c | n/a (server load test) | `latency/p50_ms` | 390.9 | n/a (point estimate) | 150 | `stub-c401c89faf18` | `4bb2b5e` | concurrency=20, named-load test |
| 2026-08-31 | 0c | n/a (server load test) | `latency/p95_ms` | 476.8 | [472.6, 489.1] | 150 | `stub-c401c89faf18` | `4bb2b5e` | concurrency=20; ~16x the concurrency=1 p95 above, single uvicorn worker, handler is CPU-bound XML parsing under the GIL, so concurrent requests serialize rather than parallelize; a real finding about this server, not the eventual retriever |
| 2026-08-31 | 0c | n/a (server load test) | `latency/ttft_ms` | 263.8 | [245.2, 276.4] | 150 | `stub-c401c89faf18` | `4bb2b5e` | concurrency=20, p95 TTFT (time to first streamed match); both p95 numbers well under the 6s/1.5s TASK_CONTRACT.md targets, expected since this is a trivial handler, not generation |

**Git SHA note:** `4bb2b5e` is the commit ("feat: add Step 0c FastAPI measurement surface, drop
Step 0d") that added `service/search.py` and `service/app.py` exactly as they were when these
numbers were measured; nothing in the handler changed between measuring and committing.

| 2026-09-02 | M1 | answer | `baseline/no_retrieval_direction` | 0.0 | [0.00, 0.49] | 4 | `cfg-63d436fc7730` | `c062228` | SUPERSEDED by the 19-case row below; kept for the trail, not a current number |
| 2026-09-02 | M1 | answer | `baseline/no_retrieval_groundedness` | 0.0 | [0.00, 0.49] | 4 | `cfg-63d436fc7730` | `c062228` | SUPERSEDED by the 19-case row below |
| 2026-09-02 | M1 | answer | `baseline/no_retrieval_disagreement` | 0.0 | [0.00, 0.49] | 4 | `cfg-63d436fc7730` | `c062228` | SUPERSEDED by the 19-case row below |
| 2026-09-02 | M1 | answer | `baseline/no_retrieval_not_found` | 0.833 | [0.55, 0.95] | 12 | `cfg-63d436fc7730` | `c062228` | SUPERSEDED by the 19-case row below |

**On the first (12-case) baseline run:** first real M1 numbers, not yet a system-quality claim,
superseded a few hours later the same day by the 19-case rerun below once the 7 ordinary evidence
cases existed (see `docs/DECISION_LOG.md`, "first 7 ordinary evidence cases"). Kept rather than
deleted per this file's own append-only rule.

### 19-case run: no_retrieval vs. bm25_only, paired

Both baselines run on the same 19 cases (4 disagreement, 8 negative, 7 ordinary), same judge model,
same day, so the comparison below is paired per this file's own rule, not two marginal rates.

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-02 | M1 | answer | `baseline/no_retrieval_direction` | 0.182 | [0.05, 0.48] | 11 | `cfg-249fc8b15f43` | `c062228` | evidence-stratum, non-negative cases only (n=11 of 19) |
| 2026-09-02 | M1 | answer | `baseline/no_retrieval_groundedness` | 0.0 | [0.00, 0.26] | 11 | `cfg-249fc8b15f43` | `c062228` | fails by construction, no spans to cite, see `eval/baselines/no_retrieval.py` |
| 2026-09-02 | M1 | answer | `baseline/no_retrieval_disagreement` | 0.0 | [0.00, 0.49] | 4 | `cfg-249fc8b15f43` | `c062228` | the 4 disagreement cases only |
| 2026-09-02 | M1 | answer | `baseline/no_retrieval_not_found` | 0.842 | [0.62, 0.94] | 19 | `cfg-249fc8b15f43` | `c062228` | pools all 19 cases, see "extended_check" in `docs/DECISION_LOG.md` |
| 2026-09-02 | M1 | answer | `baseline/bm25_only_direction` | 0.182 | [0.05, 0.48] | 11 | `cfg-df5eb0e9a175` | `c062228` | **paired vs no_retrieval above: delta +0pp, McNemar exact p=1.000.** Retrieval did not move this property at all, see notes below |
| 2026-09-02 | M1 | answer | `baseline/bm25_only_groundedness` | 0.75 | [0.47, 0.91] | 12 | `cfg-df5eb0e9a175` | `c062228` | n=12 of 19 (7 cases had `not_found=true`, no claims to grade); paired McNemar delta on the 11 shared-n cases +73pp, **p=0.008**, real and significant even at this n |
| 2026-09-02 | M1 | answer | `baseline/bm25_only_disagreement` | 0.75 | [0.30, 0.95] | 4 | `cfg-df5eb0e9a175` | `c062228` | paired delta +75pp, McNemar exact p=0.250, not significant at n=4 (too small, not a null result) |
| 2026-09-02 | M1 | answer | `baseline/bm25_only_not_found` | 0.895 | [0.69, 0.97] | 19 | `cfg-df5eb0e9a175` | `c062228` | paired delta +5pp, McNemar exact p=1.000 |

**Retrieval mechanism:** hand-built Okapi BM25 (`eval/bm25.py`, no ranking library, per
`PROJECT_PLAN.md`'s "implement at least one component with no library" rule), paragraph-granularity
index over the full 7,863-article corpus (437,133 paragraphs), `k1=1.5 b=0.75` textbook defaults,
top-8 retrieved per query. Judge: Groq free tier, `openai/gpt-oss-120b` (the model named in the
"Model & embedding stack" decision, `llama-3.3-70b-versatile`, was removed from Groq's lineup by
the time this ran, see `docs/DECISION_LOG.md`, "Groq model drift"). Config hashes are sha256
prefixes of the model/judge/prompt-version/retriever string, an informal stand-in for the
config-as-code hash M2 formalizes. Paired test: `eval/compare_runs.py`, McNemar exact, partial
verdicts counted as not-pass (strict reading, noted since it's a real choice). Full per-case scores
and judge rationale: `eval/runs/*_scores.json` (git-ignored, regenerable, see `eval/README.md`).

**What this actually answers, the M1 question "how much does retrieval buy you":** groundedness
goes from impossible (0%, no citations exist without retrieval) to 75%, real and significant even
at n=11-12. That's expected by construction but still the number the whole project exists to
produce. The genuinely interesting result is what *didn't* move: **direction/strength pass rate is
identical, 18% both ways, zero cases flipped either direction.** Retrieval handed the model real,
correct citations and it still got the reported direction wrong at the same rate as guessing from
memory. That's evidence the direction failures aren't a retrieval problem, they're a synthesis/
reading-comprehension problem on top of correct retrieval, worth a closer read once M4 error
analysis exists, not something a better retriever would fix on its own.

**Specific findings kept, not just the pass rates:** no-retrieval fabricated a confident pathogenic
classification for `brca2_c9097c_t_ovarian_neg_001`, a variant this corpus was built specifically
to not contain (the memorization risk this eval property exists to catch); BM25 correctly returned
`not_found` for that same case (the retrieved excerpts didn't cover the specific variant). BM25 also
introduced 2 new false-not-found misses on ordinary cases whose real supporting paragraph existed
in the corpus but wasn't retrieved into the top-8 (`tp53_chondrosarcoma_survival_ord_001`,
`tp53_her2_breast_ord_001`), a genuine retrieval-recall miss, not a generation failure, an early,
small-n instance of exactly the retrieval-vs-generation attribution question M4 exists to answer
systematically.

**On the stub handler:** these are Step 0c's required first `RESULTS.md` row (`PROJECT_PLAN.md`
0c exit criterion), not a system-quality baseline. The handler is deliberately trivial (literal
keyword match, no retriever); see `docs/DECISION_LOG.md`, "Step 0c built as a stub handler, v1
formally dropped." What these numbers establish is that the measurement mechanism itself works:
real concurrent HTTP requests, real streaming, a real p95/TTFT/CI computation off the live server.
That mechanism, not these values, is what M1 onward reuses once a real retriever/generator exists
to measure.

## Metric families

Keep names consistent so rows stay comparable over the whole project.

- `eval/pass_rate`, `eval/judge_human_kappa`, `eval/self_agreement_kappa`, `eval/label_error_rate`
- `retrieval/recall@5`, `retrieval/recall@10`, `retrieval/mrr`, `retrieval/ndcg@10`
- `baseline/no_retrieval`: **always report per date-stratum** (`_pre_cutoff` / `_post_cutoff`).
  The pooled number conflates retrieval lift with memorization.
- `baseline/bm25_only`, `baseline/full_doc_in_context`
- `latency/p50_ms`, `latency/p95_ms`, `latency/ttft_ms`, `latency/stage_breakdown_*`
- `cost/usd_per_query`, `cost/stage_breakdown_*`, `cost/index_rebuild_usd`
- `cache/hit_rate`
- `guardrails/catch_rate`, `guardrails/false_positive_rate`
- `agent/quality_delta_vs_ragchain`, `agent/cost_multiplier_vs_ragchain`, `agent/p95_delta_ms`
- `ann/recall_at_ef_*`, `ann/latency_at_ef_*`: the sweep that makes the recall/latency curve
- `etl/articles_parsed`, `etl/wall_clock_s`, `etl/output_files`, `etl/skew_ratio`

---

*Example rows, note what they do and don't claim. Delete once real ones exist.*

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-09 | M1 | answer | `baseline/no_retrieval_pre_cutoff` | 0.61 | [0.47, 0.75] | 44 | `cfg-a0` | `a1b2c3d` | high, likely memorization, papers are in pretraining |
| 2026-09-09 | M1 | answer | `baseline/no_retrieval_post_cutoff` | 0.19 | [0.08, 0.38] | 28 | `cfg-a0` | `a1b2c3d` | the honest floor; the pooled number would have hidden this |
| 2026-09-09 | M1 | answer | `baseline/bm25_only` | 0.44 | [0.33, 0.56] | 72 | `cfg-a1` | `a1b2c3d` | first real baseline; full answer set (44 pre + 28 post) |
| 2026-09-11 | M1 | answer | `eval/judge_human_kappa` | 0.68 | [0.52, 0.81] | 40 | `cfg-a1` | `a1b2c3d` | self-agreement ceiling was 0.79, judge is close to my own noise floor |
| 2026-09-24 | M6 | retrieval | `retrieval/recall@10` (fixed-size) | 0.712 | [0.66, 0.76] | 320 | `cfg-c1` | `def5678` | paired vs `cfg-c2` below |
| 2026-09-24 | M6 | retrieval | `retrieval/recall@10` (section-aware) | 0.741 | [0.69, 0.79] | 320 | `cfg-c2` | `def5678` | paired bootstrap on same 320 items: delta = +2.9pp, 95% CI [+0.4, +5.3], p=0.03, small but real |
