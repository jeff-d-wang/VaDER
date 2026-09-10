"""
The M1 answer-set scorer. Implements the rubric logged in
docs/DECISION_LOG.md, "Answer-set scoring rubric" (confirmed 2026-09-01):
four pass/partial/fail sub-scores per evidence case (direction, strength,
citation/groundedness, surfaces disagreement, says not-found).

Direction and strength are scored separately, and in code, not by a judge:
see eval/labels.py and docs/DECISION_LOG.md, "direction property redesign".

The rubric also names a `methods_extraction` stratum (parameter accuracy,
citation). It was scored here until 2026-09-05 and is gone: the v4 audit
deferred those cases out of M1, the answer set holds 17 evidence cases and
zero methods cases, and a branch no case can reach reads as live support for
a stratum that does not exist. Recover it from git history when the cases
are actually built.

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
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from common.corpus_text import load_span_text
from common.stats import wilson_ci
from eval.judge import Judge, JudgeResult, make_judge
from eval.labels import grade_direction, grade_strength, majority_class_baseline
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

    @staticmethod
    def from_dict(d: dict) -> "SystemAnswer":
        claims = [Claim(**c) for c in d.get("claims", [])]
        return SystemAnswer(
            case_id=d["case_id"], direction=d.get("direction"), strength=d.get("strength"),
            not_found=d.get("not_found", False), answer_text=d.get("answer_text", ""),
            claims=claims,
        )


@dataclass
class PropertyScore:
    verdict: Optional[str]  # "pass" | "partial" | "fail" | None (not applicable to this case)
    rationale: str
    note: str = ""


@dataclass
class CoverageUnit:
    text: str
    covered_by_claim: Optional[int]
    critical: bool

    @staticmethod
    def from_dict(value: dict, answer: SystemAnswer) -> "CoverageUnit":
        if (not isinstance(value, dict) or not isinstance(value.get("text"), str)
                or not value["text"].strip()):
            raise ValueError("each coverage unit needs non-empty text")
        critical = value.get("critical")
        if type(critical) is not bool:
            raise ValueError("coverage critical must be a JSON boolean")
        claim_number = value.get("covered_by_claim")
        if claim_number is not None and (
            type(claim_number) is not int or not 1 <= claim_number <= len(answer.claims)
        ):
            raise ValueError("covered_by_claim must be null or a valid 1-based claim number")
        return CoverageUnit(value["text"].strip(), claim_number, critical)


@dataclass
class CaseScore:
    case_id: str
    stratum: str
    direction: Optional[PropertyScore] = None
    strength: Optional[PropertyScore] = None
    groundedness: Optional[PropertyScore] = None
    claim_coverage: Optional[PropertyScore] = None
    disagreement: Optional[PropertyScore] = None
    not_found: Optional[PropertyScore] = None


def _refuses(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def score_groundedness(answer: SystemAnswer, judge: Judge, xml_dir: Path) -> PropertyScore:
    if not answer.claims:
        return PropertyScore("fail", "no claims/citations provided", note="empty_claims")
    supported = 0
    problems = []
    for claim in answer.claims:
        if not claim.cited_pmcid or not claim.cited_section:
            problems.append("invalid citation")
            continue
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


def score_claim_coverage(answer: SystemAnswer, units: list[CoverageUnit]) -> PropertyScore:
    """Grade human-annotated factual units against the submitted claim list."""
    if not units and (answer.not_found or _refuses(answer.answer_text)):
        return PropertyScore(None, "not applicable to an abstention")
    if not units:
        return PropertyScore("fail", "no factual coverage units annotated", note="empty_units")
    uncovered = [unit for unit in units if unit.covered_by_claim is None]
    critical = [unit for unit in uncovered if unit.critical]
    rate = (len(units) - len(uncovered)) / len(units)
    if not uncovered:
        verdict = "pass"
    elif rate >= 0.80 and not critical:
        verdict = "partial"
    else:
        verdict = "fail"
    return PropertyScore(
        verdict,
        f"{len(units) - len(uncovered)}/{len(units)} factual units represented ({rate:.0%}); "
        f"{len(critical)} critical omission(s)",
    )


def score_direction(case: dict, answer: SystemAnswer) -> PropertyScore:
    """Graded against a controlled vocabulary in code, with no LLM in the
    loop, and reported against the majority-class baseline, never against
    zero. Note this takes no judge. See eval/labels.py and
    docs/DECISION_LOG.md, "direction property redesign", for why this
    stopped being an LLM call: the same model was grading its own output on
    the property with the worst measured agreement, and the free-text gold
    made that agreement unmeasurable anyway."""
    verdict, rationale = grade_direction(case["gold"].get("direction"), answer.direction)
    return PropertyScore(verdict, rationale)


def score_strength(case: dict, answer: SystemAnswer) -> PropertyScore:
    """Scored separately from direction, where the two used to be conflated
    into one verdict. A right-direction/wrong-strength answer was
    indistinguishable from a wrong-direction one in the pass rate, since
    `partial` collapses to not-pass."""
    verdict, rationale = grade_strength(case["gold"].get("strength"), answer.strength)
    return PropertyScore(verdict, rationale)


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


def score_case(case: dict, answer: SystemAnswer, judge: Judge, xml_dir: Path = XML_DIR,
               coverage_units: list[CoverageUnit] | None = None) -> CaseScore:
    stratum = case["stratum"]
    result = CaseScore(case_id=case["case_id"], stratum=stratum)

    is_negative = case["is_negative_case"]
    gold = case["gold"]

    result.not_found = score_not_found(case, answer)
    if coverage_units is not None:
        result.claim_coverage = score_claim_coverage(answer, coverage_units)

    if is_negative:
        # direction/strength and disagreement don't apply: there's nothing
        # to state a direction about, and nothing to surface. Groundedness
        # only applies if the system made claims anyway (should be none).
        if answer.claims:
            result.groundedness = score_groundedness(answer, judge, xml_dir)
        return result

    result.direction = score_direction(case, answer)
    result.strength = score_strength(case, answer)
    result.groundedness = score_groundedness(answer, judge, xml_dir)
    if gold["has_disagreement"]:
        result.disagreement = score_disagreement(case, answer, judge)
    return result


def load_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def load_coverage_labels(path: Path, answers: dict[str, SystemAnswer]) -> dict[str, list[CoverageUnit]]:
    labels = {}
    for row in load_jsonl(path):
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id not in answers:
            raise ValueError(f"coverage row has unknown case_id: {case_id!r}")
        if case_id in labels:
            raise ValueError(f"duplicate coverage row: {case_id}")
        units = row.get("units")
        if not isinstance(units, list):
            raise ValueError(f"coverage units must be a list: {case_id}")
        labels[case_id] = [CoverageUnit.from_dict(unit, answers[case_id]) for unit in units]
    return labels


def summarize(scores: list[CaseScore]) -> dict:
    """Per-property pass rate, N/A cases excluded from the denominator.
    Deliberately not a single blended score: DECISION_LOG.md's rubric entry
    rejected a holistic pass/fail specifically so a property's failure
    doesn't hide behind the others."""
    properties = ["direction", "strength", "groundedness", "claim_coverage",
                  "disagreement", "not_found"]
    summary = {}
    for prop in properties:
        verdicts = [getattr(s, prop).verdict for s in scores
                    if getattr(s, prop) is not None and getattr(s, prop).verdict is not None]
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
    parser.add_argument("--coverage-labels",
                        help="human JSONL mapping factual answer units to submitted claims")
    parser.add_argument("--exploratory", action="store_true",
                        help="allow unreviewed cases and incomplete answers/coverage; not release evidence")
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
    try:
        coverage = (load_coverage_labels(Path(args.coverage_labels), answers)
                    if args.coverage_labels else {})
    except ValueError as exc:
        print(f"Invalid coverage labels: {exc}", file=sys.stderr)
        return 2
    judge = make_judge(args.judge)

    if args.held_out != "exclude":
        held_out_ids = [cid for cid in cases if split.get(cid) == "held_out"]
        n_touches = record_touch(args.touch_reason, args.touched_by, len(held_out_ids))
        warn = "  *** exceeds the recommended 3-touch cap, see eval/README.md ***" if \
            n_touches > MAX_RECOMMENDED_TOUCHES else ""
        print(f"Held-out split touched: {len(held_out_ids)} case(s), "
              f"this is touch #{n_touches}.{warn}\n", file=sys.stderr)

    missing = set(cases) - set(answers)
    rejected = [cid for cid, case in cases.items()
                if case.get("validation_verdict") in ("wrong", "rejected")]
    unreviewed = [cid for cid, case in cases.items() if not case.get("validated_by")]
    missing_coverage = set(cases) - set(coverage)
    if rejected or (not args.exploratory and (missing or unreviewed or missing_coverage)):
        print(f"Refusing release scoring: rejected={len(rejected)}, unreviewed={len(unreviewed)}, "
              f"missing answers={len(missing)}, missing coverage labels={len(missing_coverage)}. "
              "Review inputs or use --exploratory for incomplete inputs.",
              file=sys.stderr)
        return 2
    if missing:
        print(f"WARNING: {len(missing)} case(s) have no system answer, skipped: {sorted(missing)[:5]}...",
              file=sys.stderr)

    scores = []
    for case_id, case in cases.items():
        if case_id not in answers:
            continue
        scores.append(score_case(case, answers[case_id], judge, Path(args.xml_dir),
                                 coverage.get(case_id)))

    summary = summarize(scores)
    print(f"Judge: {args.judge}. Scored {len(scores)}/{len(cases)} cases.\n")
    for prop, stats in summary.items():
        ci = stats["pass_rate_ci95"]
        print(f"  {prop:20s} n={stats['n']:3d}  pass={stats['pass']:3d}  "
              f"partial={stats['partial']:3d}  fail={stats['fail']:3d}  "
              f"pass_rate={stats['pass_rate']:.0%}  95% CI [{ci[0]:.0%}, {ci[1]:.0%}]")

    # A direction pass rate is meaningless on its own while the gold set is
    # class-imbalanced, so it never gets printed on its own. See labels.py.
    scored_ids = {s.case_id for s in scores}
    value, rate, n_majority = majority_class_baseline(
        [c["gold"].get("direction") for cid, c in cases.items() if cid in scored_ids])
    if n_majority:
        print(f"\n  majority-class baseline for direction: always answer {value!r} "
              f"scores {rate:.0%} (n={n_majority}). Read the direction row against this, "
              f"not against zero.")

    if args.out:
        from common.run_meta import append_run, file_hash
        payload = {"summary": summary, "cases": [asdict(s) for s in scores],
                   "exploratory": args.exploratory, "judge": args.judge,
                   "expected_cases": len(cases), "missing_answers": sorted(missing),
                   "missing_coverage_labels": sorted(missing_coverage)}
        Path(args.out).write_text(json.dumps(payload, indent=2))
        append_run(eval_set="answer_scores", results_path=args.out, metrics=summary,
                   run_config={"judge": args.judge, "exploratory": args.exploratory,
                               "cases_sha256": file_hash(Path(args.cases)),
                               "answers_sha256": file_hash(Path(args.answers)),
                               "coverage_labels_sha256": (file_hash(Path(args.coverage_labels))
                                                          if args.coverage_labels else None)},
                   input_paths={"cases": Path(args.cases), "answers": Path(args.answers),
                                **({"coverage_labels": Path(args.coverage_labels)}
                                   if args.coverage_labels else {})})
        print(f"\nWrote {args.out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
