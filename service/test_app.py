"""
Tests for the Step 0c service. Builds a tiny synthetic corpus (manifest +
JATS-ish XML) in a temp dir per test via `create_app`, so these never touch
the real ../corpus and stay fast and hermetic. Run:

    python -m pytest test_app.py -v
    # or, no pytest available:
    python test_app.py
"""
from __future__ import annotations

import csv
import json
import sys
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


def run_tests():
    failures = []

    def check(name, cond, detail=""):
        if cond:
            print(f"  ok   {name}")
        else:
            print(f"  FAIL {name}  {detail}")
            failures.append(name)

    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)

        # --- healthz reports corpus size and config ---
        with _make_client(tmp / "a", max_scan=7, max_matches=3) as client:
            r = client.get("/healthz")
            check("healthz status 200", r.status_code == 200, r.text)
            body = r.json()
            check("healthz corpus_size == 4", body["corpus_size"] == 4, body)
            check("healthz reports config", body["config"]["max_scan"] == 7, body)

            # --- query returns a match with a source span ---
            r = client.post("/query", json={"query": "BRCA1 pathogenic variant breast cancer"})
            check("query status 200", r.status_code == 200, r.text)
            lines = [json.loads(l) for l in r.text.strip().split("\n")]
            matches = [l for l in lines if l["type"] == "match"]
            summary = [l for l in lines if l["type"] == "summary"]
            check("at least one match", len(matches) >= 1, lines)
            check("exactly one summary line, last", lines[-1]["type"] == "summary", lines)
            m = matches[0]
            check("match has pmcid", m["pmcid"] == "PMC1000001", m)
            check("match has char offsets", m["char_end"] > m["char_start"] >= 0, m)
            check("match text is truncated to <=500", len(m["text"]) <= 500, m)

            # --- no hit: unrelated query ---
            r = client.post("/query", json={"query": "zebrafish coral reef photosynthesis"})
            lines = [json.loads(l) for l in r.text.strip().split("\n")]
            check("not_found line present", any(l["type"] == "not_found" for l in lines), lines)
            check("not_found note text", [l for l in lines if l["type"] == "not_found"][0]["note"]
                  == "not found in this corpus")

            # --- candidate on manifest, xml missing on disk: no crash, just skipped ---
            r = client.post("/query", json={"query": "BRCA2 variant classification guidelines"})
            check("missing-xml candidate does not 500", r.status_code == 200, r.text)

            # --- max_matches cap ---
            r = client.post("/query", json={"query": "cohort genomics"})
            lines = [json.loads(l) for l in r.text.strip().split("\n")]
            matches = [l for l in lines if l["type"] == "match"]
            check("respects max_matches cap", len(matches) <= 3, matches)

            # --- validation: query too short ---
            r = client.post("/query", json={"query": "ab"})
            check("short query rejected (422)", r.status_code == 422, r.text)

            # --- request log: one JSONL line per attempted query, required fields present ---
            log_path = tmp / "a" / "logs" / "requests.jsonl"
            log_lines = [json.loads(l) for l in log_path.read_text().strip().split("\n")]
            # 4 successful /query calls logged; the 422 (query too short) never
            # reaches the handler, so it correctly does not produce a log line.
            check("one log line per attempted /query call", len(log_lines) == 4, len(log_lines))
            rec = log_lines[0]
            for field in ("query", "ttft_ms", "total_ms", "n_matches", "stopped_reason", "logged_at_utc"):
                check(f"log record has {field}", field in rec, rec)
            check("ttft_ms <= total_ms", all(r["ttft_ms"] <= r["total_ms"] + 0.01 for r in log_lines), log_lines)

        # --- empty corpus: /query is 503, healthz says so ---
        with tempfile.TemporaryDirectory() as empty_dir:
            empty = Path(empty_dir)
            (empty / "logs").mkdir()
            from service.app import create_app as _create_app
            app = _create_app(manifest_path=empty / "manifest.csv", xml_dir=empty / "xml",
                               log_path=empty / "logs" / "requests.jsonl")
            with TestClient(app) as client:
                r = client.get("/healthz")
                check("empty corpus healthz status field", r.json()["status"] == "corpus not loaded", r.json())
                r = client.post("/query", json={"query": "anything at all"})
                check("empty corpus query is 503", r.status_code == 503, r.text)

    if failures:
        print(f"\n{len(failures)} FAILED: {failures}")
        sys.exit(1)
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run_tests()
