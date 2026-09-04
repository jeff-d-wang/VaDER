"""
Tests for hold_out_case.py. Builds a tiny synthetic corpus per run in a temp
dir, exercises hold-out, idempotency, cross-pair conflict, missing-file
handling, and restore, all via the real CLI (subprocess). Run:

    python -m eval.tests.test_hold_out_case
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # repo root: CLIs run as "python -m eval.<mod>"


def _write_corpus(tmp: Path, pmcids: list) -> Path:
    xml_dir = tmp / "corpus" / "xml"
    xml_dir.mkdir(parents=True)
    for pmcid in pmcids:
        (xml_dir / f"{pmcid}.xml").write_text(f"<article>{pmcid}</article>")
    return tmp / "corpus"


def run(args: list) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "eval.hold_out_case"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))


def run_tests():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name}  {detail}")
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        corpus_dir = _write_corpus(tmp, ["PMC1000001", "PMC1000002", "PMC1000003"])
        held_out_dir = tmp / "held_out"

        # --- hold out two pmcids ---
        r = run(["--corpus-dir", str(corpus_dir), "--held-out-dir", str(held_out_dir),
                 "--pair-id", "palb2_pancreatic", "--gene", "PALB2", "--condition", "pancreatic cancer",
                 "--pmcid", "PMC1000001", "--pmcid", "PMC1000002"])
        check("hold-out CLI exits 0", r.returncode == 0, r.stderr)
        check("PMC1000001 moved out of corpus", not (corpus_dir / "xml" / "PMC1000001.xml").exists())
        check("PMC1000001 present in held_out/xml", (held_out_dir / "xml" / "PMC1000001.xml").exists())
        check("PMC1000003 untouched, still in corpus", (corpus_dir / "xml" / "PMC1000003.xml").exists())

        registry = list(csv.DictReader(open(held_out_dir / "held_out_pmcids.csv")))
        check("registry has 2 rows", len(registry) == 2, registry)
        check("registry row has pair_id/gene/condition",
              all(r2["pair_id"] == "palb2_pancreatic" and r2["gene"] == "PALB2" for r2 in registry), registry)

        # --- idempotent: re-running the same pair/pmcid is a no-op, not a duplicate row ---
        r = run(["--corpus-dir", str(corpus_dir), "--held-out-dir", str(held_out_dir),
                 "--pair-id", "palb2_pancreatic", "--gene", "PALB2", "--condition", "pancreatic cancer",
                 "--pmcid", "PMC1000001"])
        registry = list(csv.DictReader(open(held_out_dir / "held_out_pmcids.csv")))
        check("idempotent: still 2 registry rows after re-run", len(registry) == 2, registry)

        # --- cross-pair conflict: same pmcid, different pair_id -> refused ---
        r = run(["--corpus-dir", str(corpus_dir), "--held-out-dir", str(held_out_dir),
                 "--pair-id", "other_pair", "--gene", "PALB2", "--condition", "something else",
                 "--pmcid", "PMC1000001"])
        check("cross-pair reassignment refused (nonzero exit)", r.returncode != 0, r.stderr)
        registry = list(csv.DictReader(open(held_out_dir / "held_out_pmcids.csv")))
        check("registry unchanged after refused reassignment", len(registry) == 2, registry)

        # --- missing source file: warns, doesn't crash, no registry row ---
        r = run(["--corpus-dir", str(corpus_dir), "--held-out-dir", str(held_out_dir),
                 "--pair-id", "ghost_pair", "--gene", "X", "--condition", "y",
                 "--pmcid", "PMC9999999"])
        check("missing pmcid: nonzero exit, no crash", r.returncode != 0)
        registry = list(csv.DictReader(open(held_out_dir / "held_out_pmcids.csv")))
        check("registry unchanged after missing-file attempt", len(registry) == 2, registry)

        # --- list mode doesn't crash ---
        r = run(["--held-out-dir", str(held_out_dir), "--list"])
        check("--list exits 0", r.returncode == 0, r.stderr)
        check("--list mentions palb2_pancreatic", "palb2_pancreatic" in r.stdout, r.stdout)

        # --- restore ---
        r = run(["--corpus-dir", str(corpus_dir), "--held-out-dir", str(held_out_dir),
                 "--pair-id", "palb2_pancreatic", "--restore"])
        check("restore CLI exits 0", r.returncode == 0, r.stderr)
        check("PMC1000001 back in corpus", (corpus_dir / "xml" / "PMC1000001.xml").exists())
        check("PMC1000002 back in corpus", (corpus_dir / "xml" / "PMC1000002.xml").exists())
        registry = list(csv.DictReader(open(held_out_dir / "held_out_pmcids.csv")))
        check("registry empty after restore", len(registry) == 0, registry)

        # --- CLI validation ---
        r = run(["--corpus-dir", str(corpus_dir), "--held-out-dir", str(held_out_dir),
                 "--pair-id", "x", "--pmcid", "PMC1000003"])
        check("missing --condition -> nonzero exit", r.returncode != 0)
        r = run(["--corpus-dir", str(corpus_dir), "--held-out-dir", str(held_out_dir),
                 "--pair-id", "x", "--condition", "y"])
        check("missing --pmcid -> nonzero exit", r.returncode != 0)

    if failures:
        print(f"\n{len(failures)} FAILED: {failures}")
        sys.exit(1)
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run_tests()
