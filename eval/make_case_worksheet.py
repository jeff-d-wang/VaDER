"""
Phase A1 of the v4 execution order (see docs/PROJECT_PLAN.md, "Tier 1
execution order (v4)"): a worksheet for validating the eval CASES
themselves, by hand, by a person.

This is not judge calibration. Kappa asks "does the judge grade like a
human." This asks the question underneath it: "is the gold label right at
all." Every case in answer_cases.jsonl was
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
from common.stats import wilson_ci
from eval.split import load_split

CASES_PATH = Path(__file__).parent / "data" / "answer_cases.jsonl"
XML_DIR = Path(__file__).parent.parent / "corpus" / "xml"

VERDICTS = ("valid", "wrong", "unsure")
_VERDICT_RE = re.compile(r"^-\s*\*\*verdict:\*\*\s*(.*)$", re.IGNORECASE)
# Matches both worksheet headings: "## Case 3: `id`" (case focus) and
# "## 3. `id`  (dev split)" (strength focus). One parser for both, so a
# filled-in worksheet of either kind summarizes the same way.
_CASE_RE = re.compile(r"^##\s+(?:Case\s+)?\d+[.:]\s+`([^`]+)`")
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


def render_strength_case(case: dict, number: int, xml_dir: Path, split: dict) -> str:
    """One evidence case, focused on whether its `strength` label is right.

    Separate renderer from render_case because the question is different.
    Case validation asks "is this gold label right at all"; this asks one
    narrow thing: given the source text, is the assigned point on the
    strength scale the right one. The scale, the assignment, the reasoning
    behind it and the evidence are all on screen together, because that is
    what makes the answer checkable rather than a vibe."""
    gold = case["gold"]
    lines = [
        f"## {number}. `{case['case_id']}`  ({split.get(case['case_id'], '?')} split)",
        "",
        f"**Query:** {case['query']}",
        "",
        f"**Direction (for context, not what you are checking):** `{gold.get('direction')}`",
        "",
        f"**Assigned strength: `{gold.get('strength')}`**",
        "",
        f"*Why I assigned it:* {gold.get('qualifier') or '(no qualifier recorded)'}",
        "",
        f"*Quantitative detail from the source (`strength_detail`):* "
        f"{gold.get('strength_detail') or '(none)'}",
        "",
        "**The evidence, full text of every gold span:**",
        "",
    ]
    for i, span in enumerate(case["gold_spans"], start=1):
        text, err = load_span_text(xml_dir, span["pmcid"], span["section"],
                                   span["char_start"], span["char_end"])
        head = f"Span {i}: {span['pmcid']} / {span['section']}"
        if err is not None:
            lines += [f"- **{head}: COULD NOT RESOLVE ({err})**", ""]
            continue
        lines += [f"- **{head}**", "", "  > " + text.replace("\n", "\n  > "), ""]
    lines += [
        "**Your verdict.** `valid` = this is the right point on the scale. `wrong` = it should be "
        "a different value (say which). `unsure` = you cannot tell from the span alone.",
        "",
        "- **verdict:** ___",
        "- **why:** ___",
        "",
        "---",
        "",
    ]
    return "\n".join(lines)


def render_strength_worksheet(cases: list[dict], xml_dir: Path, split: dict) -> str:
    header = [
        "# Strength label review",
        "",
        f"All {len(cases)} evidence cases. **What you are checking:** whether each case's "
        "`strength` value is the right point on the scale, given the source text below it.",
        "",
        "**Why this matters more than it looks.** These 11 assignments were made by an agent "
        "reading the sources, not by you and not by a domain expert, and the project's current "
        "headline finding rests on them: strength is the one property perfect retrieval does not "
        "fix (0.375 with the exact gold spans, identical to BM25). If these labels are wrong, that "
        "finding is wrong. It is the same dependency that produced the phase A1 problem, one layer "
        "up.",
        "",
        "**The scale:**",
        "",
        "| Value | Means |",
        "|---|---|",
        "| `high` | large reported effect (roughly OR/RR > 5, or described as high-risk) |",
        "| `moderate` | intermediate reported effect (roughly OR/RR 2-5) |",
        "| `low` | small reported effect (roughly OR/RR < 2, or framed as low-penetrance/background) |",
        "| `none` | no association reported |",
        "| `disputed` | sources conflict on the magnitude |",
        "| `unstated` | the source reports no effect size at all |",
        "",
        "`low`/`moderate`/`high` are ordered, so a one-tier miss scores `partial`. `none`, "
        "`disputed` and `unstated` are categorical: they are either right or wrong.",
        "",
        "Fill in the two `___` lines per case, then run:",
        "",
        "```",
        "python -m eval.make_case_worksheet --summarize strength_worksheet.md",
        "```",
        "",
        "---",
        "",
    ]
    body = [render_strength_case(c, i, xml_dir, split)
            for i, c in enumerate(cases, start=1)]
    return "\n".join(header) + "".join(body)


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
        "**A bare number sitting alone in a span's text, often on its own line, is a citation "
        "marker** (JATS renders `<xref ref-type=\"bibr\">` inline with no separator, e.g. "
        "\"were poor.\\n5\\nCCAs can be...\"), not a reported figure.",
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


def _parse_verdict(raw: str) -> str:
    """Extract the verdict word from a line that may qualify it.

    A rater writing "wrong (should be unstated)" is giving MORE information
    than a bare "wrong", and the first version of this parser threw those
    away as unparseable and reported them as UNFILLED. On the first real
    strength review that turned 5 corrections into a printed "valid 6
    (100%)", which is the most dangerous kind of bug this file can have: it
    reported a clean sheet where the truth was a 45% error rate. Match the
    leading verdict word and keep the qualifier as the reason."""
    # Emphasis markers can appear mid-string ("**WRONG** (should be low)"),
    # so strip them everywhere rather than just at the ends.
    cleaned = raw.replace("*", "").replace("`", "").strip().lower()
    for verdict in VERDICTS:
        if cleaned == verdict or cleaned.startswith(verdict + " ") or \
                cleaned.startswith(verdict + "(") or cleaned.startswith(verdict + ","):
            return verdict
    return cleaned


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
            pending_verdict = _parse_verdict(m.group(1))
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
    if n_filled:
        wrong_rate = counts["wrong"] / n_filled
        lo, hi = wilson_ci(counts["wrong"], n_filled)
        print(f"\nError rate on the reviewed labels: {counts['wrong']}/{n_filled} = "
              f"{wrong_rate:.0%}, 95% CI [{lo:.0%}, {hi:.0%}]. At this n the interval is wide; it "
              f"establishes that a problem exists, not its size.")
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
    parser.add_argument("--focus", choices=["case", "strength"], default="case",
                        help="case (default): is the gold label right at all, on a stratified "
                             "sample. strength: is the strength value the right point on the "
                             "scale, over every evidence case.")
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

    if args.focus == "strength":
        evidence = [c for c in load_jsonl(Path(args.cases)) if not c["is_negative_case"]]
        evidence.sort(key=lambda c: (c["gold"].get("strength") or "", c["case_id"]))
        out = args.out if args.out != "case_worksheet.md" else "strength_worksheet.md"
        Path(out).write_text(render_strength_worksheet(evidence, Path(args.xml_dir), split))
        print(f"Wrote {out}: {len(evidence)} evidence case(s), grouped by assigned strength.")
        return 0

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
