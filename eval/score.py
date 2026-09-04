"""
The M1 answer-set scorer. Implements the rubric logged in
docs/DECISION_LOG.md, "Answer-set scoring rubric" (confirmed 2026-09-01):
four pass/partial/fail sub-scores per evidence case (direction/strength,
citation/groundedness, surfaces disagreement, says not-found), two for the
methods_extraction stratum (parameter accuracy, citation).

Two things here are this script's own implementation choices, not settled
in that rubric discussion, flagged so they're easy to revisit:
  - Property 3 (surfaces disagreement) is graded pass/partial/fail here.
    The rubric discussion only specified this for properties 1 and 2;
    "partial" for property 3 means citing both conflicting sources without
    stating they conflict. See judge.py's _DISAGREEMENT_PROMPT.
  - Property 4 (says not-found) is checked for negative cases exactly as
    the rubric describes, AND, as an extension, checked in reverse for
    ordinary evidence cases: did the system wrongly refuse to answer when
    the corpus does have grounding. CaseScore.property4.note says
    "extended_check" when this reverse form applied, so it's easy to find
    and drop if that reading is wrong.

Scores a case against a *system answer*, not a live system: this module
takes prior-generated answers (one JSON object per case_id, schema below)
and grades them. See eval/README.md for the schema and how to produce one
(eval/baselines/no_retrieval.py is the first such generator).

Usage:
    python -m eval.score --answers path/to/answers.jsonl --judge fake|groq [--out results.json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from common.corpus_text import load_span_text
from eval.judge import Judge, JudgeResult, make_judge
from eval.split import load_split, record_touch, MAX_RECOMMENDED_TOUCHES

CASES_PATH = Path(__file__).parent / "data" / "answer_cases.jsonl"
XML_DIR = Path(__file__).parent.parent / "corpus" / "xml"

REFUSAL_MARKERS = (
    "not found in this corpus", "not found in the corpus", "no information",
    "not covered in this corpus", "not present in this corpus", "could not find",
    "no articles in this corpus", "does not appear in this corpus",
)


@dataclass
class Claim:
    text: str
    cited_pmcid: str
    cited_section: str
    cited_char_start: int
    cited_char_end: int


@dataclass
class SystemAnswer:
    case_id: str
    direction: Optional[str] = None
    strength: Optional[str] = None
    not_found: bool = False
    answer_text: str = ""
    claims: list[Claim] = field(default_factory=list)
    # methods_extraction stratum only
    parameter_value: Optional[str] = None
    cited_pmcid: Optional[str] = None

    @staticmethod
    def from_dict(d: dict) -> "SystemAnswer":
        claims = [Claim(**c) for c in d.get("claims", [])]
        return SystemAnswer(
            case_id=d["case_id"], direction=d.get("direction"), strength=d.get("strength"),
            not_found=d.get("not_found", False), answer_text=d.get("answer_text", ""),
            claims=claims, parameter_value=d.get("parameter_value"), cited_pmcid=d.get("cited_pmcid"),
        )


@dataclass
class PropertyScore:
    verdict: Optional[str]  # "pass" | "partial" | "fail" | None (not applicable to this case)
    rationale: str
    note: str = ""


@dataclass
class CaseScore:
    case_id: str
    stratum: str
    direction: Optional[PropertyScore] = None
    groundedness: Optional[PropertyScore] = None
    disagreement: Optional[PropertyScore] = None
    not_found: Optional[PropertyScore] = None
    parameter_accuracy: Optional[PropertyScore] = None
    citation: Optional[PropertyScore] = None


def _refuses(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def score_groundedness(answer: SystemAnswer, judge: Judge, xml_dir: Path) -> PropertyScore:
    if not answer.claims:
        return PropertyScore("fail", "no claims/citations provided", note="empty_claims")
    supported = 0
    problems = []
    for claim in answer.claims:
        span_text, err = load_span_text(
            xml_dir, claim.cited_pmcid, claim.cited_section,
            claim.cited_char_start, claim.cited_char_end,
        )
        if err is not None:
            problems.append(f"{claim.cited_pmcid}: {err}")
            continue
        if judge.grade_claim_groundedness(claim.text, span_text):
            supported += 1
    hit_rate = supported / len(answer.claims)
    if hit_rate >= 0.90:
        verdict = "pass"
    elif hit_rate >= 0.70:
        verdict = "partial"
    else:
        verdict = "fail"
    rationale = f"{supported}/{len(answer.claims)} claims grounded ({hit_rate:.0%})"
    if problems:
        rationale += f"; unresolvable citations: {'; '.join(problems)}"
    return PropertyScore(verdict, rationale)


def score_direction(case: dict, answer: SystemAnswer, judge: Judge) -> PropertyScore:
    gold = case["gold"]
    result = judge.grade_direction(
        case["query"], gold["direction"], gold.get("strength"),
        answer.direction or "", answer.strength or "",
    )
    return PropertyScore(result.verdict, result.rationale)


def score_disagreement(case: dict, answer: SystemAnswer, judge: Judge) -> PropertyScore:
    gold = case["gold"]
    result = judge.grade_disagreement(case["query"], gold["disagreement_note"], answer.answer_text)
    return PropertyScore(result.verdict, result.rationale)


def score_not_found(case: dict, answer: SystemAnswer) -> PropertyScore:
    gold = case["gold"]
    stated_not_found = answer.not_found or _refuses(answer.answer_text)
    if gold["expected_not_found"]:
        verdict = "pass" if stated_not_found else "fail"
        return PropertyScore(verdict, "system said not-found" if stated_not_found
                              else "system answered despite no corpus grounding (a fabrication risk)")
    verdict = "fail" if stated_not_found else "pass"
    return PropertyScore(
        verdict,
        "system wrongly refused; corpus does have grounding" if stated_not_found
        else "system correctly did not refuse",
        note="extended_check",
    )


def score_methods_case(case: dict, answer: SystemAnswer) -> tuple[PropertyScore, PropertyScore]:
    gold = case["gold"]
    expected = (gold.get("expected_value") or "").strip().lower()
    got = (answer.parameter_value or "").strip().lower()
    param_verdict = "pass" if expected and expected == got else "fail"
    parameter_accuracy = PropertyScore(
        param_verdict, f"expected {gold.get('expected_value')!r}, got {answer.parameter_value!r}",
    )
    expected_pmcids = gold.get("expected_pmcids") or ([gold["expected_pmcid"]] if gold.get("expected_pmcid") else [])
    cite_verdict = "pass" if answer.cited_pmcid in expected_pmcids else "fail"
    citation = PropertyScore(
        cite_verdict, f"expected one of {expected_pmcids}, got {answer.cited_pmcid!r}",
    )
    return parameter_accuracy, citation


def score_case(case: dict, answer: SystemAnswer, judge: Judge, xml_dir: Path = XML_DIR) -> CaseScore:
    stratum = case["stratum"]
    result = CaseScore(case_id=case["case_id"], stratum=stratum)

    if stratum == "methods_extraction":
        result.parameter_accuracy, result.citation = score_methods_case(case, answer)
        return result

    # evidence stratum
    is_negative = case["is_negative_case"]
    gold = case["gold"]

    result.not_found = score_not_found(case, answer)

    if is_negative:
        # direction/strength and disagreement don't apply: there's nothing
        # to state a direction about, and nothing to surface. Groundedness
        # only applies if the system made claims anyway (should be none).
        if answer.claims:
            result.groundedness = score_groundedness(answer, judge, xml_dir)
        return result

    result.direction = score_direction(case, answer, judge)
    result.groundedness = score_groundedness(answer, judge, xml_dir)
    if gold["has_disagreement"]:
        result.disagreement = score_disagreement(case, answer, judge)
    return result


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion. Used instead of
    the normal approximation because CLAUDE.md's own rule ("every number in
    RESULTS.md carries ... a 95% CI") gets applied here at n as small as 4,
    where the normal approximation can produce a nonsense interval (below 0
    or above 1); Wilson stays valid at small n and exactly at p=0 or p=1."""
    if n == 0:
        return (0.0, 0.0)
    phat = successes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def summarize(scores: list[CaseScore]) -> dict:
    """Per-property pass rate, N/A cases excluded from the denominator.
    Deliberately not a single blended score: DECISION_LOG.md's rubric entry
    rejected a holistic pass/fail specifically so a property's failure
    doesn't hide behind the others."""
    properties = ["direction", "groundedness", "disagreement", "not_found",
                  "parameter_accuracy", "citation"]
    summary = {}
    for prop in properties:
        verdicts = [getattr(s, prop).verdict for s in scores if getattr(s, prop) is not None]
        n = len(verdicts)
        if n == 0:
            continue
        passes = verdicts.count("pass")
        ci_low, ci_high = wilson_ci(passes, n)
        summary[prop] = {
            "n": n,
            "pass": passes,
            "partial": verdicts.count("partial"),
            "fail": verdicts.count("fail"),
            "pass_rate": round(passes / n, 3),
            "pass_rate_ci95": [round(ci_low, 3), round(ci_high, 3)],
        }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", required=True, help="JSONL of system answers, one per case_id")
    parser.add_argument("--judge", default="fake", choices=["fake", "groq"])
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--xml-dir", default=str(XML_DIR))
    parser.add_argument("--out", help="write full per-case results as JSON here")
    parser.add_argument("--held-out", choices=["exclude", "include", "only"], default="exclude",
                         help="exclude (default, safe): dev split only. include/only: also or "
                              "only score the held-out split, requires --touch-reason and is "
                              "logged to held_out_touches.csv")
    parser.add_argument("--touch-reason", help="required with --held-out include|only")
    parser.add_argument("--touched-by", default="user")
    args = parser.parse_args(argv)

    if args.held_out != "exclude" and not args.touch_reason:
        print("--held-out include|only requires --touch-reason (this gets logged to "
              "held_out_touches.csv; a real reason, not a placeholder)", file=sys.stderr)
        return 2

    cases = {c["case_id"]: c for c in load_jsonl(Path(args.cases))}
    split = load_split()
    if split and args.held_out != "include":
        wanted_split = "held_out" if args.held_out == "only" else "dev"
        cases = {cid: c for cid, c in cases.items()
                 if split.get(cid, "dev") == wanted_split}
    answers = {a["case_id"]: SystemAnswer.from_dict(a) for a in load_jsonl(Path(args.answers))}
    judge = make_judge(args.judge)

    if args.held_out != "exclude":
        held_out_ids = [cid for cid in cases if split.get(cid) == "held_out"]
        n_touches = record_touch(args.touch_reason, args.touched_by, len(held_out_ids))
        warn = "  *** exceeds the recommended 3-touch cap, see eval/README.md ***" if \
            n_touches > MAX_RECOMMENDED_TOUCHES else ""
        print(f"Held-out split touched: {len(held_out_ids)} case(s), "
              f"this is touch #{n_touches}.{warn}\n", file=sys.stderr)

    missing = set(cases) - set(answers)
    if missing:
        print(f"WARNING: {len(missing)} case(s) have no system answer, skipped: {sorted(missing)[:5]}...",
              file=sys.stderr)

    scores = []
    for case_id, case in cases.items():
        if case_id not in answers:
            continue
        scores.append(score_case(case, answers[case_id], judge, Path(args.xml_dir)))

    summary = summarize(scores)
    print(f"Judge: {args.judge}. Scored {len(scores)}/{len(cases)} cases.\n")
    for prop, stats in summary.items():
        ci = stats["pass_rate_ci95"]
        print(f"  {prop:20s} n={stats['n']:3d}  pass={stats['pass']:3d}  "
              f"partial={stats['partial']:3d}  fail={stats['fail']:3d}  "
              f"pass_rate={stats['pass_rate']:.0%}  95% CI [{ci[0]:.0%}, {ci[1]:.0%}]")

    if args.out:
        payload = {"summary": summary, "cases": [asdict(s) for s in scores]}
        Path(args.out).write_text(json.dumps(payload, indent=2))
        print(f"\nWrote {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
