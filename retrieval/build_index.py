"""Build a reproducible evaluation index with explicit corpus exclusions."""
import argparse
import csv
from pathlib import Path

from common.run_meta import append_run, file_hash
from retrieval.bm25 import build_index
from retrieval.chunker import paragraph_chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, default=Path('corpus'))
    parser.add_argument('--exclusions', type=Path, default=Path('eval/held_out/held_out_pmcids.csv'))
    parser.add_argument('--paragraphs', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with (args.corpus / 'manifest.csv').open(newline='') as f:
        rows = [r for r in csv.DictReader(f) if r['status'] == 'ok']
    with args.exclusions.open(newline='') as f:
        excluded = {r['pmcid'] for r in csv.DictReader(f)}
    for row in rows:
        if row['pmcid'] in excluded:
            continue
        path = args.corpus / 'xml' / (row['pmcid'] + '.xml')
        if file_hash(path) != row['sha256']:
            raise ValueError(f"source hash mismatch: {path}")
    index = build_index(args.corpus / 'xml', [r['pmcid'] for r in rows],
                        chunker=paragraph_chunks if args.paragraphs else None,
                        excluded_pmcids=excluded)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise FileExistsError('Choose a new index path; existing artifacts are not overwritten')
    index.save(args.out)
    # Indexes are rebuildable caches. Persist their identity separately from their large bytes.
    import json
    meta = args.out.with_suffix('.meta.json')
    meta.write_text(json.dumps({'index_sha256': file_hash(args.out), 'n_chunks': index.n_docs,
                               'paragraphs': args.paragraphs}, indent=2) + '\n')
    append_run(eval_set='index_build', run_config={'paragraphs': args.paragraphs},
               results_path=str(meta), metrics={'n_chunks': index.n_docs},
               input_paths={'manifest': args.corpus / 'manifest.csv', 'exclusions': args.exclusions})


if __name__ == '__main__':
    main()
