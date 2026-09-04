"""
Step 0c: the measurement surface. A FastAPI service wrapping the stub
keyword-match handler in search.py over the Step 0b corpus. Not a retrieval
system: see docs/DECISION_LOG.md, "Step 0c built as a stub handler, v1
formally dropped." It exists so p95 latency, TTFT (time to first streamed
byte), and concurrency get measured off a real HTTP path from the first
number, per PROJECT_PLAN.md 0c -- those are properties of a server, not a
notebook loop, and measuring them in a loop would produce different numbers
with the same names.

Run:
    cd service
    uvicorn app:app --host 0.0.0.0 --port 8000

Env vars (all optional, defaults point at ../corpus):
    VADER_CORPUS_DIR   directory containing manifest.csv and xml/ (default ../corpus)
    VADER_REQUEST_LOG  path to the per-request JSONL log (default ./logs/requests.jsonl)
    VADER_MAX_SCAN     candidate XML files opened per query (default 40)
    VADER_MAX_MATCHES  spans returned per query (default 5)
    VADER_DEADLINE_S   wall-clock cap per search (default 5.0)

Endpoints:
    GET  /healthz   liveness, corpus size, and the active config
    POST /query     {"query": "BRCA1 pathogenic variant hereditary breast cancer"}
                     -> streamed newline-delimited JSON: one "match" line per
                     supporting span found (as it's found), a "not_found" line
                     if none were, then one "summary" line.
"""
import json
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import service.search as searchmod

# No `from __future__ import annotations` here (unlike the rest of this
# project): FastAPI/pydantic resolve route and model annotations at runtime
# via get_type_hints, and QueryRequest is defined locally inside create_app,
# so a stringified forward ref to it can't be resolved from module globals.


def create_app(*, manifest_path: Path, xml_dir: Path, log_path: Path,
               max_scan: int = 40, max_matches: int = 5, deadline_s: float = 5.0) -> FastAPI:
    """App factory so tests (and any future caller) can point the service at
    an isolated corpus and log file instead of the real ../corpus. The
    module-level `app` below is the instance uvicorn actually serves."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.articles = searchmod.load_manifest(manifest_path)
        app.state.xml_dir = xml_dir
        log_path.parent.mkdir(parents=True, exist_ok=True)
        yield

    app = FastAPI(title="VaDER Step 0c measurement surface", lifespan=lifespan)

    class QueryRequest(BaseModel):
        query: str = Field(min_length=3, max_length=500)

    def _stream(query: str, articles: list[searchmod.ArticleMeta], corpus_xml_dir: Path):
        stats = searchmod.SearchStats()
        t0 = time.monotonic()
        ttft_s: Optional[float] = None
        n_yielded = 0
        try:
            for span in searchmod.search(query, articles, corpus_xml_dir, stats,
                                          max_scan=max_scan, max_matches=max_matches,
                                          deadline_s=deadline_s):
                if ttft_s is None:
                    ttft_s = time.monotonic() - t0
                n_yielded += 1
                yield json.dumps({"type": "match", **asdict(span)}) + "\n"
            if n_yielded == 0:
                if ttft_s is None:
                    ttft_s = time.monotonic() - t0
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
        return {
            "status": "ok" if articles else "corpus not loaded",
            "corpus_size": len(articles),
            "config": {"max_scan": max_scan, "max_matches": max_matches, "deadline_s": deadline_s},
        }

    @app.post("/query")
    def query(req: QueryRequest, request: Request):
        articles = getattr(request.app.state, "articles", [])
        if not articles:
            raise HTTPException(503, "corpus not loaded; check VADER_CORPUS_DIR and manifest.csv")
        return StreamingResponse(
            _stream(req.query, articles, request.app.state.xml_dir),
            media_type="application/x-ndjson",
        )

    return app


_CORPUS_DIR = Path(os.environ.get("VADER_CORPUS_DIR", Path(__file__).resolve().parent.parent / "corpus"))

app = create_app(
    manifest_path=_CORPUS_DIR / "manifest.csv",
    xml_dir=_CORPUS_DIR / "xml",
    log_path=Path(os.environ.get("VADER_REQUEST_LOG", Path(__file__).resolve().parent / "logs" / "requests.jsonl")),
    max_scan=int(os.environ.get("VADER_MAX_SCAN", "40")),
    max_matches=int(os.environ.get("VADER_MAX_MATCHES", "5")),
    deadline_s=float(os.environ.get("VADER_DEADLINE_S", "5.0")),
)
