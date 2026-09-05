"""
Tests for hold_out_case.py. Builds a tiny synthetic corpus per run in a temp
dir, exercises hold-out, idempotency, cross-pair conflict, missing-file
handling, and restore, all via the real CLI (subprocess). Run:

    python -m eval.tests.test_hold_out_case
"""
from __future__ import annotations

import unittest

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


class TestHoldOutCase(unittest.TestCase):
    """A fresh corpus per test. `hold_out_two` is the shared starting state
    for everything that needs an existing hold-out to act on, so no test
    depends on another one having run first."""

    ARGS = ("--pair-id", "palb2_pancreatic", "--gene", "PALB2",
            "--condition", "pancreatic cancer")

    def setUp(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.corpus_dir = _write_corpus(tmp, ["PMC1000001", "PMC1000002", "PMC1000003"])
        self.held_out_dir = tmp / "held_out"

    def run_cli(self, *args):
        return run(["--corpus-dir", str(self.corpus_dir),
                    "--held-out-dir", str(self.held_out_dir), *args])

    def registry(self):
        with open(self.held_out_dir / "held_out_pmcids.csv", newline="") as f:
            return list(csv.DictReader(f))

    def hold_out_two(self):
        r = self.run_cli(*self.ARGS, "--pmcid", "PMC1000001", "--pmcid", "PMC1000002")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_holding_out_moves_the_files_and_records_them(self):
        self.hold_out_two()
        self.assertFalse((self.corpus_dir / "xml" / "PMC1000001.xml").exists(),
                         "held-out article must leave the corpus")
        self.assertTrue((self.held_out_dir / "xml" / "PMC1000001.xml").exists())
        self.assertTrue((self.corpus_dir / "xml" / "PMC1000003.xml").exists(),
                        "PMC1000003 was not named, must be untouched")
        registry = self.registry()
        self.assertEqual(len(registry), 2, registry)
        self.assertTrue(all(r["pair_id"] == "palb2_pancreatic" and r["gene"] == "PALB2"
                            for r in registry), registry)

    def test_rerunning_the_same_pair_is_a_noop_not_a_duplicate_row(self):
        self.hold_out_two()
        self.run_cli(*self.ARGS, "--pmcid", "PMC1000001")
        self.assertEqual(len(self.registry()), 2, "idempotent: still 2 rows after a re-run")

    def test_the_same_pmcid_under_a_different_pair_is_refused(self):
        self.hold_out_two()
        r = self.run_cli("--pair-id", "other_pair", "--gene", "PALB2",
                         "--condition", "something else", "--pmcid", "PMC1000001")
        self.assertNotEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.registry()), 2, "registry unchanged after a refused reassignment")

    def test_a_missing_source_file_fails_without_recording_anything(self):
        self.hold_out_two()
        r = self.run_cli("--pair-id", "ghost_pair", "--gene", "X", "--condition", "y",
                         "--pmcid", "PMC9999999")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(len(self.registry()), 2, "registry unchanged after a missing-file attempt")

    def test_list_mode(self):
        self.hold_out_two()
        r = run(["--held-out-dir", str(self.held_out_dir), "--list"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("palb2_pancreatic", r.stdout)

    def test_restore_puts_everything_back_and_empties_the_registry(self):
        self.hold_out_two()
        r = self.run_cli("--pair-id", "palb2_pancreatic", "--restore")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.corpus_dir / "xml" / "PMC1000001.xml").exists())
        self.assertTrue((self.corpus_dir / "xml" / "PMC1000002.xml").exists())
        self.assertEqual(len(self.registry()), 0, "registry empty after restore")

    def test_cli_requires_condition_and_pmcid(self):
        self.assertNotEqual(self.run_cli("--pair-id", "x", "--pmcid", "PMC1000003").returncode, 0,
                            "missing --condition must fail")
        self.assertNotEqual(self.run_cli("--pair-id", "x", "--condition", "y").returncode, 0,
                            "missing --pmcid must fail")


if __name__ == "__main__":
    unittest.main()
