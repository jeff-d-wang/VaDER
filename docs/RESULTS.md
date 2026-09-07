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

> ### Standing caveat on every `baseline/bm25_only` row below (added 2026-09-05)
>
> **Every `bm25_only` row in this file retrieved sentence fragments, not paragraphs.** The BM25
> index those runs used was built by a `"\n"`-join/split round trip that treated JATS line wrapping
> inside a `<p>` as a paragraph boundary: 436,834 records where the corrected extractor produces
> 344,900, and on the worst article 2,273 fragments where there are 186 paragraphs. So a run
> labelled "top 8 BM25 paragraphs in context" put roughly eight *sentences* in the prompt.
>
> Confirmed by timestamp, not inferred: the index was written 2026-09-05 01:48 and
> `bm25_only_answers.jsonl.meta.json` records the run at 01:52 the same morning, about fourteen
> hours before the commit that unified the paragraph convention.
>
> The rows are **not withdrawn**, they measure exactly what ran, and the numbers reproduce from
> their git SHA. But the label claims more context than the run had, so read the retrieval lift
> they report as a lower bound. **These rows are pending a re-run against the rebuilt index**; that
> re-run is an experiment with its own prediction, logged before it happens. Nothing else in this
> file is affected: `no_retrieval` and `oracle_spans` never touch the index, and the SciFact and
> NFCorpus rows build their own index from benchmark text through `build_index_from_texts`.
> Details in `DECISION_LOG.md`, "the BM25 index was a cache of sentence fragments."

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-08-31 | 0c | n/a (server load test) | `latency/p95_ms` | 30.0 | [27.2, 35.8] | 60 | `stub-c401c89faf18` | `87ee3ac` | concurrency=1 baseline; stub keyword-match handler, not a RAG quality number, see notes below the table |
| 2026-08-31 | 0c | n/a (server load test) | `latency/p50_ms` | 390.9 | n/a (point estimate) | 150 | `stub-c401c89faf18` | `87ee3ac` | concurrency=20, named-load test |
| 2026-08-31 | 0c | n/a (server load test) | `latency/p95_ms` | 476.8 | [472.6, 489.1] | 150 | `stub-c401c89faf18` | `87ee3ac` | concurrency=20; ~16x the concurrency=1 p95 above, single uvicorn worker, handler is CPU-bound XML parsing under the GIL, so concurrent requests serialize rather than parallelize; a real finding about this server, not the eventual retriever |
| 2026-08-31 | 0c | n/a (server load test) | `latency/ttft_ms` | 263.8 | [245.2, 276.4] | 150 | `stub-c401c89faf18` | `87ee3ac` | concurrency=20, p95 TTFT (time to first streamed match); both p95 numbers well under the 6s/1.5s TASK_CONTRACT.md targets, expected since this is a trivial handler, not generation |

**Git SHA note:** `87ee3ac` is the commit ("feat: add Step 0c FastAPI measurement surface, drop
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
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/ndcg@10` | 0.598 | [0.550, 0.648] | 300 | `cfg-0338e902ce5e` | `82684e0`+ | reference 0.665, delta -0.067, **90% of reference**; within the predicted [0.55, 0.70] |
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/recall@100` | 0.825 | [0.782, 0.867] | 300 | `cfg-0338e902ce5e` | `82684e0`+ | reference 0.908, delta -0.083; point estimate fell *below* the predicted [0.85, 0.91], the one sub-prediction that missed |
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/recall@10` | 0.718 | [0.668, 0.767] | 300 | `cfg-0338e902ce5e` | `82684e0`+ | no published reference at this depth |
| 2026-09-03 | M1/A2 | SciFact (BEIR test) | `retrieval/mrr` | 0.569 | [0.521, 0.620] | 300 | `cfg-0338e902ce5e` | `82684e0`+ | full-depth MRR |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/ndcg@10` | 0.288 | [0.255, 0.321] | 323 | `cfg-ff86812f1dc3` | `82684e0`+ | reference 0.325, delta -0.037, **89% of reference**; predicted point estimate was 0.29 |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/recall@100` | 0.220 | [0.192, 0.250] | 323 | `cfg-ff86812f1dc3` | `82684e0`+ | reference 0.250, delta -0.030 |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/recall@10` | 0.135 | [0.111, 0.160] | 323 | `cfg-ff86812f1dc3` | `82684e0`+ | low by construction: 38 relevant docs per query on average, so 10 slots cannot hold many of them |
| 2026-09-03 | M1/A2 | NFCorpus (BEIR test) | `retrieval/mrr` | 0.505 | [0.454, 0.554] | 323 | `cfg-ff86812f1dc3` | `82684e0`+ | see the note below on why MRR and recall@10 disagree this violently |

**What this establishes, and what it does not.** Both nDCG@10 figures land at 89-90% of an external
published reference, far above the 60%-of-reference bug threshold registered before the run. The
metric definitions, the tokenizer, the BM25 scoring loop, and the qrel join are therefore
approximately right, and the domain numbers above that depend on the same retriever do not inherit
an obvious plumbing bug. It does **not** establish that this BM25 matches the reference: the CI
half-widths here are about 0.05 and 0.03, so a real 0.07 shortfall on SciFact is visible and
correctly attributed to the known implementation differences (untuned `k1=1.5, b=0.75` against
Lucene's `0.9/0.4`, no stemming, no stopword removal, one concatenated field instead of two
weighted ones).

### k1=1.2 vs k1=1.5, paired on BEIR, 2026-09-06

Asked whether the standard Okapi configuration (k1=1.2, b=0.75) had ever been tried. It had not.
Run on BEIR rather than the domain set, deliberately: the domain set is currently ~55% defective,
and the v4 audit reserved its independence for phase D. b was already 0.75, so only k1 changed.
Paired, one index per dataset scored twice, because k1 is a scoring-time parameter.

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-06 | M1/C | SciFact (BEIR test) | `retrieval/ndcg@10` (k1=1.2) | 0.600 | [0.553, 0.649] | 300 | `cfg-0338e902ce5e`+k1=1.2 | `b40d84e` | **paired vs k1=1.5: +0.0020, 95% CI [-0.0050, +0.0090], no detectable difference** |
| 2026-09-06 | M1/C | NFCorpus (BEIR test) | `retrieval/ndcg@10` (k1=1.2) | 0.286 | [0.253, 0.318] | 323 | `cfg-0338e902ce5e`+k1=1.2 | `b40d84e` | **paired vs k1=1.5: -0.0023, 95% CI [-0.0057, +0.0005], no detectable difference**, and the sign flips against SciFact |

**k1 stays at 1.5.** The rule was fixed before the run: only a paired interval excluding zero moves
the default. Both straddle zero, both point estimates are two thousandths, and the two datasets
disagree about the direction.

**The finding worth keeping is that k1 barely does anything here.** It changed recall@10 for **4 of
300** SciFact queries and 15 of 323 NFCorpus queries; most rankings came out bit-identical. k1
governs how fast a repeated term saturates, so its leverage scales with within-document term
frequency, and on abstracts (and on this project's 92-token paragraphs) almost every term appears
once. **k1 is close to inert for short-document retrieval.** The knob with real leverage on this
corpus is `b`, because the corpus mixes 1,500-character abstracts with short body paragraphs, and
that is still untested.

**The NFCorpus MRR/recall gap is the most instructive number in the table.** MRR 0.505 against
recall@10 0.135 on the same ranking is not a contradiction: NFCorpus averages 38 relevant documents
per query, so finding *one* of them near the top is easy (that is MRR) while getting a meaningful
share of them into 10 slots is arithmetically close to impossible (that is recall@10). Reporting
either alone would badly misdescribe this retriever. That is the argument for the metric families
below being reported together rather than a single headline retrieval number.

**Git SHA caveat:** `82684e0`+ means commit `82684e0` plus the then-uncommitted
`eval/ir_metrics.py`, `eval/benchmarks/run_benchmark.py`, and the `bm25.py` split of
`index_from_paragraphs` out of `build_index`. The BM25 formula itself is unchanged from `82684e0`
(`test_bm25.py` passes unmodified across that refactor). Update these rows to the real SHA on the
next commit, the same way the 0c rows were handled.

### Repaired-set rerun (12 dev cases), 2026-09-04: the direction finding does not survive

Both baselines re-run against the repaired 17-case set (12 dev), on the rebuilt BM25 index over
the post-hold-out corpus (7,857 articles, 436,834 paragraphs). Same judge and judge-prompt version
as the 2026-09-03 rows, so the only things that changed are the gold labels and the negative-case
construction. **These rows supersede every `answer`-set row above.**

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_direction` | 0.250 | [0.07, 0.59] | 8 | `cfg-5d548c010eeb` | `82684e0`+ | was 0.125 on the defective set |
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_groundedness` | 0.0 | [0.00, 0.32] | 8 | `cfg-5d548c010eeb` | `82684e0`+ | fails by construction, no spans to cite |
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_disagreement` | 0.0 | [0.00, 0.56] | 3 | `cfg-5d548c010eeb` | `82684e0`+ | |
| 2026-09-04 | M1 | answer | `baseline/no_retrieval_not_found` | 0.917 | [0.65, 0.98] | 12 | `cfg-5d548c010eeb` | `82684e0`+ | all 4 dev hold-out negatives pass; see the note on what that costs |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_direction` | 0.375 | [0.14, 0.69] | 8 | `cfg-9c6b643661a9` | `82684e0`+ | **paired delta +12pp, McNemar exact p=1.000, 3 cases flipped.** The "exactly flat, zero flips" result is gone, see below |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_groundedness` | 0.750 | [0.41, 0.93] | 8 | `cfg-9c6b643661a9` | `82684e0`+ | paired delta +75pp, **McNemar exact p=0.031**, 6 of 8 cases flipped to pass, 0 the other way |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_disagreement` | 0.667 | [0.21, 0.94] | 3 | `cfg-9c6b643661a9` | `82684e0`+ | paired delta +67pp, p=0.500, n=3 too small to read |
| 2026-09-04 | M1 | answer | `baseline/bm25_only_not_found` | 0.917 | [0.65, 0.98] | 12 | `cfg-9c6b643661a9` | `82684e0`+ | paired delta 0pp; the two baselines fail on *different* cases (1 each) |

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

### Independent-judge check on groundedness, 2026-09-05

Groundedness and disagreement are still graded by `openai/gpt-oss-120b`, **the same model that
generates the answers**. Re-graded the same answers with `qwen/qwen3.8-27b`, changing nothing else.

| Judge | oracle_spans | bm25_only |
|---|---|---|
| `openai/gpt-oss-120b` (self) | 8/8 | 7/10 |
| `qwen/qwen3.8-27b` (independent) | 8/8 | **8/10** |

**No evidence of self-preference inflation.** The independent judge scored `bm25_only` *higher*,
not lower, so the self-judge is if anything the stricter of the two, and the groundedness numbers
in this file do not appear to be flattered by self-grading.

**But marginal agreement is hiding per-case disagreement.** The two judges differ on *which* cases
fail: `qwen` fails `brca_prs_ovarian_risk_ord_001` outright (0 of 3 claims grounded) where the
self-judge passed it. Two judges landing on nearly the same rate while disagreeing about the cases
is precisely the pattern raw percent agreement flatters and kappa exposes. A claim-level kappa
between the two judges is the outstanding follow-up and has not been run, so read this as "the
worst reading is ruled out", not "the judges agree".

### Redesigned direction/strength properties, 2026-09-05: the failure moves to strength

All three baselines re-run under the controlled vocabulary (`eval/labels.py`), with `direction` and
`strength` **split into separate properties and graded deterministically in code, no judge**. The
judge now grades only groundedness and disagreement. Prompt version v2 in all three baselines, so
these are not comparable to the 09-04 rows above; **they supersede them.**

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-05 | M1 | answer | `baseline/no_retrieval_direction` | 0.625 | [0.31, 0.86] | 8 | `cfg-d71b7cfa6e81` | `5c7037f` | **below the 75% majority-class baseline** |
| 2026-09-05 | M1 | answer | `baseline/no_retrieval_strength` | 0.250 | [0.07, 0.59] | 8 | `cfg-d71b7cfa6e81` | `5c7037f` | new property, split out of direction |
| 2026-09-05 | M1 | answer | `baseline/no_retrieval_groundedness` | 0.0 | [0.00, 0.32] | 8 | `cfg-d71b7cfa6e81` | `5c7037f` | fails by construction |
| 2026-09-05 | M1 | answer | `baseline/no_retrieval_not_found` | 0.750 | [0.47, 0.91] | 12 | `cfg-d71b7cfa6e81` | `5c7037f` | |
| 2026-09-05 | M1 | answer | `baseline/bm25_only_direction` | 0.625 | [0.31, 0.86] | 8 | `cfg-2f081d65e1b6` | `5c7037f` | **also below the 75% majority-class baseline**; identical to no-retrieval |
| 2026-09-05 | M1 | answer | `baseline/bm25_only_strength` | 0.375 | [0.14, 0.69] | 8 | `cfg-2f081d65e1b6` | `5c7037f` | |
| 2026-09-05 | M1 | answer | `baseline/bm25_only_groundedness` | 0.700 | [0.40, 0.89] | 10 | `cfg-2f081d65e1b6` | `5c7037f` | |
| 2026-09-05 | M1 | answer | `baseline/bm25_only_disagreement` | 0.667 | [0.21, 0.94] | 3 | `cfg-2f081d65e1b6` | `5c7037f` | |
| 2026-09-05 | M1 | answer | `baseline/bm25_only_not_found` | 0.917 | [0.65, 0.99] | 12 | `cfg-2f081d65e1b6` | `5c7037f` | |
| 2026-09-05 | M1 | answer | `baseline/oracle_spans_direction` | **1.000** | [0.68, 1.00] | 8 | `cfg-a15e09ce1833` | `5c7037f` | paired vs bm25 **+38pp**, 3 discordant all one way, McNemar p=0.250 |
| 2026-09-05 | M1 | answer | `baseline/oracle_spans_strength` | 0.375 | [0.14, 0.69] | 8 | `cfg-a15e09ce1833` | `5c7037f` | **identical to BM25. Perfect retrieval does not move this one** |
| 2026-09-05 | M1 | answer | `baseline/oracle_spans_groundedness` | 1.000 | [0.68, 1.00] | 8 | `cfg-a15e09ce1833` | `5c7037f` | |
| 2026-09-05 | M1 | answer | `baseline/oracle_spans_disagreement` | 0.333 | [0.06, 0.79] | 3 | `cfg-a15e09ce1833` | `5c7037f` | lower than BM25's 0.667; n=3 |
| 2026-09-05 | M1 | answer | `baseline/oracle_spans_not_found` | 1.000 | [0.68, 1.00] | 8 | `cfg-a15e09ce1833` | `5c7037f` | |

**The 2026-09-04 finding does not survive, but the cross-run comparison is CONFOUNDED and the
first version of this paragraph over-attributed it.** Oracle spans scored 3/8 on direction under
the old setup and 8/8 under the new one. Two things changed at once: the scorer (free-text judge to
deterministic vocabulary match) **and the prompt** (v2 constrains the model to emit one of four
values, which is a materially easier task than free-text). The jump cannot be attributed to the
property redesign alone, and the original wording here claimed it could.

**The confound has since been resolved by experiment** (`DECISION_LOG.md`, "is the direction jump
the scorer or the prompt?"). Grading the **same v2 answers** with the old LLM judge gives **3/8**
for oracle spans, the same as it gave the v1 answers, while the new scorer gives 8/8. So under the
old grader the prompt version makes no difference, and under the new grader the same answers score
8/8: **the grader is the entire cause and the prompt contributed nothing measurable.**

**The mechanism, visible in the old judge's verdicts:** 3 pass, 5 partial, **zero fail**. It never
disagreed about direction once. It downgraded five answers on *strength*, because it graded the two
as one conflated verdict and `partial` collapses to not-pass. Eight correct directions were being
reported as three. That is precisely the defect the property redesign was built to remove, measured
directly.

**What is clean either way:** comparisons *within* the 2026-09-05 run, where all three baselines
share prompt v2 and the same scorer. Oracle 1.000 against BM25 0.625 is a like-for-like +38pp, 3
discordant pairs all one way, McNemar p=0.250.

**Read direction against the majority-class baseline, not against zero.** Six of the eight scored
cases are gold `increased`, so "always answer increased" scores **75%**. No-retrieval and BM25 both
score **62.5%, worse than that trivial baseline.** Only the oracle run beats it. `score.py` prints
this baseline under every direction line so the number cannot be quoted without it.

**SUPERSEDED 2026-09-05 by the human strength review.** This section originally read: "Strength
sits at 0.375 for BM25 and 0.375 for oracle spans: identical ... perfect retrieval moves strength
not at all. This is the reading failure the project has been chasing." A human review of the 11
strength labels found **5 of them wrong (45%)**, two of those in the dev split, and re-scoring
against the corrected labels gives:

| baseline | strength, my labels | strength, reviewed labels |
|---|---|---|
| no_retrieval | 0.250 | 0.250 |
| bm25_only | 0.375 | **0.250** |
| oracle_spans | 0.375 | **0.500** |

**Perfect retrieval does help strength**, 4/8 against BM25's 2/8, +25pp, McNemar p=0.625 at n=8.
Strength is the weakest property, not an untouched one. Direction is unchanged (62.5 / 62.5 /
100.0). Two corrected labels out of eight flipped the conclusion, which is what a 12.5-points-per-
case eval set does when its labels carry a 45% error rate. See `DECISION_LOG.md`, "human review of
the strength labels.

**What the strength failures are.** Also withdrawn: the original list here was computed against
the labels the review found 45% wrong, and two of the three examples it cited (`high` against gold
`disputed`) rested on `disputed` values that were themselves incorrect. Under the corrected labels
oracle spans scores 4 pass, 1 partial, 3 fail on strength. A characterisation of the remaining
three failures is **not** offered here: at n=8 with the labels only just corrected, the honest
position is that strength is the weakest property and the reason is not yet established.

**Caveats.** n=8 for direction and strength, n=3 for disagreement, so nothing here is significant;
the direction delta's p=0.250 is the best available and comes from 3 discordant pairs. Gold
`strength` values are my assignments from the source text and are reviewable, not authoritative.
And direction now carries a 75% floor, which is a property of an eval set that is 6/8 one class.

### Date stratification (A4), 2026-09-04: the per-stratum rule is not computable yet

This file's own metric-family note says `baseline/no_retrieval` must **always** be reported per
date-stratum, because the pooled number conflates retrieval lift with memorization. No row above
obeys it. Phase A4 built the stratification (`eval/strata.py`, `earliest_evidence_year` now stored
on every case) and ran it. The result is that the rule cannot be honoured on this eval set:

| Stratum (dev, non-negative, cutoff 2024) | n |
|---|---|
| pre_cutoff | 7 |
| **post_cutoff** | **1** |

A pass rate over one case is an anecdote, so no `_pre_cutoff` / `_post_cutoff` rows are being
added. The tooling refuses to print one below n=5, where the Wilson interval spans more than half
of [0,1].

**This is a statement about the eval set, not the corpus.** 1,569 corpus articles (about 20% of the
snapshot) are post-2024, so the material for a real post-cutoff stratum exists; the gap is labeling
effort. The memorization question `PROJECT_PLAN.md`'s statistical rule 4 exists to answer therefore
**remains unanswered**, and every no-retrieval number above should be read knowing that some of its
apparent competence may be memorization that this project has not yet been able to measure.

The cutoff year is an assumption, not a fact: `gpt-oss-120b`'s training cutoff is not published
anywhere citable here, so `strata.py` takes it as a parameter (default 2024) and prints the full
per-case year distribution. The 7/1 split is unchanged at a 2023 or 2025 cutoff. Details and the
rejected alternatives, including the tempting one of moving the cutoff until the strata balance,
are in `docs/DECISION_LOG.md`, "date stratification built."

### Oracle-span baseline (A3), 2026-09-04: perfect retrieval does not fix direction

Phase A3's substitute for the plan's whole-document-in-context baseline, which is blocked on the
free tier (a hard 8,000 TPM per-request ceiling against 3k-20k-token gold articles; probe returned
HTTP 413). This baseline supplies exactly the case's **gold spans** as context, so retrieval is
perfect by construction. Same model, prompt shape and citation mechanism as BM25-only, so the only
variable is which passages reached the model. Negative cases have no gold spans and are excluded,
so this scores the 8 non-negative dev cases. Method, prediction and the blocker measurement are in
`docs/DECISION_LOG.md`, "oracle-span baseline (A3)".

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-04 | M1/A3 | answer | `baseline/oracle_spans_groundedness` | 1.000 | [0.68, 1.00] | 8 | `cfg-be9db797fd63` | `5c7037f` | paired vs bm25_only +25pp, 2 discordant, p=0.500 |
| 2026-09-04 | M1/A3 | answer | `baseline/oracle_spans_not_found` | 1.000 | [0.68, 1.00] | 8 | `cfg-be9db797fd63` | `5c7037f` | extended check; BM25's one wrong refusal (a retrieval miss) disappears, as predicted |
| 2026-09-04 | M1/A3 | answer | `baseline/oracle_spans_direction` | 0.375 | [0.14, 0.69] | 8 | `cfg-be9db797fd63` | `5c7037f` | **identical to bm25_only's 0.375. +0pp, though 4 of 8 cases flipped verdict, p=1.000** |
| 2026-09-04 | M1/A3 | answer | `baseline/oracle_spans_disagreement` | 0.333 | [0.06, 0.79] | 3 | `cfg-be9db797fd63` | `5c7037f` | *lower* than bm25_only's 0.667; n=3, unreadable alone, but see the note below |

**What this settles, narrowed after the 2026-09-05 correction below.** The flat-direction result
has been the project's central puzzle since 2026-09-02, and it was always ambiguous: BM25 might
simply not have retrieved the right passage. This run removes *that* explanation by construction.
Handed the exact gold span, the system cites it correctly **100%** of the time and never wrongly
refuses, and still scores 3/8 on direction. So retrieval is not what limits the direction score.

That is the whole of what it settles. The original version of this section went further and
concluded "whatever is wrong with direction is downstream of retrieval, in reading." **That does
not follow**, because a third possibility was never excluded and turns out to dominate: the
direction property itself is badly specified, and much of the 3/8 is the scorer, not the system.
See the correction below.

**CORRECTION (2026-09-05): the failure taxonomy first published here was withdrawn.** The original
text claimed the five non-passing direction verdicts fell into two buckets, "strength
overstatement (3 of 8)" and "disagreement collapse (2 of 8)", and that neither was a retrieval
problem. That was derived from the judge's free-text rationales **without reading the system
answers underneath**. Reading them dissolves both buckets substantially. What follows replaces it.

**Most of the five "failures" are scoring artifacts, not reading failures.**

- `atm_variants_controversy_disagree_001`, graded `fail` for contradicting gold's "mixed_evidence":
  its `answer_text` reads "the evidence is **mixed and considered controversial**, with the overall
  role of ATM as a breast cancer gene described as uncertain." The model reported the disagreement.
  It just put it in `answer_text` and `strength` rather than the `direction` field.
- **The mechanism is in the scorer, and it is structural.** `score_direction` passes the judge only
  `gold.direction`, `gold.strength`, `answer.direction` and `answer.strength`. **It never passes
  `answer_text`.** The judge cannot see nuance stated in the answer, so a system that hedges
  correctly in prose is scored as if it had not.
- `brca2_pancreatic_risk_ord_001`: gold direction "increased risk", system "increased risk", an
  exact match, graded `partial` because gold strength reads "background association; approximately
  4-7%..." and the system said "moderate evidence (4-7% prevalence)". It cites the same figure.
- `atm_at_lymphoid_tumor_ord_001`: gold `strength` is "cohort of 296 genetically confirmed A-T
  patients ... 66 developed a malignant tumour", which is a **cohort description, not a strength**.
  The system said "substantial protective effect observed", the source's own phrase, and was marked
  down for not reciting cohort sizes.

**The root cause is that the gold label vocabulary is uncontrolled free text.** Eleven evidence
cases carry **nine distinct `direction` strings**: `'mixed'` and `'mixed_evidence'` are the same
concept written two ways, `'high_risk_vs_moderate'` is snake_case among prose, and several fold
strength into direction. `strength` mixes effect sizes, cohort descriptions and provenance with no
scale. This also explains the direction kappa of 0.216 recorded earlier, which had been attributed
to the judge: the label space itself is ill-defined, so the property is close to unmeasurable as
currently specified.

**What survives, and what does not.** The raw number stands: handed the exact gold span, the system
scores 100% on grounding and refusal and 3/8 on direction. What does **not** stand is the
explanation. The direction failures cannot currently be attributed to reading, because the property
that measures them is not well posed. Any claim about *why* direction fails is on hold until the
property is redesigned. See `docs/DECISION_LOG.md`, "direction property redesign."

**Caveat, stated because the number invites over-reading.** n=8, and four of the eight direction
verdicts flipped (two each way), so the identical 0.375 is churn rather than stability, and the
rate itself is noise. The pre-registered MDE said this run could not be a significance test and it
was not one. What it provides is the per-case *composition* of failures, which is the raw material
M4 needs and does not depend on the rate being precise.

**On the stub handler:** these are Step 0c's required first `RESULTS.md` row (`PROJECT_PLAN.md`
0c exit criterion), not a system-quality baseline. The handler is deliberately trivial (literal
keyword match, no retriever); see `docs/DECISION_LOG.md`, "Step 0c built as a stub handler, v1
formally dropped." What these numbers establish is that the measurement mechanism itself works:
real concurrent HTTP requests, real streaming, a real p95/TTFT/CI computation off the live server.
That mechanism, not these values, is what M1 onward reuses once a real retriever/generator exists
to measure.

> ### Git SHA note (2026-09-05): history rewritten, and two SHAs that never existed
>
> The `Co-Authored-By` trailers were stripped from five commit messages, which rewrote every
> commit in this repository. Content is unchanged (the tree hash is identical) but every SHA moved.
> The SHAs in the tables above have been remapped: `4bb2b5e` to `87ee3ac`, `ea364b7` to `82684e0`,
> `4ffbfd9` to `5c7037f`.
>
> **Two cited SHAs, `c062228` and `57d356d`, were never in this repository's history at all.** They
> appear on the 2026-09-02 and 2026-09-03 baseline rows and cannot be checked out. This predates
> the rewrite and is a real reproducibility gap in exactly the way rule 4 exists to prevent: those
> rows carry a SHA-shaped string that resolves to nothing. The runs happened, the numbers are real,
> and their exact code state is not recoverable. Left visible rather than quietly deleted; the rows
> they sit on are already marked superseded.

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

> ### Standing caveat on every phase C row below (added 2026-09-06, after human review)
>
> **A human read 20 of the 138 paragraphs and marked 11 of them wrong: 55%, 95% CI [34%, 74%].**
> That is the third time this project has measured roughly a 50% defect rate in unreviewed
> agent-written labels (phase A1: 4 of 8; the strength pass: 5 of 11). Two systematic causes, both
> traceable to a design decision logged on 2026-09-05:
>
> 1. **Tautological queries (6 of 11).** The rule that anchors appear verbatim in both queries is
>    sound only if anchors are *identifiers*. The generator often chose the *finding* instead, so
>    the question carried its own answer: "How many amplicons were designed to cover the 159 kb
>    target region, specifically 1663 amplicons?"
> 2. **The paragraph does not answer the query (5 of 11).** The query asked about the topic a
>    paragraph announces rather than anything it states. One paragraph says a systematic analysis
>    "has been lacking" and produced "What is the role of RiboSis in cancer according to recent
>    pan-cancer analyses?"
>
> **What this does and does not invalidate.** The recall figures are rates over a set that is
> roughly half defective, so **`retrieval/recall@10` = 0.801 is withdrawn as an estimate of
> anything** and the set must be rebuilt before a real one is quoted.
>
> **The lexical-bias result survives, and strengthens.** It was re-tested against a mechanical
> tautology proxy validated on the 20 human verdicts (precision 1.00, catching 6 of the 11):
>
> | subset | lexical | paraphrased | delta | McNemar p | pairs |
> |---|---|---|---|---|---|
> | all 138 paragraphs | 0.870 | 0.732 | +13.8pp | 0.000 | 138 |
> | clean (flagged removed) | 0.895 | 0.737 | **+15.8pp** | 0.000 | 95 |
> | flagged as tautological | 0.814 | 0.721 | +9.3pp | 0.219 | 43 |
> | human-marked `wrong` | 1.000 | 1.000 | +0.0pp | 1.000 | 11 |
>
> The defective queries are **trivially easy** (100% recall in both styles, zero gap, because a
> query containing its own answer is found by anyone) and were **diluting** the effect, not
> creating it. Removing them makes it larger. So the finding is not an artifact of the defect; it
> is measured despite it.
>
> Details in `DECISION_LOG.md`, "the retrieval set is 55% defective, and what the defects were."

### Phase C, the domain `retrieval` set: INTERIM, half the strata (2026-09-05)

**These are not the phase C exit number.** The build stopped at **138 of 330 paragraphs** when the
free tier's 200,000-tokens-per-day budget ran out: abstract 55/55, intro 55/55, methods 28/55,
and results / discussion / body_other not started. n=276 queries is also below the plan's n>=300.
Reported because the measurement is real and the code path is validated end to end, and because
the lexical-bias result is unlikely to move. Superseded the moment the set is finished.

**Two caveats attach to every row here.** (1) The **single-gold hole rate is not yet measured**
(no token budget left for `--measure-holes`), so every recall figure is a **lower bound** by an
unknown amount: another paragraph may answer a query as well as the gold one and scores as a miss.
(2) **No labels have been reviewed by a person yet.** `eval/retrieval_worksheet.md` is generated
and waiting; on this project's measured base rate, unreviewed agent-written labels run about 50%
defective.

| Date | Module | Eval set | Metric | Value | 95% CI | n | Config hash | Git SHA | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@10` | 0.801 | [0.754, 0.848] | 276 | `cfg-50865433fd64` | `b40d84e` | BM25 k1=1.5 b=0.75 over the rebuilt 344,900-paragraph index, top_k=100. Both query styles pooled |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@1` | 0.554 | [0.493, 0.612] | 276 | `cfg-50865433fd64` | `b40d84e` | |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@100` | 0.938 | [0.909, 0.964] | 276 | `cfg-50865433fd64` | `b40d84e` | 6% of gold paragraphs are not in the top 100 at all |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/ndcg@10` | 0.671 | [0.624, 0.717] | 276 | `cfg-50865433fd64` | `b40d84e` | |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/mrr` | 0.637 | [0.589, 0.685] | 276 | `cfg-50865433fd64` | `b40d84e` | |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@10` (lexical style) | 0.870 | [0.812, 0.920] | 138 | `cfg-50865433fd64` | `b40d84e` | **paired vs paraphrased below: delta +13.8pp, discordant 21/2, McNemar exact p=0.000** |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@10` (paraphrased style) | 0.732 | [0.652, 0.804] | 138 | `cfg-50865433fd64` | `b40d84e` | same 138 paragraphs, same gold spans; only the query wording differs |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@10` (abstract) | 0.818 | [0.736, 0.879] | 110 | `cfg-50865433fd64` | `b40d84e` | per-section stratum |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@10` (intro) | 0.773 | [0.686, 0.841] | 110 | `cfg-50865433fd64` | `b40d84e` | per-section stratum |
| 2026-09-05 | M1/C | retrieval (domain, INTERIM) | `retrieval/recall@10` (methods) | 0.821 | [0.702, 0.900] | 56 | `cfg-50865433fd64` | `b40d84e` | per-section stratum, only 28 of 55 paragraphs built |

**Git SHA `b40d84e`:** these rows were measured from an uncommitted working tree and carried
`pending` until it was committed, rather than being stamped with `8c710c3`, which was HEAD at the
time and named code that did not run. `b40d84e` is the commit containing every module that produced
them. Recorded this way because a SHA resolving to the wrong code is the exact defect
`common/run_meta.py`'s `config_hash` docstring was written about.

**The lexical-bias row is the finding here**, and it is the one least likely to move when the set
is finished. Both styles ask about the same fact, anchored on the same verbatim identifiers,
against the same gold span; only the surrounding prose differs. BM25 loses **13.8 points of
recall@10** to that alone. Note where the loss lands: recall@100 barely moves (0.971 to 0.906)
while recall@1 falls from 0.652 to 0.457, so wording is not deciding whether the right paragraph
is reachable, it is deciding where in the ranking it sits. The practical consequence is that a
retrieval set built only from wording-reusing queries, which is what generating queries from
paragraphs naturally produces, would have credited BM25 with about 14 points it does not have
against any semantic retriever it is later compared to.

**Verification pass, 2026-09-06.** Everything above was re-checked before any more budget was
spent on it. What was confirmed:

- **Reproducible.** The scoring run was repeated end to end: **zero differences** in any metric,
  and the same computed config hash `cfg-50865433fd64`. The bootstrap CIs are seeded, so this is a
  real check that the pipeline is deterministic, not a coincidence.
- **The harness is unchanged by the phase C work.** SciFact re-run through the same BM25 and the
  same metrics reproduces the logged run **identically to four decimals** on all five metrics
  (nDCG@10 0.5979, recall@100 0.8246, 90% and 91% of the published Pyserini reference). The
  `common/corpus_text.py` refactor changed no behaviour.
- **The set is mechanically clean.** `python -m eval.verify_retrieval_set`: all 138 gold spans
  resolve to text matching a stored content hash, every anchor is still present in the paragraph
  and in both queries, every stored `lexical_overlap` recomputes to its stored value, all 138 pairs
  are complete, no duplicate query ids or query texts, **no row cites a held-out article**, and no
  article contributes more than 2 paragraphs (so the queries are not correlated in a way that would
  narrow these intervals).
- **The +13.8pp lexical result survives its confound check, and the check points the other way.**
  Paraphrased queries are slightly **longer** than lexical ones (18.1 against 17.4 tokens, longer
  on 72 of 138 pairs), which if anything favours them, since more query terms means more chances to
  match. The gap is +13.8pp anyway, so it is conservative.
- **An unplanned asset: 25 of 138 paragraphs are post-2024.** The answer set could never populate
  this stratum (1 of 8 cases), which is why `PROJECT_PLAN.md`'s statistical rule 4 has gone
  unanswerable. It does not matter for BM25, which cannot memorise anything, but it means the
  memorisation question becomes askable here the moment a dense or LLM-based retriever lands in
  Tier 2.

**recall@10 against lexical overlap** (`score_retrieval.py` now prints this on every run). This is
the table that makes the paired style result interpretable: recall tracks how much of the query
survives into the gold paragraph, and inside a fixed band the style label adds almost nothing
(1 to 6pp, against 13.8pp unconditioned). The transferable claim is about **overlap**; style is
just a controlled way of moving it.

| overlap band | recall@10 | 95% CI | n | lexical | paraphrased |
|---|---|---|---|---|---|
| [0.00, 0.50) | 0.429 | [0.265, 0.609] | 28 | n=1 | 0.444 (n=27) |
| [0.50, 0.65) | 0.767 | [0.669, 0.842] | 90 | 0.833 (n=18) | 0.750 (n=72) |
| [0.65, 0.80) | 0.873 | [0.794, 0.924] | 102 | 0.853 (n=68) | 0.912 (n=34) |
| [0.80, 0.90) | 0.913 | [0.797, 0.966] | 46 | 0.927 (n=41) | 0.800 (n=5) |
| [0.90, 1.01) | 0.900 | [0.596, 0.982] | 10 | 0.900 (n=10) | n=0 |

The paired gap is present in **every** stratum and at **every** cutoff, largest where wording should
matter most: methods +21.4pp (p=0.031), intro +16.4pp (p=0.012), abstract +7.3pp (p=0.219); and
+19.6pp at k=1 falling monotonically to +6.5pp at k=100. Method in `DECISION_LOG.md`, "is the
lexical style gap actually the style, or is it the overlap underneath it?"

**Median rank of the gold paragraph, when it is found at all, is 1**, and 17 of 276 queries never
surface it inside the top 100.

**Lexical overlap, against human-written queries** (`build_retrieval_set --calibrate-overlap`,
share of a query's distinct tokens present in its gold document):

| Query set | mean | median | n |
|---|---|---|---|
| ours, lexical style | 0.763 | 0.778 | 138 |
| ours, paraphrased style | 0.588 | 0.588 | 138 |
| SciFact, human-written | 0.529 | 0.533 | 300 |
| NFCorpus, human-written | 0.261 | 0.167 | 323 |

De-lexicalization moves this set to roughly SciFact's genre and does not reach NFCorpus's. That is
the honest position of the set on the bias axis, and it belongs on any row read out of it.


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
