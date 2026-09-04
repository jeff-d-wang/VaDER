# Ingestion: Step 0b corpus pull

`pull_corpus.py` searches PMC via E-utilities for the cancer-genomics variant-disease net
described in `../docs/TASK_CONTRACT.md` Part 4, then downloads the matching full-text JATS XML
from the free `pmc-oa-opendata` S3 bucket. See the module docstring at the top of the script for
the full design (rate limiting, resumability, output layout).

## Status: corpus of record pulled (2026-08-30), validated against the real APIs

The Step 0b corpus is on disk: 7,863 PMC OA full-text articles, `corpus/`. Query, counts, and
composition are in `../docs/DECISION_LOG.md`, "Corpus snapshot v2". The MeSH/Title-Abstract query
tags and `medline[sb]` all work against the real `pmc` database, and the bucket metadata uses
`is_pmc_openaccess` (the `is_open_access` fallback was not needed).

History: the first pull (2026-08-29, `--target-n 4000`, default sort, bare-term query) was
discarded on review. Default esearch order gave a 98%-single-year slice, and bare terms matched
anywhere in full text including reference lists, so roughly half the hits were off-topic. The
script was then changed to (a) a MeSH/Title-Abstract-anchored query plus the MEDLINE subset,
(b) pull the whole matched ID set and take a seeded uniform-random sample, and (c) write a
per-file `sha256` into the manifest. See `../docs/DECISION_LOG.md`, the SUPERSEDED and "Corpus
re-pull" entries.

`test_pull_corpus.py` fakes NCBI E-utilities and the S3 bucket and drives the real script through
both: version selection, OA-status skip, missing-article skip, download-error handling,
resume-from-disk, esearch pagination, sample determinism, and the sha256 column. It stays the
regression check for any future script edit.

## What you need to do

1. **Get an NCBI API key** (optional but worth it for a multi-thousand-article pull): sign in at
   ncbi.nlm.nih.gov, account settings, "API Key Management." Raises the rate limit from 3 req/sec
   to 10 req/sec.
2. **Install dependencies:** `pip install -r requirements.txt`
3. **Smoke-test first, small:**
   ```
   python -m ingestion.pull_corpus --email you@actual-email.com --target-n 5
   ```
   Check the printed esearch match count is non-zero (a zero means a query tag is wrong for the
   `pmc` database), then that `corpus/xml/` has real JATS XML and `corpus/manifest.csv` looks
   sane, sha256 column included. This is the step that catches anything the real NCBI/S3 APIs do
   differently from what the script assumes.
4. **Run the real pull** once the smoke test looks right:
   ```
   python -m ingestion.pull_corpus --email you@actual-email.com --api-key YOUR_KEY --target-n 10000 --seed 0
   ```
   The default query anchors the gene and pathway terms (BRCA1/2, TP53, PALB2, ATM, CHEK2, DNA
   damage response, PARP inhibitor, HRD) to `[Title/Abstract]`, the disease side to
   `"Neoplasms"[MeSH]`, and the variant side to `"Mutation"[MeSH] OR "Genetic Variation"[MeSH] OR
   variant[Title/Abstract]`, plus `medline[sb]` and the OA filter. The script pulls every match
   (up to `--id-fetch-cap`, default 300k) and takes a uniform-random sample of size
   `target-n * 1.15`; `--seed` is recorded in `run_info.json`. Edit `DEFAULT_QUERY` at the top of
   the script, or pass `--query`, for a different net.
5. **Re-run the offline test suite** after any edit to the script, before trusting a new version
   at scale:
   ```
   python -m ingestion.test_pull_corpus
   ```
6. **When the real pull finishes**, log the exact query, the `--seed`, and the snapshot date/time
   from the printed `run_info.json` into `../docs/DECISION_LOG.md`. The script prints a
   ready-to-paste entry at the end. This is not optional: the corpus is a configuration input, and
   every later gold label and baseline number is corpus-specific (see `../docs/PROJECT_PLAN.md`,
   Step 0b).

## Output layout

```
corpus/
  xml/<PMCID>.xml       one file per article, latest OA version
  manifest.csv          one row per sampled PMCID: status ok/skipped/error, license,
                         title/journal/pubdate, byte count, sha256 of the XML
  run_info.json         the query, the sample seed and method, id-fetch counts,
                         snapshot timestamps, and ok/skipped/error counts
```

`corpus/xml/` is git-ignored (see `../.gitignore`); it's a few thousand XML files, not something
to commit. `corpus/manifest.csv` and `corpus/run_info.json` are tracked: they are the
reproducibility record. The manifest carries a per-file `sha256`, so a regenerated corpus can be
checked byte-for-byte against the record without the XML ever living in git.

## Deferred: citation-quality weighting

The corpus is not filtered or ranked by citation count or Relative Citation Ratio. The
MEDLINE-indexed subset (`medline[sb]` in the query) is the only venue-quality gate. Adding an NIH
iCite lookup pass (annotate the manifest with `citation_count` / `rcr` / `nih_percentile`, then
optionally filter) is a well-scoped later addition, to be made only if M4 error analysis shows
source quality is hurting results. Full rationale and the step-by-step plan are in
`../docs/DECISION_LOG.md`, "Defer citation-quality weighting of the corpus."
