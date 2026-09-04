"""
Retrieval metrics: recall@k, MRR, nDCG@k, and a query-level bootstrap CI.
Hand-written, no IR library, same rule eval/bm25.py was built under
(PROJECT_PLAN.md, "implement at least one component with no library").

Definitions, written out because the details are where these go wrong:

  recall@k   |relevant docs in the top k| / |relevant docs that exist|.
             Binary: any judged relevance > 0 counts. Undefined when a query
             has no relevant docs at all, and such queries are DROPPED from
             the mean rather than scored 0 or 1, either of which would be a
             silent lie about a query that cannot be answered.

  MRR        1 / (rank of the first relevant doc), 1-indexed, 0 if none of
             the retrieved docs is relevant. Reported over the full ranking
             unless a cutoff is passed.

  nDCG@k     DCG@k / IDCG@k, with the standard graded gain

                 DCG@k = sum over i in 1..k of rel_i / log2(i + 1)

             and IDCG@k the same sum over the best possible ordering of the
             judgments this query actually has. Graded relevance is used as
             given (NFCorpus judges 0-2), which is why nDCG and recall can
             disagree about which system is better: nDCG cares that a
             relevance-2 doc outranks a relevance-1 doc, recall does not.
             Note the convention: unjudged retrieved docs count as gain 0,
             the standard BEIR treatment, which penalizes a system that
             surfaces good-but-unjudged documents. That is a property of the
             benchmark, not of the retriever.

  A note on the ceiling. IDCG@k is computed from the judged relevances only,
  so a query with 38 relevant docs (NFCorpus's average) has an IDCG@10 built
  from its 10 best judgments, and nDCG@10 = 1.0 is attainable. A query with
  1 relevant doc (SciFact's average) has IDCG@10 = that one gain at rank 1.
  This is why the two datasets' numbers are not comparable to each other,
  only each to its own published reference.

Bootstrap CIs resample QUERIES, not judgments: the unit of independent
observation is a query, and RESULTS.md requires an interval and an n on
every number.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass
class QueryResult:
    """One query's retrieved ranking plus its judgments.

    `retrieved` is doc ids in rank order, best first. `judgments` maps doc id
    to graded relevance; a doc id absent from it is unjudged, treated as 0.
    """
    query_id: str
    retrieved: list[str]
    judgments: dict[str, int]

    def n_relevant(self) -> int:
        return sum(1 for rel in self.judgments.values() if rel > 0)


def recall_at_k(result: QueryResult, k: int) -> float | None:
    """None when the query has no relevant documents: undefined, not zero."""
    total = result.n_relevant()
    if total == 0:
        return None
    hits = sum(1 for doc_id in result.retrieved[:k] if result.judgments.get(doc_id, 0) > 0)
    return hits / total


def reciprocal_rank(result: QueryResult, k: int | None = None) -> float:
    ranking = result.retrieved if k is None else result.retrieved[:k]
    for rank, doc_id in enumerate(ranking, start=1):
        if result.judgments.get(doc_id, 0) > 0:
            return 1.0 / rank
    return 0.0


def dcg(gains: list[float]) -> float:
    return sum(gain / math.log2(i + 1) for i, gain in enumerate(gains, start=1))


def ndcg_at_k(result: QueryResult, k: int) -> float | None:
    """None when the query has no relevant documents (IDCG would be 0 and the
    ratio undefined)."""
    gains = [float(result.judgments.get(doc_id, 0)) for doc_id in result.retrieved[:k]]
    ideal = sorted((float(r) for r in result.judgments.values() if r > 0), reverse=True)[:k]
    idcg = dcg(ideal)
    if idcg == 0:
        return None
    return dcg(gains) / idcg


def mean_ignoring_none(values: list[float | None]) -> tuple[float, int]:
    """Returns (mean, n), where n counts only the queries the metric was
    actually defined on. Reporting that n matters: a mean over 290 of 300
    queries is a different claim than a mean over 300."""
    defined = [v for v in values if v is not None]
    if not defined:
        return 0.0, 0
    return sum(defined) / len(defined), len(defined)


def bootstrap_ci(values: list[float], n_resamples: int = 2000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap over per-query scores. Seeded, so a reported
    interval is reproducible from the same per-query values."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int((alpha / 2) * n_resamples)]
    hi = means[min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))]
    return lo, hi


@dataclass
class MetricSummary:
    name: str
    value: float
    ci_low: float
    ci_high: float
    n: int


def evaluate(results: list[QueryResult], ks: tuple[int, ...] = (5, 10, 100),
             ndcg_k: int = 10, seed: int = 0) -> list[MetricSummary]:
    """Every metric over the same set of queries, each with its own bootstrap
    CI and its own n (queries where a metric is undefined are excluded from
    that metric only, not from the whole run)."""
    summaries: list[MetricSummary] = []

    for k in ks:
        per_query = [recall_at_k(r, k) for r in results]
        mean, n = mean_ignoring_none(per_query)
        lo, hi = bootstrap_ci([v for v in per_query if v is not None], seed=seed)
        summaries.append(MetricSummary(f"recall@{k}", mean, lo, hi, n))

    per_query_ndcg = [ndcg_at_k(r, ndcg_k) for r in results]
    mean, n = mean_ignoring_none(per_query_ndcg)
    lo, hi = bootstrap_ci([v for v in per_query_ndcg if v is not None], seed=seed)
    summaries.append(MetricSummary(f"ndcg@{ndcg_k}", mean, lo, hi, n))

    per_query_rr = [reciprocal_rank(r) for r in results]
    mean, n = mean_ignoring_none(per_query_rr)
    lo, hi = bootstrap_ci(per_query_rr, seed=seed)
    summaries.append(MetricSummary("mrr", mean, lo, hi, n))

    return summaries
