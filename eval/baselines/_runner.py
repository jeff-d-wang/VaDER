"""
The parts every baseline shares, in one place.

The three baselines answer the same cases with the same model, judged by the
same scorer, and differ only in what context reaches the model. That is the
entire point of running them: `no_retrieval` gets nothing, `bm25_only` gets
whatever BM25 ranked into the top k, `oracle_spans` gets the gold spans, and
the difference between the scores is what retrieval bought.

Which is why the prompt lives here and not in each file. Until 2026-09-05
`bm25_only` and `oracle_spans` each carried their own byte-identical copy,
with a comment in one of them warning that a difference between the two
would confound the comparison. A warning is not a mechanism. Editing the
prompt now edits it for both, so the comparison stays clean by construction.
The response schema is shared one level further out: `no_retrieval` needs
the same controlled vocabulary (see eval/labels.py) even though it has no
excerpts to cite.

Phase D's real pipeline is the fourth baseline. It should import from here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from common.run_meta import append_run, config_hash, git_sha

CASES_PATH = Path(__file__).parent.parent / "data" / "answer_cases.jsonl"

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


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


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
    offset; a claim citing an excerpt number that doesn't exist is dropped
    rather than guessed at, which scores as ungrounded, the honest outcome."""
    claims = []
    for c in raw_claims or []:
        idx = c.get("excerpt_index")
        if not isinstance(idx, int) or not (1 <= idx <= len(excerpts)):
            continue
        span = excerpts[idx - 1][0]
        claims.append({
            "text": c.get("text", ""), "cited_pmcid": span["pmcid"],
            "cited_section": span["section"], "cited_char_start": span["char_start"],
            "cited_char_end": span["char_end"],
        })
    return claims


def answer_from(case: dict, out: dict, claims: list[dict]) -> dict:
    return {
        "case_id": case["case_id"], "direction": out.get("direction"),
        "strength": out.get("strength"), "not_found": bool(out.get("not_found", False)),
        "answer_text": out.get("answer_text", ""), "claims": claims,
    }


def write_run(out_path: Path, answers: list[dict], model: str, prompt_version: str,
              **extra_meta) -> None:
    """Answers as JSONL plus the sibling *.meta.json that makes a run
    attributable, per CLAUDE.md's rule that every RESULTS.md number carries a
    git SHA and a config."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for a in answers:
            f.write(json.dumps(a) + "\n")

    config = {"model": model, "prompt_version": prompt_version, "git_sha": git_sha(),
              **extra_meta}
    meta = {
        **config,
        "config_hash": config_hash(config),
        "n_cases": len(answers), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = Path(str(out_path) + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))

    # Run registry: ties this results file to a commit and a config. Scored
    # metrics land in RESULTS.md via score.py; the row here is attribution.
    run_id = append_run(eval_set="answer", run_config=config, results_path=str(out_path),
                        metrics={"n_answers": len(answers)})

    print(f"Wrote {len(answers)} answers to {out_path}")
    print(f"Wrote run metadata to {meta_path}")
    print(f"Registered run {run_id}")
