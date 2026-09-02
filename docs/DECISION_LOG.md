# Decision Log

Two entry types, don't mix them. A **design decision** is architecture/scope/tool choice, decided
by reasoning, logged before building. An **experiment** is an empirical question, logged as a
prediction *before* running it, with the outcome (including "I was wrong") logged after.

Delete this instructions block and the two example entries once you've made your first real ones.
They're here to show the shape, not to stay as clutter.

---

## Design decision: [short title]

- **Date / module:**
- **Decision:** what was decided.
- **Alternatives considered:** what else was on the table, and why each lost.
- **Reasoning:** why this one won.
- **Reversibility:** how expensive would it be to change this later. Cheap config flip, or a
  rebuild?

*Example:*

## Design decision: Vector DB, self-hosted Qdrant over managed Pinecone

- **Date / module:** Step 0 / M3
- **Decision:** self-host Qdrant.
- **Alternatives considered:** Pinecone serverless (managed, no ops, was the v2 default).
- **Reasoning:** three things at once. (1) Pinecone does not expose HNSW parameters (its
  `HnswConfig` class is unused and slated for removal), so the recall-vs-latency tradeoff that is
  the entire point of the ANN module is *unobservable* on it. A managed index hides exactly the
  thing this project exists to learn. (2) Qdrant exposes `hnsw_config` (`m`, `ef_construct`) and
  search-time `hnsw_ef`, so that curve becomes plottable. (3) A stateful service with a persistent
  volume gives the Kubernetes module real content instead of a contrived stateless deployment,
  and it costs $0, which matters against a $75-100/month ceiling.
  The interview trade favors it too: "why Pinecone" has one answer; "why did you self-host, and
  what did it cost you" has an answer with numbers in it.
- **Reversibility:** moderate. The retriever is a thin wrapper, so the adapter swap is cheap, but
  re-indexing the corpus is a real (if inexpensive) operation. Decide before the corpus grows.

---

## Design decision: Model & embedding stack, free tier for iteration, small reserved paid budget for calibration

- **Date / module:** Step 0, pre-implementation cost planning (2026-08-28)
- **Decision:** Embed with a local open-source model (e.g. `bge-small-en-v1.5` via
  `sentence-transformers`, CPU) rather than a paid embedding API. Use Gemini 2.5 Flash-Lite's free
  tier and/or Groq's free tier (Llama 3.3 70B or similar 70B-class open model) as the default
  generation/judge model for iteration and ablations. Reserve a small paid budget (about $10-20
  total across the whole project, well under the existing $75-100/month ceiling) on a single
  pinned mid-tier paid model (Claude Haiku 4.5) for two specific things only: the held-out final
  answer-set evaluation, and judge-vs-human kappa calibration.
- **Alternatives considered:**
  (a) *Fully local/open generation model* (e.g. an 8B model via Ollama, zero cost, zero rate
  limit): rejected for Tier 1. CPU-inference latency risks blowing the p95 <= 6s / TTFT <= 1.5s
  targets, and a genuinely weak model's shaky instruction-following would confound tool-calling
  and groundedness findings with model capability rather than system design. Exactly the kind of
  noise the project's own statistical rules (M1, `RESULTS.md`) exist to catch.
  (b) *Fully paid stack throughout* (Haiku/Sonnet for every call): rejected as unnecessary, not
  as unaffordable. Back-of-envelope math on realistic call volume (n approximately 50-80 answer
  set, run about 15-20 times across chunking/hybrid/reranking/context/agent ablations, generation
  plus judge calls each) puts total spend at roughly $10-30 for the *entire* multi-month project
  even at full paid pricing. The free tiers get the same coverage at $0 given the eval-set sizes
  already in the plan (the n>=300 retrieval set needs no generation at all).
  (c) *OpenAI's cheapest current model*: deferred; could not confirm current pricing/model name
  from a primary source at the time of this decision, only a third-party aggregator.
- **Reasoning:** Infra is already $0 (self-hosted Qdrant, local k3d, local Spark, free PMC OA S3
  pull); the only real cost lever left is generation and judge calls, and the actual volume this
  plan generates is small enough that "free" and "cheap" both land near-zero. Two real risks came
  out of checking this, both worth planning around rather than discovering later: (1) a capability
  confound, mitigated by choosing a 70B-class / Flash-Lite model rather than the smallest free
  option available, so failures read as system-design failures rather than model-weakness noise;
  (2) free-tier terms and rate limits can change or vanish without notice. This is not just a
  risk, it's a live instance of the exact lesson M13 (model/provider version drift) already wants
  taught, so treat a future free-tier disruption as material rather than a setback. Google's
  free-tier terms permit training on free-tier prompts; judged immaterial here since PMC OA
  content is already public, but noted for the M9 telemetry-hygiene discussion.
- **Reversibility:** Cheap. The generation/judge model is a config value under config-as-code, so
  swapping free tier for paid model is a config edit plus a harness rerun, which is itself the
  natural M13 regression-suite exercise, not extra work bolted on.

---

## Design decision: Task contract, candidate A (variant-disease evidence), scoped to cancer genomics

- **Date / module:** Step 0a (2026-08-28)
- **Decision:** Adopt candidate A from `TASK_CONTRACT.md`, *"given a gene or variant, what does
  the recent literature say about its role in condition X, with citations to supporting spans,"*
  as the finalized task contract, scoped to cancer genomics (germline and somatic variants; DNA
  damage response / PARP pathway as an initial query net). Full contract text and cost note live
  in `TASK_CONTRACT.md` Part 4.
- **Alternatives considered:**
  *Contract shape*: B (CRISPR guide/off-target evidence): strong personal-signal match but a
  narrower literature and a milder refusal surface. C (methods provenance extraction): near-zero
  labeling cost and clean ground truth, but almost no disagreement or refusal surface, so it
  starves M7/M9, kept as a cheap second eval stratum rather than the primary contract. D
  (drug-target mechanism): rejected outright, synthesized-across-papers answers have no gold
  span, so groundedness and recall@k are both unscoreable.
  *Subfield*: pharmacogenomics (tightest match to the toxicity/dosing guardrail test, but a
  narrower literature); cardiometabolic genetics (active, decent identifier density, weaker
  disagreement track record); CRISPR/gene-editing variant effects (drags in tables, useful for
  chunking, but scored weaker on refusal surface).
- **Reasoning:** Candidate A scored best or tied-best on 7 of 8 feasibility tests in
  `TASK_CONTRACT.md` Part 1-2, and its clinical-advice refusal boundary is the richest guardrail
  story of the four: real false-positive risk on toxicity/dosage questions, which is exactly the
  false-positive lesson M9 needs. Cancer genomics wins the subfield choice on breadth (largest PMC
  OA coverage of the options considered, so the 3,000-5,000-article Tier 1 target is comfortably
  reachable) and on disagreement (replication failures and VUS reclassification are a documented,
  recurring pattern in this literature, test 5, real not hypothetical). Pharmacogenomics remains
  the stronger pick if the guardrail story ever needs sharpening further, worth remembering as a
  fallback rather than discarding.
- **Reversibility:** Expensive once labeling starts. Gold spans, baselines, and every Phase A
  number are corpus-specific (this is why the corpus decision was moved to Step 0, ahead of any
  labeling, per `PROJECT_PLAN.md`). Cheap to revise right now, before Step 0b's pull.

---

## Experiment: [short title]

- **Date / module:**
- **Prediction (write this BEFORE running anything):** the expected direction and magnitude.
- **Minimum detectable effect:** given the eval set size and a paired test, what's the smallest
  difference this run can actually distinguish from noise? **If the MDE is larger than the
  predicted effect, the run is inconclusive by construction. Know that before spending the
  money, not after.** This field is what stops the log from filling with results read out of
  noise.
- **Method:** what was run, against which eval set (`retrieval` n>=300, or `answer` n approximately
  50-80), at which config hash and git SHA. Paired against which comparison config?
- **Result:** the number(s), **with a confidence interval and the paired-test outcome**, not two
  bare point estimates.
- **Did the prediction hold?** yes / no / partially / **inconclusive**, and why, in a sentence or
  two. A "no" is a good outcome, not a failed module. An "inconclusive" is an honest one; write it
  down rather than rounding it to whichever direction the point estimate happened to fall.
- **What changed because of this:** a later module's plan, a config default, or nothing? Say so
  explicitly rather than letting the result quietly vanish.

*Example:*

## Experiment: Does section-aware chunking beat fixed-size on this corpus?

- **Date / module:** M6 (Chunking as an ablation)
- **Prediction:** section-aware chunking beats fixed-size by more than 5 points on recall@10.
- **Minimum detectable effect:** about 2.5pp, using a paired bootstrap over the 320-item retrieval
  eval set. The predicted 5pp effect is comfortably above that, so the run is adequately powered.
  (Had this been run on the 72-case answer set instead, MDE would have been about 12pp and the
  whole experiment would have been pointless. Noted here because that was the mistake the v2 plan
  built in.)
- **Method:** both chunkers run through the M1/M2 harness against the same 320 retrieval cases,
  labels attached to source spans so they survive the chunker change. Configs `cfg-c1` /
  `cfg-c2`, git SHA `def5678`.
- **Result:** fixed-size recall@10 = 0.712 [0.66, 0.76]; section-aware = 0.741 [0.69, 0.79].
  Paired bootstrap on the same items: delta = **+2.9pp, 95% CI [+0.4, +5.3], p = 0.03**.
- **Did the prediction hold?** Partially. Direction right, magnitude overstated. The effect is
  real but roughly half what I predicted, and the CI's lower bound is close enough to zero that
  I'd want a larger set before calling it decisive.
- **What changed because of this:** kept section-aware as the default, but downgraded confidence
  in intuition-sized magnitude guesses generally. Also noted that the *unpaired* comparison of
  these same two numbers would have had overlapping intervals and looked like nothing. The
  pairing is what made a 3-point effect visible at all. Worth remembering for every later
  ablation.

## Design decision: Corpus snapshot, Step 0b first pull (SUPERSEDED, kept for the trail)

- **Date / module:** Step 0b (2026-08-29)
- **Status:** Superseded by the re-pull decision below. This snapshot was discarded, not labeled.
- **What was run:** `pull_corpus.py --email jeff.zw07@gmail.com --target-n 4000`, default query
  (`(BRCA1 OR BRCA2 OR TP53 OR PALB2 OR ATM OR CHEK2 OR "DNA damage response" OR "PARP inhibitor"
  OR "homologous recombination deficiency") AND (variant OR mutation OR polymorphism OR "pathogenic
  variant") AND (cancer OR tumor OR tumour OR carcinoma OR neoplasm) AND "open access"[filter]`),
  script sha256 prefix `117214092a36`. esearch reported 228,015 matches; the script overfetched
  4,600 PMCIDs, downloaded 4,597 ok, skipped 3, errored 0. Snapshot window
  2026-08-29T21:46:21Z to 2026-08-29T21:50:07Z. 869 MB of JATS XML on disk.
- **Why it was discarded, two independent problems found on review:**
  1. **Recency skew.** The esearch call set no `sort`, so PMC returned its default order (most
     recently added first). The pull is the newest 4,600 of 228,015 matches: 4,512 of 4,597 kept
     articles (98%) are dated 2026, 49 are 2025, the rest older. A one-month slice, not "recent
     literature." The disagreement surface the task contract leans on (replication failures, VUS
     reclassification, `TASK_CONTRACT.md` test 5) plays out across years and is mostly absent from
     a single-year corpus.
  2. **Query precision.** Terms match anywhere in full text including reference lists, with no
     field restriction, so a 90-reference paper on almost any subject can match. Title-keyword
     check on the 4,597: only 48% mention cancer/tumor/oncology, only 5% mention any
     variant/mutation concept, and 48% carry none of the target concept families in the title. A
     random sample turned up food-science, plant-biology, and synthetic-chemistry papers.
- **Reusable output:** `corpus/manifest.csv` and `corpus/run_info.json` from this run are the
  record that this snapshot existed. The XML was not committed (see `.gitignore`).

---

## Design decision: Corpus re-pull, MeSH/TIAB-anchored query with uniform random sampling

- **Date / module:** Step 0b (2026-08-29), logged before building
- **Decision:** Re-pull the Tier 1 corpus with three changes to `pull_corpus.py`:
  1. **Tighten the query.** Gene and pathway terms restricted to `[Title/Abstract]`; cancer as a
     MeSH anchor (`"Neoplasms"[MeSH]`); the variant concept as
     `"Mutation"[MeSH] OR "Genetic Variation"[MeSH] OR variant[Title/Abstract]`; plus
     `AND medline[sb]` (MEDLINE-indexed subset, a venue-quality floor) `AND "open access"[filter]`.
  2. **Sample uniformly at random** from the full matched ID set (cap the ID fetch at ~50k),
     with a `--seed` flag whose value is written to `run_info.json`. Not PMC's default
     "most recently added" order and not its relevance ranking. Uniform random gives no date
     bias, no dependence on an opaque ranker, and a one-sentence description that holds up
     under scrutiny.
  3. **Add a `sha256` column to `manifest.csv`**, one hash per downloaded XML file, so the
     snapshot is byte-verifiable against any future re-fetch without the blobs living in git.
- **Target size:** 8,000 to 12,000 articles. Still minutes to pull and a few GB on disk. A larger
  pool gives labeling room and raises near-duplicate / superseded-finding density, but only
  because it is paired with random sampling; a bigger `target-n` under the old default sort would
  just widen the date window from one month to a few.
- **Alternatives considered:**
  - *Keep the 2026-only pull, rescope the contract to "2026 literature."* Rejected. Cheapest
    option, but even setting recency aside the set is roughly half off-topic, and the contract's
    disagreement surface needs multi-year coverage.
  - *Relevance sort instead of random.* Workable, but embeds PMC's undocumented ranking and
    over-weights whatever it judges most on-topic, which cuts the near-duplicate and contradiction
    density that makes retrieval and context engineering hard on purpose.
  - *Date-stratified quota (N per year).* Rejected: imposes a date distribution rather than
    letting the corpus reflect the matched literature's real age spread.
  - *Citation / RCR quality filtering in this pull.* Deferred, see the next entry.
- **Reasoning:** Two defects compounded in the first pull, one of sampling and one of precision.
  A MeSH/TIAB-anchored query fixes precision at the source. Uniform random sampling fixes the
  temporal skew without introducing a new bias. MEDLINE-subset is a cheap venue-quality gate that
  does not touch topical balance. Doing this now, before any gold labels attach to
  `(pmcid, section_id, char_start, char_end)`, is far cheaper than discovering it after.
- **Reversibility:** Cheap right now (no labels exist). Expensive the moment labeling starts.
  This is why `PROJECT_PLAN.md` puts the corpus decision ahead of the eval set.

---

## Design decision: Defer citation-quality weighting of the corpus

- **Date / module:** Step 0b (2026-08-29), logged before building
- **Decision:** Do not filter or rank the corpus by citation count or Relative Citation Ratio
  (RCR) in the Step 0b re-pull. Ship the MeSH/TIAB-anchored, uniformly random, MEDLINE-subset
  corpus as-is. Revisit citation weighting only if error analysis (M4) shows retrieval or answer
  quality is being dragged down by low-quality or fringe sources that the MEDLINE gate did not
  catch.
- **Alternatives considered:**
  - *Add an NIH iCite (`icite.od.nih.gov/api`) lookup pass to the re-pull*: map each sampled
    PMCID to its PMID, fetch `citation_count`, `relative_citation_ratio`, `nih_percentile`, and
    either annotate the manifest or drop the bottom decile. Rejected for this pull on two grounds.
    (1) It adds a pipeline stage and a PMCID->PMID mapping step to a module that is meant to be
    thin. (2) RCR needs roughly two years post-publication to stabilize and raw counts need even
    longer, so any citation filter pulls the corpus age distribution toward 2020-2023 and works
    directly against the task contract's word "recent." That trade should be made deliberately
    with evidence, not baked in pre-emptively.
  - *Journal whitelist instead of MEDLINE subset*: stronger venue gate, but hand-maintained and
    easy to bias toward journals I already know. MEDLINE subset is the cheap 80%.
- **Reasoning:** The MEDLINE-indexed subset already removes predatory and marginal venues, which
  is the quality floor that matters most. Citation-based ranking is a real lever but it is not
  free of cost (recency trade, extra pipeline, unstable signal for new papers), and the project's
  own rules say to add machinery when a measured number demands it, not on speculation. If M4
  error analysis surfaces a source-quality problem, the iCite pass is a well-scoped addition at
  that point.
- **Plan if revisited:**
  1. Batch the corpus PMIDs through `POST icite.od.nih.gov/api/pubs` (up to ~1000 IDs per call).
  2. Add `citation_count`, `rcr`, `nih_percentile`, `icite_year` columns to `manifest.csv`.
     Annotate first, do not filter, so the citation profile of the existing corpus is visible.
  3. Only then decide on a filter (e.g. drop bottom-decile RCR among articles at least two years
     old, leave newer articles untouched) and log it as its own experiment with a prediction.
- **Reversibility:** Cheap. Annotation is additive. A filter would drop articles, which for an
  unlabeled corpus is a re-pull, not a rebuild.

---

## Design decision: Corpus snapshot v2, the Step 0b corpus of record

- **Date / module:** Step 0b (2026-08-30). This is the corpus every later gold label attaches to.
  Supersedes the 2026-08-29 first pull (SUPERSEDED entry above). Implements the "Corpus re-pull"
  decision above.
- **Decision:** Ship 7,863 PMC OA full-text JATS articles as the Tier 1 corpus.
- **Query (exact):**
  `(BRCA1[Title/Abstract] OR BRCA2[Title/Abstract] OR TP53[Title/Abstract] OR PALB2[Title/Abstract]
  OR ATM[Title/Abstract] OR CHEK2[Title/Abstract] OR "DNA damage response"[Title/Abstract] OR
  "PARP inhibitor"[Title/Abstract] OR "homologous recombination deficiency"[Title/Abstract]) AND
  ("Mutation"[MeSH] OR "Genetic Variation"[MeSH] OR variant[Title/Abstract]) AND "Neoplasms"[MeSH]
  AND medline[sb] AND "open access"[filter]`
- **Method:** esearch returned 7,889 total matches. That is below the sample pool size
  (`target_n 10000` x 1.15 overfetch = 11,500), so the whole matched set was taken;
  `seed 0` only shuffled fetch order, it did not subsample. Of 7,889 attempted: 7,863 downloaded
  ok, 26 skipped (21 marked non-OA in bucket metadata, 5 absent from the OA bucket), 0 errors.
  Snapshot window 2026-08-30T04:02:06Z to 2026-08-30T04:06:36Z. Script sha256 prefix
  `fecef88fe335`. Recorded in `corpus/run_info.json`; per-file sha256 in `corpus/manifest.csv`.
- **Validation against the real APIs (first time for this query):** `[Title/Abstract]`,
  `"Neoplasms"[MeSH]`, `"Mutation"[MeSH]`, `"Genetic Variation"[MeSH]`, and `medline[sb]` all
  behave as expected for the `pmc` database. The bucket metadata field-name fallback
  (`is_pmc_openaccess` vs `is_open_access`) was not needed; `is_pmc_openaccess` is present.
- **Composition:**
  - Publication years spread 2015-2026, no single year above 13% (2025 n=979, 2026 n=585,
    2020-2024 each 600-735, tail back to 2015). The first pull's 98%-single-year skew is gone.
  - Title-keyword precision proxy on the 7,863: 65% of titles mention a cancer/oncology term
    (first pull 48%), 27% mention a variant/mutation concept (first pull 5%), 19% carry none of
    the target concept families in the title (first pull 48%). The MeSH/TIAB anchoring worked.
  - Licenses: CC BY 5,230; CC BY-NC-ND 1,158; CC BY-NC 849; CC BY-NC-SA 129; CC BY-ND 7; CC0 28;
    TDM 164; blank 298. All permit research and text-mining use. The 298 blank-license rows are a
    known gap, revisit only if a downstream step needs a hard license guarantee per article.
  - Body-text health: in a 300-article random sample, 0 unparseable, ~1.7% with little or no
    `<body>` text (conference-abstract stubs). Prune these at ingestion time, do not treat them
    as full articles.
- **Size vs plan:** 7,863 is above `START_HERE.md`'s stated 3,000-5,000 target. Kept deliberately:
  it is still small (962 MB), a larger unlabeled pool gives the eval-set sampling headroom and
  raises near-duplicate density, and labeling draws a subset regardless. If it proves unwieldy,
  subsampling down is a seeded `random.sample` over the manifest, not a re-pull.
- **On-disk cleanup:** the re-pull was run into the same `corpus/` directory as the first pull,
  so 4,441 XML files from the discarded first pull were left as orphans (dir had 12,304 files, the
  manifest 7,863). Those 4,441 were deleted; `corpus/xml/` now matches the manifest exactly and
  sha256 spot-checks pass. 161 of the 7,863 were carried over from the first pull via the
  resume-from-disk path, so their bytes were fetched 2026-08-29 (a day before the snapshot
  window) though `retrieved_at_utc` reads the re-pull time. sha256 is correct for all of them; a
  fully single-pass snapshot would need `rm -rf corpus/xml` and a re-run, judged not worth it.
- **Reversibility:** Expensive once labeling starts. Re-running with the same query and seed at a
  later date will not reproduce this set: PMC keeps indexing, which changes both the match count
  and the shuffle. `corpus/manifest.csv` (with per-file sha256) plus `corpus/run_info.json` are
  the reproducibility record; keep them committed even if the XML is regenerated or moved.

---

## Design decision: Step 0c built as a stub handler, v1 formally dropped

- **Date / module:** Step 0c (2026-08-31), logged before building.
- **Decision:** `PROJECT_PLAN.md` 0c says to stand up a FastAPI service "around whatever exists,"
  which per the plan's own sequencing means v1 (the pre-built LangChain/LangGraph/Pinecone system
  Step 0d says to install and run). v1 is not in this repo; `CRITIQUE.md` and `PROJECT_PLAN.md`
  describe it, but no code for it was ever checked in here. Rather than build a real
  retriever/generator from scratch to give 0c something to wrap, build the FastAPI service around
  a deliberately trivial handler: literal keyword match over the corpus manifest and body text, no
  chunker, no embedder, no vector DB, no LLM. It exists to prove the server-level measurement
  surface, not to answer questions well.
- **Alternatives considered:**
  - *Locate and bring in v1*: not available; no copy of it exists outside the planning docs'
    description.
  - *Build a real retriever now (BM25 or vector) to make 0c meaningful*: rejected. This is
    exactly the sequencing error the project's own standing rule exists to prevent: "do not skip
    to writing pipeline code (chunker, retriever, agent) before the eval harness and
    instrumentation spine exist" (M1/M2). A retriever built now, before there is an eval set to
    score it against, is unscored work that would need to be redone or retrofitted later anyway.
  - *Skip 0c, go straight to M1*: rejected. `PROJECT_PLAN.md`'s Step 0 exit criteria explicitly
    wants a FastAPI endpoint and one `RESULTS.md` row before Tier 1 starts, and the reasoning
    (p95/streaming/concurrency are server properties, not notebook properties) doesn't depend on
    the handler being a real RAG pipeline.
- **Reasoning:** The actual point of 0c is establishing that latency, TTFT, and concurrency get
  measured off a real HTTP path, not a notebook loop, before any number is trusted. That property
  holds regardless of what the handler does. A trivial keyword-match handler over real corpus
  files still does real, variable-cost disk I/O per request, so it exercises genuine streaming,
  timeout, and concurrency behavior, without pretending to be a retrieval-quality result. The
  first `RESULTS.md` row from this handler will be labeled as stub-handler numbers, not a system
  baseline, so it can't be mistaken for a real latency claim later.
- **Reversibility:** Cheap. The handler (`service/search.py`) is deliberately isolated behind one
  function boundary; the FastAPI app, request logging, streaming, and timeout/backpressure
  scaffolding are what M1/M2 keep, and the handler gets replaced wholesale once a real
  retriever/generator exists to score against the eval harness.

---

## Design decision: Drop Step 0d, close out Step 0

- **Date / module:** Step 0 (2026-08-31), logged before moving on.
- **Decision:** Drop Step 0d ("install v1, key it up, run it end to end") as written. Step 0 is
  closed out with 0a-0c done and no 0d. This is not a decision to skip retrieval or generation:
  they get built under Tier 1 (M3 retrieval, M7 context, M8 agents), scored against the eval
  harness from the start, same as everything else in this project. What's dropped is specifically
  *resurrecting the old v1 code*, because there is no old v1 code to resurrect.
- **Alternatives considered:**
  - *Locate v1 elsewhere and bring it in*: the only way 0d as originally written could still
    happen. Not pursued: no copy of it exists outside the planning docs' description of it, and
    even if found, it would need real work to reconcile with decisions already made without it
    (Qdrant over Pinecone in particular, logged separately in this file, plus the corpus and query
    net decided in Step 0b). Resurrecting it would mean partially rebuilding it anyway.
  - *Build a minimal v1-equivalent now, just to have "run something end to end"*: rejected, same
    reasoning as the Step 0c decision above. A retriever/generator built before the eval harness
    exists is unscored work, and the project's standing rule is explicit that this ordering is a
    mistake, not a shortcut.
- **Reasoning:** 0d's actual purpose in the plan was cheap signal early: what breaks, what a query
  costs, roughly how a small eval set scores, before investing in a from-scratch build. That
  purpose no longer applies once v1 turns out not to exist; there is nothing to install and get
  cheap signal from. Step 0c's stub handler already delivered the *other* thing 0d would have
  given, a real measurement surface with a first `RESULTS.md` row. What remains, a real
  retriever/generator, is Tier 1's job by design, not Step 0's.
- **Reversibility:** Free. Nothing was built under this decision; it only removes a checklist item
  that could not be completed as written. If v1 code ever surfaces, evaluate it then, against the
  eval harness that exists at that point.

---

## Design decision: Answer-set scoring rubric

- **Date / module:** M1 (2026-08-31 to 2026-09-01), discussed over several turns, confirmed
  2026-09-01, logged before building the scorer or labeling any cases.
- **Decision:** The `answer` eval set (n approximately 50-80) scores each case on four
  sub-questions, one per `TASK_CONTRACT.md` correctness property, each graded **pass/partial/fail**
  rather than binary:
  1. **Direction/strength.** Pass: direction and strength both match gold. Partial: right
     direction, strength off by one tier (e.g. "pathogenic" vs. gold "likely pathogenic"). Fail:
     wrong direction.
  2. **Citation/groundedness.** Scored as a continuous per-case hit rate (claims grounded / claims
     total) by an LLM judge, then bucketed: >=90% pass (the contract's own groundedness target),
     70-90% partial, <70% fail.
  3. **Surfaces disagreement.** Needs deliberately-curated cases: two real corpus sources that
     genuinely conflict, found via `eval/find_coverage.py`, vetted by a human or agent read, not
     by keyword match alone.
  4. **Says "not found in this corpus."** Needs constructed negative cases: a real gene/condition
     where every covering article has been identified (via `find_coverage.py`, recall-oriented)
     and deliberately held out of the corpus. Doubles as a test of retrieval (nothing should be
     retrievable) and of generation restraint (the model should refuse rather than answer from
     pretraining).
  A second, lighter stratum (methods-provenance extraction, candidate C from `TASK_CONTRACT.md`)
  gets a 2-sub-score rubric instead of four: parameter accuracy and citation. Near-objective
  ground truth, so the richer rubric is overkill. Allocated the minority of the labeling budget
  (~15-20 of the ~50-80 cases), most stays on the harder evidence cases. Within the evidence
  stratum, 5-8 cases are negative cases (property 4), each built from a *narrow* variant-condition
  pair (a specific HGVS notation, not a whole gene) so the covering-article list is small enough
  to verify completely by hand; a gene-level pair like BRCA1 + breast cancer returned 3,391
  candidate articles in a real corpus sweep, unverifiable and useless for this purpose.
- **Alternatives considered:**
  - *Binary pass/fail per property*: simpler to label, but collapses "wrong direction" and
    "completely unrelated answer" into the same bucket, and the plan's own M1 section warns that
    coarse labels get their apparent agreement inflated by class imbalance; a finer scale costs
    little extra since you're already reading the case.
  - *One holistic pass/fail per case* instead of four sub-scores: rejected earlier in this same
    discussion, loses the ability to distinguish which property failed without going back to raw
    notes, and `RESULTS.md`'s metric-family convention already expects named sub-metrics.
  - *Binary per-claim groundedness* instead of a hit rate: rejected, throws away exactly the
    signal (partial groundedness) that M4 error analysis most wants to see.
- **Reasoning:** Every choice here optimizes for the same thing: keep the signal that later
  modules (M4 error analysis in particular) need, without adding labeling time disproportionate
  to what it buys. The three-point scale and the continuous-then-bucketed groundedness score both
  do that; binary options were rejected specifically because they'd throw away information this
  project's own later steps are built to use.
- **Reversibility:** Moderate once labeling starts under this rubric: re-grading existing cases to
  a different scale is possible but tedious. Cheap right now, before any case is labeled.

---

## Design decision: find_coverage.py gene/variant matching bug, found and fixed in review

- **Date / module:** M1, `eval/` (2026-09-01).
- **What happened:** three tasks (disagreement-pair discovery, negative-case construction,
  SciFact/NFCorpus acquisition) were delegated to separate agent sessions per the briefings in the
  prior turn. Reviewing the output caught a real bug before it reached the corpus permanently.
  - Benchmark acquisition and disagreement-pair discovery: both good. SciFact/NFCorpus counts
    match `PROJECT_PLAN.md`'s own table exactly, the loader works (verified by calling it
    directly, not just running its tests). All 4 disagreement cases cite real PMCIDs (checked:
    all 8 exist in the corpus) with specific, sourced quotes showing genuine conflict.
  - Negative-case construction: **wrong.** It held out 247 articles across 8 pairs (15-63 per
    pair), far more than the "5-8 cases, small enough to hand-verify" instruction, and wrote
    directly to the shared `answer_cases.jsonl` instead of an isolated file, bypassing the
    coordination safeguard (harmless this time, nothing else collided with it).
- **Root cause:** `find_coverage.py`'s `TermSet.compiled()` OR'd genes and variants into one
  "subject" pattern. Given both `--gene MRE11` and a specific variant notation, any paragraph
  mentioning `MRE11` alone, without the variant, satisfied the subject match. This is not a
  labeling-judgment failure, it's a tool bug: re-running the exact same 8 pairs with the fix
  (subject pattern is variant-only when a variant is given, not gene-OR-variant) returned **zero**
  matches for all 8. None of the 247 held-out articles actually contained the specific variant
  anywhere in the text.
- **Decision:**
  1. Restored all 8 pairs (`hold_out_case.py --restore`), corpus back to the full 7,863 articles.
  2. Fixed `find_coverage.py`: subject pattern is variant-terms-only when variants are supplied,
     falls back to gene terms only for gene-level queries (unaffected, e.g. the disagreement
     cases that used `variant: null`). Added `--warn-threshold` (default 20): a loud `[WARN]`
     banner on stderr when a pair's `same_paragraph` count exceeds it, so an agent (or a person)
     gets a hard-to-miss stop sign instead of self-justifying a large list as "verified."
  3. Added regression tests: a gene-mentioned-but-variant-absent article must not match a
     variant-specific query; the warning banner fires/doesn't fire at the right thresholds.
  4. Archived the invalid negative-case output (`eval/_archive/`, not deleted, kept for the
     trail) rather than silently discarding it.
  5. Merged the 4 verified disagreement cases into the canonical `answer_cases.jsonl`.
  6. `eval/README.md` now states the isolate-your-output rule explicitly (write to your own file,
     not the shared ones) and the multi-notation-search recommendation for future negative-case
     work, both learned here.
  7. Rewrote `eval/benchmarks/test_loader.py` off `pytest` (the only test file in this project
     that used it, an unstated dependency) onto the same stdlib-only convention as every other
     test file. Added `eval/benchmarks/requirements.txt` for `ir_datasets`.
- **Reasoning:** The instinct to trust "narrow variant, small candidate list" as self-verifying
  was correct in principle, the actual failure was that the tool silently handed back a broader
  list than the query asked for, and that broader list still looked plausible enough (real
  articles, real gene, real condition) not to trigger suspicion. The fix targets the tool, not the
  process: a correct tool plus the same verify-by-hand discipline should not reproduce this.
- **Reversibility:** The corpus mutation was fully reversible (that's what `hold_out_case.py
  --restore` is for) and was reversed. The tool fix and test additions are the permanent part.
- **Redo outcome (2026-09-01, same day):** re-delegated with the fixed tool and an explicit
  briefing (isolate output, search multiple variant notations, respect the `[WARN]` banner). All
  8 new pairs (PALB2, BRCA2 x2, ATM x2, CHEK2, TP53 x2, each with a specific variant against
  genes that otherwise have 90-953 corpus articles mentioning them) came back with **zero**
  same_paragraph or doc_level_only matches under 2-3 notation variants each. No hold-out was
  needed, the corpus already contained no grounding for any of them. Wrote correctly to the
  isolated `answer_cases.negative.jsonl`, merged into `answer_cases.jsonl` after review (now 12
  cases: 4 disagreement, 8 negative). One residual caveat, not a defect: each case's notes claim
  "verified complete," but only 2-3 notation variants were searched per variant, missing
  protein-level HGVS and rsID forms `eval/README.md` recommends. Treat "verified complete" as
  "verified complete against the notations searched," not an absolute guarantee, until a wider
  notation sweep is run.