"""Shared baseline prompts and source-citation mapping."""

# The vocabulary halves must match eval/labels.py's DIRECTIONS and STRENGTHS
# exactly. An answer outside the vocabulary is graded off-vocabulary and
# fails, so a drift here would look like a model failure.
_RESPONSE_FIELDS = """  "direction": "EXACTLY ONE of: increased | decreased | none | mixed. increased = higher risk or worse outcome; decreased = lower risk or protective; none = no significant association reported; mixed = the sources genuinely conflict. Write nothing else in this field; put nuance in answer_text.",
  "strength": "EXACTLY ONE of: high | moderate | low | none | disputed | unstated. The magnitude of the reported association, not your confidence. disputed = sources conflict on magnitude; unstated = no effect size is reported.","""

# Shared by every baseline that has excerpts to cite. Do not copy it.
EXCERPT_PROMPT = """You are answering a question about cancer genomics variant-disease evidence, using ONLY the excerpts below, retrieved from a literature corpus. Do not use outside knowledge. If the excerpts don't actually answer the question, say so.

Question: {query}

Excerpts:
{excerpts}

Respond with strict JSON:
{{
""" + _RESPONSE_FIELDS + """
  "not_found": true if the excerpts do not answer this question, else false,
  "answer_text": "1-3 sentence answer explaining your reasoning, referencing excerpt numbers like [1]",
  "claims": [
    {{"text": "a specific factual claim from your answer", "excerpt_index": 1}}
  ]
}}
Every entry in "claims" must reference the excerpt number (1-indexed into the list above) that actually supports it. Do not cite an excerpt number that doesn't exist."""

NO_CONTEXT_PROMPT = """You are answering a question about cancer genomics variant-disease evidence,
from your own training knowledge only. You have no access to any external documents or search.

Question: {query}

If you are not confident you know a specific, well-documented answer to this exact question,
say so rather than guessing plausibly.

Respond with strict JSON:
{{
""" + _RESPONSE_FIELDS + """
  "not_found": true if you do not have reliable knowledge of this specific variant-condition pair, else false,
  "answer_text": "1-3 sentence answer explaining your reasoning"
}}"""


def format_excerpts(excerpts: list[tuple[dict, str]]) -> str:
    """`excerpts` is [(span, text)], span being a dict with at least pmcid
    and section. Numbered from 1, matching what the prompt asks the model to
    cite."""
    return "\n\n".join(
        f"[{i}] (from {span['pmcid']}, {span['section']}) {text}"
        for i, (span, text) in enumerate(excerpts, start=1)
    )


def map_claims(raw_claims: list, excerpts: list[tuple[dict, str]]) -> list[dict]:
    """Resolve each claim's excerpt_index back to that excerpt's real
    (pmcid, section, char_start, char_end). The model never invents an
    offset; a claim citing an excerpt number that does not exist is retained
    with an empty citation and scores as unsupported. It must not disappear
    from the grounding denominator."""
    claims = []
    for c in raw_claims or []:
        if not isinstance(c, dict) or not isinstance(c.get("text"), str):
            raise ValueError("each claim must contain text")
        idx = c.get("excerpt_index")
        if type(idx) is not int or not (1 <= idx <= len(excerpts)):
            claims.append({"text": c["text"], "cited_pmcid": "", "cited_section": "",
                           "cited_char_start": 0, "cited_char_end": 0})
            continue
        span = excerpts[idx - 1][0]
        claims.append({
            "text": c.get("text", ""), "cited_pmcid": span["pmcid"],
            "cited_section": span["section"], "cited_char_start": span["char_start"],
            "cited_char_end": span["char_end"],
        })
    return claims


def answer_from(case: dict, out: dict, claims: list[dict]) -> dict:
    if type(out.get("not_found", False)) is not bool:
        raise ValueError("not_found must be a JSON boolean")
    if not isinstance(out.get("answer_text", ""), str):
        raise ValueError("answer_text must be text")
    return {
        "case_id": case["case_id"], "direction": out.get("direction"),
        "strength": out.get("strength"), "not_found": out.get("not_found", False),
        "answer_text": out.get("answer_text", ""), "claims": claims,
    }



from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class RuntimeClaim(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=2000)
    excerpt_index: int = Field(ge=1)


class RuntimeAnswer(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=True)
    direction: Literal["increased", "decreased", "none", "mixed"]
    strength: Literal["high", "moderate", "low", "none", "disputed", "unstated"]
    not_found: bool
    answer_text: str = Field(min_length=1, max_length=6000)
    claims: list[RuntimeClaim] = Field(max_length=20)


def validate_runtime_answer(out: dict, excerpts: list[tuple[dict, str]]) -> dict:
    """Reject malformed serving output. Offline scoring retains invalid citations."""
    parsed = RuntimeAnswer.model_validate(out).model_dump()
    if any(claim["excerpt_index"] > len(excerpts) for claim in parsed["claims"]):
        raise ValueError("claim cites an unavailable excerpt")
    if parsed["not_found"]:
        if parsed["claims"] or parsed["direction"] != "none" or parsed["strength"] != "unstated":
            raise ValueError("abstention contradicts claims or labels")
        # Do not display free-form factual assertions in an abstention.
        parsed["answer_text"] = "The retrieved excerpts do not establish an answer to this question."
    elif not parsed["claims"]:
        raise ValueError("an answer requires cited claims")
    parsed["claims"] = map_claims(parsed["claims"], excerpts)
    return parsed
