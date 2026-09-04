"""
Phase A1 of the v4 execution order (see docs/PROJECT_PLAN.md, "Tier 1
execution order (v4)"): a worksheet for validating the eval CASES
themselves, by hand, by a person.

This is not make_kappa_worksheet.py and not judge calibration. Kappa asks
"does the judge grade like a human." This asks the question underneath it:
"is the gold label right at all." Every case in answer_cases.jsonl was
written by an agent (`created_by: agent:*`) and has never been read by a
person, so both the judge and any human rater have so far been grading
against ground truth nobody checked.

What it renders per case, and why each part is there:
  - the query, as a system would receive it;
  - the gold direction/strength the case asserts;
  - for each gold span, the REAL source text pulled from the corpus XML at
    those exact offsets, untruncated. Untruncated is deliberate: truncating
    span display to 400 characters is exactly the bug that contaminated the
    first kappa pass (docs/DECISION_LOG.md, "kappa worksheet truncation
    bug"), because the sentence that supports a claim is usually past the
    cutoff.
  - for negative cases there is no span to read, so it renders the case's
    own completeness claim (which variant notations were searched) and asks
    the reviewer to judge whether that sweep was wide enough.

Samples the dev split only by default. Reading a held-out case's gold label
is not a scoring touch, but it is still exposure, and there is no reason to
spend it here.

Usage:
    python -m eval.make_case_worksheet --n 8 --out case_worksheet.md
    # ... a human fills in the verdict lines ...
    python -m eval.make_case_worksheet --summarize case_worksheet.md
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from common.corpus_text import load_span_text
from eval.split import load_split

CASES_PATH = Path(__file__).parent / "data" / "answer_cases.jsonl"
XML_DIR = Path(__file__).parent.parent / "corpus" / "xml"

VERDICTS = ("valid", "wrong", "unsure")
_VERDICT_RE = re.compile(r"^-\s*\*\*verdict:\*\*\s*(.*)$", re.IGNORECASE)
_CASE_RE = re.compile(r"^##\s+Case\s+\d+:\s+`([^`]+)`")
_WHY_RE = re.compile(r"^-\s*\*\*why:\*\*\s*(.*)$", re.IGNORECASE)


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def case_type(case: dict) -> str:
    """Same three-way typing split.py stratifies on, so a sample here is
    comparable to the dev/held-out split's own strata."""
    if case["is_negative_case"]:
        return "negative"
    if case["gold"].get("has_disagreement"):
        return "disagreement"
    return "ordinary"


def sample_cases(cases: list[dict], n: int, seed: int) -> list[dict]:
    """Stratified by case type, proportional, seeded. Takes at least one of
    every type present rather than letting a small n drop a whole stratum:
    the negative and disagreement cases are the ones most likely to be
    subtly wrong, so a sample that skips them checks the easy cases only."""
    by_type: dict[str, list[dict]] = {}
    for case in cases:
        by_type.setdefault(case_type(case), []).append(case)

    rng = random.Random(seed)
    for group in by_type.values():
        group.sort(key=lambda c: c["case_id"])
        rng.shuffle(group)

    picked: list[dict] = []
    types = sorted(by_type)
    for t in types:  # one of each first
        picked.append(by_type[t].pop(0))
    remaining = [c for t in types for c in by_type[t]]
    remaining.sort(key=lambda c: c["case_id"])
    rng.shuffle(remaining)
    picked.extend(remaining[: max(0, n - len(picked))])
    picked.sort(key=lambda c: (case_type(c), c["case_id"]))
    return picked[:n]


def render_case(case: dict, number: int, xml_dir: Path) -> str:
    gold = case["gold"]
    ctype = case_type(case)
    lines = [
        f"## Case {number}: `{case['case_id']}`",
        "",
        f"**Type:** {ctype}  |  **Gene:** {case['gene']}  |  "
        f"**Variant:** {case['variant'] or '(none, gene-level)'}  |  "
        f"**Condition:** {case['condition']}",
        "",
        f"**Query the system gets:** {case['query']}",
        "",
    ]

    if ctype == "negative":
        lines += [
            "**This case asserts the corpus contains NO grounding for this pair.** There is no "
            "span to read; what you are checking is whether that absence claim is believable.",
            "",
            "The case's own completeness claim, verbatim:",
            "",
            f"> {case['notes']}",
            "",
            "**What to look for:** does the list of searched notations cover the forms this "
            "variant is actually written in? Protein-level HGVS (`p.Arg675Trp`) and rsIDs are the "
            "two most commonly missing, and a paper describing the variant only in prose "
            "(\"the previously reported truncating variant in exon 10\") will not be caught by "
            "any notation search. Mark `unsure` if the sweep looks too narrow to trust.",
            "",
        ]
    else:
        lines += [
            f"**Gold direction:** {gold.get('direction')!r}",
            f"**Gold strength:** {gold.get('strength')!r}",
            "",
        ]
        if gold.get("has_disagreement"):
            lines += [
                "**Gold asserts the sources disagree.** The claimed disagreement, verbatim:",
                "",
                f"> {gold.get('disagreement_note')}",
                "",
                "**What to look for:** do the two spans below actually conflict, or do they just "
                "share a topic? A newer paper reporting a different endpoint is not a "
                "disagreement; a newer paper reporting the opposite result on the same endpoint "
                "is.",
                "",
            ]
        lines += [f"**Gold spans ({len(case['gold_spans'])}), full source text, untruncated:**", ""]
        for i, span in enumerate(case["gold_spans"], start=1):
            span_text, err = load_span_text(
                xml_dir, span["pmcid"], span["section"], span["char_start"], span["char_end"],
            )
            head = (f"Span {i}: {span['pmcid']} / {span['section']} / "
                    f"chars {span['char_start']}-{span['char_end']}")
            if err is not None:
                lines += [f"- **{head}: COULD NOT RESOLVE ({err}).** That is itself a finding, "
                          f"mark this case `wrong`.", ""]
                continue
            lines += [f"- **{head}** ({len(span_text)} chars)", "", "  > " +
                      span_text.replace("\n", "\n  > "), ""]

    lines += [
        f"**Case author's notes:** {case['notes']}",
        "",
        f"*(written by `{case['created_by']}`)*",
        "",
        "**Your verdict.** `valid` = the gold label is right and the spans support it. "
        "`wrong` = the gold label is wrong, the spans do not support it, or the case is "
        "unanswerable as written. `unsure` = you cannot tell without more domain knowledge or "
        "more reading; this is a legitimate answer and more useful than a guess.",
        "",
        "- **verdict:** ___",
        "- **why:** ___",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def render_worksheet(cases: list[dict], xml_dir: Path, seed: int) -> str:
    header = [
        "# Eval case validation worksheet",
        "",
        f"{len(cases)} of the answer set's cases, stratified by type, sampled at seed {seed}, "
        "dev split only.",
        "",
        "**What this is for.** Every case in `answer_cases.jsonl` was written by an agent and "
        "read by no person. Every number in `docs/RESULTS.md` is graded against these labels. "
        "This worksheet asks one question per case: is the gold label actually right?",
        "",
        "**You are not grading a system answer here.** There is no system answer in this file. "
        "You are checking the ruler, not the measurement.",
        "",
        "Fill in the two `___` lines at the end of each case, then run:",
        "",
        "```",
        "python -m eval.make_case_worksheet --summarize case_worksheet.md",
        "```",
        "",
        "---",
        "",
    ]
    body = [render_case(c, i, xml_dir) for i, c in enumerate(cases, start=1)]
    return "\n".join(header) + "".join(body)


def summarize(path: Path) -> int:
    """Parses a filled-in worksheet. Deliberately strict about unfilled
    verdicts: a blank left as `___` is reported as unfilled rather than
    quietly counted as anything, so a half-finished worksheet cannot be
    mistaken for a completed validation pass."""
    current: str | None = None
    results: list[tuple[str, str, str]] = []
    pending_verdict: str | None = None
    for line in path.read_text().splitlines():
        m = _CASE_RE.match(line.strip())
        if m:
            if current is not None and pending_verdict is not None:
                results.append((current, pending_verdict, ""))
            current, pending_verdict = m.group(1), None
            continue
        m = _VERDICT_RE.match(line.strip())
        if m and current is not None:
            pending_verdict = m.group(1).strip().strip("`*").lower()
            continue
        m = _WHY_RE.match(line.strip())
        if m and current is not None and pending_verdict is not None:
            results.append((current, pending_verdict, m.group(1).strip()))
            pending_verdict = None
    if current is not None and pending_verdict is not None:
        results.append((current, pending_verdict, ""))

    if not results:
        print(f"No cases found in {path}. Is this a case worksheet?", file=sys.stderr)
        return 1

    counts = {v: 0 for v in VERDICTS}
    unfilled = []
    for case_id, verdict, why in results:
        if verdict in counts:
            counts[verdict] += 1
        else:
            unfilled.append(case_id)

    n_filled = sum(counts.values())
    print(f"{len(results)} case(s) in worksheet, {n_filled} with a usable verdict.\n")
    for v in VERDICTS:
        share = f"{counts[v] / n_filled:.0%}" if n_filled else "n/a"
        print(f"  {v:8s} {counts[v]:3d}  ({share})")
    if unfilled:
        print(f"\n  UNFILLED ({len(unfilled)}): {', '.join(unfilled)}")

    flagged = [(c, v, w) for c, v, w in results if v in ("wrong", "unsure")]
    if flagged:
        print("\nCases needing action:")
        for case_id, verdict, why in flagged:
            print(f"  [{verdict}] {case_id}\n        {why or '(no reason given)'}")
    print("\nA single `wrong` in a sample of this size is worth taking seriously: at n=8 the "
          "95% CI on a 1/8 error rate runs to roughly 50%, so it bounds the true rate loosely, "
          "not tightly.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summarize", metavar="WORKSHEET",
                        help="parse a filled-in worksheet and report verdict counts")
    parser.add_argument("--n", type=int, default=8, help="how many cases to sample (default 8)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--xml-dir", default=str(XML_DIR))
    parser.add_argument("--out", default="case_worksheet.md")
    parser.add_argument("--include-held-out", action="store_true",
                        help="also sample held-out cases (off by default; reading a held-out "
                             "case's gold is not a scoring touch, but it is still exposure)")
    args = parser.parse_args(argv)

    if args.summarize:
        return summarize(Path(args.summarize))

    cases = load_jsonl(Path(args.cases))
    split = load_split()
    if split and not args.include_held_out:
        cases = [c for c in cases if split.get(c["case_id"], "dev") == "dev"]
    if not cases:
        print("No cases to sample.", file=sys.stderr)
        return 1

    picked = sample_cases(cases, args.n, args.seed)
    Path(args.out).write_text(render_worksheet(picked, Path(args.xml_dir), args.seed))

    by_type: dict[str, int] = {}
    for c in picked:
        by_type[case_type(c)] = by_type.get(case_type(c), 0) + 1
    print(f"Wrote {args.out}: {len(picked)} case(s) of {len(cases)} available "
          f"({', '.join(f'{n} {t}' for t, n in sorted(by_type.items()))}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
