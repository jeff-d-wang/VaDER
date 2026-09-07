"""
A hand-written span emitter. JSONL out, OpenTelemetry GenAI semantic-convention
attribute names, no OTel SDK. Phase B / M2 spine; see docs/DECISION_LOG.md,
"Phase B / M2 instrumentation spine, the build shape".

The OTLP exporter and a self-hosted Phoenix/Langfuse backend are deferred until
there is traffic worth looking at (v4 plan audit). Until then the sink is a
greppable JSONL file.

Usage:
    with trace_request("answer_case", case_id=case["case_id"]):
        with span("retrieve") as s:
            hits = index.search(query)
            s["retrieval.hit_count"] = len(hits)
        out = groq_chat_json(prompt)   # emits its own `chat` span with gen_ai.* attrs

With no active trace, `span(...)` runs its body and writes nothing, so
instrumented code stays callable from unit tests and ad-hoc scripts.
"""
from __future__ import annotations

import contextvars
import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Per-model price, USD per million tokens, (input, output). A model absent here
# gets cost_usd = None: "not priced" must not read as "free". Free-tier models
# are a real 0.0. Paid numbers are the ones named in docs/DECISION_LOG.md,
# "Model & embedding stack".
_PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.0, 0.0),          # Groq free tier
    "llama-3.3-70b-versatile": (0.0, 0.0),      # Groq free tier (retired, kept for old runs)
    "claude-haiku-4-5-20251001": (0.80, 4.00),  # reserved paid calibration model
}


def price_of(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """USD cost of one call, or None if the model is not in the price table or
    token counts are missing."""
    if model not in _PRICES or input_tokens is None or output_tokens is None:
        return None
    p_in, p_out = _PRICES[model]
    return input_tokens / 1e6 * p_in + output_tokens / 1e6 * p_out


class _Trace:
    __slots__ = ("trace_id", "stack")

    def __init__(self, trace_id: str) -> None:
        self.trace_id = trace_id
        self.stack: list[str] = []  # span ids, innermost last


_current: contextvars.ContextVar[_Trace | None] = contextvars.ContextVar("vader_trace", default=None)


def _sink() -> Path:
    return Path(os.environ.get(
        "VADER_TRACE_FILE", Path(__file__).parent.parent / "traces" / "spans.jsonl"))


def _write(record: dict) -> None:
    # ponytail: one open per span. Fine at eval/dev volume; a buffered handle if
    # the service ever emits these at request rate.
    path = _sink()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


@contextmanager
def trace_request(name: str, **attributes):
    """Open a trace and its root span. Nest `span(...)` calls inside it."""
    trace = _Trace(uuid.uuid4().hex)
    token = _current.set(trace)
    try:
        with span(name, **attributes):
            yield
    finally:
        _current.reset(token)


@contextmanager
def span(name: str, **attributes):
    """Time the block and append one span record. Yields the mutable
    attributes dict so the body can add fields. No-op (still runs the body,
    writes nothing) when there is no active trace."""
    trace = _current.get()
    if trace is None:
        yield dict(attributes)
        return

    span_id = uuid.uuid4().hex[:16]
    parent = trace.stack[-1] if trace.stack else None
    trace.stack.append(span_id)
    attrs = dict(attributes)
    start_wall = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    try:
        yield attrs
    finally:
        duration_ms = round((time.monotonic() - t0) * 1000, 3)
        trace.stack.pop()
        _write({
            "trace_id": trace.trace_id,
            "span_id": span_id,
            "parent_span_id": parent,
            "name": name,
            "start": start_wall,
            "duration_ms": duration_ms,
            "attributes": attrs,
        })


def record_llm_usage(attrs: dict, *, provider: str, model: str,
                     input_tokens: int | None, output_tokens: int | None,
                     operation: str = "chat") -> None:
    """Set the OTel GenAI attributes plus vader.cost_usd on a span's attribute
    dict. Safe to call on the plain dict `span` yields when untraced."""
    attrs["gen_ai.operation.name"] = operation
    attrs["gen_ai.provider.name"] = provider
    attrs["gen_ai.request.model"] = model
    attrs["gen_ai.usage.input_tokens"] = input_tokens
    attrs["gen_ai.usage.output_tokens"] = output_tokens
    attrs["vader.cost_usd"] = price_of(model, input_tokens, output_tokens)
