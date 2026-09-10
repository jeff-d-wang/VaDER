"""Create blind human worksheets for claim-to-source grounding labels."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path

from common.corpus_text import load_span_text
from eval.score import CASES_PATH, XML_DIR, Claim, SystemAnswer, load_jsonl
from eval.split import load_split


@dataclass(frozen=True, eq=False)
class Candidate:
    source_run: str
    case: dict
    claim_number: int
    claim: Claim


@dataclass(frozen=True)
class DisplayPair:
    candidate: Candidate
    citation: Claim
    span_text: str
    stratum: str
    donor: Candidate | None = None


def select_pairs(cases: dict, answers: dict[str, SystemAnswer], limit: int) -> list[tuple[dict, int, object]]:
    """Round-robin claims across sorted cases to avoid claim-heavy case dominance."""
    case_ids = sorted(set(cases) & set(answers))
    selected = []
    claim_number = 1
    while len(selected) < limit:
        added = False
        for case_id in case_ids:
            claims = answers[case_id].claims
            if claim_number <= len(claims):
                selected.append((cases[case_id], claim_number, claims[claim_number - 1]))
                added = True
                if len(selected) == limit:
                    break
        if not added:
            break
        claim_number += 1
    return selected


def _citation(claim: Claim) -> dict:
    return {
        "pmcid": claim.cited_pmcid,
        "section_id": claim.cited_section,
        "char_start": claim.cited_char_start,
        "char_end": claim.cited_char_end,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _span(claim: Claim, xml_dir: Path) -> str:
    text, error = load_span_text(
        xml_dir, claim.cited_pmcid, claim.cited_section,
        claim.cited_char_start, claim.cited_char_end,
    )
    if error:
        raise ValueError(f"citation does not resolve for {claim.cited_pmcid}: {error}")
    return text


def _pilot_pairs(path: Path) -> set[tuple[str, int]]:
    pattern = r"^## Pair \d+: (.+?) claim (\d+)$"
    return {(case_id, int(number)) for case_id, number in re.findall(pattern, path.read_text(), re.M)}


def collect_candidates(
    cases: dict,
    answer_paths: list[Path],
    excluded: set[tuple[str, int]],
    exclude_source: Path | None,
) -> list[Candidate]:
    candidates = []
    excluded_source = str(exclude_source.resolve()) if exclude_source else None
    for path in answer_paths:
        answers = {
            row["case_id"]: SystemAnswer.from_dict(row)
            for row in load_jsonl(path)
            if row["case_id"] in cases
        }
        for case, number, claim in select_pairs(cases, answers, 10**9):
            if excluded_source == str(path.resolve()) and (case["case_id"], number) in excluded:
                continue
            candidates.append(Candidate(path.name, case, number, claim))
    return candidates


def _words(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[A-Za-z0-9]+", text) if len(word) > 2}


def make_stress_pairs(
    candidates: list[Candidate], count: int, xml_dir: Path,
) -> list[DisplayPair]:
    """Pair real claims with lexically plausible spans from different cases."""
    spans = {candidate: _span(candidate.claim, xml_dir) for candidate in candidates}
    unused_donors = set(candidates)
    output = []
    for source in candidates:
        if len(output) == count:
            break
        claim_words = _words(source.claim.text)
        eligible = [
            donor for donor in candidates
            if donor.case["case_id"] != source.case["case_id"] and donor in unused_donors
        ]
        if not eligible:
            eligible = [donor for donor in candidates if donor.case["case_id"] != source.case["case_id"]]
        if not eligible:
            raise ValueError("stress pairs require claims from at least two cases")
        donor = max(
            eligible,
            key=lambda item: (
                len(claim_words & _words(spans[item])) / max(1, len(claim_words)),
                item.source_run,
                item.case["case_id"],
                -item.claim_number,
            ),
        )
        unused_donors.discard(donor)
        output.append(DisplayPair(source, donor.claim, spans[donor], "stress", donor))
    if len(output) != count:
        raise ValueError(f"requested {count} stress pairs but only {len(output)} could be created")
    return output


def render_pair(number: int, case: dict, claim_number: int, claim, xml_dir: Path) -> str:
    """Render the original rubric-pilot format."""
    try:
        source = _span(claim, xml_dir)
    except ValueError as error:
        source = str(error)
    return "\n".join([
        f"## Pair {number}: {case['case_id']} claim {claim_number}", "",
        f"**Query:** {case['query']}", "",
        f"**Claim:** {claim.text}", "",
        (f"**Citation:** `{claim.cited_pmcid}`, `{claim.cited_section}`, "
         f"characters {claim.cited_char_start}:{claim.cited_char_end}"), "",
        "**Complete cited source span:**", "", f"> {source.replace(chr(10), chr(10) + '> ')}", "",
        "**Your label:** `supported | unsupported | unclear`", "",
        "**Your rationale:**", "", "", "---", "",
    ])


def render_final_pair(pair_id: str, pair: DisplayPair) -> str:
    claim = pair.citation
    return "\n".join([
        f"## {pair_id}", "",
        f"**Claim:** {pair.candidate.claim.text}", "",
        (f"**Citation:** `{claim.cited_pmcid}`, `{claim.cited_section}`, "
         f"characters {claim.cited_char_start}:{claim.cited_char_end}"), "",
        "**Complete cited source span:**", "",
        f"> {pair.span_text.replace(chr(10), chr(10) + '> ')}", "",
        "**Your label:** `supported | unsupported`", "",
        "**Failure subtype, if applicable:**", "", "",
        "**Your rationale:**", "", "", "---", "",
    ])


def _final_header() -> list[str]:
    return [
        "# Blind claim-grounding calibration", "",
        "Label whether each complete cited span explicitly supports the entire claim. Use only the "
        "shown span. Every material entity, variant, condition, direction, magnitude, population, "
        "time and uncertainty qualifier must be supported.", "",
        "Silence cannot support a scientific negative such as no association, no effect or no "
        "reported outcome. Every component of a compound claim must be supported. A caption can "
        "support a result it states explicitly. If a result is only encoded in an unavailable "
        "figure, label it unsupported and enter `figure_required` as the failure subtype. Judge "
        "claim-to-span support only, not whether the claim answers the original query.", "",
        "Choose one label per pair and explain unsupported decisions. Do not inspect the separate "
        "manifest or any automated judge output until all labels are complete.", "", "---", "",
    ]


def write_final(
    candidates: list[Candidate], natural_count: int, stress_count: int, seed: int,
    out: Path, manifest_path: Path, answer_paths: list[Path], exclusion_path: Path,
    exclude_source: Path, xml_dir: Path,
) -> None:
    if natural_count > len(candidates):
        raise ValueError(f"requested {natural_count} natural pairs but only {len(candidates)} are available")
    natural_candidates = candidates[:natural_count]
    natural = [
        DisplayPair(candidate, candidate.claim, _span(candidate.claim, xml_dir), "natural")
        for candidate in natural_candidates
    ]
    stress = make_stress_pairs(natural_candidates, stress_count, xml_dir)
    pairs = natural + stress
    random.Random(seed).shuffle(pairs)

    sections = _final_header()
    ids = [f"GCV1-{number:03d}" for number in range(1, len(pairs) + 1)]
    for pair_id, pair in zip(ids, pairs):
        sections.append(render_final_pair(pair_id, pair))
    out.write_text("\n".join(sections))

    records = []
    for pair_id, pair in zip(ids, pairs):
        record = {
            "pair_id": pair_id,
            "stratum": pair.stratum,
            "source_run": pair.candidate.source_run,
            "case_id": pair.candidate.case["case_id"],
            "claim_number": pair.candidate.claim_number,
            "claim_text": pair.candidate.claim.text,
            "original_citation": _citation(pair.candidate.claim),
            "displayed_citation": _citation(pair.citation),
            "displayed_span_sha256": hashlib.sha256(pair.span_text.encode()).hexdigest(),
            "perturbation": "citation_swap" if pair.donor else "none",
        }
        if pair.donor:
            record["donor"] = {
                "source_run": pair.donor.source_run,
                "case_id": pair.donor.case["case_id"],
                "claim_number": pair.donor.claim_number,
            }
        records.append(record)
    manifest = {
        "schema_version": 1,
        "rubric_version": "text_span_grounding_v1",
        "seed": seed,
        "counts": {"natural": len(natural), "stress": len(stress), "total": len(pairs)},
        "inputs": [{"path": str(path), "sha256": _sha256(path)} for path in answer_paths],
        "exclusion": {
            "worksheet": str(exclusion_path),
            "worksheet_sha256": _sha256(exclusion_path),
            "source_run": str(exclude_source),
        },
        "worksheet": str(out),
        "worksheet_sha256": _sha256(out),
        "pairs": records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", required=True, action="append")
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--cases", action="append")
    parser.add_argument("--xml-dir", default=str(XML_DIR))
    parser.add_argument("--exclude-worksheet")
    parser.add_argument("--exclude-source")
    parser.add_argument("--stress-count", type=int, default=0)
    parser.add_argument("--manifest")
    parser.add_argument("--seed", type=int, default=20260910)
    args = parser.parse_args(argv)
    if args.limit < 1 or args.stress_count < 0:
        parser.error("--limit must be positive and --stress-count cannot be negative")

    case_paths = [Path(path) for path in args.cases] if args.cases else [CASES_PATH]
    cases = {
        row["case_id"]: row
        for path in case_paths
        for row in load_jsonl(path)
    }
    split = load_split()
    if split:
        cases = {case_id: case for case_id, case in cases.items()
                 if split.get(case_id, "dev") == "dev"}
    answer_paths = [Path(path) for path in args.answers]

    if args.stress_count or args.manifest or args.exclude_worksheet:
        if not (args.stress_count and args.manifest and args.exclude_worksheet and args.exclude_source):
            parser.error("final calibration requires --stress-count, --manifest, --exclude-worksheet and --exclude-source")
        exclusion_path = Path(args.exclude_worksheet)
        exclude_source = Path(args.exclude_source)
        candidates = collect_candidates(cases, answer_paths, _pilot_pairs(exclusion_path), exclude_source)
        write_final(
            candidates, args.limit, args.stress_count, args.seed, Path(args.out),
            Path(args.manifest), answer_paths, exclusion_path, exclude_source, Path(args.xml_dir),
        )
        print(f"Wrote {args.limit} natural and {args.stress_count} stress pairs to {args.out}")
        return 0

    answers = {row["case_id"]: SystemAnswer.from_dict(row)
               for row in load_jsonl(answer_paths[0])}
    pairs = select_pairs(cases, answers, args.limit)
    sections = [
        "# Blind claim-grounding rubric pilot", "",
        "Label whether each complete cited span supports the entire claim. Use only the shown span. "
        "Every material entity, variant, condition, direction, magnitude, population, time and "
        "uncertainty qualifier must be supported. Topic overlap is insufficient.", "",
        "Use `unclear` when the written rule cannot decide the pair. Explain why. We will resolve "
        "those examples and freeze the rubric before measuring judge agreement.", "", "---", "",
    ]
    for number, (case, claim_number, claim) in enumerate(pairs, 1):
        sections.append(render_pair(number, case, claim_number, claim, Path(args.xml_dir)))
    Path(args.out).write_text("\n".join(sections))
    print(f"Wrote {len(pairs)} blind development claim/span pairs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
