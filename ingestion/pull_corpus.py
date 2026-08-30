#!/usr/bin/env python3
"""
Step 0b corpus pull: cancer-genomics variant-disease evidence, PMC Open Access.

Two phases:
  1. Search  : NCBI E-utilities (esearch, paged via history) to pull the FULL
               set of PMCIDs matching the topic query (up to a safety cap),
               then take a seeded uniform-random sample of the target size.
               Random, not "most recently added" order and not relevance
               rank, so the corpus has no date skew and no dependence on an
               undocumented ranker. IDs are sorted before sampling, so the
               same (query, seed, snapshot) reproduces the same sample
               regardless of the order NCBI returns them in.
  2. Fetch   : for each sampled PMCID, find its latest version in the free
               `pmc-oa-opendata` S3 bucket (us-east-1, anonymous/unsigned
               requests, no AWS account needed), pull its JSON metadata to
               confirm OA status + license, and download the full-text JATS
               XML.

Every run writes:
  <out-dir>/xml/<PMCID>.xml             one file per article
  <out-dir>/manifest.csv                one row per PMCID attempted, with
                                         status (ok/skipped/error) and a
                                         sha256 of the downloaded XML
  <out-dir>/run_info.json               the exact query, the sample seed,
                                         snapshot timestamps, and counts, so
                                         the pull is reproducible and loggable

Rate limits (NCBI E-utilities): 3 req/sec without an API key, 10/sec with
one. This script defaults to a conservative pace under whichever applies.
S3 GETs are not NCBI-rate-limited but are still paced/parallelized modestly
to be a reasonable citizen of a public anonymous bucket.

Usage:
    pip install requests boto3
    python pull_corpus.py --email you@example.com --target-n 5              # smoke test first
    python pull_corpus.py --email you@example.com --target-n 10000 --seed 0 # real pull

See the printed summary at the end for what to log in DECISION_LOG.md.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

try:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config as BotoConfig
except ImportError:
    print("Missing dependency: boto3. Install with `pip install boto3`.", file=sys.stderr)
    raise

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
S3_BUCKET = "pmc-oa-opendata"
S3_REGION = "us-east-1"

# Editable: the topic net for cancer genomics variant-disease evidence, per
# TASK_CONTRACT.md Part 4 (germline + somatic variants, DNA damage response /
# PARP pathway as the initial net). Adjust freely: this is a starting point,
# not a fixed decision; whatever you actually run gets recorded in
# run_info.json regardless of what this default says.
#
# Design notes (see DECISION_LOG.md, "Corpus re-pull ..."). The first pull used
# bare terms with no field tags, so terms matched anywhere in full text,
# including reference lists, and roughly half the hits were off-topic. This
# version anchors precision three ways:
#   - gene / pathway terms are restricted to [Title/Abstract]. A paper that is
#     actually about BRCA1 variants says so in its title or abstract.
#   - the disease side is the MeSH term "Neoplasms"[MeSH], not a bag of free-text
#     synonyms.
#   - the variant side is MeSH ("Mutation", "Genetic Variation") OR variant in
#     the title/abstract.
# Plus medline[sb] (MEDLINE-indexed subset: a venue-quality floor that drops
# marginal and predatory journals) and the OA filter. Verify medline[sb] and the
# field tags behave as expected in the --target-n 5 smoke test: if esearch
# reports 0 matches, a tag is wrong for the `pmc` database.
DEFAULT_QUERY = (
    '('
    'BRCA1[Title/Abstract] OR BRCA2[Title/Abstract] OR TP53[Title/Abstract] '
    'OR PALB2[Title/Abstract] OR ATM[Title/Abstract] OR CHEK2[Title/Abstract] '
    'OR "DNA damage response"[Title/Abstract] OR "PARP inhibitor"[Title/Abstract] '
    'OR "homologous recombination deficiency"[Title/Abstract]'
    ') AND ('
    '"Mutation"[MeSH] OR "Genetic Variation"[MeSH] OR variant[Title/Abstract]'
    ') AND "Neoplasms"[MeSH] '
    'AND medline[sb] AND "open access"[filter]'
)


# --------------------------------------------------------------------------
# NCBI E-utilities: rate-limited session
# --------------------------------------------------------------------------

class EutilsClient:
    def __init__(self, tool: str, email: str, api_key: str | None):
        self.tool = tool
        self.email = email
        self.api_key = api_key
        self.session = requests.Session()
        # Stay a little under the documented limit rather than riding the edge.
        self.min_interval = 1.0 / 9.0 if api_key else 1.0 / 2.8
        self._last_call = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.monotonic()

    def _params(self, extra: dict) -> dict:
        p = {"tool": self.tool, "email": self.email, **extra}
        if self.api_key:
            p["api_key"] = self.api_key
        return p

    def get(self, endpoint: str, params: dict, retries: int = 4) -> requests.Response:
        url = f"{EUTILS_BASE}/{endpoint}"
        last_exc = None
        for attempt in range(retries):
            self._throttle()
            try:
                resp = self.session.get(url, params=self._params(params), timeout=30)
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"eutils request failed after {retries} retries: {last_exc}")


def esearch_all_pmcids(client: EutilsClient, query: str, fetch_cap: int,
                        page_size: int = 10000) -> tuple[list[str], int, bool]:
    """Pull every matching PMCID, up to fetch_cap, in NCBI's own order.

    Returns (pmcids, total_count_available, truncated). `truncated` is True when
    the query has more matches than fetch_cap, so the returned list is a prefix
    in NCBI's default order rather than the whole result set; the caller should
    warn, because sampling from a prefix reintroduces ordering bias. page_size
    is capped at 10000 by esearch.
    """
    resp = client.get("esearch.fcgi", {
        "db": "pmc", "term": query, "retmax": 0, "usehistory": "y", "retmode": "json",
    })
    data = resp.json()["esearchresult"]
    total = int(data["count"])
    webenv, query_key = data["webenv"], data["querykey"]

    want = min(fetch_cap, total)
    pmcids: list[str] = []
    retstart = 0
    while retstart < want:
        resp = client.get("esearch.fcgi", {
            "db": "pmc", "retmax": min(page_size, want - retstart), "retstart": retstart,
            "usehistory": "y", "WebEnv": webenv, "query_key": query_key, "retmode": "json",
        })
        ids = resp.json()["esearchresult"]["idlist"]
        if not ids:
            break
        pmcids.extend(f"PMC{i}" for i in ids)
        retstart += len(ids)
    return pmcids, total, total > fetch_cap


def esummary_metadata(client: EutilsClient, pmcids: list[str], batch_size: int = 200) -> dict:
    """Best-effort title/journal/pubdate per PMCID, via esummary. Non-fatal on failure."""
    out: dict[str, dict] = {}
    for i in range(0, len(pmcids), batch_size):
        batch = pmcids[i:i + batch_size]
        ids = ",".join(p.replace("PMC", "") for p in batch)
        try:
            resp = client.get("esummary.fcgi", {"db": "pmc", "id": ids, "retmode": "json"})
            result = resp.json().get("result", {})
            for uid in result.get("uids", []):
                doc = result[uid]
                out[f"PMC{uid}"] = {
                    "title": doc.get("title", ""),
                    "journal": doc.get("fulljournalname", ""),
                    "pubdate": doc.get("pubdate", ""),
                }
        except Exception as exc:  # noqa: BLE001 (metadata is a nice-to-have, never fatal)
            print(f"  [warn] esummary batch starting at {i} failed: {exc}", file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# S3: anonymous access to the OA bucket
# --------------------------------------------------------------------------

def make_s3_client():
    return boto3.client("s3", region_name=S3_REGION, config=BotoConfig(signature_version=UNSIGNED))


def find_latest_version(s3, pmcid: str) -> int | None:
    resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=f"{pmcid}.", Delimiter="/")
    prefixes = resp.get("CommonPrefixes", [])
    versions = []
    for p in prefixes:
        # e.g. "PMC8123456.1/" -> 1
        name = p["Prefix"].rstrip("/")
        suffix = name.rsplit(".", 1)[-1]
        if suffix.isdigit():
            versions.append(int(suffix))
    return max(versions) if versions else None


@dataclass
class FetchResult:
    pmcid: str
    version: int | None = None
    status: str = "error"  # ok | skipped | error
    note: str = ""
    license_code: str = ""
    is_open_access: bool | None = None
    xml_bytes: int = 0
    sha256: str = ""  # hex digest of the XML on disk; "" for skipped/error rows


def fetch_one(s3, pmcid: str, out_dir: Path) -> FetchResult:
    xml_path = out_dir / "xml" / f"{pmcid}.xml"
    if xml_path.exists() and xml_path.stat().st_size > 0:
        return FetchResult(pmcid=pmcid, status="ok", note="already on disk (resumed)",
                            xml_bytes=xml_path.stat().st_size,
                            sha256=hashlib.sha256(xml_path.read_bytes()).hexdigest())

    version = find_latest_version(s3, pmcid)
    if version is None:
        return FetchResult(pmcid=pmcid, status="skipped", note="not present in OA bucket")

    key_prefix = f"{pmcid}.{version}/{pmcid}.{version}"
    try:
        meta_obj = s3.get_object(Bucket=S3_BUCKET, Key=f"{key_prefix}.json")
        meta = json.loads(meta_obj["Body"].read())
    except Exception as exc:  # noqa: BLE001
        return FetchResult(pmcid=pmcid, version=version, status="error",
                            note=f"metadata fetch failed: {exc}")

    is_oa = bool(meta.get("is_pmc_openaccess", meta.get("is_open_access", True)))
    license_code = meta.get("license_code", meta.get("license", ""))
    if not is_oa:
        return FetchResult(pmcid=pmcid, version=version, status="skipped",
                            note="bucket metadata marks this version non-OA",
                            license_code=license_code, is_open_access=False)

    try:
        xml_obj = s3.get_object(Bucket=S3_BUCKET, Key=f"{key_prefix}.xml")
        xml_bytes = xml_obj["Body"].read()
    except Exception as exc:  # noqa: BLE001
        return FetchResult(pmcid=pmcid, version=version, status="error",
                            note=f"xml fetch failed: {exc}")

    # Light sanity check: does this parse as XML at all? Don't reject on
    # failure, just note it, so a malformed article doesn't silently look
    # identical to a healthy one in the manifest.
    note = ""
    try:
        ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        note = f"warning: xml did not parse cleanly ({exc})"

    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_bytes(xml_bytes)
    return FetchResult(pmcid=pmcid, version=version, status="ok", note=note,
                        license_code=license_code, is_open_access=True, xml_bytes=len(xml_bytes),
                        sha256=hashlib.sha256(xml_bytes).hexdigest())


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", default=DEFAULT_QUERY, help="PMC esearch query (default: cancer-genomics variant net)")
    ap.add_argument("--target-n", type=int, default=10000, help="Target number of articles to attempt (default 10000)")
    ap.add_argument("--overfetch-factor", type=float, default=1.15,
                     help="Sample this many extra PMCIDs to absorb skips (default 1.15)")
    ap.add_argument("--seed", type=int, default=0,
                     help="RNG seed for the uniform-random PMCID sample. Recorded in run_info.json (default 0)")
    ap.add_argument("--id-fetch-cap", type=int, default=300000,
                     help="Max PMCIDs to pull from esearch before sampling. If the query has more "
                          "matches than this, the sample is drawn from a truncated prefix and the "
                          "run is flagged (default 300000)")
    ap.add_argument("--out-dir", default="./corpus", help="Output directory (default ./corpus)")
    ap.add_argument("--tool", default="cancer-genomics-rag-pull", help="NCBI 'tool' parameter")
    ap.add_argument("--email", required=True, help="NCBI 'email' parameter, required by E-utilities")
    ap.add_argument("--api-key", default=None, help="NCBI API key (raises rate limit 3/s -> 10/s). Also reads NCBI_API_KEY env var.")
    ap.add_argument("--workers", type=int, default=8, help="Parallel S3 fetch workers (default 8)")
    ap.add_argument("--skip-metadata", action="store_true", help="Skip the esummary title/journal/pubdate pass")
    args = ap.parse_args()

    import os
    api_key = args.api_key or os.environ.get("NCBI_API_KEY")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)

    print(f"[1/3] Searching PMC (query below), target {args.target_n} articles...")
    print(f"      {args.query}")
    eutils = EutilsClient(tool=args.tool, email=args.email, api_key=api_key)
    all_pmcids, total_available, truncated = esearch_all_pmcids(eutils, args.query, args.id_fetch_cap)
    if truncated:
        print(f"      [warn] esearch reports {total_available} matches, above the id-fetch-cap of "
              f"{args.id_fetch_cap}. Sampling from the first {len(all_pmcids)} in NCBI's default "
              f"order, which is NOT uniform. Raise --id-fetch-cap to sample the whole result set.")

    # Uniform-random sample. Sort first so the sample depends only on
    # (query, seed, snapshot), not on the order NCBI happened to return IDs in.
    all_pmcids = sorted(all_pmcids)
    sample_n = min(int(args.target_n * args.overfetch_factor), len(all_pmcids))
    pmcids = random.Random(args.seed).sample(all_pmcids, sample_n)
    print(f"      esearch reports {total_available} total matches; fetched {len(all_pmcids)} PMCIDs; "
          f"randomly sampled {len(pmcids)} to attempt (seed {args.seed}).")

    metadata = {}
    if not args.skip_metadata:
        print("[2/3] Fetching title/journal/pubdate via esummary (best-effort)...")
        metadata = esummary_metadata(eutils, pmcids)

    print(f"[3/3] Downloading full-text XML from s3://{S3_BUCKET}/ with {args.workers} parallel workers...")
    manifest_path = out_dir / "manifest.csv"
    fieldnames = ["pmcid", "version", "status", "note", "license_code", "is_open_access",
                  "xml_bytes", "sha256", "title", "journal", "pubdate", "retrieved_at_utc"]

    counts = {"ok": 0, "skipped": 0, "error": 0}
    # One S3 client per worker thread (boto3 clients aren't guaranteed thread-safe to share).
    thread_local_clients: dict[int, object] = {}

    def get_client():
        import threading
        tid = threading.get_ident()
        if tid not in thread_local_clients:
            thread_local_clients[tid] = make_s3_client()
        return thread_local_clients[tid]

    def worker(pmcid: str) -> FetchResult:
        return fetch_one(get_client(), pmcid, out_dir)

    results: list[FetchResult] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, res in enumerate(pool.map(worker, pmcids), 1):
            results.append(res)
            counts[res.status] += 1
            if i % 100 == 0 or i == len(pmcids):
                print(f"      {i}/{len(pmcids)} attempted, ok={counts['ok']} skipped={counts['skipped']} error={counts['error']}")

    now = datetime.now(timezone.utc).isoformat()
    with open(manifest_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for res in results:
            meta = metadata.get(res.pmcid, {})
            writer.writerow({
                "pmcid": res.pmcid, "version": res.version, "status": res.status, "note": res.note,
                "license_code": res.license_code, "is_open_access": res.is_open_access,
                "xml_bytes": res.xml_bytes, "sha256": res.sha256, "title": meta.get("title", ""),
                "journal": meta.get("journal", ""), "pubdate": meta.get("pubdate", ""),
                "retrieved_at_utc": now,
            })

    finished = datetime.now(timezone.utc)
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    run_info = {
        "query": args.query,
        "target_n": args.target_n,
        "sampling": "uniform_random",
        "seed": args.seed,
        "id_fetch_cap": args.id_fetch_cap,
        "esearch_total_available": total_available,
        "esearch_ids_fetched": len(all_pmcids),
        "esearch_ids_truncated": truncated,
        "pmcids_sampled": len(pmcids),
        "ok": counts["ok"], "skipped": counts["skipped"], "error": counts["error"],
        "snapshot_started_utc": started.isoformat(),
        "snapshot_finished_utc": finished.isoformat(),
        "s3_bucket": S3_BUCKET,
        "script_sha256_prefix": script_hash,
    }
    (out_dir / "run_info.json").write_text(json.dumps(run_info, indent=2))

    print("\n--- Done ---")
    print(json.dumps(run_info, indent=2))
    print(f"\nXML files: {out_dir / 'xml'}")
    print(f"Manifest:  {manifest_path}")
    print(f"Run info:  {out_dir / 'run_info.json'}")
    print("\nSuggested DECISION_LOG.md entry (fill in the module/date):")
    print(f"""
## Design decision: Corpus snapshot, cancer genomics, Step 0b pull

- **Date / module:** Step 0b ({started.date().isoformat()})
- **Decision:** Pulled {counts['ok']} PMC OA full-text articles.
- **Query:** `{args.query}`
- **Method:** esearch -> {total_available} total matches; fetched {len(all_pmcids)} PMCIDs
  (truncated={truncated}); uniform-random sample, seed {args.seed}, of {len(pmcids)} PMCIDs
  attempted; {counts['ok']} downloaded ok, {counts['skipped']} skipped (not in OA bucket / not OA),
  {counts['error']} errored. Snapshot window {started.isoformat()} to {finished.isoformat()}.
  Script sha256 prefix {script_hash}.
- **Reversibility:** Re-running with the same query and seed but a later snapshot date will not
  reproduce this exact set (PMC keeps indexing new articles, which shifts the sample). The
  manifest's per-file sha256 column is the byte-level record. Log the query, seed, and date
  here, not just in run_info.json, since this is the corpus every later gold label depends on.
""")


if __name__ == "__main__":
    main()
