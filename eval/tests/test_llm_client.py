"""Stdlib-only tests for llm_client.py's .env loading and key-checking.
Never makes a real network call. Run directly: python -m eval.tests.test_llm_client
"""
from __future__ import annotations

import unittest

import os
import tempfile
from pathlib import Path

import common.llm_client as llm_client

def _reset(monkeypatch_path: Path | None) -> None:
    llm_client._dotenv_loaded = False
    llm_client._DOTENV_PATH = monkeypatch_path if monkeypatch_path else Path("/nonexistent/.env")
    os.environ.pop("GROQ_API_KEY", None)


class _FakeResp:
    def __init__(self, headers: dict) -> None:
        self.headers = headers


class TestLlmClient(unittest.TestCase):
    def test_missing_dotenv_and_missing_env_raises(self) -> None:
        _reset(None)
        try:
            llm_client.require_api_key(None)
            self.assertTrue(False, "raises when no key anywhere")
        except RuntimeError as e:
            self.assertIn("GROQ_API_KEY is not set", str(e), "raises when no key anywhere")

    def test_explicit_api_key_wins_no_dotenv_read(self) -> None:
        _reset(None)
        key = llm_client.require_api_key("explicit-key-123")
        self.assertEqual(key, "explicit-key-123", "explicit api_key argument returned as-is")

    def test_dotenv_populates_environ(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            env_path = Path(d) / ".env"
            env_path.write_text("# comment\nGROQ_API_KEY=from-dotenv-456\nOTHER=ignored\n")
            _reset(env_path)
            key = llm_client.require_api_key(None)
            self.assertEqual(key, "from-dotenv-456", "%s -- %s" % (".env value picked up", key))
            self.assertEqual(os.environ.get("GROQ_API_KEY"), "from-dotenv-456", ".env value lands in os.environ too")

    def test_real_env_var_takes_priority_over_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            env_path = Path(d) / ".env"
            env_path.write_text("GROQ_API_KEY=from-dotenv-should-not-win\n")
            _reset(env_path)
            os.environ["GROQ_API_KEY"] = "from-real-env-789"
            key = llm_client.require_api_key(None)
            self.assertTrue(key == "from-real-env-789", "%s -- %s" % ("a real env var already set is not overwritten by .env", key))

    def test_dotenv_handles_quotes_and_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            env_path = Path(d) / ".env"
            env_path.write_text('\nGROQ_API_KEY="quoted-value"\n\n# trailing comment\n')
            _reset(env_path)
            key = llm_client.require_api_key(None)
            self.assertEqual(key, "quoted-value", "%s -- %s" % ("quotes stripped from .env value", key))

    def test_parse_retry_seconds(self) -> None:
        self.assertTrue(llm_client._parse_retry_seconds(_FakeResp({"retry-after": "5"})) == 5.0, "prefers standard Retry-After header")
        self.assertTrue(llm_client._parse_retry_seconds(_FakeResp({"x-ratelimit-reset-tokens": "37.252s"})) == 37.252, "falls back to Groq's x-ratelimit-reset-tokens, strips trailing 's'")
        self.assertTrue(llm_client._parse_retry_seconds(_FakeResp({})) == 15.0, "falls back to a fixed default with no usable header")


if __name__ == "__main__":
    unittest.main()
