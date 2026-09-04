# VaDER

**Variant-Disease Evidence Retriever**

A biomedical literature RAG and agent system, scoped to cancer genomics: given a gene or variant, retrieve what the literature reports about its role in a disease, with citations to the exact supporting passage.

This is a hands-on production AI-engineering project meant for me to not only build the system,
but to understand the practice around it too: evaluation methodology, error analysis, guardrails, observability, latency and cost engineering, caching, and deployment. Every number this project reports comes with a confidence interval, a sample size, and the reproducable code and config.

## Status

**Step 0 done. Tier 1 in progress (M1 mostly built, phase A of the v4 execution order next).**

Task contract: variant-disease evidence retrieval, scoped to cancer genomics
(`docs/TASK_CONTRACT.md`). Corpus: 7,863 PMC Open Access full-text articles, snapshot 2026-08-30.
A FastAPI service is up and measured (`service/`), still wrapping a deliberately trivial stub
handler. The eval harness exists and has produced real numbers: a four-property scorer with an LLM
judge, a hand-built BM25 over 437k paragraphs, two baselines run and compared with a paired
McNemar test, and an enforced dev/held-out split (`docs/RESULTS.md`).

**The headline number, and the story behind it, is the honest advertisement for this project.**
Retrieval buys real groundedness: 0% to 75%, +75 points paired, McNemar p=0.031 at n=8. Whether it
helps the model report the *direction* of an association correctly is, at this sample size,
unknown: +12 points, p=1.000.

That second sentence used to read "buys nothing at all, 12.5% either way, zero cases flipped."
Then a human validation pass over 8 of the 19 eval cases found **4 of them defective**, including
one where the tool meant to verify gold spans had itself repointed a span onto a paragraph about a
different variant. After repairing the set, three cases flip where none had before, and the
confident negative result evaporated. Repairing the gold labels also roughly doubled both
baselines' measured direction scores, because two cases had been marking correct answers wrong.

The most interesting result in the repo was the one that did not survive contact with a validated
eval set. That is written up rather than quietly corrected: see `docs/DECISION_LOG.md`'s phase A1
entries and the standing caveat in `docs/RESULTS.md`. `docs/START_HERE.md` has current status.

## Why this exists

I want to do a production-esque AI engineering project that covers issues outside of just implementing RAG and a vector database: catching failures before users do, knowing whether an output is right, tracing a bad answer to its root cause, keeping latency and cost under control, and making deliberate tradeoffs instead of copying a tutorial's defaults.

## Layout

```
docs/         Project plan, decisions, results, and reference material
ingestion/    Corpus pull: PMC Open Access full text via E-utilities and S3
service/      Step 0c: FastAPI measurement surface (stub handler, see docs/DECISION_LOG.md)
```
