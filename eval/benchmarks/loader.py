"""
Load benchmark datasets (SciFact, NFCorpus) into a normalized structure.

Common data structures:
- Document: id, text, and optional title
- Query: id, text
- Judgment: query_id, doc_id, relevance (0 or 1 for binary relevance)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional


@dataclass
class Document:
    """A document in the corpus."""

    id: str
    text: str
    title: Optional[str] = None


@dataclass
class Query:
    """A query."""

    id: str
    text: str


@dataclass
class Judgment:
    """A relevance judgment."""

    query_id: str
    doc_id: str
    relevance: int


@dataclass
class BenchmarkDataset:
    """A benchmark dataset with corpus, queries, and relevance judgments."""

    name: str
    path: Path
    documents: dict[str, Document]
    queries: dict[str, Query]
    judgments: list[Judgment]

    @property
    def doc_count(self) -> int:
        """Number of documents in the corpus."""
        return len(self.documents)

    @property
    def query_count(self) -> int:
        """Number of queries."""
        return len(self.queries)

    @property
    def judgment_count(self) -> int:
        """Number of relevance judgments."""
        return len(self.judgments)

    def get_judgments_for_query(self, query_id: str) -> list[Judgment]:
        """Get all judgments for a specific query."""
        return [j for j in self.judgments if j.query_id == query_id]

    def get_relevant_docs(self, query_id: str) -> list[str]:
        """Get doc IDs relevant to a query (relevance > 0)."""
        return [j.doc_id for j in self.get_judgments_for_query(query_id) if j.relevance > 0]


def load_corpus(path: Path) -> dict[str, Document]:
    """Load documents from corpus.jsonl."""
    documents = {}
    with open(path) as f:
        for line in f:
            doc_dict = json.loads(line)
            doc = Document(
                id=doc_dict["id"],
                text=doc_dict["text"],
                title=doc_dict.get("title"),
            )
            documents[doc.id] = doc
    return documents


def load_queries(path: Path) -> dict[str, Query]:
    """Load queries from queries.jsonl."""
    queries = {}
    with open(path) as f:
        for line in f:
            query_dict = json.loads(line)
            query = Query(id=query_dict["id"], text=query_dict["text"])
            queries[query.id] = query
    return queries


def load_qrels(path: Path) -> list[Judgment]:
    """Load relevance judgments from qrels.txt (TREC format)."""
    judgments = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 4:
                query_id, _, doc_id, relevance = parts[0], parts[1], parts[2], int(parts[3])
                judgments.append(Judgment(query_id=query_id, doc_id=doc_id, relevance=relevance))
    return judgments


def load_benchmark(dataset_name: str, base_path: Path = None) -> BenchmarkDataset:
    """
    Load a benchmark dataset.

    Args:
        dataset_name: "scifact" or "nfcorpus"
        base_path: directory containing the dataset subdirectories. Defaults to this file's directory.

    Returns:
        A BenchmarkDataset instance.
    """
    if base_path is None:
        base_path = Path(__file__).parent

    dataset_path = base_path / dataset_name
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    corpus_path = dataset_path / "corpus.jsonl"
    queries_path = dataset_path / "queries.jsonl"
    qrels_path = dataset_path / "qrels.txt"

    if not all([corpus_path.exists(), queries_path.exists(), qrels_path.exists()]):
        raise FileNotFoundError(f"Missing dataset files in {dataset_path}")

    documents = load_corpus(corpus_path)
    queries = load_queries(queries_path)
    judgments = load_qrels(qrels_path)

    return BenchmarkDataset(
        name=dataset_name,
        path=dataset_path,
        documents=documents,
        queries=queries,
        judgments=judgments,
    )
