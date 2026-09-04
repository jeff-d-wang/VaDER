# Benchmark Setup Manifest

## What was created

This directory contains the infrastructure for Tier 1, M1 (eval harness with benchmark datasets).

### Data Files (git-ignored, regenerable)

Both datasets are downloaded from the BEIR benchmark collection via `ir_datasets`:

- **scifact/** (7.6M corpus.jsonl + 5.6K qrels.txt + 34K queries.jsonl)
  - 5,183 documents (scientific paper abstracts)
  - 300 queries (claims to verify)
  - 339 relevance judgments (binary: claim supported or not)
  - Avg relevant per query: 1.1

- **nfcorpus/** (5.7M corpus.jsonl + 285K qrels.txt + 17K queries.jsonl)
  - 3,633 documents (health/nutrition information)
  - 323 queries
  - 12,334 relevance judgments (graded: 0-2, interpreted as binary)
  - Avg relevant per query: 38.2

Both datasets can be re-downloaded with `python -m eval.benchmarks.download_datasets`.

### Code Files (committed)

- **loader.py**: Python module with normalized interface
  - Data classes: `Document`, `Query`, `Judgment`, `BenchmarkDataset`
  - Functions: `load_benchmark(name)`, `load_corpus()`, `load_queries()`, `load_qrels()`
  - Utility methods: `get_judgments_for_query()`, `get_relevant_docs()`

- **test_loader.py**: Test suite covering:
  - Corpus/query/qrel loading
  - Data structure validation
  - Real dataset verification (run with `python -m eval.benchmarks.test_loader`, stdlib-only, no pytest)

- **download_datasets.py**: Standalone script to fetch and normalize datasets from BEIR

- **__init__.py**: Package exports for `from benchmarks import ...`

- **README.md**: Complete documentation
  - Dataset descriptions and statistics
  - File format specifications (corpus.jsonl, queries.jsonl, qrels.txt)
  - Python API reference
  - Licensing terms (CC-BY-4.0 for both)
  - References and citations

## Usage

```python
from eval.benchmarks import load_benchmark

# Load a dataset
scifact = load_benchmark("scifact")
nfcorpus = load_benchmark("nfcorpus")

# Access data
print(scifact.doc_count, scifact.query_count, scifact.judgment_count)

query_id = "1"
relevant_docs = scifact.get_relevant_docs(query_id)
query_text = scifact.queries[query_id].text
doc_text = scifact.documents[relevant_docs[0]].text
```

## Design Decisions

1. **JSONL format for data files**: Human-readable, line-based, enables streaming large files
2. **TREC qrels format**: Standard in IR, compatible with standard evaluation tools
3. **Source-span vs. chunk labels**: Gold labels attach to source documents (via doc_id), not chunks. This enables re-chunking without re-labeling
4. **No scoring in this module**: Scoring requires domain expertise and rubric discussion (M1 next step)

## Next Steps (M1 continued)

1. Hand-write the eval scorer (claim-to-evidence groundedness for SciFact, correctness for domain set)
2. Establish baselines: no-retrieval, BM25-only, whole-document
3. Build domain-specific eval set on VaDER corpus with cancer genomics expertise
4. Measure Cohen's kappa with a second annotator on a sample

## References

- [PROJECT_PLAN.md](../../docs/PROJECT_PLAN.md) Tier 1, M1
- [BEIR Benchmark](https://github.com/beir-cellar/beir)
- [ir_datasets](https://ir-datasets.com/)
