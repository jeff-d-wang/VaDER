# Service: the retrieval measurement surface

A FastAPI app that answers a query by streaming supporting spans found by BM25 over the phase D
structure-aware chunk index. See the module docstrings in `app.py` and `search.py` for the
mechanics.

## Phase E, retrieval-only so far

`search.py` builds a real `retrieval/bm25.py` index over the corpus at startup (the same
structure-aware chunking, `retrieval/chunker.py`, phase D measured) and searches it per request.
**No LLM yet.** Generation is Phase E's next piece, kept separate on purpose: a load test against
retrieval alone gives an attributable number for that stage before the two are bundled, per
`docs/DECISION_LOG.md`'s v1 definition (each measured upgrade lands alone with its own paired
test, not bundled). Full rationale for how this replaced the Step 0c stub keyword matcher is in
`docs/DECISION_LOG.md`, "Step 0c built as a stub handler, v1 formally dropped" (history) and the
phase E service rewrite entry (current).

What it's for regardless: **p95, TTFT, and concurrency are properties of a server, not a notebook
loop.** This app is the real HTTP path every latency number in this project gets measured against,
per `PROJECT_PLAN.md`. The FastAPI app, request logging, streaming, and timeout/backpressure
scaffolding built at Step 0c carried forward unchanged; only the handler behind `/query` is real
now.

## Run it

```
pip install -r requirements.txt
uvicorn service.app:app --host 0.0.0.0 --port 8000
```

By default it reads the corpus from `../corpus` (the Step 0b pull). Override with
`VADER_CORPUS_DIR` if running from elsewhere. **Building the BM25 index over the full 7,863-article
corpus at startup takes about a minute**; `/healthz` reports `"status": "corpus not loaded"` until
it's done. See the docstring at the top of `app.py` for the rest of the env vars
(`VADER_MAX_SCAN`, `VADER_MAX_MATCHES`, `VADER_DEADLINE_S`, `VADER_REQUEST_LOG`).

```
curl http://127.0.0.1:8000/healthz

curl -N -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "BRCA1 pathogenic variant hereditary breast and ovarian cancer"}'
```

The response streams newline-delimited JSON: one `"match"` line per supporting chunk (as ranked by
BM25), a `"not_found"` line if none matched, then one `"summary"` line with the search's stop
reason (`max_matches`, `deadline`, `exhausted`, or `no_query_words`). Retrieval is one bounded
index lookup rather than the old stub's incremental per-candidate file scan, so all matches are
known before the first line is sent; TTFT still measures real work; it now measures the full
retrieval call rather than time-to-first-XML-open. See `search.py`'s module docstring for what
changed under `SearchStats`' field names, which stayed the same on the wire.

Every request is traced (`common/trace.py`): a `query` trace with a `retrieve` span
(`retriever=bm25`, `retrieval.hit_count`), written as JSONL to `VADER_TRACE_FILE` (default
`../traces/spans.jsonl`).

## Test it

```
python -m service.test_app
```

Builds a tiny synthetic corpus per test in a temp dir, so it never touches `../corpus` and stays
fast and hermetic (the BM25 index built from 4 articles is instant). Covers matching, the
not-found path, a manifest row whose XML is missing on disk, the `max_matches` cap, request
validation, the per-request JSONL log, the retrieval trace span, and the empty-corpus 503 path.

## Measure it

`loadtest.py` is what turns "the server responds" into a `RESULTS.md` row: real concurrent HTTP
requests against the live server, reporting p50/p95 total latency and p50/p95 TTFT with a
percentile-bootstrap 95% CI, per `RESULTS.md`'s rule that a number needs an interval and an `n`.

```
uvicorn service.app:app --port 8000 &
python -m service.loadtest --base-url http://127.0.0.1:8000 --n 150 --concurrency 20
```

`--seed` controls both which of the 10 built-in sample queries get sent and the bootstrap
resampling, so a run is reproducible. Writes `loadtest_result.json` (git-ignored, regenerated
every run; the durable record is the `RESULTS.md` row, not this file). This measures the
**retrieval-only** stage: no generation cost yet, so a `RESULTS.md` row off this run is a
component number against the task contract's 1.5s TTFT target, not yet the full 6s p95 / $0.05
per-query numbers, which need the generation half.

## Layout

```
service/
  app.py            FastAPI app: /healthz, /query (streaming, NDJSON), builds the BM25 index at startup
  search.py          BM25 retrieval over the phase D chunk index, isolated behind one function boundary
  test_app.py        offline test suite, synthetic corpus fixture
  loadtest.py        concurrency/latency measurement against a live server
  logs/               git-ignored: requests.jsonl, one line per request served
  requirements.txt
```
