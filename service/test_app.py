"""
Tests for the Step 0c service. Builds a tiny synthetic corpus (manifest +
JATS-ish XML) in a temp dir per test via `create_app`, so these never touch
the real ../corpus and stay fast and hermetic. Run:

    python -m unittest service.test_app
"""
from __future__ import annotations

import unittest

import csv
import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from service.app import create_app

ARTICLES = {
    "PMC1000001": {
        "title": "BRCA1 pathogenic variants in hereditary breast and ovarian cancer",
        "journal": "J Fake Genomics", "pubdate": "2024",
        "body": [
            "Introductory paragraph about cohort design and methods.",
            "BRCA1 pathogenic variant carriers showed elevated risk of breast cancer "
            "and ovarian cancer relative to non-carriers in this cohort.",
        ],
    },
    "PMC1000002": {
        "title": "TP53 mutation spectrum in Li-Fraumeni syndrome families",
        "journal": "J Fake Genomics", "pubdate": "2022",
        "body": [
            "TP53 germline mutation was identified in all affected family members.",
            "No association with BRCA1 or BRCA2 was observed in this cohort.",
        ],
    },
    "PMC1000003": {
        "title": "A study of pig muscle stem cell differentiation",
        "journal": "J Fake Animal Sci", "pubdate": "2021",
        "body": ["This paper is entirely unrelated to cancer genomics."],
    },
    "PMC1000004": {
        # In the manifest, but its XML file is deliberately missing, to
        # exercise the "candidate matched by title, but nothing on disk" path.
        "title": "BRCA2 variant classification guidelines",
        "journal": "J Fake Genomics", "pubdate": "2023",
        "body": None,
    },
}


def _write_corpus(tmp: Path) -> tuple[Path, Path]:
    xml_dir = tmp / "xml"
    xml_dir.mkdir(parents=True)
    manifest_path = tmp / "manifest.csv"
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["pmcid", "status", "title", "journal", "pubdate"])
        writer.writeheader()
        for pmcid, art in ARTICLES.items():
            writer.writerow({"pmcid": pmcid, "status": "ok", "title": art["title"],
                              "journal": art["journal"], "pubdate": art["pubdate"]})
            if art["body"] is not None:
                paras = "".join(f"<p>{p}</p>" for p in art["body"])
                xml = (f"<article><front><article-meta><title-group>"
                       f"<article-title>{art['title']}</article-title></title-group>"
                       f"</article-meta></front><body>{paras}</body></article>")
                (xml_dir / f"{pmcid}.xml").write_text(xml)
    return manifest_path, xml_dir


def _make_client(tmp: Path, **kw) -> TestClient:
    manifest_path, xml_dir = _write_corpus(tmp)
    app = create_app(manifest_path=manifest_path, xml_dir=xml_dir,
                      log_path=tmp / "logs" / "requests.jsonl", **kw)
    return TestClient(app)


class TestService(unittest.TestCase):
    """Each method gets its own temp corpus and its own client, so a failure
    isolates to one behaviour instead of aborting the rest of the file."""

    def client(self, **kw):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        return self.enterContext(_make_client(tmp / "a", **kw))

    def query(self, client, text):
        r = client.post("/query", json={"query": text})
        return r, [json.loads(l) for l in r.text.strip().split("\n")]

    def test_healthz_reports_corpus_size_and_config(self):
        client = self.client(max_scan=7, max_matches=3)
        r = client.get("/healthz")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["corpus_size"], 4, r.json())
        self.assertEqual(r.json()["config"]["max_scan"], 7, r.json())

    def test_query_returns_a_match_with_a_source_span(self):
        client = self.client(max_scan=7, max_matches=3)
        r, lines = self.query(client, "BRCA1 pathogenic variant breast cancer")
        self.assertEqual(r.status_code, 200, r.text)
        matches = [l for l in lines if l["type"] == "match"]
        self.assertGreaterEqual(len(matches), 1, lines)
        self.assertEqual(lines[-1]["type"], "summary", "exactly one summary line, last")
        m = matches[0]
        self.assertEqual(m["pmcid"], "PMC1000001", m)
        self.assertTrue(m["char_end"] > m["char_start"] >= 0, m)
        self.assertLessEqual(len(m["text"]), 500, "match text is truncated to <=500")

    def test_unrelated_query_reports_not_found(self):
        client = self.client(max_scan=7, max_matches=3)
        _, lines = self.query(client, "zebrafish coral reef photosynthesis")
        not_found = [l for l in lines if l["type"] == "not_found"]
        self.assertTrue(not_found, lines)
        self.assertEqual(not_found[0]["note"], "not found in this corpus")

    def test_candidate_with_missing_xml_is_skipped_not_a_500(self):
        client = self.client(max_scan=7, max_matches=3)
        r, _ = self.query(client, "BRCA2 variant classification guidelines")
        self.assertEqual(r.status_code, 200, r.text)

    def test_respects_max_matches_cap(self):
        client = self.client(max_scan=7, max_matches=3)
        _, lines = self.query(client, "cohort genomics")
        self.assertLessEqual(len([l for l in lines if l["type"] == "match"]), 3)

    def test_short_query_is_rejected(self):
        client = self.client(max_scan=7, max_matches=3)
        r = client.post("/query", json={"query": "ab"})
        self.assertEqual(r.status_code, 422, r.text)

    def test_one_log_line_per_attempted_query(self):
        tmp = Path(self.enterContext(tempfile.TemporaryDirectory())) / "a"
        client = self.enterContext(_make_client(tmp, max_scan=7, max_matches=3))
        for q in ("BRCA1 pathogenic variant breast cancer", "zebrafish coral reef photosynthesis",
                  "BRCA2 variant classification guidelines", "cohort genomics"):
            client.post("/query", json={"query": q})
        client.post("/query", json={"query": "ab"})  # 422, never reaches the handler

        log_lines = [json.loads(l) for l in
                     (tmp / "logs" / "requests.jsonl").read_text().strip().split("\n")]
        self.assertEqual(len(log_lines), 4,
                         "4 handled queries logged; the 422 never reaches the handler")
        for field in ("query", "ttft_ms", "total_ms", "n_matches", "stopped_reason", "logged_at_utc"):
            self.assertIn(field, log_lines[0])
        self.assertTrue(all(r["ttft_ms"] <= r["total_ms"] + 0.01 for r in log_lines), log_lines)

    def test_empty_corpus_is_503_and_says_so(self):
        empty = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (empty / "logs").mkdir()
        app = create_app(manifest_path=empty / "manifest.csv", xml_dir=empty / "xml",
                          log_path=empty / "logs" / "requests.jsonl")
        client = self.enterContext(TestClient(app))
        self.assertEqual(client.get("/healthz").json()["status"], "corpus not loaded")
        self.assertEqual(client.post("/query", json={"query": "anything at all"}).status_code, 503)


if __name__ == "__main__":
    unittest.main()
