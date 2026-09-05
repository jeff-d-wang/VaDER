"""
Tests for the benchmark loader module. Converted from a pytest-based suite
during review (2026-09-01): this project's other test files are stdlib-only,
`python -m <pkg>.tests.test_x`, no test framework dependency, so this one now matches.
Run:

    python -m unittest eval.benchmarks.test_loader
"""
import json
import unittest
import sys
import tempfile
from pathlib import Path

from eval.benchmarks.loader import load_benchmark, load_corpus, load_qrels, load_queries


def _make_temp_dataset(base_dir: Path, name: str) -> Path:
    dataset_dir = base_dir / name
    dataset_dir.mkdir()

    docs = [
        {"id": "doc1", "text": "Machine learning is about algorithms.", "title": "ML Basics"},
        {"id": "doc2", "text": "Neural networks are powerful models."},
    ]
    with open(dataset_dir / "corpus.jsonl", "w") as f:
        for doc in docs:
            f.write(json.dumps(doc) + "\n")

    queries = [
        {"id": "q1", "text": "What is machine learning?"},
        {"id": "q2", "text": "How do neural networks work?"},
    ]
    with open(dataset_dir / "queries.jsonl", "w") as f:
        for query in queries:
            f.write(json.dumps(query) + "\n")

    with open(dataset_dir / "qrels.txt", "w") as f:
        f.write("q1 0 doc1 1\n")
        f.write("q1 0 doc2 0\n")
        f.write("q2 0 doc1 0\n")
        f.write("q2 0 doc2 1\n")

    return dataset_dir


class TestLoaders(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.dataset = _make_temp_dataset(self.base_dir, "test_dataset")

    def link(self, name):
        """load_benchmark takes a dataset NAME under a base path, so each
        test gets its own symlink to the one temp dataset."""
        (self.base_dir / name).symlink_to(self.dataset)
        return load_benchmark(name, base_path=self.base_dir)

    def test_load_corpus(self):
        docs = load_corpus(self.dataset / "corpus.jsonl")
        self.assertEqual(set(docs), {"doc1", "doc2"}, docs)
        self.assertEqual(docs["doc1"].id, "doc1")
        self.assertEqual(docs["doc1"].text, "Machine learning is about algorithms.")
        self.assertEqual(docs["doc1"].title, "ML Basics")
        self.assertIsNone(docs["doc2"].title, "title is optional and defaults to None")

    def test_load_queries(self):
        queries = load_queries(self.dataset / "queries.jsonl")
        self.assertEqual(set(queries), {"q1", "q2"}, queries)
        self.assertEqual(queries["q1"].id, "q1")
        self.assertEqual(queries["q1"].text, "What is machine learning?")

    def test_load_qrels(self):
        judgments = load_qrels(self.dataset / "qrels.txt")
        self.assertEqual(len(judgments), 4, judgments)
        j0 = judgments[0]
        self.assertEqual((j0.query_id, j0.doc_id, j0.relevance), ("q1", "doc1", 1), j0)

    def test_load_benchmark_counts(self):
        ds = self.link("link_a")
        self.assertEqual(ds.name, "link_a")
        self.assertEqual((ds.doc_count, ds.query_count, ds.judgment_count), (2, 2, 4))

    def test_get_judgments_for_query(self):
        q1 = self.link("link_b").get_judgments_for_query("q1")
        self.assertEqual(len(q1), 2, q1)
        self.assertEqual({j.doc_id for j in q1}, {"doc1", "doc2"})

    def test_get_relevant_docs(self):
        ds = self.link("link_c")
        self.assertEqual(ds.get_relevant_docs("q1"), ["doc1"])
        self.assertEqual(ds.get_relevant_docs("q2"), ["doc2"])

    def test_a_missing_dataset_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_benchmark("nonexistent", base_path=self.base_dir)

    def test_a_dataset_missing_queries_or_qrels_raises(self):
        incomplete = self.base_dir / "incomplete"
        incomplete.mkdir()
        (incomplete / "corpus.jsonl").touch()
        with self.assertRaises(FileNotFoundError):
            load_benchmark("incomplete", base_path=self.base_dir)


class TestDownloadedDatasets(unittest.TestCase):
    """The real BEIR datasets, if they have been downloaded. Skipped, never
    failed, when they have not: run download_datasets.py first."""

    EXPECTED = {
        "scifact": (5183, 300, 339),
        "nfcorpus": (3633, 323, 12334),
    }

    def counts(self, name):
        try:
            ds = load_benchmark(name)
        except FileNotFoundError:
            self.skipTest(f"{name} not downloaded (run download_datasets.py first)")
        return ds.doc_count, ds.query_count, ds.judgment_count

    def test_scifact(self):
        self.assertEqual(self.counts("scifact"), self.EXPECTED["scifact"])

    def test_nfcorpus(self):
        self.assertEqual(self.counts("nfcorpus"), self.EXPECTED["nfcorpus"])


if __name__ == "__main__":
    unittest.main()
