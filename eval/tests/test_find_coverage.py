"""
Tests for find_coverage.py. Builds a small synthetic corpus per run in a temp
dir, exercises the CLI end to end via subprocess (single-pair and batch
modes, so the multiprocessing path is exercised for real), and unit-tests
the term-matching regex directly. Run:

    python -m eval.tests.test_find_coverage
"""
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

from eval.find_coverage import _or_pattern

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]  # repo root: CLIs run as "python -m eval.<mod>"

ARTICLES = {
    "PMC2000001": {
        # gene and condition co-occur in the same paragraph
        "title": "BRCA1 pathogenic variants and breast cancer risk",
        "journal": "J Fake Genomics", "pubdate": "2023",
        "abstract": ["Background on hereditary cancer risk assessment."],
        "body": [
            "Cohort description and methods, unrelated to any specific gene.",
            "BRCA1 pathogenic variant carriers in this cohort showed elevated breast cancer risk.",
        ],
    },
    "PMC2000002": {
        # gene and condition both present, never in the same paragraph
        "title": "A broad survey of hereditary cancer genes",
        "journal": "J Fake Genomics", "pubdate": "2022",
        "abstract": [],
        "body": [
            "This study examines BRCA1 structure and function across several model systems.",
            "Separately, breast cancer epidemiology has shifted over the last two decades.",
        ],
    },
    "PMC2000003": {
        "title": "Pig muscle stem cell differentiation",
        "journal": "J Fake Animal Sci", "pubdate": "2021",
        "abstract": [],
        "body": ["This paper is entirely unrelated to human cancer genetics."],
    },
    "PMC2000004": {
        # in the manifest, XML deliberately absent on disk
        "title": "BRCA1 variant classification guidelines and breast cancer screening",
        "journal": "J Fake Genomics", "pubdate": "2020",
        "abstract": None, "body": None,
    },
    "PMC2000005": {
        "title": "TP53 mutation spectrum in Li-Fraumeni families",
        "journal": "J Fake Genomics", "pubdate": "2019",
        "abstract": [],
        "body": ["TP53 germline mutation carriers in Li-Fraumeni families face elevated cancer risk."],
    },
    "PMC2000006": {
        # gene mentioned with the condition, but the SPECIFIC variant never appears anywhere.
        # A variant-specific query for this pair must NOT match this article (regression test
        # for the gene-alone-satisfies-a-variant-query bug found in review, 2026-09-01).
        "title": "BRCA1 variants broadly and breast cancer susceptibility",
        "journal": "J Fake Genomics", "pubdate": "2018",
        "abstract": [],
        "body": ["BRCA1 carriers in general show elevated breast cancer risk across many distinct variants."],
    },
    "PMC2000007": {
        # the specific variant IS present, same paragraph as the condition.
        "title": "Case report: a novel BRCA1 c.68_69delAG carrier",
        "journal": "J Fake Genomics", "pubdate": "2017",
        "abstract": [],
        "body": ["This patient carried BRCA1 c.68_69delAG and developed early-onset breast cancer."],
    },
}


def _write_corpus(tmp: Path) -> tuple:
    xml_dir = tmp / "xml"
    xml_dir.mkdir(parents=True)
    manifest_path = tmp / "manifest.csv"
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pmcid", "status", "title", "journal", "pubdate"])
        writer.writeheader()
        for pmcid, art in ARTICLES.items():
            writer.writerow({"pmcid": pmcid, "status": "ok", "title": art["title"],
                              "journal": art["journal"], "pubdate": art["pubdate"]})
            if art["body"] is None:
                continue
            abs_paras = "".join(f"<p>{p}</p>" for p in art["abstract"])
            body_paras = "".join(f"<p>{p}</p>" for p in art["body"])
            xml = (f"<article><front><article-meta><title-group>"
                   f"<article-title>{art['title']}</article-title></title-group>"
                   f"<abstract>{abs_paras}</abstract></article-meta></front>"
                   f"<body>{body_paras}</body></article>")
            (xml_dir / f"{pmcid}.xml").write_text(xml)
    return manifest_path, xml_dir


def run_cli(tmp: Path, extra_args: list) -> tuple:
    _write_corpus(tmp)
    out = tmp / "out.csv"
    cmd = ([sys.executable, "-m", "eval.find_coverage",
            "--corpus-dir", str(tmp), "--workers", "2", "--out", str(out)] + extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    return result, out


def run_tests():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name}  {detail}")
            failures.append(name)

    # --- regex unit tests: word-boundary matching, the whole point of using
    # \b\b instead of a naive substring check ---
    pat = _or_pattern(["BRCA1"])
    check("word-boundary: matches standalone BRCA1", bool(pat.search("the BRCA1 gene")))
    check("word-boundary: rejects substring match", not pat.search("subBRCA1xyz"))
    check("word-boundary: case-insensitive", bool(pat.search("a brca1 variant")))

    multi = _or_pattern(["breast cancer", "HBOC"])
    check("multi-word phrase matches", bool(multi.search("risk of breast cancer in carriers")))
    check("short alias matches as whole word", bool(multi.search("diagnosed with HBOC")))
    check("short alias rejects substring", not multi.search("HBOCX syndrome"))

    check("empty term list returns None", _or_pattern([]) is None)
    check("blank-only term list returns None", _or_pattern(["  "]) is None)

    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)

        # --- single-pair mode: same_paragraph vs doc_level_only vs no match ---
        result, out = run_cli(tmp / "a", [
            "--pair-id", "brca1_breast", "--gene", "BRCA1", "--condition", "breast cancer",
        ])
        check("single-pair CLI exits 0", result.returncode == 0, result.stderr)
        rows = list(csv.DictReader(open(out))) if out.exists() else []
        by_pmcid = {r["pmcid"]: r for r in rows}

        check("PMC2000001 found, same_paragraph",
              by_pmcid.get("PMC2000001", {}).get("strength") == "same_paragraph", rows)
        check("PMC2000002 found, doc_level_only",
              by_pmcid.get("PMC2000002", {}).get("strength") == "doc_level_only", rows)
        check("PMC2000003 not matched (unrelated)", "PMC2000003" not in by_pmcid, rows)
        check("PMC2000004 (missing xml on disk) does not crash and is not matched",
              "PMC2000004" not in by_pmcid, rows)
        check("PMC2000005 (different gene) not matched", "PMC2000005" not in by_pmcid, rows)
        # Gene-level query (no --variant) also picks up PMC2000006/7, both mention BRCA1 + breast
        # cancer; that's correct, this query never asked for a specific variant.
        check("gene-level query: exactly 4 matches total", len(rows) == 4, rows)

        # --- variant-specific query: gene alone must NOT satisfy it (regression test for the
        # gene-alone-satisfies-a-variant-query bug found in review, 2026-09-01) ---
        result, out = run_cli(tmp / "a2", [
            "--pair-id", "brca1_variant", "--gene", "BRCA1", "--variant", "c.68_69delAG",
            "--condition", "breast cancer",
        ])
        check("variant-specific CLI exits 0", result.returncode == 0, result.stderr)
        rows2 = list(csv.DictReader(open(out))) if out.exists() else []
        by_pmcid2 = {r["pmcid"]: r for r in rows2}
        check("variant-specific: only PMC2000007 matches (has the exact variant)",
              set(by_pmcid2) == {"PMC2000007"}, rows2)
        check("variant-specific: PMC2000006 excluded (gene mentioned, variant never mentioned)",
              "PMC2000006" not in by_pmcid2, rows2)
        check("variant-specific: PMC2000001 excluded (generic 'pathogenic variant', not this one)",
              "PMC2000001" not in by_pmcid2, rows2)

        # --- warn-threshold: a low threshold on the gene-level query (4 matches) should trip
        # the warning banner on stderr ---
        result, _ = run_cli(tmp / "a3", [
            "--pair-id", "brca1_breast", "--gene", "BRCA1", "--condition", "breast cancer",
            "--warn-threshold", "1",
        ])
        check("warn-threshold banner appears on stderr when exceeded",
              "[WARN]" in result.stderr and "too many to hand-verify" in result.stderr, result.stderr)
        result, _ = run_cli(tmp / "a4", [
            "--pair-id", "brca1_variant", "--gene", "BRCA1", "--variant", "c.68_69delAG",
            "--condition", "breast cancer", "--warn-threshold", "20",
        ])
        check("no warning when under threshold", "[WARN]" not in result.stderr, result.stderr)

        # --- batch mode: two independent term sets scored in one corpus pass ---
        term_sets_csv = tmp / "term_sets.csv"
        with open(term_sets_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pair_id", "genes", "variants", "conditions"])
            w.writerow(["brca1_breast", "BRCA1", "", "breast cancer"])
            w.writerow(["tp53_lfs", "TP53", "", "Li-Fraumeni"])
        result, out = run_cli(tmp / "b", ["--term-sets-csv", str(term_sets_csv)])
        check("batch CLI exits 0", result.returncode == 0, result.stderr)
        rows = list(csv.DictReader(open(out))) if out.exists() else []
        check("both pair_ids present in batch output",
              {r["pair_id"] for r in rows} == {"brca1_breast", "tp53_lfs"}, rows)
        tp53_rows = [r for r in rows if r["pair_id"] == "tp53_lfs"]
        check("tp53_lfs matches only PMC2000005", {r["pmcid"] for r in tp53_rows} == {"PMC2000005"}, tp53_rows)

        # --- validation errors ---
        result, _ = run_cli(tmp / "c", [])
        check("no term set given -> nonzero exit", result.returncode != 0)
        result, _ = run_cli(tmp / "d", ["--pair-id", "x", "--condition", "breast cancer"])
        check("pair with condition but no gene/variant -> nonzero exit", result.returncode != 0)

    if failures:
        print(f"\n{len(failures)} FAILED: {failures}")
        sys.exit(1)
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run_tests()
