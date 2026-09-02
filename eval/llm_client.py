"""
One shared function for calling Groq's OpenAI-compatible chat completions
endpoint, used by judge.py's GroqJudge and baselines/no_retrieval.py. Kept
in one place so both go through identical auth/timeout/error handling
rather than drifting apart.

Model default (llama-3.3-70b-versatile) matches the 70B-class free-tier
default in docs/DECISION_LOG.md, "Model & embedding stack" design decision.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_MODEL = "openai/gpt-oss-120b"
# llama-3.3-70b-versatile (the model named in docs/DECISION_LOG.md's original "Model & embedding
# stack" decision) was removed from Groq's lineup by the time this was first run, 2026-09-01; see
# the "Groq model drift" addendum to the M1 scorer architecture entry. gpt-oss-120b is Groq's
# current 120B-class open-weight offering, clears the same "avoid a capability confound" bar the
# original decision set (70B-class minimum), and is still free-tier.

_DOTENV_PATH = Path(__file__).parent.parent / ".env"  # repo root, alongside .env.example
_dotenv_loaded = False


def _load_dotenv() -> None:
    """Populates os.environ from a KEY=VALUE .env file at the repo root, for
    any key not already set. Stdlib only, no dependency added just for this.
    Silent no-op if the file doesn't exist: .env is optional, an already-set
    real env var always wins. Runs once per process."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    if not _DOTENV_PATH.exists():
        return
    for line in _DOTENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_api_key(api_key: str | None) -> str:
    if api_key:
        return api_key
    _load_dotenv()
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free-tier key at https://console.groq.com/keys, "
            f"then either `export GROQ_API_KEY=...` or put `GROQ_API_KEY=...` in {_DOTENV_PATH} "
            "(git-ignored, see .env.example)."
        )
    return key


def _parse_retry_seconds(resp) -> float:
    """Groq's free tier enforces a small tokens-per-minute cap (8000 for
    some models), hit routinely by anything beyond a handful of calls in a
    burst. Prefer the standard Retry-After header; fall back to Groq's own
    x-ratelimit-reset-tokens ("37.252s" style), then a fixed default."""
    retry_after = resp.headers.get("retry-after")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    reset = resp.headers.get("x-ratelimit-reset-tokens") or resp.headers.get("x-ratelimit-reset-requests")
    if reset:
        try:
            return float(reset.rstrip("s"))
        except ValueError:
            pass
    return 15.0


def groq_chat_json(prompt: str, *, model: str = DEFAULT_MODEL, api_key: str | None = None,
                    temperature: float = 0.0, timeout_s: float = 30.0, max_retries: int = 5) -> dict:
    """Sends `prompt` as a single user message, asks for a JSON object back
    (Groq's response_format json_object mode), and returns it parsed. Raises
    on a non-2xx response (other than 429, retried) or unparseable JSON;
    callers should let that propagate rather than silently substituting a
    default, a judge or baseline call that fails should be visibly missing,
    not silently wrong. A 429 is retried with the server's own requested
    backoff (see _parse_retry_seconds), up to max_retries times, since it's
    routine on the free tier, not a real failure."""
    import time
    import httpx  # local import: only needed when actually calling the API
    key = require_api_key(api_key)
    for attempt in range(max_retries + 1):
        resp = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout_s,
        )
        if resp.status_code == 429 and attempt < max_retries:
            wait_s = _parse_retry_seconds(resp)
            print(f"  [rate limited, waiting {wait_s:.1f}s, attempt {attempt + 1}/{max_retries}]",
                  file=__import__("sys").stderr)
            time.sleep(wait_s)
            continue
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    raise RuntimeError(f"groq_chat_json: exhausted {max_retries} retries on 429")
