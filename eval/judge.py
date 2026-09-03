"""
Judges for the two answer_cases.jsonl sub-scores that need semantic
comparison rather than exact-match: direction/strength (property 1),
disagreement surfacing (property 3), and per-claim groundedness
(property 2). Property 4 ("says not found") is decided in score.py without
a judge: it's a check for refusal language, not a semantic comparison.

Two implementations:
  - FakeJudge: deterministic, no network, keyword-overlap heuristic. Exists
    so score.py's grading logic (bucket thresholds, partial-credit rules)
    is unit-testable without an API key or nondeterministic LLM output. Not
    a real groundedness judge; scores made with it are not evaluation
    results, only pipeline self-tests. See test_score.py.
  - GroqJudge: calls the free-tier 70B-class model already decided in
    docs/DECISION_LOG.md ("Model & embedding stack" entry) via Groq's
    OpenAI-compatible chat completions endpoint. Needs GROQ_API_KEY in the
    environment; raises a clear error otherwise rather than silently
    falling back to the fake judge, so a real run can't be mistaken for one
    that used it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

Verdict = str  # "pass" | "partial" | "fail"


@dataclass
class JudgeResult:
    verdict: Verdict
    rationale: str


class Judge(Protocol):
    def grade_direction(self, query: str, gold_direction: str, gold_strength: str | None,
                         answer_direction: str, answer_strength: str | None) -> JudgeResult: ...

    def grade_disagreement(self, query: str, disagreement_note: str, answer_text: str) -> JudgeResult: ...

    def grade_claim_groundedness(self, claim_text: str, cited_span_text: str) -> bool: ...


_DIRECTION_PROMPT = """You are grading whether a system's answer matches the gold direction/strength label for a variant-disease evidence question.

Query: {query}
Gold direction: {gold_direction}
Gold strength: {gold_strength}
System's stated direction: {answer_direction}
System's stated strength: {answer_strength}

Grade pass/partial/fail:
- pass: direction and strength both match the gold label in substance (paraphrase is fine).
- partial: right direction, strength off by one tier, OR direction correct but strength unstated,
  OR strength overstated/understated by any amount as long as direction is correct.
- fail: wrong direction, or a direction that contradicts the gold label. Never grade fail for a
  magnitude/strength mismatch alone: if the direction is correct, the worst verdict is partial, no
  matter how far off the strength/magnitude is (a "moderate" claim graded as "high risk" is still
  partial, not fail, if the direction itself, e.g. "increases risk", is right).

Respond with strict JSON: {{"verdict": "pass|partial|fail", "rationale": "one sentence"}}"""

_DISAGREEMENT_PROMPT = """You are grading whether a system's answer surfaces a known disagreement between sources.

Query: {query}
Known disagreement in the corpus: {disagreement_note}
System's answer: {answer_text}

Grade pass/partial/fail:
- pass: the answer explicitly states that sources conflict/disagree, in substance matching the known disagreement.
- partial: the answer cites both conflicting sources or mentions both findings, but never states outright that they disagree.
- fail: the answer presents only one side, or doesn't mention the conflict at all.

Respond with strict JSON: {{"verdict": "pass|partial|fail", "rationale": "one sentence"}}"""

_GROUNDEDNESS_PROMPT = """Does the cited span support the claim? Judge only what the span actually states, not outside knowledge.

A figure caption, table title, or section heading that merely describes what a figure/table is
about (e.g. "Figure 1: Cumulative risk of X by Y") is NOT support for a claim about what that
figure/table actually shows, unless the caption itself states the finding (a number, a direction,
a comparison). "The span mentions the right topic" is not the same as "the span states the claim."
If the span is only a caption/title/heading with no stated finding, mark unsupported.

Claim: {claim_text}
Cited span: {cited_span_text}

Respond with strict JSON: {{"supported": true|false, "rationale": "one sentence"}}"""


class FakeJudge:
    """No network. A claim/direction/disagreement is graded by crude word
    overlap against the gold text. Deterministic, for testing score.py's
    own logic only -- see the module docstring."""

    def _overlap(self, a: str, b: str) -> float:
        wa = {w.lower() for w in a.split() if len(w) > 3}
        wb = {w.lower() for w in b.split() if len(w) > 3}
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / len(wa)

    def grade_direction(self, query, gold_direction, gold_strength, answer_direction, answer_strength):
        gold_norm = (gold_direction or "").lower().replace("_", " ")
        ans_norm = (answer_direction or "").lower().replace("_", " ")
        if gold_norm and gold_norm in ans_norm:
            return JudgeResult("pass", "fake judge: normalized direction string matched")
        overlap = self._overlap(gold_norm, ans_norm)
        if overlap >= 0.3:
            return JudgeResult("partial", f"fake judge: partial word overlap ({overlap:.2f})")
        return JudgeResult("fail", "fake judge: no meaningful overlap with gold direction")

    def grade_disagreement(self, query, disagreement_note, answer_text):
        overlap = self._overlap(disagreement_note, answer_text)
        refusal_markers = ("disagree", "conflict", "contradict", "inconsistent", "differ")
        states_conflict = any(m in answer_text.lower() for m in refusal_markers)
        if overlap >= 0.25 and states_conflict:
            return JudgeResult("pass", "fake judge: overlap + explicit conflict language")
        if overlap >= 0.15:
            return JudgeResult("partial", f"fake judge: some overlap ({overlap:.2f}), no explicit conflict language")
        return JudgeResult("fail", "fake judge: little overlap with the known disagreement")

    def grade_claim_groundedness(self, claim_text, cited_span_text):
        return self._overlap(claim_text, cited_span_text) >= 0.35


class GroqJudge:
    """Calls Groq's OpenAI-compatible chat completions endpoint via
    llm_client.groq_chat_json. Model defaults to llm_client.DEFAULT_MODEL
    (see that module for why it's gpt-oss-120b and not the originally
    decided Llama 3.3 70B, Groq model drift, discovered running this)."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from llm_client import DEFAULT_MODEL, require_api_key
        self.model = model or DEFAULT_MODEL
        # Fail fast at construction, not on the first grade_* call: refusing
        # to silently fall back to a fake judge, a real score needs a real
        # judge, and a run should not get partway through before erroring.
        self.api_key = require_api_key(api_key)

    def _call(self, prompt: str) -> dict:
        from llm_client import groq_chat_json
        return groq_chat_json(prompt, model=self.model, api_key=self.api_key)

    def grade_direction(self, query, gold_direction, gold_strength, answer_direction, answer_strength):
        out = self._call(_DIRECTION_PROMPT.format(
            query=query, gold_direction=gold_direction, gold_strength=gold_strength,
            answer_direction=answer_direction, answer_strength=answer_strength,
        ))
        return JudgeResult(out["verdict"], out.get("rationale", ""))

    def grade_disagreement(self, query, disagreement_note, answer_text):
        out = self._call(_DISAGREEMENT_PROMPT.format(
            query=query, disagreement_note=disagreement_note, answer_text=answer_text,
        ))
        return JudgeResult(out["verdict"], out.get("rationale", ""))

    def grade_claim_groundedness(self, claim_text, cited_span_text):
        out = self._call(_GROUNDEDNESS_PROMPT.format(
            claim_text=claim_text, cited_span_text=cited_span_text,
        ))
        return bool(out["supported"])


def make_judge(name: str) -> Judge:
    if name == "fake":
        return FakeJudge()
    if name == "groq":
        return GroqJudge()
    raise ValueError(f"unknown judge: {name!r} (expected 'fake' or 'groq')")
