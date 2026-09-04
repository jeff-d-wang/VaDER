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
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from retrieval.bm25 import BM25Index
from eval.llm_client import DEFAULT_MODEL, groq_chat_json

CASES_PATH = Path(__file__).parent.parent / "data" / "answer_cases.jsonl"
PROMPT_VERSION = "bm25_only_v1"
TOP_K = 8

_PROMPT = """You are answering a question about cancer genomics variant-disease evidence, using ONLY the excerpts below, retrieved from a literature corpus. Do not use outside knowledge. If the excerpts don't actually answer the question, say so.

Question: {query}

Excerpts:
{excerpts}

Respond with strict JSON:
{{
  "direction": "short phrase describing the reported direction/effect, or null if the excerpts don't establish one",
  "strength": "short phrase describing effect strength/confidence, or null if unknown",
  "not_found": true if the excerpts do not answer this question, else false,
  "answer_text": "1-3 sentence answer explaining your reasoning, referencing excerpt numbers like [1]",
  "claims": [
    {{"text": "a specific factual claim from your answer", "excerpt_index": 1}}
  ]
}}
Every entry in "claims" must reference the excerpt number (1-indexed into the list above) that actually supports it. Do not cite an excerpt number that doesn't exist."""


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


def format_excerpts(hits: list[tuple]) -> str:
    lines = []
    for i, (para, _score) in enumerate(hits, start=1):
        lines.append(f"[{i}] (from {para.pmcid}, {para.section}) {para.text}")
    return "\n\n".join(lines)


def run(cases: list[dict], index: BM25Index, model: str, top_k: int) -> list[dict]:
    answers = []
    for case in cases:
        if case["stratum"] != "evidence":
            continue
        hits = index.search(case["query"], top_k=top_k)
        if not hits:
            answers.append({
                "case_id": case["case_id"], "direction": None, "strength": None,
                "not_found": True, "answer_text": "No retrieval hits for this query.", "claims": [],
            })
            continue

        excerpts_text = format_excerpts(hits)
        out = groq_chat_json(_PROMPT.format(query=case["query"], excerpts=excerpts_text), model=model)

        claims = []
        for c in out.get("claims", []):
            idx = c.get("excerpt_index")
            if not isinstance(idx, int) or not (1 <= idx <= len(hits)):
                continue  # model cited a nonexistent excerpt; drop rather than guess
            para, _score = hits[idx - 1]
            claims.append({
                "text": c.get("text", ""), "cited_pmcid": para.pmcid, "cited_section": para.section,
                "cited_char_start": para.char_start, "cited_char_end": para.char_end,
            })

        answers.append({
            "case_id": case["case_id"], "direction": out.get("direction"), "strength": out.get("strength"),
            "not_found": bool(out.get("not_found", False)), "answer_text": out.get("answer_text", ""),
            "claims": claims,
        })
    return answers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args()

    print(f"Loading index from {args.index}...")
    index = BM25Index.load(Path(args.index))
    print(f"Loaded: {index.n_docs} paragraphs.")

    cases = load_cases()
    answers = run(cases, index, args.model, args.top_k)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for a in answers:
            f.write(json.dumps(a) + "\n")

    meta = {
        "model": args.model, "prompt_version": PROMPT_VERSION, "git_sha": git_sha(),
        "top_k": args.top_k, "n_cases": len(answers),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = out_path.with_suffix(out_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"Wrote {len(answers)} answers to {out_path}")
    print(f"Wrote run metadata to {meta_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
