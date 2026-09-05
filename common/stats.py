"""
The two interval estimators this project keeps needing, in one place.

CLAUDE.md's rule: every number written to docs/RESULTS.md carries a git SHA,
a config hash, a 95% CI, and an n. So every module that produces a number
needs an interval, and by 2026-09-05 three of them had grown their own copy:
wilson_ci in eval/score.py and again in eval/make_case_worksheet.py, and two
bootstraps in retrieval/ir_metrics.py and service/loadtest.py that differed
only in which statistic they resampled.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Sequence


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion. Used instead of
    the normal approximation because the rule above gets applied here at n as
    small as 4, where the normal approximation can produce a nonsense
    interval (below 0 or above 1); Wilson stays valid at small n and exactly
    at p=0 or p=1."""
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def bootstrap_ci(values: Sequence[float], statistic: Callable[[Sequence[float]], float] = _mean,
                 n_resamples: int = 2000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap interval for `statistic` over `values`. Seeded,
    so a reported interval is reproducible from the same inputs.

    `statistic` defaults to the mean (per-query IR scores); pass a percentile
    function for a latency percentile. Resampling the statistic you actually
    report is the point: a CI on the mean says nothing about the p95."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    stats = [statistic([values[rng.randrange(n)] for _ in range(n)]) for _ in range(n_resamples)]
    stats.sort()
    lo = stats[int((alpha / 2) * n_resamples)]
    hi = stats[min(n_resamples - 1, int((1 - alpha / 2) * n_resamples))]
    return lo, hi
