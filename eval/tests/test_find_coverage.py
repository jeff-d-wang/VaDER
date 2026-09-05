"""
Tests for find_coverage.py. Builds a small synthetic corpus per run in a temp
dir, exercises the CLI end to end via subprocess (single-pair and batch
modes, so the multiprocessing path is exercised for real), and unit-tests
the term-matching regex directly. Run:

    python -m eval.tests.test_find_coverage
"""
from __future__ import annotations

import unittest

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


class TestTermPatterns(unittest.TestCase):
    """Word-boundary matching, the whole point of using \\b rather than a
    naive substring check."""

    def test_matches_a_standalone_term_case_insensitively(self):
        pat = _or_pattern(["BRCA1"])
        self.assertTrue(pat.search("the BRCA1 gene"))
        self.assertTrue(pat.search("a brca1 variant"))

    def test_rejects_a_substring_match(self):
        self.assertIsNone(_or_pattern(["BRCA1"]).search("subBRCA1xyz"))

    def test_multi_word_phrases_and_short_aliases(self):
        multi = _or_pattern(["breast cancer", "HBOC"])
        self.assertTrue(multi.search("risk of breast cancer in carriers"))
        self.assertTrue(multi.search("diagnosed with HBOC"))
        self.assertIsNone(multi.search("HBOCX syndrome"), "short alias must not match a substring")

    def test_an_empty_term_list_has_no_pattern(self):
        self.assertIsNone(_or_pattern([]))
        self.assertIsNone(_or_pattern(["  "]))


class TestFindCoverageCli(unittest.TestCase):
    GENE_LEVEL = ["--pair-id", "brca1_breast", "--gene", "BRCA1", "--condition", "breast cancer"]
    VARIANT_LEVEL = ["--pair-id", "brca1_variant", "--gene", "BRCA1",
                     "--variant", "c.68_69delAG", "--condition", "breast cancer"]

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def rows(self, name, args):
        result, out = run_cli(self.tmp / name, args)
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f)) if out.exists() else []
        return result, rows

    def test_gene_level_query_separates_same_paragraph_from_doc_level(self):
        result, rows = self.rows("a", self.GENE_LEVEL)
        self.assertEqual(result.returncode, 0, result.stderr)
        by_pmcid = {r["pmcid"]: r for r in rows}
        self.assertEqual(by_pmcid.get("PMC2000001", {}).get("strength"), "same_paragraph", rows)
        self.assertEqual(by_pmcid.get("PMC2000002", {}).get("strength"), "doc_level_only", rows)
        self.assertNotIn("PMC2000003", by_pmcid, "unrelated article must not match")
        self.assertNotIn("PMC2000004", by_pmcid, "missing xml on disk: skipped, not a crash")
        self.assertNotIn("PMC2000005", by_pmcid, "different gene must not match")
        # PMC2000006/7 also mention BRCA1 + breast cancer, correctly: this
        # query never asked for a specific variant.
        self.assertEqual(len(rows), 4, rows)

    def test_a_variant_query_is_not_satisfied_by_the_gene_alone(self):
        """Regression: the gene-alone-satisfies-a-variant-query bug found in
        review, 2026-09-01."""
        result, rows = self.rows("a2", self.VARIANT_LEVEL)
        self.assertEqual(result.returncode, 0, result.stderr)
        by_pmcid = {r["pmcid"]: r for r in rows}
        self.assertEqual(set(by_pmcid), {"PMC2000007"},
                         "only the article carrying the exact variant may match")

    def test_warn_threshold_banner(self):
        result, _ = run_cli(self.tmp / "a3", self.GENE_LEVEL + ["--warn-threshold", "1"])
        self.assertIn("[WARN]", result.stderr)
        self.assertIn("too many to hand-verify", result.stderr)

    def test_no_warning_when_under_threshold(self):
        result, _ = run_cli(self.tmp / "a4", self.VARIANT_LEVEL + ["--warn-threshold", "20"])
        self.assertNotIn("[WARN]", result.stderr, result.stderr)

    def test_batch_mode_scores_two_term_sets_in_one_corpus_pass(self):
        term_sets_csv = self.tmp / "term_sets.csv"
        with open(term_sets_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pair_id", "genes", "variants", "conditions"])
            w.writerow(["brca1_breast", "BRCA1", "", "breast cancer"])
            w.writerow(["tp53_lfs", "TP53", "", "Li-Fraumeni"])
        result, rows = self.rows("b", ["--term-sets-csv", str(term_sets_csv)])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({r["pair_id"] for r in rows}, {"brca1_breast", "tp53_lfs"}, rows)
        tp53 = [r for r in rows if r["pair_id"] == "tp53_lfs"]
        self.assertEqual({r["pmcid"] for r in tp53}, {"PMC2000005"}, tp53)

    def test_an_incomplete_term_set_is_refused(self):
        self.assertNotEqual(run_cli(self.tmp / "c", [])[0].returncode, 0,
                            "no term set given must fail")
        self.assertNotEqual(
            run_cli(self.tmp / "d", ["--pair-id", "x", "--condition", "breast cancer"])[0].returncode,
            0, "a condition with no gene or variant must fail")


if __name__ == "__main__":
    unittest.main()
