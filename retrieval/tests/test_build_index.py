import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from retrieval import build_index


class TestIndexBuild(unittest.TestCase):
    def test_verified_build_and_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'xml').mkdir()
            xml = root / 'xml/PMC1.xml'
            xml.write_text('<article><body><p>BRCA1 variants were studied in this cancer cohort.</p></body></article>')
            with (root / 'manifest.csv').open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['pmcid','status','sha256'])
                writer.writeheader()
                writer.writerow({'pmcid':'PMC1','status':'ok','sha256':hashlib.sha256(xml.read_bytes()).hexdigest()})
            exclusions = root / 'excluded.csv'
            exclusions.write_text('pmcid\n')
            out = root / 'index.pkl'
            argv = ['build_index', '--corpus', str(root), '--exclusions', str(exclusions), '--out', str(out)]
            with patch.object(sys, 'argv', argv), patch.object(build_index, 'append_run') as register:
                build_index.main()
                register.assert_called_once()
                self.assertEqual(json.loads(out.with_suffix('.meta.json').read_text())['n_chunks'], 1)
                xml.write_text('<article/>')
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    build_index.main()
