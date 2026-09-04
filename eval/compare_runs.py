"""
Paired comparison between two score.py --out runs, per property. Required
by RESULTS.md's own rule ("Comparisons are paired... record the paired test
result, not just the two marginal rates") whenever two baselines or configs
are run on the same case set. Reusable beyond this first comparison: every
future ablation (M3 retrieval, M6 chunking, ...) needs the same thing.

Binary pass/not-pass per property (partial counts as not-pass, a
deliberately strict reading; noted in the printed summary since it's a real
choice, not a neutral default). McNemar's exact test on the discordant
pairs (cases where the two runs disagreed): with n this small, this is the
right test, not a proxy for a two-sample test that assumes independence
the paired design specifically avoids needing.

Usage:
    python -m eval.compare_runs --a runs/no_retrieval_scores.json --b runs/bm25_only_scores.json \
        --label-a no_retrieval --label-b bm25_only
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

PROPERTIES = ["direction", "groundedness", "disagreement", "not_found",
              "parameter_accuracy", "citation"]


def mcnemar_exact_p(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value on the discordant-pair counts b, c
    (b = A-fail/B-pass, c = A-pass/B-fail), via the binomial distribution
    under the null that a discordant pair is equally likely to go either
    way. No discordant pairs at all is "no evidence of a difference",
    p = 1.0, not an error."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) * (0.5 ** n)
    return min(1.0, 2 * tail)


def load_cases(path: Path) -> dict[str, dict]:
    data = json.loads(Path(path).read_text())
    return {c["case_id"]: c for c in data["cases"]}


def compare(cases_a: dict, cases_b: dict, label_a: str, label_b: str) -> None:
    shared = sorted(set(cases_a) & set(cases_b))
    dropped = (set(cases_a) | set(cases_b)) - set(shared)
    if dropped:
        print(f"NOTE: {len(dropped)} case(s) present in only one run, excluded from pairing: "
              f"{sorted(dropped)[:5]}{'...' if len(dropped) > 5 else ''}", file=sys.stderr)

    for prop in PROPERTIES:
        pairs = []
        for cid in shared:
            va = cases_a[cid].get(prop)
            vb = cases_b[cid].get(prop)
            if va is None or vb is None:
                continue  # N/A in at least one run for this case; not comparable
            pairs.append((va["verdict"] == "pass", vb["verdict"] == "pass"))
        if not pairs:
            continue

        n = len(pairs)
        a_pass = sum(1 for pa, _ in pairs if pa)
        b_pass = sum(1 for _, pb in pairs if pb)
        both_pass = sum(1 for pa, pb in pairs if pa and pb)
        both_fail = sum(1 for pa, pb in pairs if not pa and not pb)
        improved = sum(1 for pa, pb in pairs if not pa and pb)   # A fail -> B pass
        regressed = sum(1 for pa, pb in pairs if pa and not pb)  # A pass -> B fail
        p = mcnemar_exact_p(regressed, improved)

        print(f"{prop:20s} n={n:3d}  {label_a}={a_pass}/{n} ({a_pass/n:.0%})  "
              f"{label_b}={b_pass}/{n} ({b_pass/n:.0%})  "
              f"delta={(b_pass - a_pass)/n:+.0%}")
        print(f"{'':20s}  both_pass={both_pass} both_fail={both_fail} "
              f"{label_a}_only={regressed} {label_b}_only={improved}  "
              f"McNemar exact p={p:.3f}{'  (n too small to be conclusive)' if n < 10 else ''}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a", required=True)
    parser.add_argument("--b", required=True)
    parser.add_argument("--label-a", default="A")
    parser.add_argument("--label-b", default="B")
    args = parser.parse_args()

    cases_a = load_cases(Path(args.a))
    cases_b = load_cases(Path(args.b))
    print("pass/not-pass is strict: partial counts as not-pass.\n")
    compare(cases_a, cases_b, args.label_a, args.label_b)
    return 0


if __name__ == "__main__":
    sys.exit(main())
