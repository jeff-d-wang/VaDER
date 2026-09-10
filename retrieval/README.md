# Retrieval

`bm25.py` indexes `Chunk` objects from `common.corpus_text`. `chunker.py` provides structure-aware
and paragraph-only chunkers. `index_from_chunks` is the shared construction path; benchmarks use
`build_index_from_texts`. Retrieval has no dependency on eval code.

Build a new, hash-verified evaluation corpus view from the repo root:

```sh
python -m retrieval.build_index --out eval/runs/index-new.pkl
python -m retrieval.build_index --paragraphs --out eval/runs/index-paragraph-new.pkl
```

The builder applies `eval/held_out/held_out_pmcids.csv` explicitly, even when excluded XML exists.
Choose a fresh output name. Pickles are trusted local caches, never untrusted uploads.

`ir_metrics.py` implements recall, MRR and nDCG. Current aggregate CIs resample queries; paired
styles/article clusters require a follow-up before representative quality claims. Tests compare
BM25 against brute force, including ties. Search supports an optional cooperative deadline.
