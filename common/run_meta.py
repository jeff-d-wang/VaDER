"""
How this project stamps a run, in one place.

CLAUDE.md's rule: every number written to docs/RESULTS.md carries a git SHA
and a config hash. Both halves of that stamp live here, for the same reason
common/stats.py exists: the moment a helper has two callers, two copies is
the outcome nobody chooses and everybody gets. The answer-set baselines
(eval/baselines/_runner.py) and the retrieval scorer (eval/score_retrieval.py)
both stamp runs, and they must stamp them the same way or two rows in
RESULTS.md carrying the same-looking hash would mean different things.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = _REPO_ROOT / "config" / "vader.yaml"
# Not under eval/runs/ (git-ignored): the registry is the durable tie between a
# results file, a commit, and a config, so it is committed.
REGISTRY_PATH = _REPO_ROOT / "eval" / "run_registry.jsonl"


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).parent, text=True,
        ).strip()
    except Exception:
        return "unknown"


def config_hash(config: dict) -> str:
    """Hash of the values a run actually used, so a RESULTS.md row can be
    tied back to one.

    Every cfg-* hash in RESULTS.md before 2026-09-05 was typed by hand from
    a string composed for the occasion: nothing computed them, so they named
    no state and could not be checked. That is the same defect as a git SHA
    that resolves to nothing, which this repo also turned out to have.

    Excludes the case count and the timestamp deliberately: two runs of the
    same config on the same cases should collide, and a wall-clock field
    would make every hash unique and therefore useless."""
    payload = json.dumps(config, sort_keys=True, default=str)
    return "cfg-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def load_config(path: Path = CONFIG_PATH) -> dict:
    """The one config-as-code file, parsed. config_hash(load_config()) is the
    pipeline stamp that goes on a RESULTS.md row alongside the run's own
    parameters."""
    import yaml  # in vader_env; imported lazily so run_meta stays import-cheap
    return yaml.safe_load(Path(path).read_text())


def append_run(*, eval_set: str, run_config: dict, results_path: str,
               metrics: dict, registry: Path = REGISTRY_PATH) -> str:
    """Append one row to the run registry: what config produced which results
    file, at which commit, with a one-line metrics summary. `run_config` is the
    run-specific dict the caller already builds (k1, top_k, model, ...); the
    pipeline YAML is hashed in separately so both stamps land on the row."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + eval_set
    row = {
        "run_id": run_id,
        "git_sha": git_sha(),
        "pipeline_config_hash": config_hash(load_config()),
        "run_config_hash": config_hash(run_config),
        "eval_set": eval_set,
        "results_path": results_path,
        "metrics": metrics,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    registry.parent.mkdir(parents=True, exist_ok=True)
    with open(registry, "a") as f:
        f.write(json.dumps(row) + "\n")
    return run_id
