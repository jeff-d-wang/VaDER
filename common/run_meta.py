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
from pathlib import Path


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
