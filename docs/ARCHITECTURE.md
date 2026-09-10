# Current architecture

```text
PMC APIs/S3 -> ingestion/pull_corpus.py -> corpus manifest + XML
                                               |
                 exclusions CSV ---------------+ -> retrieval/build_index.py
                                               |          |
                                               |       BM25 cache + metadata
                                               |
HTTP -> service/app.py -> service/search.py -> BM25 / structure-aware chunks
                                               |
                                      common/corpus_text.py
                                      canonical source offsets

Offline eval -> retrieval + common -> per-case outputs -> immutable artifact bundle
            -> common/llm_client.py for baseline generation and LLM judging
```

The HTTP service builds the index at startup. `/query` streams complete retrieved chunks;
opt-in `/answer` retrieves bounded context and calls the async client in `common/llm_client.py`.
`common/answer.py` shares the unchanged baseline prompts and mapping with offline evaluation,
and adds strict runtime validation. Serving does not import eval, its judge or gold labels.
The synchronous offline client retains its historical retry policy; serving makes one bounded
async call. Model output is returned only after validation, with canonical source citations.

`common/run_meta.py` records full git SHA, source fingerprint, effective run configuration,
input hashes where supplied, and a copied output in a unique artifact folder. YAML remains a
pipeline description; runtime defaults are not all driven by it. Each command must record its
actual parameters. Index build checks source hashes and applies explicit exclusions.

The deadline now cooperatively interrupts the postings scan and is checked around ranking.
It is not a hard process deadline. `/answer` has per-process admission and a bounded provider
call; `/query` admission and immediate disconnect detection remain work. Each process builds its own index, so more workers multiply memory.

Use only locally built/trusted pickle indexes. Public deployment requires access controls,
request budgets and a log retention policy. Current request logs include query text.
