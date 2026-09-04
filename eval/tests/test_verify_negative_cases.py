"""
Tests for verify_negative_cases.py. Stdlib only, no pytest.

Builds a synthetic corpus and manifest per test and points the module's
path constants at it, so nothing here touches the real 7,857-article corpus
or the real held-out registry.

    python -m eval.tests.test_verify_negative_cases
"""
from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import eval.verify_negative_cases as vnc


def _negative_case(case_id="neg1", variant="c.9275A>G", pmcid="PMC1",
                   construction="hold_out"):
    case = {
        "case_id": case_id, "stratum": "evidence", "is_negative_case": True,
        "gene": "BRCA2", "variant": variant, "condition": "ovarian cancer",
        "query": "q", "gold_spans": [],
        "gold": {"direction": None, "strength": None, "has_disagreement": False,
                 "disagreement_note": "", "expected_not_found": True},
        "held_out_pmcids": [pmcid], "notes": "", "created_by": "agent:test",
        "created_at_utc": "2026-09-04T00:00:00Z",
    }
    if construction:
        case["construction"] = construction
    return case


class VerifyNegativeCasesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.xml = self.root / "xml"
        self.xml.mkdir()
        self.cases_path = self.root / "cases.jsonl"

        # Two articles present in the corpus; PMC1 is the one a case will
        # claim to have held out.
        self._write_article("PMC2", "An unrelated study of BRCA2 in ovarian cancer.")

        self.manifest = self.root / "manifest.csv"
        with self.manifest.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pmcid", "status"])
            for pmcid in ("PMC1", "PMC2"):
                w.writerow([pmcid, "ok"])

        self.registry = self.root / "held_out_pmcids.csv"
        self._write_registry(["PMC1"])

        self._saved = (vnc.MANIFEST, vnc.REGISTRY, vnc.XML_DIR)
        vnc.MANIFEST, vnc.REGISTRY, vnc.XML_DIR = self.manifest, self.registry, self.xml

    def tearDown(self):
        vnc.MANIFEST, vnc.REGISTRY, vnc.XML_DIR = self._saved
        self.tmp.cleanup()

    def _write_article(self, pmcid, text):
        (self.xml / f"{pmcid}.xml").write_text(
            f"<article><front><abstract><p>{text}</p></abstract></front></article>"
        )

    def _write_registry(self, pmcids):
        with self.registry.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["pair_id", "pmcid"])
            for p in pmcids:
                w.writerow(["pair", p])

    def _run(self, cases) -> tuple[int, str]:
        with self.cases_path.open("w") as f:
            for c in cases:
                f.write(json.dumps(c) + "\n")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = vnc.main(["--cases", str(self.cases_path), "--xml-dir", str(self.xml)])
        return code, buf.getvalue()

    def test_properly_held_out_case_passes(self):
        code, out = self._run([_negative_case()])
        self.assertEqual(code, 0)
        self.assertIn("[ok]", out)
        self.assertIn("1/1 negative cases verified", out)

    def test_fails_when_the_variant_is_still_groundable(self):
        """The palb2_c1592del4 shape: the case asserts an absence the corpus
        contradicts."""
        self._write_article("PMC3", "We report BRCA2 c.9275A>G in ovarian cancer.")
        with self.manifest.open("a", newline="") as f:
            csv.writer(f).writerow(["PMC3", "ok"])
        code, out = self._run([_negative_case()])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL]", out)
        self.assertIn("still appears in 1 article", out)

    def test_fails_when_the_held_out_article_is_back_in_the_corpus(self):
        """--restore was run, or the article was never removed."""
        self._write_article("PMC1", "Some text with no matching notation.")
        code, out = self._run([_negative_case()])
        self.assertEqual(code, 1)
        self.assertIn("still present in the corpus", out)

    def test_fails_when_the_registry_does_not_know_the_article(self):
        self._write_registry([])
        code, out = self._run([_negative_case()])
        self.assertEqual(code, 1)
        self.assertIn("not in held_out registry", out)

    def test_search_built_case_fails_on_construction_alone(self):
        """A case with no hold-out behind it is rejected even when its
        variant is absent right now: absence inferred from a failed search
        is not proof, which is the whole finding this script exists for."""
        code, out = self._run([_negative_case(construction=None)])
        self.assertEqual(code, 1)
        self.assertIn("not built by hold-out", out)

    def test_empty_set_is_not_a_silent_pass(self):
        code, out = self._run([])
        self.assertEqual(code, 0)
        self.assertIn("No negative cases", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
