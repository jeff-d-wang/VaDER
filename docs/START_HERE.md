# Start here

Read this at the beginning of every session. The active plan is [PROJECT_PLAN.md](PROJECT_PLAN.md).
The single implementation checklist and blockers live in [CURRENT_STATUS.md](CURRENT_STATUS.md).
The v3/v4 plan, superseded status and critiques are preserved locally in `docs/_archive/2026-09-09/`.
Do not follow their old execution order or treat their numbers as current.

## Doc map

| Document | Purpose |
|---|---|
| PROJECT_PLAN.md | Adopted milestones, engineering rules and showcase scope |
| CURRENT_STATUS.md | What exists, what is blocked and what to do next |
| TASK_CONTRACT.md | Public task, corpus and output boundary |
| ARCHITECTURE.md | Current dependencies and data flow |
| RESULTS.md | Append-only historical measurements, including caveats |
| DECISION_LOG.md | Decisions before building and experiments before running |
| GLOSSARY.md, CONCEPTS.md | Local learning notes |

## Standing rules

1. Never merge a diff you cannot explain line by line.
2. Discuss scorer design and the failure taxonomy with the user. Do not invent human labels.
3. Log design decisions before implementation; predictions and minimum detectable effects before
   experiments. An inconclusive result is not a null effect.
4. Every measurement in RESULTS.md needs a git SHA, effective config hash, 95% interval and n.
5. Labels attach to source spans, never chunks. Preserve the canonical text/offset convention.
6. Complete the foundation and usable slice before optional learning labs. The adopted v5
   milestones replace the former hard Tier 1/Tier 2 ordering.
7. Update public status and README at milestone boundaries. Do not duplicate the status checklist.
8. Time-box work that produces no usable artifact or answer after about two weeks; log the choice.
9. Budget ceiling remains $75-100/month. No paid experiment without preregistration. Free-tier
   observations are not an estimate of commercial serving cost.
10. Nothing goes on a resume until real, measured and confirmed. Keep historical caveats visible.
11. No em dashes or filler prose in code and docs.
12. Use `/Users/jeffwang/miniforge3/envs/vader_env/bin/python` or activate `vader_env` for Python.

The most recent scorer discussion froze the text-span grounding rubric and approved hybrid claim
coverage. Judge calibration is deferred to milestone 3 because the current worksheet mixes
generator versions; it does not block the milestone 2 evidence-brief workflow. Human coverage
annotations, clustered inference and representative gold remain open for later evaluation.
