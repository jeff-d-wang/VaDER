"""
Parses a filled-in kappa_worksheet.md (see make_kappa_worksheet.py) and
computes judge-vs-human Cohen's kappa per property against a score.py
--out JSON. This is the actual calibration step PROJECT_PLAN.md M1 asks
for: "Measure Cohen's kappa between judge and you... If kappa comes back
low, the rubric is underspecified, not the judge."

The worksheet's "- property: verdict" lines are what gets parsed; verdict
must be pass/partial/fail (case-insensitive), a leftover "___" blank is
treated as not-yet-answered and excluded from the comparison (not
silently scored as a disagreement).

Usage:
    python -m eval.run_kappa_calibration --worksheet kappa_worksheet_filled.md \
        --judge-scores runs/bm25_only_scores.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from eval.kappa import kappa_report

_PROPERTY_ALIASES = {
    "says_not_found": "not_found",
    "not_found": "not_found",
    "direction": "direction",
    "groundedness": "groundedness",
    "disagreement": "disagreement",
    "parameter_accuracy": "parameter_accuracy",
    "citation": "citation",
}
_VERDICT_LINE = re.compile(
    # Trailing rationale after the verdict is expected and common ("fail
    # (claim 3 relies on...)"), so only the word itself is anchored, not
    # end-of-line; a first version of this regex required end-of-line and
    # silently dropped every annotated verdict, see DECISION_LOG.md.
    r"^-\s*([a-z_]+)\s*(?:\([^)]*\))?:\s*(pass|partial|fail|___)\b", re.IGNORECASE
)


def parse_worksheet(text: str) -> dict[str, dict[str, str]]:
    """Returns {case_id: {property: verdict}}, "___" (unanswered) entries
    dropped rather than kept as a fake value."""
    result: dict[str, dict[str, str]] = {}
    current_case = None
    for line in text.splitlines():
        header = re.match(r"^##\s+(\S+)", line)
        if header:
            current_case = header.group(1)
            result.setdefault(current_case, {})
            continue
        m = _VERDICT_LINE.match(line.strip())
        if m and current_case:
            prop_raw, verdict = m.group(1).lower(), m.group(2).lower()
            if verdict == "___":
                continue
            prop = _PROPERTY_ALIASES.get(prop_raw)
            if prop:
                result[current_case][prop] = verdict
    return result


def load_judge_scores(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text())
    return {c["case_id"]: c for c in data["cases"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worksheet", required=True)
    parser.add_argument("--judge-scores", required=True)
    args = parser.parse_args()

    human = parse_worksheet(Path(args.worksheet).read_text())
    judge = load_judge_scores(Path(args.judge_scores))

    n_answered = sum(len(v) for v in human.values())
    print(f"Parsed {n_answered} human verdict(s) across {len(human)} case(s).\n")

    properties = ["direction", "groundedness", "disagreement", "not_found",
                  "parameter_accuracy", "citation"]
    for prop in properties:
        pairs = []
        for case_id, verdicts in human.items():
            if prop not in verdicts:
                continue
            judge_case = judge.get(case_id)
            if not judge_case or judge_case.get(prop) is None:
                continue
            pairs.append((judge_case[prop]["verdict"], verdicts[prop]))
        if not pairs:
            continue
        judge_ratings = [p[0] for p in pairs]
        human_ratings = [p[1] for p in pairs]
        print(f"=== {prop} ===")
        print(kappa_report(judge_ratings, human_ratings, "judge", "human"))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
