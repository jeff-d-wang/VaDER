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
import shutil
import uuid
import zipfile
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
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, text=True,
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


def file_hash(path: Path) -> str:
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def source_files() -> list[Path]:
    """Only runtime/test source and declared config, never secrets or generated data."""
    files = []
    for folder in ("common", "retrieval", "eval", "service", "ingestion", "config"):
        files.extend(p for p in (_REPO_ROOT / folder).rglob("*")
                     if p.suffix in (".py", ".yaml") and p.is_file())
    files.extend(p for p in (_REPO_ROOT / "requirements.txt",) if p.exists())
    return sorted(files)


def source_hash() -> str:
    """Fingerprint actual source, including edits and new modules, without reading secrets."""
    return config_hash({str(p.relative_to(_REPO_ROOT)): file_hash(p) for p in source_files()})


def append_run(*, eval_set: str, run_config: dict, results_path: str,
               metrics: dict, registry: Path = REGISTRY_PATH,
               input_paths: dict[str, Path] | None = None) -> str:
    """Append one row to the run registry: what config produced which results
    file, at which commit, with a one-line metrics summary. `run_config` is the
    run-specific dict the caller already builds (k1, top_k, model, ...); the
    pipeline YAML is hashed in separately so both stamps land on the row."""
    inputs = {name: {"path": str(path), "sha256": file_hash(path)}
              for name, path in (input_paths or {}).items()}
    result = Path(results_path)
    result_hash = file_hash(result)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex
    bundle = registry.parent / "artifacts" / run_id
    bundle.mkdir(parents=True)
    saved_result = bundle / ("output" + result.suffix)
    shutil.copyfile(result, saved_result)
    if file_hash(saved_result) != result_hash:
        raise RuntimeError("result changed during registration")
    for number, (name, path) in enumerate((input_paths or {}).items()):
        # Large indexes remain rebuildable caches; preserve small case/manifest inputs verbatim.
        path = Path(path)
        if path.stat().st_size <= 10 * 1024 * 1024:
            target = bundle / f"input-{number}-{path.name}"
            shutil.copyfile(path, target)
            if file_hash(target) != inputs[name]["sha256"]:
                raise RuntimeError("input changed during registration")
            inputs[name]["artifact"] = target.name
    with zipfile.ZipFile(bundle / "source.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            archive.write(path, str(path.relative_to(_REPO_ROOT)))
    row = {
        "run_id": run_id,
        "git_sha": git_sha(),
        "source_hash": source_hash(),
        "source_snapshot": "source.zip",
        "pipeline_config_hash": config_hash(load_config()),
        "run_config_hash": config_hash(run_config),
        "run_config": run_config,
        "inputs": inputs,
        "eval_set": eval_set,
        "results_path": results_path,
        "artifact_path": str(saved_result),
        "results_sha256": result_hash,
        "metrics": metrics,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (bundle / "run.json").write_text(json.dumps(row, indent=2) + "\n")
    registry.parent.mkdir(parents=True, exist_ok=True)
    with open(registry, "a") as f:
        f.write(json.dumps(row) + "\n")
    return run_id
