# Current status

Updated 2026-09-10. Active plan: PROJECT_PLAN.md v5. This is the only current checklist.

## Implemented

- [x] PMC ingestion, canonical source offsets, structure-aware and paragraph chunkers, BM25.
- [x] Retrieval FastAPI service and offline baseline/scorer harness.
- [x] Opt-in `/answer`: shared runtime helpers, strict output/citation validation, bounded context
  and async provider call, per-process admission, outcome logs and offline failure tests.
- [x] Hybrid claim-coverage contract: runtime display text derives from canonical claims;
  historical and baseline prose uses separate human factual-unit annotations. Release scoring
  requires those annotations and keeps coverage separate from groundedness.
- [x] Historical evidence snapshot: 32 worksheet/output files copied verbatim with hashes into
  `eval/artifacts/legacy-20260909/`. Retired index hash recorded; obsolete binary removed.
- [x] Old plan/status preserved locally; sanitized public plan, task and architecture written.
- [x] Root pinned direct dependencies, conda environment definition and offline CI workflow.
- [x] Strict boolean model fields; invalid citations retained as unsupported claims.
- [x] Release admission rejects rejected cases and missing answers; explicit exploratory mode
  permits unreviewed inputs. Retrieval scoring requires an explicit dataset path.
- [x] Reviewed retrieval subset released from existing human verdicts, with content manifest.
  This is a small diagnostic subset, not a representative or adequately powered product test.
- [x] Unique run output snapshots, full git SHA/source fingerprint and case/index hashes in the
  retrieval and baseline configurations. Historical collisions remain historical, not repaired.
- [x] Ingestion resume preserves version/license fields and verifies saved hashes; atomic XML
  and manifest replacement. Explicit evaluation exclusions applied when building service indexes.
- [x] Cooperative BM25 deadline checks and bounded top-k selection, with ranking regressions.

## Blockers and next steps

| Area | Blocker or remaining work | Next action |
|---|---|---|
| Representative evaluation | Existing reviews are small and incomplete; synthetic selection favors BM25. | Review real researcher questions and pooled supporting spans with the user. Do not enlarge unreviewed gold. |
| Scorer validity, deferred to M3 | Hybrid coverage rules and 60 human grounding labels are frozen. Judge calibration was deliberately deferred because the worksheet mixes historical and current generators; existing historical outputs still lack coverage annotations; CIs are query-level. This does not block M2. | Calibrate only when a representative current-system set needs automated scoring. Before then, use small human-labeled current-runtime regressions for generation changes. |
| Historical reproduction | Earlier runs overwrote inputs/outputs under shared filenames. | Treat preserved files as the surviving record, not exact reconstructions of every historical row. |
| Fresh environment | CI is authored; remote CI and fresh dependency installation have not run in this session. | Run workflow after review/push; use documented fixture tests locally. |
| Exact source restoration | Latest-version ingestion is not an exact snapshot downloader; old source versions may differ. | Add manifest-driven exact-version restore with hash verification before deleting current corpus. |
| Runtime generation | Offline-tested synthesis is implemented; live behavior and quality remain unvalidated. | Preregister a small provider smoke/quality check with an explicit quota budget. |
| Usable workflow | Evidence viewer/export and user observations are not implemented. The runtime contract is agreed and offline-tested. | Build one researcher evidence-brief flow with inspectable claim spans and an export, then observe a target user completing the task. |
| Serving limits | Answer admission is per process; retrieval is unbounded, disconnect detection is deferred, retrieval logs retain queries. | Add pilot auth/global quota, retrieval admission, retention and end-to-end load tests. |
| Product validation | No observed researcher task completion or deployment destination established. | Observe target researchers, choose a private pilot and deployment constraints. |
| Measurements | New code changes invalidate direct reuse of previous performance/quality claims. | Preregister prediction/MDE and run new immutable baseline/load experiments after labels are ready. |

No new benchmark or performance claim was published in this implementation. Do not call the
foundation a completed product. Milestones 2-5 and optional labs remain open.

## Validation of this implementation

`vader_env`: `python -m unittest discover` passed 362 tests. `git diff --check` passed.
All 32 preserved historical files and the 18-query diagnostic subset matched their manifests.
No paid inference, full-corpus benchmark, public deployment or fresh-environment installation ran.
The tests exercise synthetic source/index builds, including source hash rejection, exclusions,
strict model booleans, invalid citation denominators and missing-answer release admission.

Runtime validation used synthetic XML and mocked provider HTTP responses. Tests cover invalid
citations/types, contradictory abstention, no context, provider rate limits without retry,
truncated/oversized responses, total provider timeout, admission and task cancellation. No live
API call was made. Existing Starlette emits a TestClient/httpx deprecation warning; dependency
migration can follow separately from this runtime change.

Hybrid coverage validation checks canonical runtime rendering, critical-omission thresholds,
human annotation types and references, and release refusal when coverage labels are absent.
Historical answer files remain unchanged. The 12-pair grounding rubric pilot is complete and is
excluded from the frozen 60-pair final worksheet. Human coverage annotation and the automated
judge comparison have not yet run.
