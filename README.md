# VaDER

**Variant-Disease Evidence Retriever**

A biomedical literature RAG and agent system, scoped to cancer genomics: given a gene or variant,
retrieve what the literature reports about its role in a disease, with citations to the exact
supporting passage.

This is a hands-on production AI-engineering project meant for me to not only build the system,
but to understand the practice around it too: evaluation methodology, error analysis, guardrails, 
observability, latency and cost engineering, caching, and deployment. Every number this project 
reports comes with a confidence interval, a sample size, and the reproducable code and config.

## Status

**Step 0, in progress.** The task contract is finalized: variant-disease evidence retrieval,
scoped to cancer genomics (see `docs/TASK_CONTRACT.md`). The corpus is pulled: 7,863 PMC Open
Access full-text articles, cancer-genomics variant-disease net, snapshot 2026-08-30 (see
`docs/DECISION_LOG.md`). Next is the FastAPI serving layer, then a full end-to-end run of the
existing v1.

See `docs/START_HERE.md` for the current checklist and `docs/PROJECT_PLAN.md` for the full plan.

## Why this exists

Most RAG demos wire up a vector database and stop. The part that actually differentiates
production AI engineering work is everything around that: catching failures before users do,
knowing whether an output is right, tracing a bad answer to its root cause, keeping latency and
cost under control, and making deliberate tradeoffs instead of copying a tutorial's defaults.
This project builds that discipline against a real, narrow, well-defined task rather than a
generic chatbot.

## Layout

```
docs/         Project plan, decisions, results, and reference material
ingestion/    Corpus pull: PMC Open Access full text via E-utilities and S3
```

This README will be replaced with the real Tier 1 milestone artifact (architecture diagram,
measured numbers, baselines, failure analysis) once that exists. Until then, an honest
"in progress" is more useful than a description of a system that isn't built yet.
