"""
Offline unit test for pull_corpus.py. This sandbox's network is locked down
(no route to eutils.ncbi.nlm.nih.gov, s3.amazonaws.com, or even pypi.org), so
this fakes both NCBI E-utilities and the S3 bucket in-memory and drives the
real script end to end against them. It's here to catch logic bugs (paging
math, S3 key construction, CSV/json shape) before handing the script off,
not as a substitute for the user's own smoke test against the real APIs.
"""
import json
import sys
import types
from pathlib import Path
from unittest import mock

# ---- Fake boto3 so `import boto3` in pull_corpus.py succeeds ----

class FakeBody:
    def __init__(self, data: bytes):
        self._data = data
    def read(self):
        return self._data

class FakeS3Client:
    """In-memory stand-in for the pmc-oa-opendata bucket."""
    def __init__(self, objects: dict, common_prefixes: dict):
        self.objects = objects            # key -> bytes
        self.common_prefixes = common_prefixes  # prefix -> [full prefixes]

    def list_objects_v2(self, Bucket, Prefix, Delimiter):
        prefixes = self.common_prefixes.get(Prefix, [])
        return {"CommonPrefixes": [{"Prefix": p} for p in prefixes]}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(f"NoSuchKey: {Key}")
        return {"Body": FakeBody(self.objects[Key])}


FAKE_BUCKET_OBJECTS = {}
FAKE_BUCKET_PREFIXES = {}

def _make_article(pmcid, version, is_oa=True, license_code="CC0", xml_ok=True):
    prefix = f"{pmcid}."
    full_prefix = f"{pmcid}.{version}/"
    FAKE_BUCKET_PREFIXES.setdefault(prefix, [])
    FAKE_BUCKET_PREFIXES[prefix].append(full_prefix)
    key_prefix = f"{pmcid}.{version}/{pmcid}.{version}"
    FAKE_BUCKET_OBJECTS[f"{key_prefix}.json"] = json.dumps({
        "pmcid": pmcid, "version": version, "is_pmc_openaccess": is_oa,
        "license_code": license_code,
    }).encode()
    if xml_ok:
        FAKE_BUCKET_OBJECTS[f"{key_prefix}.xml"] = (
            f"<article><body><p>Fake full text for {pmcid} v{version}. "
            "BRCA1 c.68_69delAG is associated with hereditary breast and "
            "ovarian cancer.</p></body></article>"
        ).encode()
    # else: leave the .xml key absent -> triggers the error path


# PMC1000001: healthy, single version
_make_article("PMC1000001", 1)
# PMC1000002: two versions, should pick version 2
_make_article("PMC1000002", 1)
_make_article("PMC1000002", 2)
# PMC1000003: present but marked non-OA in bucket metadata -> skipped
_make_article("PMC1000003", 1, is_oa=False)
# PMC1000004: json exists but xml object missing -> error path
_make_article("PMC1000004", 1, xml_ok=False)
# PMC1000005: not in the bucket at all (no prefixes registered) -> skipped, "not present"

FAKE_PMCIDS = ["PMC1000001", "PMC1000002", "PMC1000003", "PMC1000004", "PMC1000005"]

# A larger pool of healthy articles, only used by the sampling test below: it
# needs more matches than the target so the uniform-random sample actually
# selects a strict subset.
FAKE_PMCIDS_LARGE = [f"PMC200{n:04d}" for n in range(40)]
for _pmcid in FAKE_PMCIDS_LARGE:
    _make_article(_pmcid, 1)

fake_botocore = types.ModuleType("botocore")
fake_botocore.UNSIGNED = "UNSIGNED_SENTINEL"
fake_botocore_config = types.ModuleType("botocore.config")
class FakeBotoConfig:
    def __init__(self, **kw):
        self.kw = kw
fake_botocore_config.Config = FakeBotoConfig
fake_boto3 = types.ModuleType("boto3")
fake_boto3.client = lambda *a, **kw: FakeS3Client(FAKE_BUCKET_OBJECTS, FAKE_BUCKET_PREFIXES)

sys.modules["boto3"] = fake_boto3
sys.modules["botocore"] = fake_botocore
sys.modules["botocore.config"] = fake_botocore_config

import ingestion.pull_corpus as pull_corpus  # noqa: E402  (must import after the fake boto3 is registered)


# ---- Fake NCBI E-utilities responses ----

class FakeResp:
    def __init__(self, payload):
        self._payload = payload
    def json(self):
        return self._payload
    def raise_for_status(self):
        pass

def _make_fake_eutils_get(id_pool):
    """Build a fake EutilsClient.get bound to a given list of PMCIDs."""
    def fake_eutils_get(self, endpoint, params, retries=4):
        if endpoint == "esearch.fcgi":
            if params.get("retmax") == 0:
                return FakeResp({"esearchresult": {"count": str(len(id_pool)),
                                                    "webenv": "FAKE_WEBENV", "querykey": "1"}})
            retstart = params.get("retstart", 0)
            retmax = params["retmax"]
            ids = [p.replace("PMC", "") for p in id_pool[retstart:retstart + retmax]]
            return FakeResp({"esearchresult": {"idlist": ids}})
        elif endpoint == "esummary.fcgi":
            ids = params["id"].split(",")
            result = {"uids": ids}
            for i in ids:
                result[i] = {"title": f"Title for PMC{i}", "fulljournalname": "Fake J. Genomics",
                             "pubdate": "2026"}
            return FakeResp({"result": result})
        raise AssertionError(f"unexpected endpoint {endpoint}")
    return fake_eutils_get


fake_eutils_get = _make_fake_eutils_get(FAKE_PMCIDS)


def run_test():
    import tempfile
    with mock.patch.object(pull_corpus.EutilsClient, "get", fake_eutils_get):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "corpus"
            sys.argv = [
                "pull_corpus.py", "--email", "test@example.com",
                "--target-n", "5", "--out-dir", str(out_dir), "--workers", "2",
            ]
            pull_corpus.main()

            manifest = (out_dir / "manifest.csv").read_text()
            run_info = json.loads((out_dir / "run_info.json").read_text())
            xml_files = sorted(p.name for p in (out_dir / "xml").glob("*.xml"))

            print("\n=== manifest.csv ===")
            print(manifest)
            print("=== run_info.json ===")
            print(json.dumps(run_info, indent=2))
            print("=== xml files written ===")
            print(xml_files)

            # Assertions
            assert run_info["ok"] == 2, f"expected 2 ok (PMC1000001, PMC1000002), got {run_info['ok']}"
            assert run_info["skipped"] == 2, f"expected 2 skipped (non-OA + not-in-bucket), got {run_info['skipped']}"
            assert run_info["error"] == 1, f"expected 1 error (missing xml object), got {run_info['error']}"
            assert "PMC1000001.xml" in xml_files
            assert "PMC1000002.xml" in xml_files, "should have picked version 2, the higher one"
            assert (out_dir / "xml" / "PMC1000002.xml").read_text().count("v2") == 1, \
                "content should be from version 2, not version 1 -- version selection bug"
            assert "PMC1000003.xml" not in xml_files
            assert "PMC1000004.xml" not in xml_files
            assert "PMC1000005.xml" not in xml_files

            # sha256 column: present in the header, correct for ok rows, empty otherwise.
            import csv as _csv
            import hashlib as _hashlib
            rows = list(_csv.DictReader((out_dir / "manifest.csv").open()))
            assert "sha256" in rows[0], "manifest is missing the sha256 column"
            for r in rows:
                if r["status"] == "ok":
                    disk = (out_dir / "xml" / f"{r['pmcid']}.xml").read_bytes()
                    want = _hashlib.sha256(disk).hexdigest()
                    assert r["sha256"] == want, f"sha256 mismatch for {r['pmcid']}"
                    assert len(r["sha256"]) == 64
                else:
                    assert r["sha256"] == "", f"{r['pmcid']} is {r['status']} but has a sha256"

            # run_info records the sampling method and seed.
            assert run_info["sampling"] == "uniform_random"
            assert run_info["seed"] == 0
            assert run_info["esearch_ids_truncated"] is False

            # Resume behavior: run again, PMC1000001/2 should be picked up from disk
            # without re-hitting the fake S3 (find_latest_version would raise if called
            # with a prefix not in FAKE_BUCKET_PREFIXES for a wiped registry -- instead
            # we just check the file still there and status still ok on a second pass).
            sys.argv = [
                "pull_corpus.py", "--email", "test@example.com",
                "--target-n", "5", "--out-dir", str(out_dir), "--workers", "2",
            ]
            pull_corpus.main()
            manifest2 = (out_dir / "manifest.csv").read_text()
            assert "already on disk (resumed)" in manifest2, "resume path did not trigger on second run"
            # sha256 still populated on the resumed (read-from-disk) path.
            import csv as _csv2
            for r in _csv2.DictReader((out_dir / "manifest.csv").open()):
                if r["status"] == "ok":
                    assert len(r["sha256"]) == 64, f"resumed row {r['pmcid']} lost its sha256"

    print("\nrun_test: ALL ASSERTIONS PASSED")


def _attempted_pmcids(out_dir):
    import csv as _csv
    return {r["pmcid"] for r in _csv.DictReader((out_dir / "manifest.csv").open())}


def run_sampling_test():
    """The PMCID sample must be a seeded uniform draw: same seed -> same subset,
    different seed -> (almost surely) a different subset, and the draw is a
    strict subset when there are more matches than the target."""
    import tempfile
    fake = _make_fake_eutils_get(FAKE_PMCIDS_LARGE)  # 40 healthy articles
    with mock.patch.object(pull_corpus.EutilsClient, "get", fake):
        with tempfile.TemporaryDirectory() as tmp:
            def pull(seed, sub):
                out_dir = Path(tmp) / sub
                sys.argv = [
                    "pull_corpus.py", "--email", "test@example.com", "--target-n", "10",
                    "--seed", str(seed), "--out-dir", str(out_dir), "--workers", "2",
                    "--skip-metadata",
                ]
                pull_corpus.main()
                return _attempted_pmcids(out_dir)

            a = pull(1, "a")
            b = pull(1, "b")
            c = pull(2, "c")

            # int(10 * 1.15) == 11 sampled from 40.
            assert len(a) == 11, f"expected 11 sampled, got {len(a)}"
            assert a <= set(FAKE_PMCIDS_LARGE), "sample drew IDs that were not in the result set"
            assert a == b, "same seed produced a different sample (not reproducible)"
            assert a != c, "different seed produced the identical sample (seed not wired through)"

    print("run_sampling_test: ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    run_test()
    run_sampling_test()
    print("\nALL TESTS PASSED")
