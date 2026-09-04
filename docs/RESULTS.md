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

> ### Standing caveat on every `answer`-set row below (added 2026-09-04)
>
> A human validation pass over 8 of the 19 answer cases (phase A1) found **4 of 8 defective**:
> 95% CI [0.22, 0.78]. One gold span cited a paragraph about a different variant, two gold labels
> asserted quantitative detail absent from the span they cite, and one negative case asserts an
> absence the corpus contradicts. Details and the failure mode in `DECISION_LOG.md`, "phase A1 case
> validation, half the gold set is defective."
>
> **Every `answer`-set row above the 2026-09-04 rerun was graded against that set.** They are not
> withdrawn (this file is append-only, and the runs really happened) but they are **superseded**:
> see "Repaired-set rerun (12 dev cases), 2026-09-04" below for the current numbers.
>
> Recorded because it is the kind of thing that is tempting to quietly fix: when this caveat was
> first written it guessed that the headline finding "is a large effect and is unlikely to be an
> artifact of four bad cases." **That guess was half wrong.** The groundedness half survived and
> got stronger. The direction half, the confident claim that retrieval moves direction/strength
> not at all, did not survive: on the repaired set three cases flip where previously none did.
>
> The `retrieval`-set rows (SciFact, NFCorpus) are **unaffected**: those labels come from BEIR, not
> from this project.

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

**Held-out split note:** both runs above scored all 19 cases, before `eval/split.py`'s dev/held-out
split existed later the same day (see `docs/DECISION_LOG.md`, "dev/held-out split"). Not counted as
a touch, since the split didn't exist yet, but these two rows are not held-out-clean: 6 of the 19
cases scored here are now the held-out set. Every run from here on defaults to the 13-case dev
split only.

**Judge prompt version note (2026-09-03):** an LLM-vs-LLM kappa cross-check (Gemini 3.1 Pro
against this judge, `docs/DECISION_LOG.md`) surfaced two real judge-prompt issues, fixed the same
day: magnitude-only strength mismatches were sometimes scored `fail` instead of `partial`, and
figure captions/table headers were sometimes credited as grounded content. Both rows above were
scored by the judge *before* this fix. SUPERSEDED by the dev-split rerun below, which also fixes
the held-out-split leakage noted above; kept for the trail, not current numbers.

### Dev-split rerun (13 cases), corrected judge, 2026-09-03

Same two baselines, same corrected `answer_cases.jsonl`, this time correctly scoped to the 13-case
dev split (`score.py`'s default `--held-out exclude`) and the post-fix judge prompts.

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-03 | M1 | answer | `baseline/no_retrieval_direction` | 0.125 | [0.02, 0.47] | 8 | `cfg-de94e6e15f71` | `57d356d` | evidence-stratum, non-negative dev cases (n=8 of 13) |
| 2026-09-03 | M1 | answer | `baseline/no_retrieval_groundedness` | 0.0 | [0.00, 0.32] | 8 | `cfg-de94e6e15f71` | `57d356d` | fails by construction, no spans to cite |
| 2026-09-03 | M1 | answer | `baseline/no_retrieval_disagreement` | 0.0 | [0.00, 0.56] | 3 | `cfg-de94e6e15f71` | `57d356d` | the 3 dev-split disagreement cases only |
| 2026-09-03 | M1 | answer | `baseline/no_retrieval_not_found` | 0.846 | [0.58, 0.96] | 13 | `cfg-de94e6e15f71` | `57d356d` | pools all 13 dev cases |
| 2026-09-03 | M1 | answer | `baseline/bm25_only_direction` | 0.125 | [0.02, 0.47] | 8 | `cfg-d5751bcf985b` | `57d356d` | **paired vs no_retrieval above: delta +0pp, McNemar exact p=1.000.** Same finding as the 19-case run: retrieval still does not move this property |
| 2026-09-03 | M1 | answer | `baseline/bm25_only_groundedness` | 0.625 | [0.31, 0.86] | 8 | `cfg-d5751bcf985b` | `57d356d` | paired delta +62pp, McNemar exact p=0.062, not quite significant at this smaller n (was p=0.008 at n=11-12 in the 19-case run); direction of effect unchanged |
| 2026-09-03 | M1 | answer | `baseline/bm25_only_disagreement` | 0.667 | [0.21, 0.94] | 3 | `cfg-d5751bcf985b` | `57d356d` | paired delta +67pp, McNemar exact p=0.500, n=3 too small to read |
| 2026-09-03 | M1 | answer | `baseline/bm25_only_not_found` | 0.923 | [0.67, 0.99] | 13 | `cfg-d5751bcf985b` | `57d356d` | paired delta +8pp, McNemar exact p=1.000 |

**What changed vs. the 19-case run, and what didn't:** the core finding survives at the smaller,
held-out-clean n: retrieval buys real groundedness (direction of effect unchanged, same size) and
buys nothing on direction/strength (still exactly flat, 12.5% both baselines, still zero cases
flipped). The groundedness paired test is no longer under the conventional p<0.05 line (p=0.062
vs the earlier p=0.008), purely a sample-size effect from correctly excluding the 6 held-out cases,
not a change in the effect itself. This is the number to cite going forward; the 19-case rows above
mixed held-out cases into a "dev" result and used the pre-fix judge, kept for the trail only.

### Harness validation: BM25 on SciFact and NFCorpus, 2026-09-03 (phase A2)

The check `PROJECT_PLAN.md` M1 asks for first and this project had skipped: run the harness against
free labeled data before trusting it on your own. Same `eval/bm25.py` the domain baselines used,
scored by the new hand-written `eval/ir_metrics.py`, against published Pyserini multi-field BM25
figures (Kamalloo et al., "Resources for Brewing BEIR," arXiv 2306.07471, Table 2). Prediction and
the pre-registered bug threshold were logged before the run (`docs/DECISION_LOG.md`).

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/ndcg@10` | 0.598 | [0.550, 0.648] | 300 | `cfg-0338e902ce5e` | `ea364b7`+ | reference 0.665, delta -0.067, **90% of reference**; within the predicted [0.55, 0.70] |
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/recall@100` | 0.825 | [0.782, 0.867] | 300 | `cfg-0338e902ce5e` | `ea364b7`+ | reference 0.908, delta -0.083; point estimate fell *below* the predicted [0.85, 0.91], the one sub-prediction that missed |
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/recall@10` | 0.718 | [0.668, 0.767] | 300 | `cfg-0338e902ce5e` | `ea364b7`+ | no published reference at this depth |
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/mrr` | 0.569 | [0.521, 0.620] | 300 | `cfg-0338e902ce5e` | `ea364b7`+ | full-depth MRR |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/ndcg@10` | 0.288 | [0.255, 0.321] | 323 | `cfg-ff86812f1dc3` | `ea364b7`+ | reference 0.325, delta -0.037, **89% of reference**; predicted point estimate was 0.29 |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/recall@100` | 0.220 | [0.192, 0.250] | 323 | `cfg-ff86812f1dc3` | `ea364b7`+ | reference 0.250, delta -0.030 |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/recall@10` | 0.135 | [0.111, 0.160] | 323 | `cfg-ff86812f1dc3` | `ea364b7`+ | low by construction: 38 relevant docs per query on average, so 10 slots cannot hold many of them |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/mrr` | 0.505 | [0.454, 0.554] | 323 | `cfg-ff86812f1dc3` | `ea364b7`+ | see the note below on why MRR and recall@10 disagree this violently |

**What this establishes, and what it does not.** Both nDCG@10 figures land at 89-90% of an external
published reference, far above the 60%-of-reference bug threshold registered before the run. The
metric definitions, the tokenizer, the BM25 scoring loop, and the qrel join are therefore
approximately right, and the domain numbers above that depend on the same retriever do not inherit
an obvious plumbing bug. It does **not** establish that this BM25 matches the reference: the CI
half-widths here are about 0.05 and 0.03, so a real 0.07 shortfall on SciFact is visible and
correctly attributed to the known implementation differences (untuned `k1=1.5, b=0.75` against
Lucene's `0.9/0.4`, no stemming, no stopword removal, one concatenated field instead of two
weighted ones).

**The NFCorpus MRR/recall gap is the most instructive number in the table.** MRR 0.505 against
recall@10 0.135 on the same ranking is not a contradiction: NFCorpus averages 38 relevant documents
per query, so finding *one* of them near the top is easy (that is MRR) while getting a meaningful
share of them into 10 slots is arithmetically close to impossible (that is recall@10). Reporting
either alone would badly misdescribe this retriever. That is the argument for the metric families
below being reported together rather than a single headline retrieval number.

**Git SHA caveat:** `ea364b7`+ means commit `ea364b7` plus the then-uncommitted
`eval/ir_metrics.py`, `eval/benchmarks/run_benchmark.py`, and the `bm25.py` split of
`index_from_paragraphs` out of `build_index`. The BM25 formula itself is unchanged from `ea364b7`
(`test_bm25.py` passes unmodified across that refactor). Update these rows to the real SHA on the
next commit, the same way the 0c rows were handled.

### Repaired-set rerun (12 dev cases), 2026-09-04: the direction finding does not survive

Both baselines re-run against the repaired 17-case set (12 dev), on the rebuilt BM25 index over
the post-hold-out corpus (7,857 articles, 436,834 paragraphs). Same judge and judge-prompt version
as the 2026-09-03 rows, so the only things that changed are the gold labels and the negative-case
construction. **These rows supersede every `answer`-set row above.**

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_direction` | 0.250 | [0.07, 0.59] | 8 | `cfg-5d548c010eeb` | `ea364b7`+ | was 0.125 on the defective set |
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_groundedness` | 0.0 | [0.00, 0.32] | 8 | `cfg-5d548c010eeb` | `ea364b7`+ | fails by construction, no spans to cite |
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_disagreement` | 0.0 | [0.00, 0.56] | 3 | `cfg-5d548c010eeb` | `ea364b7`+ | |
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_not_found` | 0.917 | [0.65, 0.98] | 12 | `cfg-5d548c010eeb` | `ea364b7`+ | all 4 dev hold-out negatives pass; see the note on what that costs |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_direction` | 0.375 | [0.14, 0.69] | 8 | `cfg-9c6b643661a9` | `ea364b7`+ | **paired delta +12pp, McNemar exact p=1.000, 3 cases flipped.** The "exactly flat, zero flips" result is gone, see below |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_groundedness` | 0.750 | [0.41, 0.93] | 8 | `cfg-9c6b643661a9` | `ea364b7`+ | paired delta +75pp, **McNemar exact p=0.031**, 6 of 8 cases flipped to pass, 0 the other way |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_disagreement` | 0.667 | [0.21, 0.94] | 3 | `cfg-9c6b643661a9` | `ea364b7`+ | paired delta +67pp, p=0.500, n=3 too small to read |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_not_found` | 0.917 | [0.65, 0.98] | 12 | `cfg-9c6b643661a9` | `ea364b7`+ | paired delta 0pp; the two baselines fail on *different* cases (1 each) |

**The headline result changed, and this is the payoff from the validation pass.** The 2026-09-03
rows supported a confident negative claim: direction/strength was *exactly* 12.5% under both
baselines with **zero cases flipping either way**, which read as strong evidence that direction
failures are a synthesis problem retrieval cannot touch. On the repaired set that claim does not
hold. Direction is 25% vs 37.5%, and **three cases flip** (two to BM25, one to no-retrieval).
The "zero flips" observation was partly an artifact of defective gold.

What replaces it is weaker and more honest: **at n=8 this eval set cannot tell whether retrieval
helps direction/strength.** A +12pp delta with McNemar p=1.000 is not evidence of an effect, and
it is not evidence of no effect either. The earlier confident negative was over-read from a set
that was both too small and partly wrong.

**Repairing gold roughly doubled measured direction quality on both baselines** (12.5% to 25% and
12.5% to 37.5%). Two of the three repaired cases had gold that penalized correct answers: one
asserted cohort figures the cited span did not contain, one attributed a BRCA2-only finding to
BRCA1 and BRCA2 both. The systems were being marked wrong for being right. A defective eval set
understated system quality by about half on this property, which is worth remembering the next
time a number here looks disappointing.

**Groundedness got stronger and now clears the conventional line:** +75pp, p=0.031, 6 of 8 cases
flipping to pass and none the other way. This is the one claim in the project that is both large
and now statistically supported at its own n.

**What the negative-case rebuild cost, stated plainly.** All four dev hold-out negatives pass
`not_found` under *both* baselines. That is the predicted consequence of building them from
document-frequency-1 variants: a variant rare enough to hold out safely is one the model does not
know either, so no-retrieval refuses correctly rather than fabricating. The old set's sharpest
single result, no-retrieval inventing a confident pathogenic classification for a variant the
corpus lacked, is not reproducible here. That result rested on a case built by a method now known
to be unsound, so it was not safe to keep, but the replacement genuinely tests less. Property 4
now measures retrieval restraint, not memorization. Recovering the memorization test needs a
different construction, and that is an open item rather than a solved one.

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
