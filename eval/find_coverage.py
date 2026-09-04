"""
Recall-oriented full-corpus sweep for eval-set construction (M1). Not a live
retrieval tool, not part of the FastAPI service. Two things need this:

  1. Negative-case construction (property 4, "not found in this corpus"):
     before holding out a variant-condition pair's articles, you need to know
     EVERY article in the corpus that covers it. Miss one and the negative
     case is silently invalid: the corpus still grounds it elsewhere.
  2. Disagreement-candidate discovery (property 3, "surfaces disagreement"):
     find every article covering a variant-condition pair, then a human (or
     an agent) reads the candidates and judges whether any genuinely
     conflict. This tool finds candidates; it does not judge disagreement.

Unlike service/search.py (title-prefiltered and capped for low-latency
serving), this scans every article's title/abstract/body in full, because
the point here is recall, not speed. It's meant to be run on demand, once
per batch of variant-condition pairs, not per query.

Term matching is deliberately not "smart." You supply gene/variant/condition
term lists yourself (aliases, HGVS notations, synonyms): the tool does
case-insensitive whole-word OR-matching within each category, AND across
categories. It reports two match strengths per article:
  - same_paragraph: a gene/variant term and a condition term appear in the
    same paragraph. Likely real coverage.
  - doc_level_only: both appear somewhere in the document, but never in the
    same paragraph. Weaker signal; read it before you trust it.

Usage, one pair:
    python -m eval.find_coverage --pair-id brca1_hboc --gene BRCA1 \\
        --condition "breast cancer" --condition "ovarian cancer" --condition HBOC

Usage, many pairs in one corpus pass (cheaper than looping the corpus once
per pair -- every article is parsed once and tested against all term sets):
    python -m eval.find_coverage --term-sets-csv term_sets.example.csv

Both write a CSV of candidate rows (default ./coverage_candidates.csv), one
row per (pair_id, pmcid) match, sorted strongest matches first.
"""
from __future__ import annotations

import argparse
import csv
import multiprocessing
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

Paragraph = tuple  # (section: str, text: str, char_start: int, char_end: int)


@dataclass
class TermSet:
    pair_id: str
    genes: list = field(default_factory=list)
    variants: list = field(default_factory=list)
    conditions: list = field(default_factory=list)

    def compiled(self) -> "CompiledTermSet":
        # Bug found in review (2026-09-01): this used to OR genes and variants
        # together into one "subject" pattern, so "MRE11 mentioned, condition
        # mentioned, the specific variant never mentioned" counted as a match.
        # That silently over-broadens what counts as "covering this pair" and
        # produced 15-63 hit candidate lists for supposedly narrow, single-
        # variant pairs, far too many to hand-verify, exactly the case this
        # tool exists to make verifiable. Fix: when a variant is given, it is
        # the subject requirement, on its own, genes are not a substitute.
        # Gene-level queries (no variant given, e.g. disagreement discovery
        # across a whole gene) are unaffected, they still match on the gene.
        subject_terms = self.variants if self.variants else self.genes
        return CompiledTermSet(
            pair_id=self.pair_id,
            subject_pat=_or_pattern(subject_terms),
            condition_pat=_or_pattern(self.conditions),
            variant_specific=bool(self.variants),
        )


@dataclass
class CompiledTermSet:
    pair_id: str
    subject_pat: Optional["re.Pattern"]
    condition_pat: Optional["re.Pattern"]
    variant_specific: bool = False


def _or_pattern(terms: list) -> Optional["re.Pattern"]:
    terms = [t for t in terms if t.strip()]
    if not terms:
        return None
    # Longest first, so alternation prefers the more specific term when terms overlap.
    ordered = sorted({t.strip() for t in terms}, key=len, reverse=True)
    body = "|".join(re.escape(t) for t in ordered)
    return re.compile(rf"\b(?:{body})\b", re.IGNORECASE)


def _split(s: str) -> list:
    return [t.strip() for t in s.split(";") if t.strip()]


def load_term_sets_from_csv(path: Path) -> list:
    out = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out.append(TermSet(
                pair_id=row["pair_id"],
                genes=_split(row.get("genes", "")),
                variants=_split(row.get("variants", "")),
                conditions=_split(row.get("conditions", "")),
            ))
    return out


def _extract_paragraphs(xml_path: Path) -> list:
    """(section, text, char_start, char_end) for every abstract and body
    paragraph. Offsets restart at 0 per section, matching the
    (pmcid, section_id, char_start, char_end) label schema."""
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return []
    paras = []
    for section_name, xpath in (("abstract", ".//abstract"), ("body", ".//body")):
        container = root.find(xpath)
        if container is None:
            continue
        offset = 0
        for p in container.findall(".//p"):
            text = "".join(p.itertext())
            paras.append((section_name, text, offset, offset + len(text)))
            offset += len(text) + 1
    return paras


_WORKER_TERMSETS: list = []


def _init_worker(termsets: list) -> None:
    global _WORKER_TERMSETS
    _WORKER_TERMSETS = termsets


def _scan_one(task) -> list:
    pmcid, xml_path, meta = task
    paras = _extract_paragraphs(xml_path)
    if not paras:
        return []

    rows = []
    for ts in _WORKER_TERMSETS:
        same_para = 0
        doc_subject = doc_condition = False
        best = None
        subject_terms_seen: set = set()
        condition_terms_seen: set = set()

        for section, text, start, end in paras:
            has_subject = bool(ts.subject_pat and ts.subject_pat.search(text))
            has_condition = bool(ts.condition_pat and ts.condition_pat.search(text))
            if has_subject:
                doc_subject = True
                subject_terms_seen.update(m.group(0) for m in ts.subject_pat.finditer(text))
            if has_condition:
                doc_condition = True
                condition_terms_seen.update(m.group(0) for m in ts.condition_pat.finditer(text))
            if has_subject and has_condition:
                same_para += 1
                if best is None:
                    best = (section, text, start, end)

        if same_para > 0:
            strength = "same_paragraph"
            section, text, start, end = best
        elif doc_subject and doc_condition:
            strength = "doc_level_only"
            candidate = next((p for p in paras if ts.subject_pat and ts.subject_pat.search(p[1])), paras[0])
            section, text, start, end = candidate
        else:
            continue

        rows.append({
            "pair_id": ts.pair_id, "pmcid": pmcid, "strength": strength,
            "n_same_paragraph_hits": same_para,
            "matched_subject_terms": ";".join(sorted(subject_terms_seen)),
            "matched_condition_terms": ";".join(sorted(condition_terms_seen)),
            "title": meta.get("title", ""), "journal": meta.get("journal", ""),
            "pubdate": meta.get("pubdate", ""),
            "section": section, "char_start": start, "char_end": end,
            "snippet": text[:400],
        })
    return rows


def scan_corpus(manifest_path: Path, xml_dir: Path, termsets: list, workers: int) -> list:
    tasks = []
    with open(manifest_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") != "ok":
                continue
            meta = {"title": row.get("title", ""), "journal": row.get("journal", ""),
                     "pubdate": row.get("pubdate", "")}
            tasks.append((row["pmcid"], xml_dir / f"{row['pmcid']}.xml", meta))

    results = []
    t0 = time.monotonic()
    with multiprocessing.Pool(processes=workers, initializer=_init_worker, initargs=(termsets,)) as pool:
        for i, matches in enumerate(pool.imap_unordered(_scan_one, tasks, chunksize=50), 1):
            results.extend(matches)
            if i % 1000 == 0 or i == len(tasks):
                print(f"  scanned {i}/{len(tasks)} articles, {len(results)} matches so far "
                      f"({time.monotonic() - t0:.0f}s elapsed)", file=sys.stderr)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus-dir", default=os.environ.get("VADER_CORPUS_DIR", "../corpus"),
                     help="directory with manifest.csv and xml/ (default ../corpus, or $VADER_CORPUS_DIR)")
    ap.add_argument("--term-sets-csv", help="CSV with columns pair_id,genes,variants,conditions (each ';'-separated)")
    ap.add_argument("--pair-id", help="single-pair mode: an id for this pair")
    ap.add_argument("--gene", action="append", default=[], help="single-pair mode, repeatable")
    ap.add_argument("--variant", action="append", default=[], help="single-pair mode, repeatable")
    ap.add_argument("--condition", action="append", default=[], help="single-pair mode, repeatable")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--out", default="coverage_candidates.csv")
    ap.add_argument("--warn-threshold", type=int, default=20,
                     help="print a hard-to-miss warning when a pair's same_paragraph count exceeds "
                          "this (default 20). A list this large cannot realistically be fully "
                          "hand-verified; if you're building a negative case, narrow the pair and "
                          "re-run rather than treating this list as complete.")
    args = ap.parse_args()

    single_pair_args = args.pair_id or args.gene or args.variant or args.condition
    if args.term_sets_csv and single_pair_args:
        ap.error("use --term-sets-csv OR --pair-id/--gene/--variant/--condition, not both")
    if args.term_sets_csv:
        term_sets = load_term_sets_from_csv(Path(args.term_sets_csv))
    elif args.pair_id:
        term_sets = [TermSet(pair_id=args.pair_id, genes=args.gene, variants=args.variant, conditions=args.condition)]
    else:
        ap.error("need --term-sets-csv, or --pair-id with --gene/--variant/--condition")
        return

    for ts in term_sets:
        if not (ts.genes or ts.variants):
            ap.error(f"pair {ts.pair_id}: need at least one --gene or a genes/variants entry")
        if not ts.conditions:
            ap.error(f"pair {ts.pair_id}: need at least one --condition")

    corpus_dir = Path(args.corpus_dir)
    manifest_path = corpus_dir / "manifest.csv"
    xml_dir = corpus_dir / "xml"
    if not manifest_path.exists():
        ap.error(f"no manifest at {manifest_path}")

    print(f"Scanning corpus for {len(term_sets)} term set(s): {[ts.pair_id for ts in term_sets]}")
    compiled = [ts.compiled() for ts in term_sets]
    results = scan_corpus(manifest_path, xml_dir, compiled, args.workers)
    results.sort(key=lambda r: (r["pair_id"], r["strength"] != "same_paragraph", -r["n_same_paragraph_hits"]))

    fieldnames = ["pair_id", "pmcid", "strength", "n_same_paragraph_hits", "matched_subject_terms",
                  "matched_condition_terms", "title", "journal", "pubdate", "section",
                  "char_start", "char_end", "snippet"]
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWrote {len(results)} candidate rows to {args.out}")
    by_pair: dict = {}
    for r in results:
        counts = by_pair.setdefault(r["pair_id"], {"same_paragraph": 0, "doc_level_only": 0})
        counts[r["strength"]] += 1
    too_broad = []
    for ts in term_sets:
        c = by_pair.get(ts.pair_id, {"same_paragraph": 0, "doc_level_only": 0})
        print(f"  {ts.pair_id}: {c['same_paragraph']} same_paragraph, {c['doc_level_only']} doc_level_only")
        if c["same_paragraph"] > args.warn_threshold:
            too_broad.append((ts.pair_id, c["same_paragraph"]))

    if too_broad:
        print(f"\n[WARN] {len(too_broad)} pair(s) exceed --warn-threshold ({args.warn_threshold}) "
              f"same_paragraph matches:", file=sys.stderr)
        for pair_id, n in too_broad:
            print(f"         {pair_id}: {n} matches, too many to hand-verify with confidence.",
                  file=sys.stderr)
        print("       If you're building a NEGATIVE CASE (property 4), do not run "
              "hold_out_case.py on these yet. Narrow the term set (a more specific variant "
              "notation, a narrower condition) and re-run first. A candidate list this large "
              "usually means the match is too permissive, not that the pair is genuinely this "
              "widely covered.", file=sys.stderr)


if __name__ == "__main__":
    main()
