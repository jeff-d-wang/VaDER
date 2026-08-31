"""
Step 0c load test. Hits a running instance of app.py with concurrent
requests and reports p50/p95 total latency and p50/p95 TTFT, with a
percentile bootstrap 95% CI, per RESULTS.md's rule that a number needs an
interval and an n, not just a point estimate.

This, not a notebook loop, is what PROJECT_PLAN.md 0c means by "the
measurement surface": real concurrent HTTP requests against the real
StreamingResponse path, so backpressure and queuing under load show up in
the numbers instead of being averaged away.

Usage:
    cd service
    uvicorn app:app --port 8000 &
    python loadtest.py --base-url http://127.0.0.1:8000 --n 150 --concurrency 20
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time

import httpx

QUERIES = [
    "BRCA1 pathogenic variant hereditary breast and ovarian cancer",
    "TP53 mutation Li-Fraumeni syndrome",
    "PALB2 germline variant pancreatic cancer risk",
    "CHEK2 founder variant breast cancer risk",
    "ATM mutation ataxia telangiectasia cancer predisposition",
    "PARP inhibitor resistance BRCA2 reversion mutation",
    "homologous recombination deficiency ovarian cancer",
    "DNA damage response pathway variant tumor",
    "BRCA2 missense variant classification",
    "somatic TP53 mutation acute myeloid leukemia",
]


async def one_request(client: httpx.AsyncClient, base_url: str, query: str) -> dict:
    t0 = time.monotonic()
    ttft_s = None
    n_lines = 0
    ok, err = True, None
    try:
        async with client.stream("POST", f"{base_url}/query", json={"query": query}, timeout=30) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if ttft_s is None:
                    ttft_s = time.monotonic() - t0
                n_lines += 1
    except Exception as exc:  # noqa: BLE001
        ok, err = False, f"{type(exc).__name__}: {exc}"
    total_s = time.monotonic() - t0
    return {
        "query": query, "ok": ok, "error": err,
        "ttft_ms": (ttft_s if ttft_s is not None else total_s) * 1000,
        "total_ms": total_s * 1000, "n_lines": n_lines,
    }


async def run(base_url: str, n: int, concurrency: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    queries = [rng.choice(QUERIES) for _ in range(n)]
    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []
    limits = httpx.Limits(max_connections=max(concurrency * 2, 20), max_keepalive_connections=concurrency)

    async def bound(q: str) -> None:
        async with sem:
            results.append(await one_request(client, base_url, q))

    async with httpx.AsyncClient(limits=limits) as client:
        await asyncio.gather(*(bound(q) for q in queries))
    return results


def percentile(values: list[float], p: float) -> float:
    if len(values) == 1:
        return values[0]
    qs = statistics.quantiles(values, n=100, method="inclusive")
    idx = min(max(int(round(p)), 1), 99) - 1
    return qs[idx]


def bootstrap_ci(values: list[float], p: float, seed: int, iters: int = 2000) -> tuple[float, float]:
    """Percentile bootstrap 95% CI for the p-th percentile of `values`."""
    rng = random.Random(seed)
    n = len(values)
    boots = [percentile([values[rng.randrange(n)] for _ in range(n)], p) for _ in range(iters)]
    boots.sort()
    lo = boots[int(0.025 * iters)]
    hi = boots[min(int(0.975 * iters), iters - 1)]
    return lo, hi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--n", type=int, default=150, help="total requests (default 150)")
    ap.add_argument("--concurrency", type=int, default=20, help="concurrent in-flight requests (default 20)")
    ap.add_argument("--seed", type=int, default=0, help="query-choice RNG seed, also used for the bootstrap")
    ap.add_argument("--out", default="loadtest_result.json")
    args = ap.parse_args()

    print(f"Running {args.n} requests at concurrency {args.concurrency} against {args.base_url} ...")
    started = time.time()
    results = asyncio.run(run(args.base_url, args.n, args.concurrency, args.seed))
    wall_s = time.time() - started

    ok = [r for r in results if r["ok"]]
    errors = [r for r in results if not r["ok"]]
    total_ms = [r["total_ms"] for r in ok]
    ttft_ms = [r["ttft_ms"] for r in ok]

    summary = {
        "base_url": args.base_url, "n": args.n, "concurrency": args.concurrency, "seed": args.seed,
        "wall_clock_s": round(wall_s, 2), "n_ok": len(ok), "n_errors": len(errors),
        "throughput_rps": round(len(ok) / wall_s, 2) if wall_s > 0 else None,
    }
    if ok:
        ci_total = bootstrap_ci(total_ms, 95, args.seed)
        ci_ttft = bootstrap_ci(ttft_ms, 95, args.seed)
        summary.update({
            "latency_p50_ms": round(percentile(total_ms, 50), 1),
            "latency_p95_ms": round(percentile(total_ms, 95), 1),
            "latency_p95_ci95": [round(ci_total[0], 1), round(ci_total[1], 1)],
            "ttft_p50_ms": round(percentile(ttft_ms, 50), 1),
            "ttft_p95_ms": round(percentile(ttft_ms, 95), 1),
            "ttft_p95_ci95": [round(ci_ttft[0], 1), round(ci_ttft[1], 1)],
        })
    if errors:
        summary["sample_errors"] = [e["error"] for e in errors[:5]]

    print(json.dumps(summary, indent=2))
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
