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
    python -m eval.baselines.no_retrieval --out runs/no_retrieval_answers.jsonl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eval.baselines._runner import (NO_CONTEXT_PROMPT, answer_from, load_cases,
                                    write_run)
from common.llm_client import DEFAULT_MODEL, groq_chat_json

PROMPT_VERSION = "no_retrieval_v2"


def run(cases: list[dict], model: str) -> list[dict]:
    answers = []
    for case in cases:
        if case["stratum"] != "evidence":
            continue  # this baseline only covers the evidence stratum for now
        out = groq_chat_json(NO_CONTEXT_PROMPT.format(query=case["query"]), model=model)
        # claims stays empty: no retrieval step, nothing to cite. See the
        # module docstring, that is the expected shape, not a bug.
        answers.append(answer_from(case, out, []))
    return answers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    answers = run(load_cases(), args.model)
    write_run(Path(args.out), answers, args.model, PROMPT_VERSION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
