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

Runtime synthesis shares common.answer; this module handles offline run artifacts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from common.run_meta import file_hash, source_hash, append_run, config_hash, git_sha

CASES_PATH = Path(__file__).parent.parent / "data" / "answer_cases.jsonl"

from common.answer import (EXCERPT_PROMPT, NO_CONTEXT_PROMPT, answer_from,
                           format_excerpts, map_claims)


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_run(out_path: Path, answers: list[dict], model: str, prompt_version: str,
              input_paths: dict[str, Path] | None = None, **extra_meta) -> None:
    """Answers as JSONL plus the sibling *.meta.json that makes a run
    attributable, per CLAUDE.md's rule that every RESULTS.md number carries a
    git SHA and a config."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for a in answers:
            f.write(json.dumps(a) + "\n")

    config = {"model": model, "prompt_version": prompt_version, "git_sha": git_sha(),
              **extra_meta, "source_hash": source_hash(),
              "inputs": {k: file_hash(v) for k, v in (input_paths or {"cases": CASES_PATH}).items()},
              "prompt_sha256": config_hash({"excerpt": EXCERPT_PROMPT, "no_context": NO_CONTEXT_PROMPT})}
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
                        metrics={"n_answers": len(answers)},
                        input_paths=input_paths or {"cases": CASES_PATH})

    print(f"Wrote {len(answers)} answers to {out_path}")
    print(f"Wrote run metadata to {meta_path}")
    print(f"Registered run {run_id}")
