# Service: Step 0c measurement surface

A FastAPI app that answers a query by streaming supporting spans found by literal keyword search
over the Step 0b corpus. See the module docstrings in `app.py` and `search.py` for the mechanics.

## This is a stub, on purpose

`search.py` is a trivial keyword matcher: no chunker, no embedder, no vector DB, no LLM. The 
service wraps a handler deliberately simple enough that it obviously isn't a quality claim. 
Full rationale in `../docs/DECISION_LOG.md`, "Step 0c built as a stub handler, v1 formally dropped."

What it's for regardless: **p95, TTFT, and concurrency are properties of a server, not a notebook
loop.** This app is the real HTTP path every later latency number in this project gets measured
against, per `PROJECT_PLAN.md` 0c. The handler gets replaced wholesale once M1/M2 (eval harness,
instrumentation) exist and a real retriever/generator is built and scored against them; the
FastAPI app, request logging, streaming, and timeout/backpressure scaffolding are what carries
forward.

## Run it

```
pip install -r requirements.txt
cd service
uvicorn app:app --host 0.0.0.0 --port 8000
```

By default it reads the corpus from `../corpus` (the Step 0b pull). Override with
`VADER_CORPUS_DIR` if running from elsewhere. See the docstring at the top of `app.py` for the
rest of the env vars (`VADER_MAX_SCAN`, `VADER_MAX_MATCHES`, `VADER_DEADLINE_S`,
`VADER_REQUEST_LOG`).

```
curl http://127.0.0.1:8000/healthz

curl -N -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "BRCA1 pathogenic variant hereditary breast and ovarian cancer"}'
```

The response streams newline-delimited JSON: one `"match"` line per supporting span found, as it's
found (this is what makes TTFT meaningful), a `"not_found"` line if none were, then one
`"summary"` line with the search's stop reason (`max_matches`, `max_scan`, `deadline`, or
`exhausted`, the backpressure mechanism: an unbounded or zero-hit query cannot hang the server).

## Test it

```
python test_app.py
```

Builds a tiny synthetic corpus per test in a temp dir, so it never touches `../corpus` and stays
fast and hermetic. Covers matching, the not-found path, a manifest row whose XML is missing on
disk, the `max_matches` cap, request validation, the per-request JSONL log, and the empty-corpus
503 path.

## Measure it

`loadtest.py` is what turns "the server responds" into a `RESULTS.md` row: real concurrent HTTP
requests against the live server, reporting p50/p95 total latency and p50/p95 TTFT with a
percentile-bootstrap 95% CI, per `RESULTS.md`'s rule that a number needs an interval and an `n`.

```
uvicorn app:app --port 8000 &
python loadtest.py --base-url http://127.0.0.1:8000 --n 150 --concurrency 20
```

`--seed` controls both which of the 10 built-in sample queries get sent and the bootstrap
resampling, so a run is reproducible. Writes `loadtest_result.json` (git-ignored, regenerated
every run; the durable record is the `RESULTS.md` row, not this file).

## Layout

```
service/
  app.py            FastAPI app: /healthz, /query (streaming, NDJSON)
  search.py          the stub keyword-match handler, isolated behind one function boundary
  test_app.py        offline test suite, synthetic corpus fixture
  loadtest.py        concurrency/latency measurement against a live server
  logs/               git-ignored: requests.jsonl, one line per request served
  requirements.txt
```
