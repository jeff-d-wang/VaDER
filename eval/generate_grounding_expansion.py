"""Generate natural runtime claims from reviewed calibration questions and gold spans."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from common.answer import RUNTIME_PROMPT, format_excerpts, validate_runtime_answer
from common.corpus_text import load_span_text
from common.llm_client import DEFAULT_MODEL, groq_chat_json
from common.run_meta import config_hash, file_hash, git_sha, source_hash

DEFAULT_INPUT = Path(__file__).parent / "data" / "grounding-calibration-expansion-v1.jsonl"
DEFAULT_XML = Path(__file__).parent.parent / "corpus" / "xml"
PROMPT_VERSION = "runtime_grounding_calibration_v1"


def load_inputs(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def generate(
    rows: list[dict], model: str, xml_dir: Path,
    client: Callable[..., dict] = groq_chat_json,
) -> list[dict]:
    answers = []
    for row in rows:
        span = row["gold_span"]
        span_text, error = load_span_text(
            xml_dir, span["pmcid"], span["section"], span["char_start"], span["char_end"],
        )
        if error:
            raise ValueError(f"{row['case_id']}: citation does not resolve: {error}")
        excerpts = [(span, span_text)]
        raw = client(
            RUNTIME_PROMPT.format(query=row["query"], excerpts=format_excerpts(excerpts)),
            model=model,
        )
        answer = validate_runtime_answer(raw, excerpts)
        answers.append({"case_id": row["case_id"], **answer})
        print(f"  {row['case_id']}: {len(answer['claims'])} claim(s)")
    return answers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", default=str(DEFAULT_INPUT))
    parser.add_argument("--out", required=True)
    parser.add_argument("--xml-dir", default=str(DEFAULT_XML))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--min-claims", type=int, default=12)
    args = parser.parse_args(argv)
    if args.min_claims < 1:
        parser.error("--min-claims must be positive")

    input_path = Path(args.inputs)
    answers = generate(load_inputs(input_path), args.model, Path(args.xml_dir))
    claim_count = sum(len(answer["claims"]) for answer in answers)
    if claim_count < args.min_claims:
        raise ValueError(
            f"generated {claim_count} claims, below the required {args.min_claims}; "
            "expand the reviewed inputs before freezing calibration"
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(answer) + "\n" for answer in answers))
    config = {
        "model": args.model,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(RUNTIME_PROMPT.encode()).hexdigest(),
        "git_sha": git_sha(),
        "source_hash": source_hash(),
        "input_sha256": file_hash(input_path),
    }
    meta = {
        **config,
        "config_hash": config_hash(config),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_inputs": len(answers),
        "n_claims": claim_count,
        "output_sha256": file_hash(out),
    }
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Wrote {len(answers)} answers and {claim_count} claims to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
