# retrieval/

Retrieval implementations and the metrics that score them.

Split out of `eval/` on 2026-09-04. The reason is a dependency direction: **eval measures
retrieval, retrieval does not know eval exists.** While BM25 lived under `eval/`, that boundary was
invisible, and it stops being a detail in phase D, when the chunker, embedder, hybrid fusion and
reranker land here and `service/` starts importing them to answer real requests. `service/` should
depend on retrieval; it should never depend on the evaluation harness.

```
retrieval/
  bm25.py         hand-built Okapi BM25, no ranking library
  ir_metrics.py   recall@k, MRR, nDCG@k, query-level bootstrap CI
  tests/
```

Depends on `common/` (corpus access) and nothing else in the project.

## bm25.py

Okapi BM25 written from scratch, satisfying `PROJECT_PLAN.md`'s rule to implement at least one
component with no library. The formula, the `+1` IDF variant and the choice of textbook
`k1=1.5, b=0.75` are all derived in the module docstring.

Two ways in, deliberately separate:

- `build_index(xml_dir, pmcids)` indexes the PMC corpus at paragraph granularity, every record
  carrying real `(pmcid, section, char_start, char_end)` provenance, so a hit is a citable span
  rather than a bare document id.
- `build_index_from_texts([(doc_id, text), ...])` indexes anything else. This is what lets the
  BEIR validation run score through the *identical* scoring code rather than a reimplementation
  that could agree with the published reference while the real one disagrees.

Both funnel into `index_from_paragraphs`, which is where the scoring-side construction actually
happens.

## ir_metrics.py

Hand-written, no IR library, with the definitions spelled out in the docstring because the details
are where these go wrong. Two choices worth knowing before reading a number out of it:

- A query with no relevant documents is **undefined** for recall and nDCG, and is dropped from the
  mean rather than scored 0 or 1. Either default would misreport a query no system could answer.
- Unjudged retrieved documents count as gain 0, the standard BEIR treatment, which penalizes a
  system for surfacing good-but-unjudged results. That is a property of the benchmark, not of the
  retriever.

`evaluate()` returns each metric with its own CI **and its own `n`**, because those `n`s differ.

## What the metrics are worth: validated against BEIR

Running this BM25 over SciFact and NFCorpus lands nDCG@10 at 90% and 89% of the published
Pyserini multi-field BM25 reference, well clear of the 60%-of-reference bug threshold registered
before the run. Numbers in `docs/RESULTS.md`, method and the sub-predictions that missed in
`docs/DECISION_LOG.md`.

The most instructive number there is NFCorpus MRR 0.505 against recall@10 0.135 on the identical
ranking. Not a contradiction: at 38 relevant documents per query, surfacing one high is easy and
capturing a meaningful share of them in ten slots is arithmetically near-impossible. Either number
alone misdescribes the retriever, which is the argument for reporting the family together.

```
python -m eval.benchmarks.run_benchmark --dataset scifact
python -m retrieval.tests.test_bm25
python -m retrieval.tests.test_ir_metrics
```
