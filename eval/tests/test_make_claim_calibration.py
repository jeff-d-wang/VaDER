import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eval.make_claim_calibration import Candidate, _pilot_pairs, select_pairs, write_final
from eval.score import Claim, SystemAnswer


class ClaimCalibrationTests(unittest.TestCase):
    def test_selection_round_robins_cases(self):
        cases = {key: {"case_id": key} for key in ("a", "b")}
        claim = Claim("fact", "PMC1", "body", 0, 4)
        answers = {
            "a": SystemAnswer("a", claims=[claim, claim]),
            "b": SystemAnswer("b", claims=[claim]),
        }
        selected = select_pairs(cases, answers, 3)
        self.assertEqual([(case["case_id"], number) for case, number, _ in selected],
                         [("a", 1), ("b", 1), ("a", 2)])

    def test_pilot_pair_parser_reads_exact_case_and_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pilot.md"
            path.write_text("## Pair 1: case_a claim 2\n\n## Pair 2: case_b claim 1\n")
            self.assertEqual(_pilot_pairs(path), {("case_a", 2), ("case_b", 1)})

    def test_final_worksheet_is_blind_and_manifest_binds_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            answers = root / "answers.jsonl"
            answers.write_text('{}\n')
            pilot = root / "pilot.md"
            pilot.write_text("pilot\n")
            out = root / "worksheet.md"
            manifest = root / "manifest.json"
            candidates = [
                Candidate("answers.jsonl", {"case_id": "case_a"}, 1,
                          Claim("ATM increases risk", "PMC1", "body", 0, 10)),
                Candidate("answers.jsonl", {"case_id": "case_b"}, 1,
                          Claim("BRCA1 increases risk", "PMC2", "body", 0, 10)),
            ]
            with patch("eval.make_claim_calibration._span",
                       side_effect=lambda claim, _: f"source text for {claim.cited_pmcid}"):
                write_final(
                    candidates, 2, 1, 7, out, manifest, [answers], pilot,
                    answers, root,
                )

            worksheet = out.read_text()
            data = json.loads(manifest.read_text())
            self.assertEqual(data["counts"], {"natural": 2, "stress": 1, "total": 3})
            self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), data["worksheet_sha256"])
            self.assertEqual(worksheet.count("## GCV1-"), 3)
            self.assertNotIn("case_a", worksheet)
            self.assertNotIn("natural", worksheet)
            stress = next(pair for pair in data["pairs"] if pair["stratum"] == "stress")
            self.assertNotEqual(stress["case_id"], stress["donor"]["case_id"])


if __name__ == "__main__":
    unittest.main()
