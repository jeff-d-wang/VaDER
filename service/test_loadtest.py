import unittest

import httpx

from service.loadtest import one_request


class TestStreamValidation(unittest.IsolatedAsyncioTestCase):
    async def test_only_complete_successful_streams_count_as_success(self):
        for body, expected in [
            ('{"type":"not_found"}\n{"type":"summary","stopped_reason":"exhausted"}\n', True),
            ('{"type":"error","code":"deadline"}\n', False),
            ('{"type":"summary","stopped_reason":"deadline"}\n', False),
            ('{"type":"match"}\n', False),
            ('', False),
            ('not json\n', False),
            ('{"type":"summary"}\n{"type":"match"}\n', False),
        ]:
            with self.subTest(body=body):
                transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body))
                async with httpx.AsyncClient(transport=transport) as client:
                    result = await one_request(client, "http://test", "BRCA1")
                self.assertEqual(result["ok"], expected, result)
