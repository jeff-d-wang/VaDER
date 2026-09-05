"""
The oracle-span baseline (phase A3). Supplies exactly the case's gold spans
as context: perfect retrieval, by construction.

This stands in for PROJECT_PLAN.md M1's third baseline,
whole-document-in-context, which is blocked on Groq's free tier (a hard
8,000 tokens-per-minute per-request ceiling against gold articles of 3k to
20k tokens; a probe returned HTTP 413). See docs/DECISION_LOG.md,
"oracle-span baseline (A3)", for the measurement and the alternatives
weighed.

What it is for: separating a RETRIEVAL failure from a READING failure.
no_retrieval gets no context, bm25_only gets whatever BM25 ranked into the
top 8, and this gets the exact passages a correct answer must rest on. Same
model, same prompt shape, same citation mechanism as bm25_only, so the only
variable between the two runs is which passages reached the model. If
direction is still wrong here, nothing about retrieval can explain it.

Negative cases have no gold spans, so there is nothing to be an oracle
about; they are skipped rather than fed an empty context, which would just
be no_retrieval wearing a different name. That means this run scores the
non-negative dev cases only.

Usage:
    python -m eval.baselines.oracle_spans --out eval/runs/oracle_spans_answers.jsonl
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common.corpus_text import load_span_text
from eval.baselines._runner import (CASES_PATH, EXCERPT_PROMPT, answer_from,
                                    format_excerpts, load_cases, map_claims, write_run)
from eval.llm_client import DEFAULT_MODEL, groq_chat_json

XML_DIR = Path(__file__).parent.parent.parent / "corpus" / "xml"
PROMPT_VERSION = "oracle_spans_v2"


def gold_excerpts(case: dict, xml_dir: Path) -> list[tuple[dict, str]]:
    """Resolve each gold span to its real text. A span that will not resolve
    is dropped loudly rather than silently: this baseline's whole claim is
    that the context is correct, so a broken span invalidates the case
    rather than merely degrading it."""
    out = []
    for span in case["gold_spans"]:
        text, err = load_span_text(xml_dir, span["pmcid"], span["section"],
                                   span["char_start"], span["char_end"])
        if err is not None:
            print(f"  WARNING {case['case_id']}: gold span {span['pmcid']} "
                  f"unresolvable ({err}), dropped from context", file=sys.stderr)
            continue
        out.append((span, text))
    return out


def run(cases: list[dict], model: str, xml_dir: Path) -> list[dict]:
    answers = []
    for case in cases:
        if case["stratum"] != "evidence" or case["is_negative_case"]:
            continue
        excerpts = gold_excerpts(case, xml_dir)
        if not excerpts:
            print(f"  SKIP {case['case_id']}: no resolvable gold spans", file=sys.stderr)
            continue

        out = groq_chat_json(
            EXCERPT_PROMPT.format(query=case["query"], excerpts=format_excerpts(excerpts)),
            model=model)
        claims = map_claims(out.get("claims"), excerpts)
        answers.append(answer_from(case, out, claims))
        print(f"  {case['case_id']}: {len(excerpts)} gold excerpt(s), {len(claims)} claim(s)")
    return answers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--xml-dir", default=str(XML_DIR))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    answers = run(load_cases(Path(args.cases)), args.model, Path(args.xml_dir))
    write_run(Path(args.out), answers, args.model, PROMPT_VERSION, context="gold_spans_only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
