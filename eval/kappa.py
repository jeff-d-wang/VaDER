"""
Cohen's kappa (unweighted and linearly-weighted), for calibrating the
scorer's judge against a real human rater. PROJECT_PLAN.md M1: "Measure
Cohen's kappa between judge and you on a sample... Re-label a 20-case
sample a week later to get your own self-agreement ceiling; no judge can
beat it. If kappa comes back low, the rubric is underspecified, not the
judge."

Two forms, both implemented since the rubric's ratings are ordinal
(pass > partial > fail), not nominal:
  - Unweighted: any disagreement counts the same, pass-vs-fail is as bad
    as pass-vs-partial. The textbook default, reported for comparability.
  - Linearly weighted: a pass-vs-partial disagreement counts as a smaller
    miss than pass-vs-fail. More appropriate for this rubric's 3-tier
    scale and the one actually worth trusting; report both, prefer this
    one when they disagree on the verdict ("kappa is fine" vs "it isn't").
"""
from __future__ import annotations

from collections import Counter

CATEGORIES = ["fail", "partial", "pass"]  # ordinal order, fail=0 .. pass=2
_INDEX = {c: i for i, c in enumerate(CATEGORIES)}

# Rough, textbook (Landis & Koch 1977) interpretation bands. A guide for
# reading the number, not a pass/fail gate on their own.
_BANDS = [
    (0.00, "no better than chance / slight"),
    (0.20, "fair"),
    (0.40, "moderate"),
    (0.60, "substantial"),
    (0.80, "almost perfect"),
]


def interpret(kappa: float) -> str:
    label = _BANDS[0][1]
    for threshold, name in _BANDS:
        if kappa >= threshold:
            label = name
    return label


def cohens_kappa(ratings_a: list[str], ratings_b: list[str], weighted: bool = False) -> float:
    """Both lists are same-length, same-order labels (one per case) from
    two raters, values in CATEGORIES. Returns NaN (as float('nan')) only in
    the degenerate case where chance agreement is already 1.0 (both raters
    used exactly one, the same, category throughout, no information)."""
    if len(ratings_a) != len(ratings_b):
        raise ValueError(f"rating lists must be the same length: {len(ratings_a)} vs {len(ratings_b)}")
    n = len(ratings_a)
    if n == 0:
        raise ValueError("no ratings to compare")

    k = len(CATEGORIES)

    def weight(i: int, j: int) -> float:
        if not weighted:
            return 1.0 if i == j else 0.0
        return 1.0 - abs(i - j) / (k - 1)

    counts_a = Counter(ratings_a)
    counts_b = Counter(ratings_b)

    po = sum(weight(_INDEX[a], _INDEX[b]) for a, b in zip(ratings_a, ratings_b)) / n
    pe = sum(
        weight(_INDEX[ca], _INDEX[cb]) * (counts_a.get(ca, 0) / n) * (counts_b.get(cb, 0) / n)
        for ca in CATEGORIES for cb in CATEGORIES
    )
    if pe >= 1.0:
        return float("nan")
    return (po - pe) / (1 - pe)


def kappa_report(ratings_a: list[str], ratings_b: list[str], label_a: str = "A", label_b: str = "B") -> str:
    n = len(ratings_a)
    agree = sum(1 for a, b in zip(ratings_a, ratings_b) if a == b)
    unweighted = cohens_kappa(ratings_a, ratings_b, weighted=False)
    weighted = cohens_kappa(ratings_a, ratings_b, weighted=True)
    lines = [
        f"n={n}, raw agreement={agree}/{n} ({agree/n:.0%})",
        f"unweighted kappa = {unweighted:.3f} ({interpret(unweighted)})",
        f"linearly weighted kappa = {weighted:.3f} ({interpret(weighted)})",
    ]
    disagreements = [(i, a, b) for i, (a, b) in enumerate(zip(ratings_a, ratings_b)) if a != b]
    if disagreements:
        lines.append(f"{len(disagreements)} disagreement(s) at indices: "
                      f"{[i for i, _, _ in disagreements]}")
    return "\n".join(lines)
