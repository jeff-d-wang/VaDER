"""
Generates a blind hand-labeling worksheet for the kappa calibration
PROJECT_PLAN.md M1 asks for: "Measure Cohen's kappa between judge and you
on a sample... If kappa comes back low, the rubric is underspecified, not
the judge." Deliberately omits the judge's own verdicts and rationale, an
independent rating this can be compared against, not a check on the
judge's homework.

For each case (default: the dev split only, holding the held-out split's
purpose intact) shows exactly what the judge saw when grading: the query,
the gold label, the system's full answer, and each cited claim resolved to
its real source text (so groundedness is checkable by reading the actual
span, same as the judge does). Leaves a blank verdict line per applicable
property, the same applicability rules score.py itself uses (property 3
only if gold.has_disagreement, groundedness/direction skipped for negative
cases, etc.) so the human labels exactly the same sub-questions.

Usage:
    python make_kappa_worksheet.py --answers runs/bm25_only_answers.jsonl --out kappa_worksheet.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from corpus_text import load_span_text
from score import CASES_PATH, XML_DIR, SystemAnswer, load_jsonl
from split import load_split


def format_case(case: dict, answer: SystemAnswer, xml_dir: Path) -> str:
    gold = case["gold"]
    is_negative = case["is_negative_case"]
    lines = [f"## {case['case_id']}", "", f"**Query:** {case['query']}", ""]

    if is_negative:
        lines.append("**Gold:** negative case, expected_not_found = true "
                      "(this variant/condition pair is deliberately absent from the corpus).")
    else:
        lines.append(f"**Gold direction:** {gold['direction']}  \n**Gold strength:** {gold.get('strength')}")
        if gold.get("has_disagreement"):
            lines.append(f"\n**Gold disagreement (what the sources actually conflict about):** "
                          f"{gold['disagreement_note']}")
    lines.append("")

    lines.append(f"**System said not_found:** {answer.not_found}")
    lines.append(f"**System answer:**\n> {answer.answer_text}")
    lines.append("")

    if answer.claims:
        lines.append("**System's cited claims, resolved to real source text:**")
        for i, claim in enumerate(answer.claims, start=1):
            span_text, err = load_span_text(
                xml_dir, claim.cited_pmcid, claim.cited_section,
                claim.cited_char_start, claim.cited_char_end,
            )
            lines.append(f"\n{i}. Claim: \"{claim.text}\"")
            if err:
                lines.append(f"   Citation ({claim.cited_pmcid}) does not resolve: {err}")
            else:
                # Full span, not truncated: score.py's judge grades against
                # the full text (corpus_text.load_span_text), so showing
                # less here would grade the human rater on less evidence
                # than the judge had, and inflate apparent disagreement
                # with a truncation artifact rather than a real one. See
                # docs/DECISION_LOG.md, "kappa worksheet truncation bug."
                lines.append(f"   Cited source ({claim.cited_pmcid}, {claim.cited_section}): "
                              f"\"{span_text}\"")
    else:
        lines.append("**System's cited claims:** none.")
    lines.append("")

    lines.append("**Your verdicts (pass/partial/fail):**")
    if is_negative:
        lines.append("- says_not_found: ___")
    else:
        lines.append("- direction: ___")
        lines.append("- groundedness: ___")
        if gold.get("has_disagreement"):
            lines.append("- disagreement: ___")
        lines.append("- says_not_found (should NOT have refused): ___")
    lines.append("\n---\n")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--split", choices=["dev", "held_out", "all"], default="dev")
    parser.add_argument("--cases", default=str(CASES_PATH))
    parser.add_argument("--xml-dir", default=str(XML_DIR))
    args = parser.parse_args()

    cases = {c["case_id"]: c for c in load_jsonl(Path(args.cases))}
    answers = {a["case_id"]: SystemAnswer.from_dict(a) for a in load_jsonl(Path(args.answers))}

    split = load_split()
    if split and args.split != "all":
        cases = {cid: c for cid, c in cases.items() if split.get(cid, "dev") == args.split}

    missing = set(cases) - set(answers)
    if missing:
        print(f"WARNING: {len(missing)} case(s) have no answer, skipped: {sorted(missing)}", file=sys.stderr)

    sections = [
        "# Kappa calibration worksheet",
        "",
        "For each case: read the query, the gold label, and the system's answer with its claims "
        "resolved to real source text. Fill in your own pass/partial/fail for each listed property, "
        "the same rubric the judge used (docs/DECISION_LOG.md, \"Answer-set scoring rubric\"). "
        "This is deliberately blind: no judge verdict is shown anywhere in this file.",
        "",
        "Rubric reminder: **pass** = fully correct; **partial** = right direction but a tier off "
        "(direction), or cites both sources without stating they conflict (disagreement), or "
        "70-90% of claims grounded (groundedness); **fail** = wrong/no citation/missed the conflict "
        "entirely/wrongly refused or wrongly answered.",
        "",
        "---",
        "",
    ]
    for case_id in sorted(cases):
        if case_id not in answers:
            continue
        sections.append(format_case(cases[case_id], answers[case_id], Path(args.xml_dir)))

    Path(args.out).write_text("\n".join(sections))
    print(f"Wrote {len([c for c in cases if c in answers])} cases to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
