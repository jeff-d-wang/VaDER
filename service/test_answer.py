"""Offline serving contracts, using a synthetic corpus and mocked provider."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from common.answer import validate_runtime_answer
from common.llm_client import groq_chat_json_async
from service.test_app import _make_client


VALID = {"direction": "increased", "strength": "unstated", "not_found": False,
         "claims": [{"text": "The cohort reports elevated risk.", "excerpt_index": 1}]}


class AnswerTests(unittest.TestCase):
    def client(self, **kwargs):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.log_path = tmp / "logs/requests.jsonl"
        self.enterContext(patch("service.app.require_api_key", return_value="test-key"))
        return self.enterContext(_make_client(tmp, generation_enabled=True, **kwargs))

    def test_answer_maps_citation_and_logs_no_query(self):
        client = self.client()
        with patch("service.app.groq_chat_json_async", new=AsyncMock(return_value=VALID)):
            response = client.post("/answer", json={"query": "BRCA1 breast cancer"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        evidence = body["evidence"][0]
        claim = body["claims"][0]
        self.assertEqual(body["answer_text"], "The cohort reports elevated risk [1].")
        self.assertEqual(claim["cited_pmcid"], evidence["pmcid"])
        self.assertEqual(claim["cited_char_end"] - claim["cited_char_start"], len(evidence["text"]))
        log = json.loads(self.log_path.read_text())
        self.assertEqual(log["trace_id"], body["trace_id"])
        self.assertNotIn("query", log)

    def test_bad_outputs_fail_and_capacity_recovers(self):
        client = self.client(generation_concurrency=1)
        invalid = [dict(VALID, not_found="false"), dict(VALID, claims=[]),
                   dict(VALID, claims=[{"text": "unsupported", "excerpt_index": 999}]),
                   dict(VALID, claims=[{"text": "unsupported", "excerpt_index": True}]),
                   dict(VALID, direction="unknown"), dict(VALID, not_found=True)]
        for payload in invalid:
            with self.subTest(payload=payload), patch(
                "service.app.groq_chat_json_async", new=AsyncMock(return_value=payload)
            ):
                self.assertEqual(client.post("/answer", json={"query": "BRCA1"}).status_code, 502)
        with patch("service.app.groq_chat_json_async", new=AsyncMock(return_value=VALID)):
            self.assertEqual(client.post("/answer", json={"query": "BRCA1"}).status_code, 200)

    def test_no_context_skips_provider(self):
        client = self.client(context_chars=1)
        with patch("service.app.groq_chat_json_async", new=AsyncMock()) as provider:
            self.assertEqual(client.post("/answer", json={"query": "BRCA1"}).json()["outcome"], "no_context")
            self.assertEqual(client.post("/answer", json={"query": "zzzzzzzzz"}).json()["outcome"], "not_found")
            provider.assert_not_called()

    def test_disabled(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        with _make_client(tmp) as client:
            self.assertEqual(client.post("/answer", json={"query": "BRCA1"}).status_code, 503)

    def test_provider_errors_are_not_abstentions(self):
        client = self.client(generation_concurrency=1)
        for error, status in [(TimeoutError(), 504), (httpx.ConnectError("secret"), 502)]:
            with patch("service.app.groq_chat_json_async", new=AsyncMock(side_effect=error)):
                response = client.post("/answer", json={"query": "BRCA1"})
                self.assertEqual(response.status_code, status)
                self.assertNotIn("secret", response.text)

    def test_abstention_replaces_model_prose(self):
        out = dict(VALID, not_found=True, claims=[], direction="none", strength="unstated")
        parsed = validate_runtime_answer(out, [({"pmcid": "PMC1"}, "text")])
        self.assertIn("do not establish", parsed["answer_text"])

    def test_runtime_rejects_independent_prose(self):
        out = dict(VALID, answer_text="An unchecked factual statement.")
        with self.assertRaises(ValueError):
            validate_runtime_answer(out, [({"pmcid": "PMC1"}, "text")])

    def test_concurrent_request_rejected_and_cancelled_slot_released(self):
        client = self.client(generation_concurrency=1)

        async def run():
            entered = asyncio.Event()
            async def provider(*args, **kwargs):
                entered.set()
                await asyncio.Event().wait()
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app),
                                         base_url="http://test") as http:
                with patch("service.app.groq_chat_json_async", new=provider):
                    first = asyncio.create_task(http.post("/answer", json={"query": "BRCA1"}))
                    await asyncio.wait_for(entered.wait(), 2)
                    second = await http.post("/answer", json={"query": "BRCA1"})
                    self.assertEqual(second.status_code, 429)
                    first.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await first
                with patch("service.app.groq_chat_json_async", new=AsyncMock(return_value=VALID)):
                    self.assertEqual((await http.post("/answer", json={"query": "BRCA1"})).status_code, 200)
        asyncio.run(run())


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_budget_and_response_validation(self):
        def handler(request):
            self.assertEqual(json.loads(request.content)["max_completion_tokens"], 1024)
            return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps(VALID)}}]})
        self.assertEqual(await groq_chat_json_async("prompt", api_key="test", transport=httpx.MockTransport(handler)), VALID)
        for payload in [[], {"choices": []}, {"choices": [{"finish_reason": "length"}]}]:
            with self.subTest(payload=payload), self.assertRaises((ValueError, AttributeError, IndexError)):
                await groq_chat_json_async("prompt", api_key="test", transport=httpx.MockTransport(
                    lambda req: httpx.Response(200, json=payload)))

    async def test_total_timeout(self):
        async def slow(request):
            await asyncio.sleep(1)
            return httpx.Response(200)
        with self.assertRaises(TimeoutError):
            await groq_chat_json_async("prompt", api_key="test", timeout_s=.01,
                                       transport=httpx.MockTransport(slow))

    async def test_rate_limit_does_not_retry(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, headers={"retry-after": "999"})
        with self.assertRaises(httpx.HTTPStatusError):
            await groq_chat_json_async("prompt", api_key="test", transport=httpx.MockTransport(handler))
        self.assertEqual(len(calls), 1)

    async def test_oversized_response(self):
        with self.assertRaises(ValueError):
            await groq_chat_json_async("prompt", api_key="test", transport=httpx.MockTransport(
                lambda req: httpx.Response(200, content=b"x" * 65_537)))
