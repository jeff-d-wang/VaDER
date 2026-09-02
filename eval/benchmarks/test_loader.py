"""
Tests for the benchmark loader module. Converted from a pytest-based suite
during review (2026-09-01): this project's other test files are stdlib-only,
`python test_x.py`, no test framework dependency, so this one now matches.
Run:

    python test_loader.py
"""
import json
import sys
import tempfile
from pathlib import Path

from loader import load_benchmark, load_corpus, load_qrels, load_queries


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


def run_tests():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name}  {detail}")
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp_s:
        base_dir = Path(tmp_s)
        temp_dataset = _make_temp_dataset(base_dir, "test_dataset")

        # --- load_corpus ---
        docs = load_corpus(temp_dataset / "corpus.jsonl")
        check("load_corpus: reads both documents", len(docs) == 2, docs)
        check("load_corpus: doc1 present", "doc1" in docs)
        check("load_corpus: doc2 present", "doc2" in docs)
        check("load_corpus: doc1 fields", docs["doc1"].id == "doc1"
              and docs["doc1"].text == "Machine learning is about algorithms."
              and docs["doc1"].title == "ML Basics")
        check("load_corpus: title optional, defaults to None", docs["doc2"].title is None)

        # --- load_queries ---
        queries = load_queries(temp_dataset / "queries.jsonl")
        check("load_queries: reads both queries", len(queries) == 2, queries)
        check("load_queries: q1 present", "q1" in queries)
        check("load_queries: q2 present", "q2" in queries)
        check("load_queries: q1 fields", queries["q1"].id == "q1"
              and queries["q1"].text == "What is machine learning?")

        # --- load_qrels ---
        judgments = load_qrels(temp_dataset / "qrels.txt")
        check("load_qrels: reads all 4 judgment lines", len(judgments) == 4, judgments)
        j0 = judgments[0]
        check("load_qrels: first judgment fields",
              j0.query_id == "q1" and j0.doc_id == "doc1" and j0.relevance == 1, j0)

        # --- BenchmarkDataset, via load_benchmark against a symlinked dataset dir ---
        for i, test_name in enumerate(["link_a", "link_b", "link_c"], 1):
            (base_dir / test_name).symlink_to(temp_dataset)

        ds = load_benchmark("link_a", base_path=base_dir)
        check("load_benchmark: name", ds.name == "link_a")
        check("load_benchmark: doc_count", ds.doc_count == 2)
        check("load_benchmark: query_count", ds.query_count == 2)
        check("load_benchmark: judgment_count", ds.judgment_count == 4)

        ds_b = load_benchmark("link_b", base_path=base_dir)
        q1_judgments = ds_b.get_judgments_for_query("q1")
        check("get_judgments_for_query: 2 judgments for q1", len(q1_judgments) == 2, q1_judgments)
        check("get_judgments_for_query: doc ids", {j.doc_id for j in q1_judgments} == {"doc1", "doc2"})

        ds_c = load_benchmark("link_c", base_path=base_dir)
        check("get_relevant_docs: q1", ds_c.get_relevant_docs("q1") == ["doc1"])
        check("get_relevant_docs: q2", ds_c.get_relevant_docs("q2") == ["doc2"])

        # --- error paths ---
        try:
            load_benchmark("nonexistent", base_path=Path("/tmp"))
            check("missing dataset raises FileNotFoundError", False)
        except FileNotFoundError:
            check("missing dataset raises FileNotFoundError", True)

        incomplete_dir = base_dir / "incomplete"
        incomplete_dir.mkdir()
        (incomplete_dir / "corpus.jsonl").touch()
        try:
            load_benchmark("incomplete", base_path=base_dir)
            check("incomplete dataset (missing queries/qrels) raises FileNotFoundError", False)
        except FileNotFoundError:
            check("incomplete dataset (missing queries/qrels) raises FileNotFoundError", True)

    # --- the actual downloaded datasets, skipped (not failed) if not present ---
    for dataset_name, expected in [
        ("scifact", {"doc_count": 5183, "query_count": 300, "judgment_count": 339}),
        ("nfcorpus", {"doc_count": 3633, "query_count": 323, "judgment_count": 12334}),
    ]:
        try:
            ds = load_benchmark(dataset_name)
        except FileNotFoundError:
            print(f"  skip  {dataset_name}: not downloaded (run download_datasets.py first)")
            continue
        check(f"{dataset_name}: doc_count == {expected['doc_count']}",
              ds.doc_count == expected["doc_count"], ds.doc_count)
        check(f"{dataset_name}: query_count == {expected['query_count']}",
              ds.query_count == expected["query_count"], ds.query_count)
        check(f"{dataset_name}: judgment_count == {expected['judgment_count']}",
              ds.judgment_count == expected["judgment_count"], ds.judgment_count)

    if failures:
        print(f"\n{len(failures)} FAILED: {failures}")
        sys.exit(1)
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run_tests()
