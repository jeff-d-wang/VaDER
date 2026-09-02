"""Stdlib-only tests for llm_client.py's .env loading and key-checking.
Never makes a real network call. Run directly: python test_llm_client.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import llm_client

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


def _reset(monkeypatch_path: Path | None) -> None:
    llm_client._dotenv_loaded = False
    llm_client._DOTENV_PATH = monkeypatch_path if monkeypatch_path else Path("/nonexistent/.env")
    os.environ.pop("GROQ_API_KEY", None)


def test_missing_dotenv_and_missing_env_raises() -> None:
    _reset(None)
    try:
        llm_client.require_api_key(None)
        check("raises when no key anywhere", False)
    except RuntimeError as e:
        check("raises when no key anywhere", "GROQ_API_KEY is not set" in str(e))


def test_explicit_api_key_wins_no_dotenv_read() -> None:
    _reset(None)
    key = llm_client.require_api_key("explicit-key-123")
    check("explicit api_key argument returned as-is", key == "explicit-key-123")


def test_dotenv_populates_environ() -> None:
    with tempfile.TemporaryDirectory() as d:
        env_path = Path(d) / ".env"
        env_path.write_text("# comment\nGROQ_API_KEY=from-dotenv-456\nOTHER=ignored\n")
        _reset(env_path)
        key = llm_client.require_api_key(None)
        check(".env value picked up", key == "from-dotenv-456", key)
        check(".env value lands in os.environ too", os.environ.get("GROQ_API_KEY") == "from-dotenv-456")


def test_real_env_var_takes_priority_over_dotenv() -> None:
    with tempfile.TemporaryDirectory() as d:
        env_path = Path(d) / ".env"
        env_path.write_text("GROQ_API_KEY=from-dotenv-should-not-win\n")
        _reset(env_path)
        os.environ["GROQ_API_KEY"] = "from-real-env-789"
        key = llm_client.require_api_key(None)
        check("a real env var already set is not overwritten by .env", key == "from-real-env-789", key)


def test_dotenv_handles_quotes_and_blank_lines() -> None:
    with tempfile.TemporaryDirectory() as d:
        env_path = Path(d) / ".env"
        env_path.write_text('\nGROQ_API_KEY="quoted-value"\n\n# trailing comment\n')
        _reset(env_path)
        key = llm_client.require_api_key(None)
        check("quotes stripped from .env value", key == "quoted-value", key)


class _FakeResp:
    def __init__(self, headers: dict) -> None:
        self.headers = headers


def test_parse_retry_seconds() -> None:
    check("prefers standard Retry-After header",
          llm_client._parse_retry_seconds(_FakeResp({"retry-after": "5"})) == 5.0)
    check("falls back to Groq's x-ratelimit-reset-tokens, strips trailing 's'",
          llm_client._parse_retry_seconds(_FakeResp({"x-ratelimit-reset-tokens": "37.252s"})) == 37.252)
    check("falls back to a fixed default with no usable header",
          llm_client._parse_retry_seconds(_FakeResp({})) == 15.0)


def run_tests() -> int:
    test_missing_dotenv_and_missing_env_raises()
    test_explicit_api_key_wins_no_dotenv_read()
    test_dotenv_populates_environ()
    test_real_env_var_takes_priority_over_dotenv()
    test_dotenv_handles_quotes_and_blank_lines()
    test_parse_retry_seconds()
    os.environ.pop("GROQ_API_KEY", None)  # leave no trace for any later test in the same run
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
