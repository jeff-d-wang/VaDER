# VaDER

Variant-Disease Evidence Retriever: cancer-genomics literature retrieval with exact source-span
citations. The current service returns BM25-ranked evidence from a named PMC OA snapshot.
Opt-in synthesis is available through `/answer`; the researcher-facing viewer remains planned.

This project studies whether an AI system can provide useful, inspectable evidence under measured
quality, latency and cost constraints. [Current status](docs/CURRENT_STATUS.md),
[active plan](docs/PROJECT_PLAN.md), [task contract](docs/TASK_CONTRACT.md), and
[architecture](docs/ARCHITECTURE.md) describe what exists and what remains.

## Run locally

Use Python 3.13 in the `vader_env` conda environment:

```sh
conda env create -f environment.yml
conda activate vader_env
# If the environment already exists:
python -m pip install -r requirements.txt
python -m unittest discover
uvicorn service.app:app --host 127.0.0.1 --port 8000
```

Tests build synthetic XML fixtures and mock provider calls. They need no API keys, downloaded
corpus or network access after dependencies are installed. The service needs the local XML corpus;
without it `/healthz` returns 503. See [ingestion](ingestion/README.md) for downloading data. A
latest-version pull is not a byte-exact restore of the recorded snapshot. Preserve current XML.

```sh
curl -N http://127.0.0.1:8000/query -H 'Content-Type: application/json' \
  -d '{"query":"BRCA1 variant breast cancer"}'
python -m retrieval.build_index --out eval/runs/index-new.pkl
python -m eval.score_retrieval --cases eval/data/releases/retrieval-reviewed-20260909.jsonl \
  --index eval/runs/index-new.pkl --out eval/runs/retrieval-new.json
```

The reviewed subset is a diagnostic sample, not a representative performance claim. Rejected
cases cannot be scored. Use `--exploratory` explicitly for unreviewed datasets; those outputs are
not release evidence. Baseline model calls require `GROQ_API_KEY` and consume provider quota.
Read the plan's experiment rules before running measured comparisons.

To enable synthesis locally, set `VADER_GENERATION_ENABLED=1` and `GROQ_API_KEY` before
starting the service, then POST the same query JSON to `/answer`. This returns one validated
JSON response with claims and evidence. It consumes provider quota. See [serving limits and
error codes](service/README.md#runtime-synthesis). No live synthesis quality has been validated.

## Layout

| Path | Role |
|---|---|
| `common/` | Source text/provenance, tracing and run artifacts |
| `retrieval/` | Chunking, BM25, index build and IR metrics |
| `service/` | HTTP retrieval, bounded synthesis and retrieval load testing |
| `eval/` | Baselines, judges, cases, validation and offline candidate-building CLIs |
| `eval/artifacts/` | Preserved run outputs and completed human review evidence |
| `ingestion/`, `corpus/` | Download pipeline, source manifest and local XML |
| `docs/` | Current public plan/status, decisions and historical results |

[RESULTS.md](docs/RESULTS.md) preserves historical measurements and their caveats; it is not a
claim that current code reproduces every old number. Historical runs include defective-label,
stale-index and attribution problems. New run bundles preserve the actual outputs and input
fingerprints. No headline quality lift is advertised until the accepted baseline is rerun.

The current service is for local research. It is not ready for unauthenticated public deployment.
