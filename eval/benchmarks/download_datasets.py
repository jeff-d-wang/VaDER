"""
Download SciFact and NFCorpus datasets from ir_datasets and normalize their structure.

Datasets are saved under their respective directories with the following structure:
  scifact/
    corpus.jsonl          - documents (id, text, title)
    queries.jsonl         - queries (id, text)
    qrels.txt             - relevance judgments (qid, 0, docid, rel)
  nfcorpus/
    corpus.jsonl          - documents (id, text)
    queries.jsonl         - queries (id, text)
    qrels.txt             - relevance judgments (qid, 0, docid, rel)
"""

import json
import ir_datasets
from pathlib import Path

BENCHMARK_DIR = Path(__file__).parent
DATASETS = {
    "scifact": ("beir/scifact", ["test"]),
    "nfcorpus": ("beir/nfcorpus", ["test"]),
}


def download_and_normalize(dataset_name: str, ir_dataset_id: str, splits: list) -> None:
    """Download a dataset and normalize it to standard format."""
    output_dir = BENCHMARK_DIR / dataset_name
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {dataset_name} from ir_datasets...")

    # Load datasets for all splits
    datasets = [ir_datasets.load(f"{ir_dataset_id}/{split}") for split in splits]

    # Collect all docs, queries, qrels across splits
    all_docs = {}
    all_queries = {}
    all_qrels = []

    for dataset in datasets:
        # Collect corpus (dedup by doc_id)
        for doc in dataset.docs_iter():
            if doc.doc_id not in all_docs:
                all_docs[doc.doc_id] = doc

        # Collect queries (dedup by query_id)
        for query in dataset.queries_iter():
            if query.query_id not in all_queries:
                all_queries[query.query_id] = query

        # Collect qrels
        for qrel in dataset.qrels:
            all_qrels.append(qrel)

    # Write corpus
    corpus_path = output_dir / "corpus.jsonl"
    print(f"  Writing corpus ({len(all_docs)} docs) to {corpus_path}")
    with open(corpus_path, "w") as f:
        for doc_id, doc in sorted(all_docs.items()):
            doc_dict = {"id": doc.doc_id, "text": doc.text}
            if hasattr(doc, "title") and doc.title:
                doc_dict["title"] = doc.title
            f.write(json.dumps(doc_dict) + "\n")

    # Write queries
    queries_path = output_dir / "queries.jsonl"
    print(f"  Writing queries ({len(all_queries)} queries) to {queries_path}")
    with open(queries_path, "w") as f:
        for query_id, query in sorted(all_queries.items()):
            f.write(json.dumps({"id": query.query_id, "text": query.text}) + "\n")

    # Write qrels (TREC format: qid 0 docid relevance)
    qrels_path = output_dir / "qrels.txt"
    print(f"  Writing qrels ({len(all_qrels)} judgments) to {qrels_path}")
    with open(qrels_path, "w") as f:
        for qrel in sorted(all_qrels, key=lambda x: (x.query_id, x.doc_id)):
            f.write(f"{qrel.query_id} 0 {qrel.doc_id} {qrel.relevance}\n")

    print(f"  Done. Corpus: {corpus_path}, Queries: {queries_path}, Qrels: {qrels_path}")


if __name__ == "__main__":
    for dataset_name, (ir_dataset_id, splits) in DATASETS.items():
        download_and_normalize(dataset_name, ir_dataset_id, splits)
    print("All datasets downloaded successfully.")
