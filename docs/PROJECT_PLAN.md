# VaDER implementation plan

Version 5, adopted 2026-09-09 after the repository review. This replaces the v3 module list and
v4 execution order. Historical plans remain in the local docs archive; historical results remain
in RESULTS.md. The current implementation checklist is CURRENT_STATUS.md.

## Goal and scope

Help a cancer-genomics researcher prepare an auditable evidence brief for a variant and condition.
Retrieve from a named PMC OA snapshot, expose supporting source passages, distinguish evidence
from uncertainty, and let the researcher inspect and correct the output. User benefit is a
hypothesis until observed in real tasks. Clinical decisions for individuals remain out of scope.

## Milestones and exit criteria

| Milestone | Work | Exit evidence |
|---|---|---|
| 1. Trustworthy foundation | Current setup/docs; complete environment; offline CI; typed outputs; explicit dataset releases; immutable runs; corpus provenance. | A fresh environment runs tests; rejected inputs cannot silently enter release scoring; a new result retains its exact evidence. |
| 2. One usable workflow | Shared runtime generation, evidence viewer/export, bounded context/retries, source links, ambiguity and error states. | A researcher completes the stated task and can inspect every claim. |
| 3. Representative evaluation | Human-reviewed user questions, calibrated judge, multiple acceptable spans, separate challenge/regression sets, clustered paired comparisons. | Frozen report with correctness, coverage, citation support, abstention and availability. |
| 4. One measured improvement | Choose a failure bucket; compare normalization, retrieval or context changes one at a time. | Preregistered paired result with uncertainty, cost and latency tradeoffs; explicit keep/revert decision. |
| 5. Small operated pilot | Simple deployment, bounded concurrency, safe logs, readiness, rollback, feedback and one alert. | Load and recovery evidence; a real feedback item becomes a regression test. Basic protections begin in milestone 2. |

MCP, agent workflows, dense retrieval, ANN tuning, Spark and Kubernetes are optional learning labs.
Each needs a named question and a stopping rule. A learning lab need not become a runtime
product dependency. Do not defer basic deployment hygiene until an orchestration exercise.

## Engineering rules

- Keep source-span provenance `(pmcid, section, char_start, char_end)` independent of chunk IDs.
- Runtime depends on common/retrieval, not on gold labels or the judge. Shared generation
  lives in common. Keep the three baselines as controls.
- Log design decisions before implementation. Log a prediction, effect of interest and justified
  minimum detectable effect before a performance or quality experiment. Synthetic regression
  checks are tests, not experiments. No outcome is required to make a good story.
- Discuss scorer meaning and the failure taxonomy with the user. The approved release rules are:
  invalid citations remain failures in the denominator; missing answers fail release admission;
  rejected cases cannot be scored; unreviewed cases require explicit exploratory mode.
- Keep capability challenges, representative user evaluation and regression suites separate.
  Do not gate the representative set on BM25 ranking success. Resample paired queries together,
  by source article when needed. A query count does not by itself establish statistical power.
- Publish only measured, attributable claims. Every RESULTS.md measurement carries code/config
  provenance, a 95% interval and n. Inventory counts and test counts are not quality estimates.
- Store effective config, input hashes and raw outputs with each new run. Historical overwritten
  artifacts cannot be reconstructed by inventing missing metadata.
- Preserve completed human reviews. Generated templates are caches; human labels and actual model
  outputs are evidence. Keep a corpus license/version record with exported content.
- Keep implementation minimal. Direct provider calls for single-shot RAG. No Pinecone, managed
  vector database or LangChain chains for the single-shot path.

## Product validation

Observe a few target researchers using their existing literature workflow and the proposed brief.
Record time to a useful brief, omitted important evidence, material corrections and return usage.
These sessions discover needs; they are not a powered market validation study. Show corpus scope
and date. 'No supporting evidence retrieved' does not mean 'no association exists'.

Do not collapse effect magnitude, evidence quality and model confidence into one field. An initial
brief should show study context, reported effect, exact source passage and uncertainty. Add fields
only when their extraction and interpretation are reviewed.

## Definition of a showcase release

A reproducible small system, a short demo, a calibrated baseline comparison, one attributable
improvement, one instructive failure, and a documented operational limit. Optional labs can remain
unfinished. See CURRENT_STATUS.md for remaining work and blockers.
