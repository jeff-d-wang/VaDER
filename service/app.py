"""
Phase E: the measurement surface, now in front of the real retrieval pipeline
instead of Step 0c's stub (docs/DECISION_LOG.md, "Step 0c built as a stub
handler, v1 formally dropped"). Retrieval is BM25 over the phase D
structure-aware chunk index (`retrieval/bm25.py`, `retrieval/chunker.py`),
built once at startup and searched per request. POST /answer adds opt-in
bounded synthesis; POST /query remains retrieval-only. p95 latency, TTFT (time to first streamed byte),
and concurrency are measured off this real HTTP path, per PROJECT_PLAN.md,
because those are properties of a server, not a notebook loop, and measuring
them in a loop would produce different numbers with the same names.

Run:
    cd service
    uvicorn app:app --host 0.0.0.0 --port 8000

Building the BM25 index over the full corpus at startup takes about a
minute; the process is not ready to serve until it's done (see /healthz).

Env vars (all optional, defaults point at ../corpus):
    VADER_CORPUS_DIR   directory containing manifest.csv and xml/ (default ../corpus)
    VADER_REQUEST_LOG  path to the per-request JSONL log (default ./logs/requests.jsonl)
    VADER_MAX_SCAN     chunks retrieved from the index per query, before
                       truncating to VADER_MAX_MATCHES (default 40)
    VADER_MAX_MATCHES  spans returned per query (default 5)
    VADER_DEADLINE_S   elapsed-time limit checked after search (default 5.0)

Endpoints:
    GET  /healthz   liveness, corpus size, index size, and the active config
    POST /query     {"query": "BRCA1 pathogenic variant hereditary breast cancer"}
                     -> streamed newline-delimited JSON: one "match" line per
                     supporting span found (as it's found), a "not_found" line
                     if none were, then one "summary" line.
"""
import json
import os
import time
import csv
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import anyio
import httpx

from common.answer import EXCERPT_PROMPT, format_excerpts, validate_runtime_answer
from common.llm_client import DEFAULT_MODEL, groq_chat_json_async, require_api_key
from common.trace import trace_request
from retrieval.bm25 import build_index
import service.search as searchmod

# No `from __future__ import annotations` here (unlike the rest of this
# project): FastAPI/pydantic resolve route and model annotations at runtime
# via get_type_hints, and QueryRequest is defined locally inside create_app,
# so a stringified forward ref to it can't be resolved from module globals.


def create_app(*, manifest_path: Path, xml_dir: Path, log_path: Path,
               max_scan: int = 40, max_matches: int = 5, deadline_s: float = 5.0,
               exclusions_path: Path | None = None, generation_enabled: bool = False,
               generation_timeout_s: float = 30.0, generation_concurrency: int = 2,
               context_chars: int = 12_000) -> FastAPI:
    """App factory so tests (and any future caller) can point the service at
    an isolated corpus and log file instead of the real ../corpus. The
    module-level `app` below is the instance uvicorn actually serves."""

    if min(max_scan, max_matches, deadline_s, generation_timeout_s,
           generation_concurrency, context_chars) <= 0:
        raise ValueError("service budgets must be positive")
    active_answers = 0

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.articles = articles = searchmod.load_manifest(manifest_path)
        excluded = set()
        if exclusions_path is not None:
            with exclusions_path.open(newline="") as f:
                excluded = {row["pmcid"] for row in csv.DictReader(f)}
        app.state.index = (build_index(xml_dir, [a.pmcid for a in articles],
                                      excluded_pmcids=excluded)
                           if articles else None)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(title="VaDER retrieval service", lifespan=lifespan)

    class QueryRequest(BaseModel):
        query: str = Field(min_length=3, max_length=500)

    def _stream(query: str, articles: list[searchmod.ArticleMeta], index):
        # trace_request's contextvar token must be set and reset within one
        # synchronous call: Starlette's StreamingResponse pumps a sync
        # generator one `next()` at a time via `anyio.to_thread.run_sync`,
        # each of which can land in a different thread/context, so a `with
        # trace_request(...)` straddling multiple `yield`s breaks contextvar
        # reset ("Token ... created in a different Context"). Retrieval is
        # one bounded index.search() call anyway (unlike Step 0c's stub,
        # there is no per-candidate work to genuinely stream), so it runs to
        # completion, traced, before the first yield -- which is also the
        # only place in this generator body guaranteed to execute in a
        # single dispatch.
        stats = searchmod.SearchStats()
        t0 = time.monotonic()
        ttft_s: Optional[float] = None
        n_yielded = 0
        try:
            with trace_request("query", query=query):
                matches = list(searchmod.search(query, articles, stats, index=index,
                                                max_scan=max_scan, max_matches=max_matches,
                                                deadline_s=deadline_s))
            for span in matches:
                if ttft_s is None:
                    ttft_s = time.monotonic() - t0
                n_yielded += 1
                yield json.dumps({"type": "match", **asdict(span)}) + "\n"
            if n_yielded == 0:
                if ttft_s is None:
                    ttft_s = time.monotonic() - t0
                if stats.stopped_reason == "deadline":
                    yield json.dumps({"type": "error", "code": "deadline",
                                      "note": "retrieval exceeded its deadline"}) + "\n"
                else:
                    yield json.dumps({
                        "type": "not_found", "note": "not found in this corpus",
                        "candidates_scanned": stats.candidates_scanned,
                    }) + "\n"
            yield json.dumps({
                "type": "summary", "n_matches": n_yielded,
                "candidates_matched_by_title": stats.candidates_matched_by_title,
                "candidates_scanned": stats.candidates_scanned,
                "stopped_reason": stats.stopped_reason,
            }) + "\n"
        finally:
            # Runs even on client disconnect or an exception mid-stream, so
            # every attempted request gets a log line, not just clean ones.
            total_s = time.monotonic() - t0
            record = {
                "query": query,
                "ttft_ms": round((ttft_s if ttft_s is not None else total_s) * 1000, 1),
                "total_ms": round(total_s * 1000, 1),
                "n_matches": n_yielded,
                "candidates_scanned": stats.candidates_scanned,
                "stopped_reason": stats.stopped_reason,
                "logged_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            with open(log_path, "a") as f:
                f.write(json.dumps(record) + "\n")

    @app.get("/healthz")
    def healthz(request: Request):
        articles = getattr(request.app.state, "articles", [])
        index = getattr(request.app.state, "index", None)
        if not articles or index is None or index.n_docs == 0:
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "corpus not loaded"}, status_code=503)
        return {
            "status": "ok" if articles and index else "corpus not loaded",
            "corpus_size": len(articles),
            "index_chunks": index.n_docs if index else 0,
            "config": {"max_scan": max_scan, "max_matches": max_matches, "deadline_s": deadline_s},
        }

    @app.post("/query")
    def query(req: QueryRequest, request: Request):
        articles = getattr(request.app.state, "articles", [])
        index = getattr(request.app.state, "index", None)
        if not articles or index is None or index.n_docs == 0:
            raise HTTPException(503, "corpus not loaded; check VADER_CORPUS_DIR and manifest.csv")
        return StreamingResponse(
            _stream(req.query, articles, index),
            media_type="application/x-ndjson",
        )

    @app.post("/answer")
    async def answer(req: QueryRequest, request: Request):
        nonlocal active_answers
        if not generation_enabled:
            raise HTTPException(503, "generation is disabled; set VADER_GENERATION_ENABLED=1")
        index = getattr(request.app.state, "index", None)
        if index is None or index.n_docs == 0:
            raise HTTPException(503, "corpus not loaded")
        try:
            key = require_api_key(None)
        except RuntimeError:
            raise HTTPException(503, "generation credentials are unavailable") from None
        # No await between admission and increment: atomic on this event loop.
        # ponytail: per-process admission; shared quotas before multiple workers or public access.
        if active_answers >= generation_concurrency:
            raise HTTPException(429, "generation capacity reached", headers={"Retry-After": "1"})
        active_answers += 1
        started = time.monotonic()
        outcome = "cancelled"
        trace_id = None
        try:
            with trace_request("answer", model=DEFAULT_MODEL) as trace_id:
                stats = searchmod.SearchStats()
                def retrieve():
                    return list(searchmod.search(
                        req.query, request.app.state.articles, stats, index=index,
                        max_scan=max_scan, max_matches=max_matches, deadline_s=deadline_s))
                matches = await anyio.to_thread.run_sync(retrieve)
                if stats.stopped_reason == "deadline":
                    raise HTTPException(504, "retrieval deadline exceeded")
                evidence = []
                remaining = context_chars
                for match in matches:
                    if len(match.text) <= remaining:
                        evidence.append(asdict(match))
                        remaining -= len(match.text)
                if not evidence:
                    outcome = "no_context" if matches else "not_found"
                    return {"not_found": True, "answer_text": "No evidence available within retrieval and context limits.",
                            "claims": [], "direction": "none", "strength": "unstated",
                            "evidence": [], "outcome": outcome, "trace_id": trace_id}
                excerpts = [(item, item["text"]) for item in evidence]
                prompt = EXCERPT_PROMPT.format(query=req.query, excerpts=format_excerpts(excerpts))
                raw = await groq_chat_json_async(prompt, api_key=key, timeout_s=generation_timeout_s)
                result = validate_runtime_answer(raw, excerpts)
                outcome = "abstained" if result["not_found"] else "answered"
                return {**result, "evidence": evidence, "outcome": outcome, "trace_id": trace_id,
                        "model": DEFAULT_MODEL, "prompt_version": "runtime_excerpt_v1"}
        except (TimeoutError, httpx.TimeoutException):
            outcome = "timeout"
            raise HTTPException(504, "generation deadline exceeded") from None
        except httpx.HTTPError:
            outcome = "provider_error"
            raise HTTPException(502, "generation provider unavailable") from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            outcome = "invalid_output"
            raise HTTPException(502, "generation returned invalid output") from None
        except HTTPException:
            outcome = "retrieval_error"
            raise
        finally:
            active_answers -= 1
            with log_path.open("a") as f:
                f.write(json.dumps({"endpoint": "/answer", "trace_id": trace_id,
                                    "outcome": outcome,
                                    "total_ms": round((time.monotonic() - started) * 1000, 1),
                                    "logged_at_utc": datetime.now(timezone.utc).isoformat()}) + "\n")

    return app


_CORPUS_DIR = Path(os.environ.get("VADER_CORPUS_DIR", Path(__file__).resolve().parent.parent / "corpus"))

app = create_app(
    manifest_path=_CORPUS_DIR / "manifest.csv",
    xml_dir=_CORPUS_DIR / "xml",
    log_path=Path(os.environ.get("VADER_REQUEST_LOG", Path(__file__).resolve().parent / "logs" / "requests.jsonl")),
    generation_enabled=os.environ.get("VADER_GENERATION_ENABLED") == "1",
    max_scan=int(os.environ.get("VADER_MAX_SCAN", "40")),
    max_matches=int(os.environ.get("VADER_MAX_MATCHES", "5")),
    deadline_s=float(os.environ.get("VADER_DEADLINE_S", "5.0")),
    exclusions_path=(Path(os.environ["VADER_EXCLUSIONS"]) if "VADER_EXCLUSIONS" in os.environ
                     else Path(__file__).resolve().parent.parent / "eval/held_out/held_out_pmcids.csv"),
)
