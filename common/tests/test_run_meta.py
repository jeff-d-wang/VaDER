"""
run_meta stamps runs. config_hash must be stable and value-sensitive;
load_config must parse the one YAML; append_run must write one registry row
carrying both the pipeline hash and the run hash.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import run_meta


class ConfigHashTest(unittest.TestCase):
    def test_stable_and_order_independent(self):
        a = run_meta.config_hash({"model": "x", "k": 1})
        b = run_meta.config_hash({"k": 1, "model": "x"})
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("cfg-"))

    def test_value_change_changes_hash(self):
        self.assertNotEqual(run_meta.config_hash({"k": 1}), run_meta.config_hash({"k": 2}))


class LoadConfigTest(unittest.TestCase):
    def test_parses_the_committed_yaml(self):
        cfg = run_meta.load_config()
        self.assertIn("retriever", cfg)
        self.assertIn("bm25", cfg)
        self.assertEqual(cfg["bm25"]["b"], 0.75)


class AppendRunTest(unittest.TestCase):
    def test_writes_one_row_with_both_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "run_registry.jsonl"
            run_config = {"retriever": "bm25", "top_k": 10}
            run_id = run_meta.append_run(
                eval_set="retrieval", run_config=run_config,
                results_path="eval/runs/x.json", metrics={"recall@10": 0.8}, registry=reg)
            rows = [json.loads(x) for x in reg.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["run_id"], run_id)
            self.assertEqual(row["eval_set"], "retrieval")
            self.assertEqual(row["run_config_hash"], run_meta.config_hash(run_config))
            self.assertEqual(row["pipeline_config_hash"],
                             run_meta.config_hash(run_meta.load_config()))
            self.assertEqual(row["metrics"], {"recall@10": 0.8})

    def test_appends_rather_than_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = Path(tmp) / "run_registry.jsonl"
            for _ in range(3):
                run_meta.append_run(eval_set="answer", run_config={"a": 1},
                                    results_path="p", metrics={}, registry=reg)
            self.assertEqual(len(reg.read_text().splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
