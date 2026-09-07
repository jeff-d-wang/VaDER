"""
common/trace.py: the span emitter must (1) write nothing and still run the body
when there is no active trace, (2) inside a trace, write one JSONL span per
`span(...)` with a shared trace_id and correct parent nesting, and (3) price a
call only when the model and token counts are both known.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from common import trace


class TraceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._sink = Path(self._tmp.name) / "spans.jsonl"
        self._prev = os.environ.get("VADER_TRACE_FILE")
        os.environ["VADER_TRACE_FILE"] = str(self._sink)

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("VADER_TRACE_FILE", None)
        else:
            os.environ["VADER_TRACE_FILE"] = self._prev
        self._tmp.cleanup()

    def _lines(self) -> list[dict]:
        if not self._sink.exists():
            return []
        return [json.loads(x) for x in self._sink.read_text().splitlines() if x.strip()]

    def test_span_is_noop_without_a_trace(self) -> None:
        ran = []
        with trace.span("retrieve") as s:
            s["k"] = 3
            ran.append(True)
        self.assertEqual(ran, [True])
        self.assertEqual(self._lines(), [])

    def test_trace_writes_nested_spans_with_one_trace_id(self) -> None:
        with trace.trace_request("bm25_only", case_id="c1"):
            with trace.span("retrieve") as s:
                s["retrieval.hit_count"] = 8
            with trace.span("chat") as s:
                trace.record_llm_usage(s, provider="groq", model="openai/gpt-oss-120b",
                                       input_tokens=800, output_tokens=100)

        lines = self._lines()
        self.assertEqual(len(lines), 3)  # root + retrieve + chat
        by_name = {ln["name"]: ln for ln in lines}

        trace_ids = {ln["trace_id"] for ln in lines}
        self.assertEqual(len(trace_ids), 1)

        root = by_name["bm25_only"]
        self.assertIsNone(root["parent_span_id"])
        self.assertEqual(by_name["retrieve"]["parent_span_id"], root["span_id"])
        self.assertEqual(by_name["chat"]["parent_span_id"], root["span_id"])

        self.assertEqual(by_name["retrieve"]["attributes"]["retrieval.hit_count"], 8)
        chat_attrs = by_name["chat"]["attributes"]
        self.assertEqual(chat_attrs["gen_ai.usage.input_tokens"], 800)
        self.assertEqual(chat_attrs["gen_ai.request.model"], "openai/gpt-oss-120b")
        self.assertEqual(chat_attrs["vader.cost_usd"], 0.0)  # free tier
        for ln in lines:
            self.assertGreaterEqual(ln["duration_ms"], 0.0)

    def test_price_of(self) -> None:
        self.assertEqual(trace.price_of("openai/gpt-oss-120b", 1000, 1000), 0.0)
        # 1M in + 1M out on the paid calibration model = 0.80 + 4.00
        self.assertAlmostEqual(
            trace.price_of("claude-haiku-4-5-20251001", 1_000_000, 1_000_000), 4.80)
        self.assertIsNone(trace.price_of("some-unpriced-model", 10, 10))
        self.assertIsNone(trace.price_of("openai/gpt-oss-120b", None, 10))


if __name__ == "__main__":
    unittest.main()
