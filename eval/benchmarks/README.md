# Benchmark Datasets

This directory contains publicly available benchmark datasets for evaluation. Each dataset includes a corpus, queries, and relevance judgments.

## Overview

| Dataset | Corpus | Queries | Avg. Relevant/Query | Use Case |
|---------|--------|---------|---------------------|----------|
| **SciFact** | 5,183 docs | 300 | 1.1 | Claim-to-evidence retrieval; validates groundedness scorer |
| **NFCorpus** | 3,633 docs | 323 | 38.2 | Dense judgments; retrieval-metric plumbing and small-scale testing |

Both datasets are part of the [BEIR benchmark collection](https://github.com/beir-cellar/beir) and are publicly available under their respective licenses.

## Directory Structure

Each dataset is organized as a subdirectory with the following files:

```
benchmarks/
├── scifact/
│   ├── corpus.jsonl       # Documents (id, text, title)
│   ├── queries.jsonl      # Queries (id, text)
│   └── qrels.txt          # Relevance judgments (TREC format)
├── nfcorpus/
│   ├── corpus.jsonl
│   ├── queries.jsonl
│   └── qrels.txt
├── loader.py              # Loader module with normalized interface
└── README.md              # This file
```

## File Formats

### corpus.jsonl

One document per line, JSON format with fields:
- `id` (str): Document identifier
- `text` (str): Full document text
- `title` (str, optional): Document title

Example:
```json
{"id": "10009203", "text": "As the nervous system develops...", "title": "Structural Homeostasis..."}
```

### queries.jsonl

One query per line, JSON format with fields:
- `id` (str): Query identifier
- `text` (str): Query text

Example:
```json
{"id": "1", "text": "Are there computing systems that have the same energy density as muscle?"}
```

### qrels.txt

Relevance judgments in TREC format: one per line with fields separated by whitespace:
- Column 1: query_id
- Column 2: iteration (always 0)
- Column 3: doc_id
- Column 4: relevance (0 for non-relevant, 1 for relevant)

Example:
```
1 0 31715818 1
1 0 27472341 0
2 0 10020701 1
```

## Python API

The `loader.py` module provides a simple interface for loading and querying datasets:

```python
from loader import load_benchmark, Document, Query, Judgment, BenchmarkDataset

# Load a dataset
dataset = load_benchmark("scifact")

# Access metadata
print(f"Corpus: {dataset.doc_count} docs")
print(f"Queries: {dataset.query_count}")
print(f"Judgments: {dataset.judgment_count}")

# Access documents and queries
doc = dataset.documents["31715818"]
query = dataset.queries["1"]

# Query relevance judgments
judgments = dataset.get_judgments_for_query("1")
relevant_docs = dataset.get_relevant_docs("1")
```

### Data Classes

- **Document**: `id`, `text`, `title` (optional)
- **Query**: `id`, `text`
- **Judgment**: `query_id`, `doc_id`, `relevance`
- **BenchmarkDataset**: `name`, `path`, `documents`, `queries`, `judgments` with utility methods:
  - `doc_count`: Total number of documents
  - `query_count`: Total number of queries
  - `judgment_count`: Total number of relevance judgments
  - `get_judgments_for_query(query_id)`: Get all judgments for a query
  - `get_relevant_docs(query_id)`: Get doc IDs relevant to a query (relevance > 0)

## Dataset Details

### SciFact

**Source:** [BEIR Benchmark Collection](https://github.com/beir-cellar/beir/raw/main/datasets/scifact.zip)

**Description:** A dataset for claim verification in scientific papers. Each claim is paired with evidence from academic papers.

**Statistics:**
- Corpus: 5,183 documents (scientific paper abstracts)
- Queries: 300 claims
- Relevance judgments: 339 binary judgments
- Average relevant documents per query: 1.1

**Relevance Scale:** Binary (0 or 1)

**Citation:**
```
@article{thakur2021beir,
  title={BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models},
  author={Thakur, Nandan and others},
  journal={arXiv preprint arXiv:2104.08663},
  year={2021}
}
```

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) (check individual papers for restrictions)

### NFCorpus

**Source:** [BEIR Benchmark Collection](https://github.com/beir-cellar/beir/raw/main/datasets/nfcorpus.zip)

**Description:** A nutrition and health information retrieval dataset with dense relevance judgments. Original corpus from the [TREC-Diabetes challenge](https://sites.google.com/view/trec-dd/).

**Statistics:**
- Corpus: 3,633 documents (health/nutrition documents)
- Queries: 323 information needs
- Relevance judgments: 12,334 graded judgments
- Average relevant documents per query: 38.2

**Relevance Scale:** Graded (0-2, treated as binary in some contexts)

**Citation:**
```
@inproceedings{koopman2016exploring,
  title={Exploring the benefits of document pool diversity for medical information search},
  author={Koopman, Bevan and Zuccon, Guido and Maistro, Maria and others},
  booktitle={International Conference of the Cross-Language Evaluation Forum for European Languages},
  year={2016}
}
```

**License:** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)

## Downloading and Setup

The datasets are pre-downloaded and normalized in the subdirectories. To re-download from scratch:

```bash
python download_datasets.py
```

This script uses the `ir_datasets` library to fetch from the BEIR mirrors. It requires:
- Python 3.7+
- `ir_datasets` package (install via `pip install ir_datasets`)

## Usage Notes

1. **No hand labeling required**: Both datasets come with complete relevance judgments, suitable for automated evaluation.
2. **Small scale by design**: SciFact and NFCorpus are intentionally small to enable fast iteration. At about 300-300 queries each, they are ideal for validating infrastructure before moving to larger benchmarks.
3. **Span-based evaluation**: The scoring harness uses span-level provenance. These datasets have document-level judgments; retrieval success is determined by whether any part of the retrieved document overlaps the relevant evidence.
4. **Not domain-specific**: These are general biomedical/scientific datasets. Domain-specific evaluation (cancer genomics, variant-disease evidence) happens on a separate hand-labeled set built from the VaDER corpus.

## References

- **BEIR**: Thakur et al., 2021. *BEIR: A Heterogenous Benchmark for Zero-shot Evaluation of Information Retrieval Models.* arXiv:2104.08663
- **SciFact**: Wadden et al., 2020. *Fact or Fiction: Predicting Verifiability in Claim Verification.* ACL 2020.
- **NFCorpus**: Koopman et al., 2016. *Exploring the benefits of document pool diversity for medical information search.* CLEF 2016.

## See Also

- [BEIR Benchmark](https://github.com/beir-cellar/beir)
- [ir_datasets Documentation](https://ir-datasets.com/)
- Project: [PROJECT_PLAN.md](../../docs/PROJECT_PLAN.md) (Tier 1, M1: Eval sets, scorer, and baselines)
