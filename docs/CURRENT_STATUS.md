# Current status

Updated 2026-09-09. Active plan: PROJECT_PLAN.md v5. This is the only current checklist.

## Implemented

- [x] PMC ingestion, canonical source offsets, structure-aware and paragraph chunkers, BM25.
- [x] Retrieval FastAPI service and offline baseline/scorer harness.
- [x] Opt-in `/answer`: shared runtime helpers, strict output/citation validation, bounded context
  and async provider call, per-process admission, outcome logs and offline failure tests.
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
| Scorer validity | Model-supplied claims may omit factual text; judge calibration remains incomplete; CIs are query-level. | Agree claim coverage rubric, calibrate with humans, add clustered paired analysis before quality claims. |
| Historical reproduction | Earlier runs overwrote inputs/outputs under shared filenames. | Treat preserved files as the surviving record, not exact reconstructions of every historical row. |
| Fresh environment | CI is authored; remote CI and fresh dependency installation have not run in this session. | Run workflow after review/push; use documented fixture tests locally. |
| Exact source restoration | Latest-version ingestion is not an exact snapshot downloader; old source versions may differ. | Add manifest-driven exact-version restore with hash verification before deleting current corpus. |
| Runtime generation | Offline-tested synthesis is implemented; live behavior and quality remain unvalidated. | Preregister a small provider smoke/quality check with an explicit quota budget. |
| Usable workflow | Evidence viewer/export and user observations are not implemented. | Build one researcher evidence-brief flow after runtime contract is agreed. |
| Serving limits | Answer admission is per process; retrieval is unbounded, disconnect detection is deferred, retrieval logs retain queries. | Add pilot auth/global quota, retrieval admission, retention and end-to-end load tests. |
| Product validation | No observed researcher task completion or deployment destination established. | Observe target researchers, choose a private pilot and deployment constraints. |
| Measurements | New code changes invalidate direct reuse of previous performance/quality claims. | Preregister prediction/MDE and run new immutable baseline/load experiments after labels are ready. |

No new benchmark or performance claim was published in this implementation. Do not call the
foundation a completed product. Milestones 2-5 and optional labs remain open.

## Validation of this implementation

`vader_env`: `python -m unittest discover` passed 353 tests. `git diff --check` passed.
All 32 preserved historical files and the 18-query diagnostic subset matched their manifests.
No paid inference, full-corpus benchmark, public deployment or fresh-environment installation ran.
The tests exercise synthetic source/index builds, including source hash rejection, exclusions,
strict model booleans, invalid citation denominators and missing-answer release admission.

Runtime validation used synthetic XML and mocked provider HTTP responses. Tests cover invalid
citations/types, contradictory abstention, no context, provider rate limits without retry,
truncated/oversized responses, total provider timeout, admission and task cancellation. No live
API call was made. Existing Starlette emits a TestClient/httpx deprecation warning; dependency
migration can follow separately from this runtime change.
