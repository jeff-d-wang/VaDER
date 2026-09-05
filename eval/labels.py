"""
The controlled vocabularies for the `direction` and `strength` properties,
and the deterministic grading that replaces an LLM judge on both.

Written 2026-09-05 after a withdrawn finding (docs/DECISION_LOG.md, "direction
property redesign"). The old gold labels were free text: eleven evidence
cases carried nine distinct `direction` strings, `'mixed'` and
`'mixed_evidence'` meaning the same thing, and four `strength` values that
contained no strength at all (a cohort description, a methodology note, two
bare percentage pairs). A property specified that loosely cannot be
measured, and the 0.216 direction kappa previously blamed on the judge was
mostly this.

Grading here is code, not a model. Two reasons that matters: it is exactly
reproducible, and it ends the same model grading its own output on the two
properties where that mattered most. The judge still handles groundedness
and disagreement, where free text genuinely has to be read.

**Known limitation, stated where it cannot be missed:** the current eval set
is 8/11 `increased`, so a system that always answers "increased" scores 73%
on direction. Always report `majority_class_baseline()` next to any direction
number. The fix is more `none`/`decreased`/`mixed` cases, not a different
metric.
"""
from __future__ import annotations

DIRECTIONS = ("increased", "decreased", "none", "mixed")

# low < moderate < high is the only ordered part. "none" (no association),
# "disputed" (sources conflict on magnitude) and "unstated" (the source
# gives no magnitude) are off-scale: they are categorically right or wrong,
# never one-tier-off.
STRENGTH_SCALE = ("low", "moderate", "high")
STRENGTHS = STRENGTH_SCALE + ("none", "disputed", "unstated")

# Tolerated spellings of a vocabulary value. Deliberately small: this maps
# obvious surface variants, not synonyms. A system that answers "elevated"
# is wrong under this rubric, and silently accepting it would rebuild the
# free-text problem one alias at a time.
_DIRECTION_ALIASES = {
    "increase": "increased", "increased risk": "increased", "higher": "increased",
    "decrease": "decreased", "decreased risk": "decreased", "lower": "decreased",
    "protective": "decreased",
    "no association": "none", "no effect": "none", "null": "none",
    "mixed evidence": "mixed", "mixed_evidence": "mixed", "conflicting": "mixed",
}
_STRENGTH_ALIASES = {
    "strong": "high", "weak": "low", "not stated": "unstated",
    "unknown": "unstated", "unclear": "unstated",
}


def normalize_direction(value: str | None) -> str | None:
    """Returns a vocabulary value, or None if the input is not one. None is
    a grading outcome (off-vocabulary), not an error to swallow."""
    return _normalize(value, DIRECTIONS, _DIRECTION_ALIASES)


def normalize_strength(value: str | None) -> str | None:
    return _normalize(value, STRENGTHS, _STRENGTH_ALIASES)


def _normalize(value: str | None, vocabulary: tuple[str, ...],
               aliases: dict[str, str]) -> str | None:
    if not value:
        return None
    key = " ".join(str(value).strip().lower().replace("_", " ").split())
    if key in vocabulary:
        return key
    if key in aliases:
        return aliases[key]
    compact = key.replace(" ", "_")
    if compact in aliases:
        return aliases[compact]
    return None


def grade_direction(gold: str | None, answer: str | None) -> tuple[str, str]:
    """Exact match against the vocabulary. Returns (verdict, rationale).

    No `partial`: direction is categorical, so there is no such thing as
    being one tier off. Strength is where partial credit lives."""
    gold_norm = normalize_direction(gold)
    ans_norm = normalize_direction(answer)
    if gold_norm is None:
        return "fail", f"gold direction {gold!r} is not in the vocabulary; fix the case"
    if ans_norm is None:
        return "fail", (f"answer direction {answer!r} is not one of {list(DIRECTIONS)} "
                        f"(off-vocabulary)")
    if ans_norm == gold_norm:
        return "pass", f"direction matches ({gold_norm})"
    return "fail", f"direction {ans_norm} does not match gold {gold_norm}"


def grade_strength(gold: str | None, answer: str | None) -> tuple[str, str]:
    """Exact match passes. One tier off on the low/moderate/high scale is
    partial. Everything else fails, including any miss involving the
    off-scale values, which are categorical."""
    gold_norm = normalize_strength(gold)
    ans_norm = normalize_strength(answer)
    if gold_norm is None:
        return "fail", f"gold strength {gold!r} is not in the vocabulary; fix the case"
    if ans_norm is None:
        return "fail", (f"answer strength {answer!r} is not one of {list(STRENGTHS)} "
                        f"(off-vocabulary)")
    if ans_norm == gold_norm:
        return "pass", f"strength matches ({gold_norm})"
    if gold_norm in STRENGTH_SCALE and ans_norm in STRENGTH_SCALE:
        if abs(STRENGTH_SCALE.index(gold_norm) - STRENGTH_SCALE.index(ans_norm)) == 1:
            return "partial", f"strength {ans_norm} is one tier from gold {gold_norm}"
    return "fail", f"strength {ans_norm} does not match gold {gold_norm}"


def majority_class_baseline(gold_values: list[str | None]) -> tuple[str | None, float, int]:
    """What a system scores by always guessing the most common gold value.
    Returns (value, rate, n). Report this next to any direction number: at
    8/11 `increased`, the trivial baseline is 73% and a real score has to be
    read against it, not against zero."""
    normalized = [v for v in (normalize_direction(g) for g in gold_values) if v]
    if not normalized:
        return None, 0.0, 0
    best = max(set(normalized), key=normalized.count)
    return best, normalized.count(best) / len(normalized), len(normalized)
