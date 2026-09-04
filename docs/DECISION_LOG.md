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

---

## Design decision: Gold-span verification found guessed offsets; re-derived from source

- **Date / module:** M1, `eval/` (2026-09-01).
- **What happened:** before building the scorer, checked whether the 4 disagreement cases' 9
  `gold_spans` actually pointed at the quoted text their `disagreement_note` claims. They didn't,
  reliably: round-number offsets (`0:305`, `950:1450`, `2500:3200`) are a guess's signature, and
  extracting the real text at those offsets confirmed it, several spans landed on the wrong
  paragraph, on-topic but not the sentence actually being cited.
- **Decision:** wrote `eval/corpus_text.py` (shared section-text extraction, joining paragraphs
  the same way `service/search.py`'s offset bookkeeping already assumes, so gold spans and a real
  system's spans are offset-compatible) and `eval/verify_spans.py`: for every span whose
  `disagreement_note` contains an attributable quote (whole quote, falling back to its individual
  sentences, whitespace/curly-quote tolerant), search the article's real text and rewrite
  `char_start`/`char_end` to the quote's actual location, widened to the containing paragraph. Ran
  it: 5 of 9 spans fixed this way (2 more turned out already correct). The remaining 4 had no
  literal quote to search for (the note only paraphrased them); those were checked and corrected by
  hand, same standard (a distinctive phrase or number from the note, located in the real abstract,
  widened to the paragraph), not left as guesses. All 9 spans now verifiably support their claim.
- **A real finding, not just a bug:** one quote failed exact matching because the note ended a
  sentence with a period where the source had a comma and kept going (PMC137944). The claim's
  substance was right, the "exact quote" wasn't byte-exact. `verify_spans.py`'s sentence-level
  fallback exists because of this: a quote that fails whole often still matches sentence by
  sentence, catching this class of drift without discarding an otherwise-good citation.
- **Reasoning:** a scorer graded against wrong gold spans would silently teach the wrong lesson,
  a "grounded" answer citing the actual supporting paragraph could score as ungrounded against a
  guessed span two paragraphs away, and vice versa. Cheap to fix now, before any answer has been
  scored against these cases; expensive to discover after M3 retrieval numbers already depend on
  them.
- **Reversibility:** Free going forward (`eval/test_verify_spans.py` regression-tests the matching
  logic). The specific 9 spans are corrected in `eval/answer_cases.jsonl`; re-running
  `verify_spans.py` on any future case with a quoted note is the same cost as this run.

---

## Design decision: M1 scorer architecture, judge choice, and the no-retrieval baseline

- **Date / module:** M1, `eval/` (2026-09-01). Implements the rubric from "Answer-set scoring
  rubric" above; this entry is the architecture underneath that rubric, not a re-decision of it.
  Built in the same working session this is logged in, not strictly before, noted here rather than
  glossed over: the rubric's sub-score definitions were already settled and logged first, what's
  decided here (schema, judge backend, N/A handling) is implementation that surfaced its own small
  choices while being written, addressed as they came up rather than staged as a separate
  pre-approval round.
- **Decision:**
  1. **System-answer schema.** A scorer run needs a generated answer to grade, not just a case.
     Defined one JSON-per-`case_id` shape (`eval/score.py`'s `SystemAnswer`): `direction`,
     `strength`, `not_found`, `answer_text`, `claims` (list of `{text, cited_pmcid, cited_section,
     cited_char_start, cited_char_end}`), plus `parameter_value`/`cited_pmcid` for the
     methods_extraction stratum. Any future generator (a real retriever, an ablation, this
     baseline) targets this one contract; `score.py` never talks to a live system directly.
  2. **Judge backend: Groq's free tier**, matching the model already decided in "Model & embedding
     stack" above (70B-class Llama, `llama-3.3-70b-versatile`), called through
     `eval/llm_client.py`. A `FakeJudge` (deterministic word-overlap, no network) exists
     specifically so `score.py`'s own branching logic is unit-tested without an API key or
     nondeterministic output; it is not a real judge and `eval/test_score.py` says so at the top.
  3. **Two rubric extensions beyond the confirmed discussion**, both flagged so they're easy to
     challenge: property 3 (surfaces disagreement) is graded pass/partial/fail here (partial =
     cites both conflicting sources without stating they conflict), the rubric discussion only
     fixed this scale for properties 1 and 2. Property 4 (says not-found) is additionally checked
     in reverse for ordinary evidence cases, did the system wrongly refuse when the corpus does
     have grounding, marked with `note: "extended_check"` in the output so it's greppable and
     droppable if that reading turns out to be wrong.
  4. **No blended per-case score.** `score.py`'s `summarize()` reports each property's pass rate
     over only the cases where it applied (N/A excluded from the denominator, not counted as a
     failure), matching the rubric decision's own reasoning against a holistic pass/fail.
  5. **First baseline: no-retrieval** (`eval/baselines/no_retrieval.py`), per `PROJECT_PLAN.md`
     M1's three-baseline requirement. Answers each evidence-stratum query from the model's
     parametric knowledge alone, `claims` always empty (there is no retrieval step to cite), so
     scoring it is expected to fail groundedness by construction, that failure is the measurement,
     not a bug. Not yet run: needs `GROQ_API_KEY`, not present in this environment. Code is
     written and unit-tested against `FakeJudge`; the first real run and its `RESULTS.md` row are
     the next step once a key is available.
- **Alternatives considered:**
  - *Skip the system-answer schema, score a live system directly*: rejected, there is no
    real system yet (M3 retrieval doesn't exist), and coupling the scorer to one would make it
    unusable for the free-benchmark harnesses (`eval/benchmarks/`) or any future ablation.
  - *Binary supported/unsupported for property 3 instead of pass/partial/fail*: rejected for
    consistency with property 1's granularity and because "cites both sources but never says they
    conflict" is a real, common, distinct failure mode worth its own bucket, not noise.
  - *Use the paid Haiku 4.5 budget for the judge now*: rejected, that budget is reserved
    specifically for the held-out final evaluation and judge-vs-human kappa calibration per the
    existing model-stack decision; iteration-time judging stays on the free tier.
- **Reasoning:** every choice here is downstream of decisions already logged (the rubric, the
  model stack); this entry exists so the *mechanics* connecting them are traceable too, and so the
  two places this script's authors (not discussed with the user) made a judgment call are visible
  rather than buried in code.
- **Reversibility:** Cheap. The schema is a dict shape, not a database; the judge is swapped by one
  CLI flag; the two rubric extensions are each gated behind a single function and a `note` field,
  easy to strip out if reviewed and rejected.

---

## Design decision: first 7 ordinary evidence cases, filling a real gap

- **Date / module:** M1, `eval/` (2026-09-02).
- **What happened:** every case in `answer_cases.jsonl` up to this point was special-cased,
  disagreement or negative. Nothing tested the plain case (single clear source, no conflict, no
  absence) that should be the majority of a 50-80 set; scoring or calibrating against a 100%
  edge-case set would give a distorted picture before any of that special-casing even matters.
- **Decision:** added 7 cases (`palb2_breast_risk_ord_001`, `chek2_prostate_risk_ord_001`,
  `tp53_chondrosarcoma_survival_ord_001`, `brca_prs_ovarian_risk_ord_001`,
  `brca2_pancreatic_risk_ord_001`, `tp53_her2_breast_ord_001`, `atm_at_lymphoid_tumor_ord_001`),
  `gold.has_disagreement: false`, `gold.expected_not_found: false`. Built directly (not delegated),
  same discipline as the span-verification fix: found candidate articles via manifest title search,
  read the actual abstract, copied an exact substring of the real reported finding, located it
  with `corpus_text.find_quote` and widened to the paragraph with `verify_spans.expand_to_paragraph`.
  No offset was typed by hand; every span is a program-verified location, same standard the
  disagreement cases were held to after their own guessed-offset problem. Deliberately picked for
  variety, not just repeating the same shape seven times: one prognosis case
  (`tp53_chondrosarcoma_survival_ord_001`, survival not susceptibility), one subtype-specific case
  (`tp53_her2_breast_ord_001`, HER2+ specifically, not generic risk), one dose-response case
  (`atm_at_lymphoid_tumor_ord_001`, kinase activity level, not mutation presence/absence), one
  modifier case (`brca_prs_ovarian_risk_ord_001`, a polygenic risk score changing risk within
  carriers, not the base gene-disease link).
- **A schema limitation surfaced, not fixed:** `brca_prs_ovarian_risk_ord_001` and
  `brca2_pancreatic_risk_ord_001` both cite sources whose finding genuinely spans two genes (BRCA1
  and BRCA2 together); the schema's single `gene` field forced picking one and noting the other in
  `notes`. Not fixed here, real multi-gene evidence cases are rare enough in this batch (2 of 7) not
  to justify a schema change yet; revisit if it keeps recurring as the set grows.
- **Reasoning:** cheap to build now with the verification tooling already in hand; expensive to
  discover the gap after kappa calibration or a baseline comparison already ran against a
  100%-edge-case set and produced a number that doesn't generalize.
- **Reversibility:** Cheap. 7 cases, same file, same schema, easy to extend or amend individually.
  Set is now 19 (4 disagreement, 8 negative, 7 ordinary), still short of the ~50-80 target.

---

## Design decision: BM25-only baseline, hand-built, and the paired comparison tool it needed

- **Date / module:** M1, `eval/` (2026-09-02), logged alongside building it.
- **Decision:** implemented Okapi BM25 from scratch (`eval/bm25.py`), no ranking library, per
  `PROJECT_PLAN.md`'s standing rule to implement at least one component with no library. Indexes
  at paragraph granularity (title/abstract/body paragraphs, the same "\\n"-joined offset convention
  `corpus_text.py` and `service/search.py` already use), so every retrieval hit carries real
  `(pmcid, section, char_start, char_end)` provenance, not just a ranked document id. `k1=1.5,
  b=0.75`: textbook defaults (Robertson & Zaragoza 2009), not tuned against this corpus, tuning is
  future work once the n>=300 retrieval set exists to tune against, not worth doing against 19
  cases. Full-corpus index (7,863 articles, 437,133 paragraphs) builds in about 50 seconds,
  single-process, no multiprocessing needed; persisted to `eval/runs/bm25_index.pkl` (586 MB,
  git-ignored, regenerable). `eval/baselines/bm25_only.py` retrieves top-8 paragraphs per query,
  prompts the model to answer using only those excerpts and cite them by index number, then maps
  cited indices back to their real spans, the model never invents an offset.
- **A real operational finding, not just a baseline number:** Groq's free tier enforces an 8,000
  token/minute cap on this model, hit immediately once judge calls (property 1-3 grading, several
  calls per case) stacked on top of two full baseline runs in the same session. Added retry/backoff
  to `llm_client.groq_chat_json` (reads the server's own `Retry-After` / `x-ratelimit-reset-tokens`
  headers, retries up to 5 times) rather than the run just failing partway through. This is exactly
  the kind of constraint the "free tier for iteration" decision flagged as a real risk to plan
  around, now a concrete number (8k tokens/min) instead of an abstract warning.
- **Also built: `eval/compare_runs.py`**, a paired comparison tool (McNemar's exact test on
  binary pass/not-pass, partial counted as not-pass, a strict reading noted in its own output), used
  immediately to compare `no_retrieval` against `bm25_only` on the same 19 cases. Built as a
  reusable tool, not a one-off script: every future ablation (M3 retrieval, M6 chunking, ...) needs
  exactly this, a paired test against the same case set, per `RESULTS.md`'s own "comparisons are
  paired" rule.
- **First real answer to M1's own question, "how much does retrieval buy you":** groundedness goes
  from 0% (impossible without retrieval, no spans exist to cite) to 75% (n=11-12), McNemar exact
  p=0.008, real even at this n. The more interesting result is what didn't move: direction/strength
  pass rate is identical (18%) between the two baselines, zero cases flipped in either direction.
  Retrieval handing the model correct source text did not fix getting the reported direction wrong.
  That's evidence the direction failures are a synthesis problem sitting on top of correct
  retrieval, not a retrieval problem, worth a specific look once M4 error analysis exists rather
  than assumed away. Full numbers, the paired deltas, and two specific named failures (a
  fabrication caught, a retrieval-recall miss) are in `docs/RESULTS.md`.
- **Reasoning:** the point of a from-scratch BM25 isn't the ranking quality (a library would rank
  fine too), it's owning the retrieval-to-citation provenance chain end to end and being able to
  explain every line of it, per the project's own "protecting the learning" rule.
- **Reversibility:** Cheap. The index is a derived artifact (rebuildable from the corpus in under a
  minute); `k1`/`b`/`top_k` are constructor/CLI parameters, not hardcoded assumptions elsewhere.

---

## Design decision: dev/held-out split, enforced by score.py, not just documented

- **Date / module:** M1, `eval/` (2026-09-02), logged alongside building it.
- **Decision:** implemented `PROJECT_PLAN.md`'s stratification rule (hold out roughly a third of
  the answer set from day one, touched at most three times across the whole project) as actual
  tooling, not a promise. `eval/split.py` assigns each case to `dev` or `held_out`, stratified by
  case type (disagreement / negative / ordinary) and seeded (seed 0, same discipline as the
  corpus's own uniform-random sampling), so the held-out third isn't accidentally all-one-type at
  n=19. `score.py --held-out {exclude,include,only}` defaults to `exclude` (dev-only, the safe
  default a normal run can't get wrong by omission); using `include` or `only` requires
  `--touch-reason` and automatically appends a row to `held_out_touches.csv`, so "at most three
  times" is an auditable count, not an honor-system rule living only in a doc.
- **Result of this run:** 19 cases split 13 dev / 6 held-out (`chek2_breast_popul_specific_disagree_001`,
  `brca2_c9097c_t_ovarian_neg_001`, `palb2_c697c_t_colorectal_neg_001`,
  `tp53_c242c_g_lymphoma_neg_001`, `chek2_prostate_risk_ord_001`, `tp53_her2_breast_ord_001`),
  spanning all three case types.
- **A real wrinkle, disclosed rather than smoothed over:** both baseline runs in `RESULTS.md`
  (`no_retrieval` and `bm25_only`, same day, before this split existed) scored all 19 cases,
  including what are now the 6 held-out ones. The split concept didn't exist yet when those ran, so
  this isn't counted as a "touch," but it does mean today's published baseline numbers are not
  held-out-clean; a stricter read would treat them as dev-set numbers that happen to include a few
  held-out cases this one time. Going forward, a normal evaluation run should use the default
  `--held-out exclude` (13 dev cases), reserving the 6 held-out for real milestone checks only.
- **Alternatives considered:**
  - *Simple random split, not stratified by case type*: rejected at n=19, a third is only 6-7 cases,
    unstratified random has a real chance of landing entirely on one case type (e.g. all negative
    cases), which would make the held-out check useless for the other two types.
  - *Document the rule in `eval/README.md` only, no enforcement*: rejected, matches the project's
    own pattern of catching a documented-but-unenforced rule failing silently (the `.gitignore`
    negation bug, the `find_coverage.py` matching bug), better to make violating it require an
    explicit flag and a logged reason than to trust memory across a multi-month project.
- **Reasoning:** the whole point of a held-out split is that repeated iteration against the same
  small set quietly turns it into a training set; a split that's easy to accidentally include in a
  normal run defeats its own purpose. Making the safe path the default and the unsafe path require
  a reason is the same shape as `hold_out_case.py`'s cross-pair-reassignment guard and
  `find_coverage.py`'s `--warn-threshold` banner, tools in this project already enforce their own
  discipline rather than relying on remembering it.
- **Reversibility:** Cheap to extend (new cases get assigned on the next `split.py assign` run
  without disturbing existing ones); expensive to undo meaningfully (once a case has been touched
  as held-out and the answer seen, that exposure can't be un-seen, which is exactly why the touch
  log exists, to make that cost visible rather than free).

---

## Design decision: kappa calibration tooling built; the calibration itself deliberately not run by me

- **Date / module:** M1, `eval/` (2026-09-02), logged alongside building it.
- **Decision:** built the full pipeline for `PROJECT_PLAN.md`'s judge-vs-human kappa step
  (`eval/kappa.py`: hand-built unweighted and linearly-weighted Cohen's kappa;
  `eval/make_kappa_worksheet.py`: generates a blind worksheet, dev-split cases, judge's own verdict
  never shown; `eval/run_kappa_calibration.py`: parses a filled-in worksheet and reports kappa
  against the judge's stored scores). Deliberately did **not** fill in the worksheet myself, that
  is the one M1 step `CLAUDE.md` and `PROJECT_PLAN.md` both name as belonging to a real person: "the
  eval scorer and failure taxonomy [are] a discussion with the user, not a handoff," and kappa
  specifically measures agreement *between the judge and a human*, an LLM (me) filling in both
  sides would produce a number that looks like a real calibration result and measures nothing.
  Verified the pipeline works end to end with a throwaway smoke test (rotating placeholder
  verdicts unrelated to any real judgment, run against a scratch copy outside `eval/`, discarded
  immediately, not committed, not reported as a result anywhere).
- **Alternatives considered:**
  - *Generate plausible-looking human verdicts myself, from reading the same worksheet content*:
    rejected outright. Even framed as "a reasonable second opinion," this is exactly the failure
    mode the calibration step exists to prevent, an automated system checking its own homework
    and reporting the result as if it were independent.
  - *Skip kappa entirely for now, note it as not-yet-done*: considered, but the tooling itself
    (worksheet generation, parsing, the weighted-kappa math) is real work with no dependency on
    who does the labeling, worth having ready rather than built later under time pressure once
    someone actually wants to run it.
- **Reasoning:** the whole point of measuring judge-vs-human agreement is that the human side is
  independent of the automated side; building the mechanism and refusing to be the mechanism's own
  human are two different things, this decision is only really about the second one.
- **Reversibility:** N/A, nothing was measured. The tooling is reusable the moment a real worksheet
  gets filled in.

---

## Experiment: kappa worksheet truncation bug, found reviewing the first real grading pass

- **Date / module:** M1, `eval/` (2026-09-03).
- **What happened:** the worksheet got filled in, not by the user directly (no professional
  oncology background) but with Gemini 3.1 Pro's help. That is a real, disclosed deviation from
  what the tool was built for, see the entry immediately below; this entry is about a second,
  independent problem the review of that grading pass surfaced, a bug in the worksheet itself.
  `make_kappa_worksheet.py` truncated every cited span to 400 characters for display
  (`span_text[:400]`). `score.py`'s judge always grades the full, untruncated span
  (`corpus_text.load_span_text`). A rater using the worksheet was therefore graded on strictly
  less evidence than the judge had, and any resulting "disagreement" could be the worksheet hiding
  real supporting text, not an actual difference of judgment.
- **Prediction (had this been caught before grading, not after):** would have predicted this
  matters a lot, most real citations are full paragraphs (200-2000+ chars), so a 400-char cutoff
  would cut off in the middle of most of them, right where a specific number or conclusion often
  sits.
- **Method:** manually re-checked the full (untruncated) span text for every claim the grading
  pass had marked as ungrounded/partially-grounded where the span exceeded 400 characters, 5
  claims across 3 cases.
- **Result:** 4 of 5 were fully supported once the truncated portion was read: an "A large cohort
  of A-T patients from the UK and the Netherlands" sentence cut off right before the word "large
  cohort" itself; a "no worse outcome for CHEK2 c.1100delC... ER-positive" sentence cut off one
  clause before the exact matching conclusion; three pancreatic-cancer relative-risk/lifetime-risk
  figures (up to 4.11-fold BRCA1, 2.13-21.7-fold BRCA2, ~1%/4.9% lifetime risk) that closely match
  what the system claimed, sitting entirely past the 400-char mark. Only 1 of 5 held up as a
  genuine miss even with full text: two claims in `atm_variants_controversy_disagree_001` cited a
  2,149-character span about BRCA1/2 prevalence in Chile with zero mention of ATM anywhere in it,
  a real mismatched/hallucinated citation the judge nonetheless scored as grounded.
- **Did the prediction hold?** Yes, more strongly than expected. This wasn't a marginal effect,
  the truncation bug explains the large majority of the groundedness disagreement in this grading
  pass, not a small fraction of it.
- **What changed because of this:** fixed `make_kappa_worksheet.py` to show the full span (no
  truncation), added a regression test. The groundedness kappa numbers from this grading pass
  (see the entry below) should be read as contaminated by this bug, not as a clean signal about
  judge accuracy, apart from the one genuine miss identified above, which is real and worth
  keeping: the judge can score a topically-plausible-sounding citation as "grounded" without the
  cited text actually being about the claimed subject. That specific failure mode is worth
  watching for in the judge going forward, independent of this bug.

---

## Design decision: the kappa grading pass used Gemini 3.1 Pro, not a human, and what that does and doesn't tell us

- **Date / module:** M1, `eval/` (2026-09-03).
- **What happened:** the user had Gemini 3.1 Pro fill in `kappa_worksheet.md`, citing lack of
  professional oncology background. This does not satisfy `PROJECT_PLAN.md`'s calibration step
  ("Measure Cohen's kappa between judge and you") or `CLAUDE.md`'s standing rule that the eval
  scorer be "a discussion with the user, not a handoff": the resulting number is agreement between
  two LLMs (Groq's `openai/gpt-oss-120b` judge and Gemini 3.1 Pro), not judge-vs-human. Logged
  here plainly rather than let a kappa number from this pass be mistaken for the real calibration
  in a later session.
- **What it is still worth, and what it isn't:** an LLM-vs-LLM cross-check is a real, if different,
  signal, two independently-prompted models grading the same rubric against the same evidence is a
  reasonable smoke test of whether the rubric itself is followable and whether the judge's
  citation-checking is basically sound (see the truncation-bug entry above: once corrected for that
  bug, the two models' groundedness judgments mostly converged). It is not a substitute for the
  domain-expertise check the human calibration step exists for: neither model has the comp-bio
  judgment the task contract's own correctness definition assumes, and two models agreeing with
  each other is not evidence that either is right about the biology.
  Per-property numbers from this pass, **contaminated by the truncation bug above for groundedness
  specifically**, not fully re-verified for the others: direction kappa (unweighted) = 0.216
  (fair), disagreement kappa = 0.0 (n=3, one real disagreement, too small to read as anything),
  not_found kappa = 1.0 (n=13, perfect agreement, this property doesn't depend on span text so
  isn't affected by the truncation bug).
- **A real, likely-genuine pattern in the direction disagreements, independent of the truncation
  bug:** all 5 direction disagreements went the same way, Gemini graded "pass," the judge graded
  "partial." In each checked case, the system's stated *direction* was correct but its *strength*
  was either vague, unquantified, or stated in different units than gold (e.g. relative-risk
  fold-change vs. gold's lifetime-risk percentage). This reads as a genuine difference in how
  strictly to weight the rubric's own "strength" half of property 1, not noise, and not either
  side being unfair: the rubric's partial criterion ("right direction, strength off by one tier
  ... or direction correct but strength unstated") explicitly supports the judge's stricter
  reading. Worth settling explicitly if this recurs once a real human labels a sample.
- **Reasoning:** disclosure over convenience. A mislabeled LLM-vs-LLM number sitting in the log as
  if it were the real calibration would be exactly the kind of quiet error this project's own
  logging discipline exists to prevent.
- **What changed because of this:** nothing is marked as "M1's kappa calibration: done." The real
  calibration, a professional or domain-literate human against a corrected (untruncated) worksheet,
  is still open.

---

## Experiment: LLM-vs-LLM grading pass, redone after the truncation fix, and two rubric-application findings

- **Date / module:** M1, `eval/` (2026-09-03), continues the two entries directly above.
- **Prediction:** fixing the truncation bug would raise groundedness agreement substantially,
  since 4 of 5 manually-checked disagreements from the first pass turned out to be truncation
  artifacts. No prediction for direction/disagreement, those don't depend on span text.
- **Method:** same worksheet generator and comparison tool, re-run against the corrected
  (untruncated) worksheet, same judge scores (`runs/bm25_only_scores.json`), same 13 dev cases.
- **Result:** groundedness kappa rose from 0.059/0.158 (unweighted/weighted) to **0.226/0.429**
  (fair/moderate), confirming the prediction, most of the first pass's apparent judge unreliability
  was the bug, not the judge. Remaining numbers: direction 0.216/0.200 (fair, unchanged, doesn't
  depend on span text), disagreement 0.0 (n=3, one real disagreement, still too small to read),
  not_found 1.0 (n=13, perfect, unaffected either time).
- **Did the prediction hold?** Yes for groundedness. No prediction was made for the others.
- **Two concrete, actionable findings survive this pass, not just a kappa number:**
  1. **The judge conflates "wrong direction" with "right direction, wrong magnitude" under `fail`,**
     contradicting its own rubric. Its stored rationale for `brca2_pancreatic_risk_ord_001`
     literally says "Direction matches, but the claimed... risk... greatly overstates the gold
     standard's... association" and still returns `fail`, when the rubric's own text defines
     `partial` as exactly "right direction, strength off by one tier." The judge prompt
     (`judge.py`, `_DIRECTION_PROMPT`) should be tightened to say so explicitly: a magnitude/
     strength mismatch alone is never `fail` when direction is correct. **Applied 2026-09-03**,
     confirmed with the user first: `_DIRECTION_PROMPT` now states this explicitly.
  2. **The judge credits a citation as "grounded" when it's a figure caption or table header,
     not a sentence stating the actual finding** (`brca_prs_ovarian_risk_ord_001`, all three
     citations are literally "FigureS1: Cumulative risk of ovarian cancer risk in BRCA1 carriers
     by polygenic risk score percentiles" and similar, not a sentence containing the quantified
     direction). Gemini's `partial` call here looks more careful than the judge's `pass`.
     **Applied 2026-09-03**: `_GROUNDEDNESS_PROMPT` now states explicitly that a caption/title/
     heading describing what a figure or table is about is not support for a claim about what it
     shows, unless the caption itself states the finding.
- **A data-quality note, not a finding about the judge:** the re-grading pass kept `palb2_breast_
  risk_ord_001`'s groundedness rationale ("the explicit '53%' figure is physically truncated")
  verbatim from the first pass, but the corrected worksheet's claim 4 excerpt for that case now
  visibly ends "...compared to an estimated 53% risk of breast cancer in women [32]." (untruncated,
  the 53% is right there). This one verdict looks like it wasn't actually re-checked against the
  fixed worksheet. Left as-is rather than silently corrected, flagged for the user to confirm; at
  n=8 for groundedness, one relabeled case moves the kappa but not the overall picture.
- **What changed because of this:** both prompt tightenings applied to `judge.py` after explicit
  user confirmation. Every judge-scored row already in `RESULTS.md` (the `no_retrieval` and
  `bm25_only` baseline runs) predates this prompt version, those numbers were produced by the
  judge as it existed before this fix and are not automatically still accurate; re-running them is
  a future step, not implied by this entry. The real (human) calibration is still the open item;
  this LLM-vs-LLM pass did what it's actually good for, stress-testing the rubric and the judge's
  consistency in applying it, cheaply, before spending a domain expert's real time on the same
  worksheet.

---

## Design decision: skip the real (human) kappa calibration for M1

- **Date / module:** M1, `eval/` (2026-09-03).
- **Decision:** do not run `PROJECT_PLAN.md`'s judge-vs-human kappa step. The tooling stays built
  (`eval/kappa.py`, `make_kappa_worksheet.py`, `run_kappa_calibration.py`), reusable the moment
  someone wants it; the calibration itself is not being done for M1.
- **Alternatives considered:**
  - *Recruit a domain expert to run it*: out of scope for a solo learning project on this
    timeline.
  - *Treat the Gemini cross-check as sufficient*: rejected as a substitute, logged plainly instead
    (see the two entries above), agreement between two LLMs is not evidence either is right about
    the biology, whatever it's separately useful for (it did find two real judge-prompt bugs).
- **Reasoning:** the LLM-vs-LLM pass already extracted the cheap, high-value part of this exercise,
  finding concrete, fixable judge-prompt issues, without needing a real rater's time. The remaining
  value a human calibration adds is specifically the domain-expertise check ("is the judge's
  biology reasoning sound"), and that value is better spent later, once M4 error analysis exists
  to show whether judge disagreement is actually a material source of wrong conclusions, rather
  than spent now on a rubric that's still expected to change as the case set grows.
- **What this means for interview-readiness:** the "answer cold" question `PROJECT_PLAN.md` poses
  for M1, "how do you know your eval set is any good," does not have a full answer. Worth stating
  plainly rather than glossed over: the honest answer right now is "the judge was cross-checked
  against a second model and two real prompt bugs were found and fixed; it has not been calibrated
  against a domain expert." That is a true, defensible, incomplete answer, not nothing.
- **Reversibility:** Free to revisit. Nothing was discarded, the tooling and the corrected
  worksheet mechanism are both still there.
---

## Design decision: v4 plan audit, and a lean-v1 reordering of Tier 1

- **Date / module:** Tier 1 planning revision (2026-09-03), logged before any of it is built.
- **What prompted it:** a full re-read of `PROJECT_PLAN.md` (v3), `START_HERE.md`,
  `TASK_CONTRACT.md`, `RESULTS.md`, this log, and the code as it stands. v3's module *content* is
  not in dispute and is not being rewritten. What this entry changes is the **order** Tier 1 gets
  executed in, and it records seven audit findings that drove the reorder.

### The seven findings

1. **The gold labels are entirely agent-authored and no person has read them.** All 19 cases in
   `eval/answer_cases.jsonl` carry `created_by: agent:*`. The judge-vs-human kappa step was
   skipped (entry above), and the one grading pass was Gemini against Groq. Every number in
   `RESULTS.md` therefore rests on ground truth that has never met a human. `CLAUDE.md` names the
   eval set and taxonomy as the intellectual core specifically to prevent this.
2. **There is no system.** What has been measured is a script that calls BM25 and one LLM. The
   FastAPI service still serves the Step 0c keyword stub. `CLAUDE.md`'s ordering rule is "eval
   harness **and instrumentation spine**"; M1 is largely built, M2 is untouched, so M2 is the
   actual gate on pipeline code, and it is the thing not being worked on.
3. **The harness has never been validated against known-good labels.** SciFact and NFCorpus are
   downloaded with a working loader and have never been run. There is no IR metric code in the
   repo at all: no recall@k, no MRR, no nDCG. M1's own first instruction is to run the harness
   against free labeled data before trusting it on your own.
4. **Priorities inside M1 are inverted.** Growing the answer set from 19 toward 80 costs many
   hours and still only detects large effects. The n>=300 retrieval set is what makes every later
   ablation computable, and it does not exist. v3 lists both as M1 work as if they were equally
   valuable. They are not.
5. **A standing `RESULTS.md` rule is violated by every row subject to it.** It requires
   `baseline/no_retrieval` to *always* be reported per date stratum. No row does.
   `corpus/manifest.csv` already carries `pubdate` and 1,564 of 7,863 articles are 2025-2026, so a
   real post-cutoff stratum exists and the fix is nearly free.
6. **The repo's most interesting result is untested and one cheap experiment away.**
   Direction/strength is 12.5% with and without retrieval, zero cases flipped. The unstarted third
   M1 baseline (whole-document-in-context) is exactly the experiment that separates "retrieval did
   not find it" from "the model cannot read it." It belongs *before* retrieval tuning: if reading
   is the bottleneck, a better retriever buys nothing.
7. **Smaller:** config hashes are ad-hoc sha256 of a string with no run registry; `README.md`
   still says "Step 0, nearly done" while M1 is mostly complete.

### The decision, in four parts (each confirmed with the user before logging)

- **Eval-set trust:** a human validation pass on a stratified sample of 8 of the 19 cases, using a
  generated worksheet showing query, gold direction/strength, and the gold span's real source
  text. Marks each case valid / wrong / unsure. This is *case* validation, not judge calibration:
  kappa measures the judge against a human, but if gold is wrong both sides are grading against
  the wrong answer. Rejected: validating all 19 (~2h, more than the risk warrants at this stage);
  skipping and logging the caveat (leaves every downstream number inheriting it).
- **Retrieval eval set (n>=300):** hybrid construction. SciFact/NFCorpus validate the harness
  against published BEIR BM25 numbers first. The domain set is then generated from sampled corpus
  paragraphs, stratified by section type, each paragraph serving as its own gold span by
  construction, filtered so the query is not answerable without that span, with a human spot-check
  of about 20. **The known bias is lexical:** an LLM writing a query while looking at a paragraph
  tends to reuse its wording, which inflates BM25 relative to dense retrieval, the exact
  comparison M3 exists to make. Mitigated by a de-lexicalization pass and reported as a caveat on
  every row that uses this set, not hidden. Rejected: hand-writing ~100 domain queries (best
  labels, but n=100 detects roughly 8-point deltas, not 3, and costs many hours); BEIR-only (great
  statistics, says nothing about this corpus, where chunking and identifier retrieval actually get
  hard).
- **Instrumentation depth (M2):** a hand-written span emitter writing JSONL, using OpenTelemetry
  GenAI semantic-convention attribute names (`gen_ai.operation.name`, `gen_ai.usage.input_tokens`,
  and so on) plus per-stage latency and cost. Gets M4's root-cause attribution and M10's stage
  breakdown working in hours. The OTLP exporter and a self-hosted Phoenix/Langfuse backend are
  deferred until there is traffic worth looking at. Rejected: full OTel SDK plus local Phoenix now,
  a day or two of setup before a single retrieval number exists, against conventions that are
  still Development-status and still moving.
- **What counts as v1:** the **lean** definition. v1 is the existing BM25 path made into a real
  system: structure-aware chunks with span provenance, served behind the FastAPI streaming
  endpoint, traced, cost-accounted, scored on both eval sets, with real p95/TTFT/cost measured
  against the contract's 6s / 1.5s / $0.05 targets. Dense embeddings, hybrid fusion, and reranking
  then land **one at a time as measured upgrades with paired tests**. Rejected: building the full
  hybrid + Qdrant + reranker stack before calling anything v1. That produces a better architecture
  diagram and a worse project: the deltas arrive bundled and unattributable, and nothing is served
  end to end for several sessions. Shipping lean and measuring each upgrade separately *is* the
  method this project exists to practice.

### The resulting execution order

Phases, each ending in a number. Full statement in `PROJECT_PLAN.md`, "Tier 1 execution order (v4)".

- **A. M1 closeout, cheap.** Case-validation worksheet (user); hand-written `eval/ir_metrics.py`
  (recall@k, MRR, nDCG@10) run over SciFact/NFCorpus with the existing BM25 and checked against
  published BEIR figures; whole-document-in-context baseline on the dev split; `pub_year` on every
  case and per-stratum reporting of the no-retrieval baseline.
- **B. M2 spine, the actual gate.** Config-as-code YAML plus hash; a run registry tying every
  result to git SHA and config hash; the chunk schema carrying source-offset provenance and the
  span-overlap hit function; per-request token/cost/latency accounting under semconv names.
- **C. The n>=300 retrieval set**, per the construction decided above.
- **D. v1 pipeline.** Structure-aware JATS chunker (hand-written), BM25 over chunks rather than
  raw paragraphs, and the exact-identifier failure case (rsID / HGVS) constructed deliberately and
  measured.
- **E. Ship it.** Replace `service/search.py`'s stub with the real pipeline behind the same
  streaming interface; re-run the load test; real p95/TTFT/cost against the contract targets, with
  a stage breakdown from B's traces.
- **F. M4 error analysis and the Tier 1 README.** Failure taxonomy hand-written with the user, per
  `CLAUDE.md`. Tier 2's order then gets picked by the failure-bucket distribution rather than
  pre-committed here.

- **Reasoning:** the binding constraint on this project is not module coverage, it is that nothing
  is yet end to end and nothing has been checked by a person. Both of those are fixed cheapest by
  reordering, not by adding scope. The lean-v1 call in particular converts what looked like
  missing features (no dense, no hybrid, no reranker) into the project's next four measured
  experiments, which is worth more than having them silently present and unattributed.
- **Reversibility:** free. This reorders v3's own modules and drops none of them. The one
  genuinely hard-to-reverse item inside it is the chunk provenance schema in phase B, which is
  exactly why it sits ahead of any pipeline code.

---

## Experiment: is the harness broken? BM25 against SciFact and NFCorpus

- **Date / module:** M1 / phase A2 (2026-09-03). Logged before writing `eval/ir_metrics.py` or
  running anything, per the standing rule.
- **The question.** `PROJECT_PLAN.md` M1's first instruction is to run the harness against free
  labeled data, because "running your harness against them tells you whether the harness is broken
  before you trust it on your own data." SciFact and NFCorpus have been sitting downloaded in
  `eval/benchmarks/` with a working loader since 2026-09-01 and have never been run. There is also
  no IR metric code anywhere in this repo yet: no recall@k, no MRR, no nDCG. So this run builds
  the metrics and validates both them and `eval/bm25.py` at the same time, against an external
  reference that does not care what this project believes.
- **The reference.** Pyserini/Anserini multi-field BM25 on the BEIR test splits, from Kamalloo et
  al., "Resources for Brewing BEIR" (arXiv 2306.07471, Table 2), fetched and checked rather than
  recalled: **SciFact nDCG@10 = 0.665, Recall@100 = 0.908; NFCorpus nDCG@10 = 0.325,
  Recall@100 = 0.250.**
- **Why an exact match is not the prediction.** Three differences from that reference, all known in
  advance, all pushing the same direction (down):
  1. *Parameters.* Lucene's defaults are `k1=0.9, b=0.4`; `eval/bm25.py` uses the textbook
     `k1=1.5, b=0.75`, untuned.
  2. *Analysis.* Lucene stems (Porter) and drops stopwords. `bm25.py` does neither: its tokenizer
     is a regex that deliberately keeps `c.1100delC` and `BRCA1` intact as single tokens, which is
     the right call for this project's own identifier-heavy corpus and the wrong call for
     NFCorpus's health-and-nutrition prose, where stemming buys real recall.
  3. *Fields.* The reference indexes title and body as separate equally-weighted fields; this run
     concatenates them into one.
- **Prediction (before running):** both land **below** the reference but in its neighborhood.
  SciFact nDCG@10 in **[0.55, 0.70]**, point estimate ~0.62. NFCorpus nDCG@10 in **[0.25, 0.33]**,
  point estimate ~0.29, with the shortfall larger on NFCorpus than SciFact because stemming helps
  prose queries more than it helps claim-style ones. Recall@100 predicted near the reference on
  SciFact (~0.85-0.91), since recall at depth 100 is far more forgiving of ranking-parameter
  differences than nDCG@10 is.
- **The failure threshold, stated in advance so it cannot be rationalized after:** if either
  nDCG@10 comes in below **60% of its reference** (SciFact < 0.40, NFCorpus < 0.20), that is not a
  parameter difference, it is a bug in the metric code or in `bm25.py`, and the domain numbers
  already in `RESULTS.md` that depend on that retriever come under suspicion with it.
- **Minimum detectable effect:** this is an absolute check against an external constant, not a
  paired A/B, so the relevant resolution is the width of the CI on our own number. Bootstrapping
  over queries at n=300 (SciFact) and n=323 (NFCorpus), with per-query nDCG@10 standard deviation
  of roughly 0.4, gives a 95% CI half-width near **0.045**. So this run can tell "close to the
  reference" apart from "broken," and can tell a 0.10 shortfall from a 0.30 one. It **cannot**
  establish that our BM25 matches the reference exactly, and no conclusion of that shape should be
  drawn from it.
- **What this run is not.** It is not a claim that `bm25.py` is a good retriever, and not a number
  that belongs in any comparison against the domain corpus. SciFact and NFCorpus documents are
  abstracts; the domain index is paragraphs of full text. This checks the plumbing: metric
  definitions, tokenization, the scoring loop, and the qrel join.
- **Method:** hand-write `eval/ir_metrics.py` (recall@k, MRR, nDCG@k, plus a query-level bootstrap
  CI), unit-test it against worked examples computed by hand, then run `eval/bm25.py` over each
  benchmark corpus via the existing `eval/benchmarks/loader.py` and score against the qrels.
  NFCorpus qrels are graded (11,758 at relevance 1, 576 at 2); nDCG uses the graded values, recall
  and MRR treat any relevance > 0 as relevant.
- **Result:** rows in `docs/RESULTS.md`, "Harness validation: BM25 on SciFact and NFCorpus."

  | | ours | reference | delta | % of reference |
  |---|---|---|---|---|
  | SciFact nDCG@10 | 0.598 [0.550, 0.648] | 0.665 | -0.067 | 90% |
  | SciFact Recall@100 | 0.825 [0.782, 0.867] | 0.908 | -0.083 | 91% |
  | NFCorpus nDCG@10 | 0.288 [0.255, 0.321] | 0.325 | -0.037 | 89% |
  | NFCorpus Recall@100 | 0.220 [0.192, 0.250] | 0.250 | -0.030 | 88% |

  n=300 and n=323 queries. Nothing came near the 60%-of-reference bug threshold.
- **Did the prediction hold?** Mostly, with one clean miss and one that was wrong for an
  interesting reason.
  - *Held:* both landed below the reference and in its neighborhood. SciFact nDCG@10 = 0.598 fell
    inside the predicted [0.55, 0.70], about 0.02 below the predicted 0.62 point estimate.
    NFCorpus nDCG@10 = 0.288 fell inside [0.25, 0.33], essentially on the predicted 0.29.
  - *Missed:* SciFact Recall@100 = 0.825 came in below the predicted [0.85, 0.91]. The CI's upper
    edge (0.867) reaches into that range, so this is a point estimate outside the prediction, not
    a decisive refutation, but it is a miss and gets written as one. The reasoning behind that
    sub-prediction, that deep recall is forgiving of ranking-parameter differences, was right in
    direction (Recall@100 lost less relative ground than nDCG@10 on NFCorpus) and simply too
    optimistic about the magnitude on SciFact.
  - *Wrong:* the prediction that the shortfall would be **larger on NFCorpus than SciFact**,
    reasoned from stemming helping prose queries more than claim-style ones. It was not. In
    relative terms the two are indistinguishable (90% vs 89% of reference); in absolute terms the
    shortfall was nearly twice as large on SciFact (-0.067 vs -0.037). Whatever the missing
    stemming and stopword handling cost, it cost about the same proportion on both, which is
    evidence the gap is dominated by the untuned `k1`/`b` and the single-field indexing rather
    than by the analyzer. That is a testable claim and the cheap follow-up is obvious: re-run with
    `k1=0.9, b=0.4` and see how much of the gap closes. Not doing that now, it is not on the
    critical path to v1, but it is logged as a known cheap experiment.
- **A finding worth keeping, separate from the validation:** NFCorpus MRR = 0.505 against
  recall@10 = 0.135 on the identical ranking. Not a contradiction: at 38 relevant documents per
  query, surfacing *one* of them high is easy and capturing a meaningful share of them in 10 slots
  is arithmetically near-impossible. Either number reported alone misdescribes the retriever. This
  is the concrete argument for `RESULTS.md`'s metric families being reported together, and it is a
  better answer to "which retrieval metric do you use" than naming one.
- **What changed because of this:**
  1. **The harness is no longer unvalidated.** `PROJECT_PLAN.md` M1's first instruction is now
     actually done, and the honest answer to its "how do you know your eval set is any good"
     question gained a real clause: the metric code and the retriever reproduce published BM25
     figures to within about 10% on two independent benchmarks with known answers.
  2. **`eval/ir_metrics.py` exists**, hand-written and unit-tested against worked examples
     computed by hand rather than against another implementation's output. This is the module
     every retrieval number from phase C onward will be computed by, so validating it here, before
     the domain retrieval set exists, is the whole point of the ordering.
  3. **`eval/bm25.py` was refactored** to split `index_from_paragraphs` out of `build_index`, so
     the benchmark run scores through the identical formula rather than a reimplementation that
     could agree with the reference while the real one disagrees. `test_bm25.py` passes unchanged
     across that refactor.
  4. **A cheap follow-up is queued, not silently dropped:** re-run with Lucene's `k1=0.9, b=0.4`
     to attribute the remaining gap between parameters and analysis.

---

## Experiment: phase A1 case validation, half the gold set is defective

- **Date / module:** M1 / phase A1 (2026-09-04). The human validation pass decided in the v4 audit.
- **Prediction (logged as the v4 audit's finding 1, before the worksheet was generated):** that an
  entirely agent-authored, never-human-read gold set was "the project's largest open risk." No
  numeric prediction was made, which in hindsight was a gap: a defect rate should have been
  predicted. Recording that omission rather than back-filling a number.
- **Minimum detectable effect:** n=8, so the CI on any rate is wide by construction (a 4/8 result
  carries a 95% CI of roughly [0.22, 0.78]). This sample can establish *that* the set has a
  serious problem. It cannot pin the rate, and no precise rate should be quoted from it.
- **Method:** `eval/make_case_worksheet.py`, 8 dev-split cases stratified 2 disagreement / 2
  negative / 4 ordinary, seed 0, each gold span rendered as full untruncated source text. Filled
  in by the user. Every flagged case was then re-checked by pulling the article text directly, and
  the two `unsure` negative cases were re-run through `find_coverage.py` with widened notation
  sweeps.
- **Result: 4 of 8 valid, 4 defective.** 50%, 95% CI [0.22, 0.78].

  | Case | Verdict | Defect |
  |---|---|---|
  | `chek2_1100delc_prognosis_disagree_001` | valid | |
  | `brca2_pancreatic_risk_ord_001` | valid | |
  | `palb2_breast_risk_ord_001` | valid | |
  | `atm_c2023c_t_breast_neg_001` | unsure -> **valid** | survived a widened sweep (p.Arg675Ter, R675X, Arg675 forms): still 0 matches |
  | `atm_c7570g_c_risk_class_disagree_001` | **wrong** | gold span cites a paragraph about a *different variant* |
  | `atm_at_lymphoid_tumor_ord_001` | **wrong** | gold `strength` asserts cohort figures (296 patients, 66 tumours, 47 lymphoid) absent from the cited span |
  | `brca_prs_ovarian_risk_ord_001` | **wrong** | gold attributes the 6%/19% OC risk figures to BRCA1 *and* BRCA2; the source says "for BRCA2 carriers". Cohort sizes also outside the span |
  | `palb2_c1592del4_pancreatic_neg_001` | unsure -> **invalid** | see below, the worst of the four |

- **Did the prediction hold?** Yes, and the qualitative call in the v4 audit was correct: this was
  the largest open risk and it was worth spending the sample on. Half.
- **The failure mode has a shape, and it is not fabrication.** In all three "wrong" evidence cases
  the article genuinely supports a corrected version of the case, and in two of the three the
  missing facts are elsewhere in the *same abstract*, just outside the recorded span. The defect is
  **citation drift**: a gold label asserting something more specific than, or subtly misattributed
  relative to, the span recorded next to it. An agent reading a whole article, writing a
  confident summary, then attaching an approximately-right span produces exactly this, and it is
  invisible to any check that only asks whether the span resolves and is in range.
- **`verify_spans.py` did not merely miss this. It caused one instance of it.**
  `atm_c7570g_c_risk_class_disagree_001`'s note quoted "up to 60% lifetime breast cancer by the age
  of 70 years." That phrase really is in PMC10092731, in a background paragraph about ATM
  **c.7271T>G**. The quote search found it, `expand_to_paragraph` widened to that paragraph, and
  `--fix` wrote the offsets in. Every step did its job. The script asked "does this quote exist in
  this article" and never asked "is this span about the variant the case is about." A tool that
  verifies existence and calls it verification will confidently cement a wrong span.
  **Fixed the same day:** `subject_check()` now classifies every resolved span as `ok` (names the
  variant) / `gene_only` (names the gene but not the variant, legitimate for a disagreement case's
  general-risk contrast span, wrong for a variant-specific claim, needs a human) / `absent`
  (names neither), `--fix` refuses to repoint into an `absent` span, and the three-way split
  exists specifically because a strict variant requirement would false-positive on contrast spans.
  Run over the real set it flags **exactly the case the human found, and nothing else** across the
  other 17 spans. Regression-tested with the real c.7271T>G-vs-c.7570G>C text.
- **The negative-case method is unsound, and this is the most important finding here.**
  `palb2_c1592del4_pancreatic_neg_001` claims the corpus contains no grounding for PALB2
  c.1592del4 + pancreatic cancer. Two things are wrong. First, `c.1592del4` is not standard HGVS
  and appears to be garbled; the real Finnish founder variant is **c.1592delT** (p.Leu531Cysfs*30).
  Second, searching the real notation finds **three articles discussing it alongside pancreatic
  cancer in the same paragraph** (PMC3751431, PMC3291835, PMC5389658). The case asserts an absence
  that is not there, and it "passed" its own construction check only because the notation searched
  does not exist in the literature. A negative case built on a nonexistent notation is not a hard
  test, it is a test that passes for the wrong reason.
  The other 6 negative cases were re-swept with widened notations and none broke (the extra hits
  were false positives: PTEN `R233X`, TP53 `I195`). That is reassurance, not a clean bill: for
  three of them the protein-level identity was inferred rather than looked up, so those sweeps are
  weaker than they look.
  **The structural problem:** proving absence by keyword search is unbounded. Notation space is
  open (cDNA, protein, rsID, legacy, genome coordinates) and prose descriptions ("the previously
  reported truncating variant in exon 10") are uncatchable by any notation list. `eval/README.md`
  already said a low match count is "suggestive, not proof," and the method was used as proof
  anyway. `hold_out_case.py` exists to make absence true **by construction**: verify *presence*
  (which search does reliably), then physically remove those articles. The negative-case builder
  found zero matches, concluded no hold-out was needed, and thereby inverted the one piece of
  logic that made the design sound.
- **What changed because of this:**
  1. `verify_spans.py` gained `subject_check()`, and `--fix` will now refuse rather than cement.
  2. Every domain row in `docs/RESULTS.md` gets a contamination note: the two baselines and the
     paired McNemar comparisons were graded against this set. See that file.
  3. The remediation plan for the cases themselves is a separate decision, taken with the user
     rather than applied unilaterally, since `CLAUDE.md` makes the eval set a discussion.
  4. The `created_by: agent:*` provenance field earned its place. It is what made this sample
     worth drawing, and the schema should keep `validated_by` / `validated_at_utc` next to it.

---

## Design decision: negative cases rebuilt by hold-out, not by failed search

- **Date / module:** M1 / phase A1 remediation (2026-09-04). Follows directly from the validation
  finding above; approach confirmed with the user before building.
- **Decision:** retire all 7 remaining search-built negative cases and replace them with 6 built by
  hold-out. The logic inverts: instead of searching for a variant, finding nothing, and asserting
  absence, pick a variant the corpus demonstrably **does** contain, verify that presence (which
  search does reliably), then physically remove the article. Absence becomes true by construction.
- **Alternatives considered:**
  - *Keep the 7, since they survived a widened notation sweep.* Rejected. They may each be fine,
    but their validity rests on a method now known to be unsound, and for 3 of them the
    protein-level notation was inferred rather than looked up, so the "widened" sweep was weaker
    than it looked. Keeping them would mean the negative stratum's trustworthiness rests on an
    argument the project has already refuted in writing.
  - *Drop negative cases entirely.* Rejected. Property 4 produced the sharpest single result the
    project has: no-retrieval fabricating a confident pathogenic classification for a variant the
    corpus does not contain.
- **How the pairs were found, and why guessing did not work.** The first attempt used famous
  founder variants, on the theory that a model most likely knows them from pretraining, which
  makes the strongest memorization test. That fails on arithmetic: BRCA1 185delAG appears in 89
  corpus articles, CHEK2 I157T in 70, BRCA2 6174delT in 73. Holding out 70-200 articles would
  remove a large, topically central slice of the corpus and silently change every other
  measurement in the project.
  So instead: mine every HGVS notation in the corpus, count document frequency, and keep
  notations appearing in exactly **one** article. Removing one article of 7,863 distorts nothing.
  **The real tension, worth stating rather than hiding:** the variants best suited to hold-out are
  rare, and a rare variant is one the model probably does not know either, which weakens the
  memorization half of what property 4 tests. Hold-out buys certainty of absence at the cost of
  some of the test's bite. That trade is worth making, because a case that is certainly valid and
  somewhat easy beats a case that is possibly invalid and looks hard, but the cost is real and
  these cases should not be described as a strong memorization test.
- **The mining tool made the same error the eval set had, which is the most useful thing that
  happened here.** It assigned each variant the nearest gene symbol in the paragraph. Reading the
  source for the 8 shortlisted candidates showed **4 were misattributed**: `c.2502_2503insA` is
  ATM, not BRCA2; `c.1919C>A` is PMS2, not PALB2; `c.5890A>G` is ATM, not BRCA1; `c.334C>T` is
  RAD51D/BARD1, not BRCA1. Proximity is not attribution. That is precisely the defect class the
  validation pass found in the hand-built cases, reproduced by a fresh tool within the hour, which
  is decent evidence it is a property of the task rather than of one careless agent. Every
  surviving case's gene attribution was read out of the source text by hand.
- **The 6 cases**, each verified to appear in exactly 1 corpus article before hold-out and 0 after:

  | Case | Gene | Variant | Condition | Held out |
  |---|---|---|---|---|
  | `brca1_c4484plus2t_c_prostate_neg_001` | BRCA1 | c.4484+2T>C | prostate | PMC12485378 |
  | `brca2_c9275a_g_ovarian_neg_001` | BRCA2 | c.9275A>G | ovarian | PMC13223255 |
  | `brca2_c8010g_c_prostate_neg_001` | BRCA2 | c.8010G>C | prostate | PMC12035019 |
  | `atm_c2502_2503insa_endometrial_neg_001` | ATM | c.2502_2503insA | endometrial | PMC9885574 |
  | `atm_c4777minus1g_c_pancreatic_neg_001` | ATM | c.4777-1G>C | pancreatic | PMC12295162 |
  | `tp53_c826_827gc_at_ovarian_neg_001` | TP53 | c.826_827GC>AT | ovarian | PMC5983728 |

- **Made re-checkable, which the old cases never were.** `eval/verify_negative_cases.py` rescans
  the corpus for every negative case's notation, confirms zero hits, confirms the claimed
  held-out article is in the registry and gone from the corpus, and **fails any case not built by
  hold-out**. Runs in about 9 seconds over the full corpus. The old cases rested on an agent's
  report of what it had searched; these rest on a check anyone can rerun.
  Residual limitation, stated plainly: this cannot prove no article discusses the same variant
  under a different name. No keyword method can. That is why hold-out, not search, is what makes
  the case sound; the script is a regression guard on the construction, not a proof of absence.
- **Corpus effect:** 7,863 to 7,857 articles (6 held out, all reversible via
  `hold_out_case.py --restore`). `corpus/manifest.csv` is untouched, per its role as the immutable
  Step 0b record. No held-out article is a gold-span source for any other case; checked before
  removing.
- **Case set is now 17** (4 disagreement, 7 ordinary, 6 negative), 12 dev / 5 held-out. Down from
  19, and further from `PROJECT_PLAN.md`'s 50-80 target than before. That is the correct direction
  anyway: the v4 audit already concluded that growing the answer set is a worse use of hours than
  building the n>=300 retrieval set, and a smaller set that is actually right beats a larger one
  that is half wrong.
- **Reversibility:** the hold-outs are fully reversible. The retired cases are archived in
  `eval/_archive/`, not deleted.

---

## Experiment: baselines re-run on the repaired case set; the direction finding does not survive

- **Date / module:** M1 / phase A1 remediation (2026-09-04). Closes the loop on the two entries
  above.
- **Prediction (written before the run, after the repairs were applied):** groundedness would hold
  up, since it is a large effect driven by a structural fact (no-retrieval has no spans to cite)
  that no gold-label defect could manufacture. Direction was expected to move somewhat, since two
  of the three repaired cases had gold that penalized correct answers, but the *shape* of the
  finding, retrieval not helping direction, was expected to survive.
- **Minimum detectable effect:** n=8 for direction, groundedness and disagreement; n=12 for
  not_found. At n=8 a paired McNemar test needs roughly 6 discordant pairs all falling one way to
  reach p<0.05. So this run can detect only very large, very consistent effects, and everything
  else it produces is inconclusive by construction. Known before running, not discovered after.
- **Method:** both baselines regenerated against the repaired 17-case set and scored on the 12-case
  dev split, judge and judge-prompt version unchanged from 2026-09-03, BM25 index rebuilt over the
  post-hold-out corpus (7,857 articles, 436,834 paragraphs). Only the gold labels and the
  negative-case construction differ.
- **Result:** rows in `RESULTS.md`, "Repaired-set rerun (12 dev cases), 2026-09-04."
  - groundedness 0% to 75%, paired delta +75pp, 6 of 8 cases flipping to pass and none the other
    way, **McNemar p=0.031**, up from p=0.062 on the defective set.
  - direction 25% vs 37.5%, paired delta +12pp, **three cases flip** (two to BM25, one to
    no-retrieval), McNemar p=1.000.
  - disagreement 0% vs 67% (n=3, p=0.500). not_found 91.7% both, failing on different cases.
- **Did the prediction hold?** Partially, and the half that failed is the important half.
  - *Held:* groundedness survived and strengthened, for exactly the structural reason predicted.
  - *Did not hold:* the direction finding's shape did not survive. The 2026-09-03 result was not
    merely "no significant difference," it was **12.5% vs 12.5% with zero cases flipping either
    direction**, which is a much stronger and more interesting observation, and it is the one
    quoted in the README and the v4 audit as the project's most interesting result. On the
    repaired set, three of eight cases flip. Zero-flips was partly an artifact of defective gold.
  - What replaces it is weaker and honest: at n=8, this eval set cannot tell whether retrieval
    helps direction. +12pp at p=1.000 is neither evidence of an effect nor evidence of its
    absence. The earlier confident negative was over-read from a set that was too small *and*
    partly wrong, and the smallness alone should have been enough to stop it being stated that
    confidently. The MDE discipline exists to catch exactly this and it was not applied to that
    claim when it was written.
- **A second result worth as much as the first: repairing gold roughly doubled measured direction
  quality on both baselines** (12.5% to 25%, and 12.5% to 37.5%). Two repaired cases had gold that
  marked correct answers wrong: one asserted cohort figures absent from the cited span, one
  attributed a BRCA2-only finding to both genes. The systems were being penalized for being right.
  A defective eval set understated system quality by about half on this property. Worth
  remembering next time a measured number here looks disappointing: check the ruler before
  concluding anything about the thing being measured.
- **The negative-case rebuild cost real test strength, as predicted in the entry above.** All four
  dev hold-out negatives pass `not_found` under both baselines. Building negatives from
  document-frequency-1 variants means the variant is rare enough that the model does not know it
  either, so no-retrieval refuses correctly instead of fabricating. The old set's sharpest single
  result, no-retrieval inventing a confident pathogenic classification for an absent variant, is
  not reproducible here. Property 4 now measures **retrieval restraint**, not memorization. The
  old result rested on a method known to be unsound so it was not safe to keep, but the honest
  accounting is that the replacement tests less, and recovering a real memorization test is an
  open item.
- **What changed because of this:**
  1. `RESULTS.md`'s answer-set rows are superseded, and the standing caveat now records that its
     own guess about which half of the finding would survive was half wrong.
  2. `README.md`'s headline claim needs rewriting; it currently quotes the superseded
     "12.5% either way, zero cases flipped" result.
  3. **Phase A3 (whole-document-in-context) gets more valuable, not less.** It was designed to
     separate a retrieval failure from a reading failure on the strength of the flat-direction
     result. That result is now uncertain, which makes the third baseline the thing that would
     actually settle it, at a depth n=8 cannot reach.
  4. A standing lesson for this project's own numbers: the strongest-sounding result in the repo
     was the one that did not survive contact with a validated eval set. Effect size and
     interestingness are not evidence.

---

## Design decision: package layout, retrieval split out of eval

- **Date / module:** repo-wide (2026-09-04), after the phase A1 work landed.
- **What prompted it:** `eval/` had reached 40 files at its top level (19 modules, 16 test files,
  5 data files) plus 6 subdirectories, with the tests interleaved alphabetically among the modules
  they test. It had also quietly become the home for things that are not evaluation: the BM25
  implementation, the IR metrics, and the corpus XML reader.
- **Decision:** three packages with a one-way dependency, `common <- retrieval <- eval`, and
  everything run as a module from the repo root.

  | Package | Holds | Depends on |
  |---|---|---|
  | `common/` | `corpus_text.py`: JATS XML to text, sections, the char-offset convention | nothing |
  | `retrieval/` | `bm25.py`, `ir_metrics.py`, `tests/` | `common` |
  | `eval/` | the harness: scorer, judge, baselines, case tooling, `data/`, `tests/` | `retrieval`, `common` |

  `ingestion/` and `service/` became packages too, for consistency and because `service/` will
  import `retrieval` in phase E.
- **Why retrieval leaves eval, which is the only interesting part of this:** the dependency
  direction is real and was invisible while BM25 lived under `eval/`. **Evaluation measures
  retrieval; retrieval does not know evaluation exists.** That boundary stops being cosmetic in
  phase D, when the chunker, embedder, hybrid fusion and reranker land, and in phase E, when
  `service/` imports the retriever to answer real requests. A service that has to import the
  evaluation harness to answer a query has the arrows pointing the wrong way.
- **Alternatives considered:**
  - *Move only tests and data into subfolders, leave modules flat.* Lowest risk and no import
    changes, but leaves 19 ungrouped modules and leaves retrieval filed under evaluation, which
    is the part that would have cost something later.
  - *Subpackages inside `eval/` (`caseset/`, `scoring/`, `retrieval/`, `common/`).* Most organized
    within `eval/`, but every module gains path-shim boilerplate and it still files retrieval
    under evaluation.
- **Why `python -m` from the repo root rather than scripts run in place:** the old layout needed
  `sys.path.insert(0, ...)` shims in `baselines/` and `benchmarks/` to reach across directories,
  and several tools only worked from a particular working directory. Running as modules deletes
  every shim (there are now none in the codebase) and makes behaviour independent of where you
  are standing. It costs a changed command line in every README, which is a one-time edit.
- **Verification, because a rename-only change is exactly where silent breakage hides:** all 19
  test modules pass, every CLI was re-run against the real corpus (`verify_spans`,
  `check_gold_claims`, `verify_negative_cases`, `split list`, `hold_out_case --list`, a SciFact
  benchmark run), and `compileall` is clean. Two bugs surfaced during the move and were fixed: an
  import shielded by a trailing `# noqa: E402` escaped the rewrite, and two subprocess-based tests
  were still invoking CLIs by file path from the wrong directory. Added `run_tests.py` at the repo
  root, which runs every test module by exit code, because the suite mixes `unittest` classes with
  hand-rolled `check()` scripts and `unittest discover` only sees half of them.
- **Path map for reading older entries in this log.** Entries above this one reference the
  pre-move paths and are left as written, since they were true when written:

  | Was | Now |
  |---|---|
  | `eval/corpus_text.py` | `common/corpus_text.py` |
  | `eval/bm25.py`, `eval/ir_metrics.py` | `retrieval/` |
  | `eval/answer_cases.jsonl`, `eval/dev_held_out_split.csv` | `eval/data/` |
  | `eval/test_*.py` | `eval/tests/`, or `retrieval/tests/` for bm25 and ir_metrics |
  | `python score.py ...` | `python -m eval.score ...` |

- **Reversibility:** cheap in principle (the moves are renames and the import rewrite was
  mechanical), but there is no reason to: nothing about the old layout was load-bearing.
