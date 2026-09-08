"""
The BM25-only baseline (PROJECT_PLAN.md M1's second required baseline).
Unlike no_retrieval.py, this one has real, citable context: bm25.py's
hand-built index retrieves the top-k paragraphs for each case's query, the
model is told to answer using only those excerpts, and its citations are
mapped back to the excerpts' real (pmcid, section, char_start, char_end)
before scoring, no offset is ever invented by the model.

This is what makes "how much does retrieval buy you over the model alone"
(PROJECT_PLAN.md's own M1 question) answerable: same cases, same judge, same
scorer as no_retrieval.py, the only thing that changes is whether real
corpus text was in the prompt.

Needs GROQ_API_KEY and a built index (see eval/README.md,
`python -m retrieval.bm25` is not a CLI; build via the one-liner in the README or
reuse eval/runs/bm25_index.pkl if already built).

Usage:
    python -m eval.baselines.bm25_only --index runs/bm25_index.pkl --out runs/bm25_only_answers.jsonl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common.trace import span, trace_request
from eval.baselines._runner import (EXCERPT_PROMPT, answer_from, format_excerpts,
                                    load_cases, map_claims, write_run)
from eval.llm_client import DEFAULT_MODEL, groq_chat_json
from retrieval.bm25 import BM25Index

PROMPT_VERSION = "bm25_only_v2"
TOP_K = 8


def run(cases: list[dict], index: BM25Index, model: str, top_k: int) -> list[dict]:
    answers = []
    for case in cases:
        if case["stratum"] != "evidence":
            continue
        with trace_request("bm25_only", case_id=case["case_id"]):
            with span("retrieve", retriever="bm25", top_k=top_k) as s:
                hits = index.search(case["query"], top_k=top_k)
                s["retrieval.hit_count"] = len(hits)
            if not hits:
                answers.append({
                    "case_id": case["case_id"], "direction": None, "strength": None,
                    "not_found": True, "answer_text": "No retrieval hits for this query.",
                    "claims": [],
                })
                continue

            excerpts = [(chunk.span(), chunk.text) for chunk, _score in hits]
            out = groq_chat_json(
                EXCERPT_PROMPT.format(query=case["query"], excerpts=format_excerpts(excerpts)),
                model=model)
            answers.append(answer_from(case, out, map_claims(out.get("claims"), excerpts)))
    return answers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args(argv)

    print(f"Loading index from {args.index}...")
    index = BM25Index.load(Path(args.index))
    print(f"Loaded: {index.n_docs} paragraphs.")

    answers = run(load_cases(), index, args.model, args.top_k)
    write_run(Path(args.out), answers, args.model, PROMPT_VERSION, top_k=args.top_k)
    return 0


if __name__ == "__main__":
    sys.exit(main())
