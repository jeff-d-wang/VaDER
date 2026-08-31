# VaDER

**Variant-Disease Evidence Retriever**

A biomedical literature RAG and agent system, scoped to cancer genomics: given a gene or variant, retrieve what the literature reports about its role in a disease, with citations to the exact supporting passage.

This is a hands-on production AI-engineering project meant for me to not only build the system,
but to understand the practice around it too: evaluation methodology, error analysis, guardrails, observability, latency and cost engineering, caching, and deployment. Every number this project reports comes with a confidence interval, a sample size, and the reproducable code and config.

## Status

**Step 0, nearly done.** Task contract: variant-disease evidence retrieval, scoped to cancer genomics (see `docs/TASK_CONTRACT.md`). The corpus is pulled: 7,863 PMC Open Access full-text articles, cancer-genomics variant-disease net, snapshot 2026-08-30. A FastAPI service is up and measured (`service/`), wrapping a deliberately trivial stub handler since v1 turned out not to exist in this repo; see `docs/DECISION_LOG.md` for both calls. What remains before Tier 1: decide whether to locate v1 or drop it, then start the eval harness (M1).

## Why this exists

I want to do a production-esque AI engineering project that covers issues outside of just implementing RAG and a vector database: catching failures before users do, knowing whether an output is right, tracing a bad answer to its root cause, keeping latency and cost under control, and making deliberate tradeoffs instead of copying a tutorial's defaults.

## Layout

```
docs/         Project plan, decisions, results, and reference material
ingestion/    Corpus pull: PMC Open Access full text via E-utilities and S3
service/      Step 0c: FastAPI measurement surface (stub handler, see docs/DECISION_LOG.md)
```
