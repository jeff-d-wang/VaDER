# AGENTS.md

VaDER is a hands-on production AI-engineering learning project: a biomedical literature RAG/agent
system (variant-disease evidence retrieval, cancer genomics), used to learn evaluation, error
analysis, guardrails, observability, latency/cost engineering, caching, deployment, and
monitoring. It is not a demo to ship; it is a vehicle for producing real measured numbers.

## Every session, before anything else

Read `docs/START_HERE.md`. It is the entry point: doc map, current status, and the standing rules
in full. Do not skip it because you read it last time; it is kept current and this file is not.

Do not duplicate `docs/START_HERE.md`'s status checklist or standing rules here. If you find
yourself updating status in this file, update the checklist there instead.

## Environment

Use the `vader_env` conda environment for everything Python in this project: running scripts,
tests, the service, ad hoc checks. Not the base environment. Either activate it
(`conda activate vader_env`) or invoke its interpreter directly
(`/Users/jeffwang/miniforge3/envs/vader_env/bin/python`). This keeps what you test against the
same as what the user tests against, so a package that's present for one and missing for the
other doesn't produce a false pass or a false failure. If a script needs a package that isn't in
`vader_env`, install it there (`vader_env`'s pip, not the base environment's) and say so, don't
silently work around a missing dependency in a different environment.

## Non-negotiable, every session

- Never merge a diff you can't explain line by line.
- Log a design decision in `docs/DECISION_LOG.md` before building it, and a prediction plus
  minimum detectable effect before running an experiment. Never after.
- Labels attach to source spans (`pmcid`, `section_id`, `char_start`, `char_end`), never to
  chunks. This is a schema decision, not a later cleanup.
- Every number written to `docs/RESULTS.md` carries a git SHA, a config hash, a 95% CI, and an
  `n`. No bare point estimates.
- Have the eval scorer and failure taxonomy be a discussion with the user, not a handoff. They
  are the intellectual core of the project.
- Do not skip to writing pipeline code (chunker, retriever, agent) before the eval harness and
  instrumentation spine exist. See `docs/PROJECT_PLAN.md` for why (Tier 1, M1/M2).
- Do not introduce Pinecone, LangChain chains for the single-shot RAG path, or a managed vector
  DB. These were deliberately rejected; see `docs/DECISION_LOG.md`.

## Writing style, in code and docs

No em-dashes. No other AI-writing tics either: no "not just X, but Y" contrastive framing used as
a crutch, no rule-of-three lists padded for rhythm, no filler intensifiers ("genuinely," "the key
thing is"). Write plainly, short sentences, and let periods and commas do the work an em-dash
would have done.
