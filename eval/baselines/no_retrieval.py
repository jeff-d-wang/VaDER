"""
The no-retrieval baseline (PROJECT_PLAN.md M1: "Establish three baselines
before any retrieval tuning: no-retrieval, BM25-only, whole-document").
Answers each answer_cases.jsonl query from the model's parametric knowledge
alone, no corpus context in the prompt at all. This is what M1's negative
cases exist to stress: PMC full text is in the model's pretraining, so a
no-retrieval answer that happens to be right may be memorization, not
reasoning, and a no-retrieval answer to a *negative* case that still
states a confident direction is a direct measurement of that risk.

By construction this baseline never has real spans to cite (there is no
retrieval step), so every answer's `claims` list is left empty. Scoring it
with score.py will correctly mark groundedness as a fail (empty_claims):
that's not a bug in the baseline or the scorer, it's the expected shape of
a no-retrieval result, and it is exactly the number M1 wants ("how much
does retrieval buy you over the model alone").

Needs GROQ_API_KEY (see eval/README.md). Writes one JSON object per case to
--out, plus a sibling *.meta.json recording the model, prompt version, and
git SHA so the run is attributable per CLAUDE.md's RESULTS.md rule.

Usage:
    python baselines/no_retrieval.py --out runs/no_retrieval_answers.jsonl
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_client import DEFAULT_MODEL, groq_chat_json  # noqa: E402

CASES_PATH = Path(__file__).parent.parent / "answer_cases.jsonl"

PROMPT_VERSION = "no_retrieval_v1"

_PROMPT = """You are answering a question about cancer genomics variant-disease evidence,
from your own training knowledge only. You have no access to any external documents or search.

Question: {query}

If you are not confident you know a specific, well-documented answer to this exact question,
say so rather than guessing plausibly.

Respond with strict JSON:
{{
  "direction": "short phrase describing the reported direction/effect, or null if unknown",
  "strength": "short phrase describing effect strength/confidence, or null if unknown",
  "not_found": true if you do not have reliable knowledge of this specific variant-condition pair, else false,
  "answer_text": "1-3 sentence answer explaining your reasoning"
}}"""


def load_cases() -> list[dict]:
    with open(CASES_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent, text=True,
        ).strip()
    except Exception:
        return "unknown"


def run(cases: list[dict], model: str) -> list[dict]:
    answers = []
    for case in cases:
        if case["stratum"] != "evidence":
            continue  # this baseline only covers the evidence stratum for now
        out = groq_chat_json(_PROMPT.format(query=case["query"]), model=model)
        answers.append({
            "case_id": case["case_id"],
            "direction": out.get("direction"),
            "strength": out.get("strength"),
            "not_found": bool(out.get("not_found", False)),
            "answer_text": out.get("answer_text", ""),
            "claims": [],  # no retrieval step, nothing to cite; see module docstring
        })
    return answers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    cases = load_cases()
    answers = run(cases, args.model)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for a in answers:
            f.write(json.dumps(a) + "\n")

    meta = {
        "model": args.model, "prompt_version": PROMPT_VERSION, "git_sha": git_sha(),
        "n_cases": len(answers), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"Wrote {len(answers)} answers to {out_path}")
    print(f"Wrote run metadata to {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
