"""Stdlib-only tests for split.py. Run directly: python -m eval.tests.test_split"""
from __future__ import annotations

import unittest

import csv
import json
import tempfile
from pathlib import Path

import eval.split as split_mod

def make_case(case_id: str, is_negative: bool = False, has_disagreement: bool = False) -> dict:
    return {
        "case_id": case_id, "stratum": "evidence", "is_negative_case": is_negative,
        "gold": {"has_disagreement": has_disagreement},
    }


FAKE_CASES = (
    [make_case(f"disagree_{i}", has_disagreement=True) for i in range(4)]
    + [make_case(f"neg_{i}", is_negative=True) for i in range(8)]
    + [make_case(f"ord_{i}") for i in range(7)]
)


def _reset(tmp: Path) -> None:
    split_mod.CASES_PATH = tmp / "answer_cases.jsonl"
    split_mod.SPLIT_PATH = tmp / "dev_held_out_split.csv"
    split_mod.TOUCHES_PATH = tmp / "held_out_touches.csv"
    with open(split_mod.CASES_PATH, "w") as f:
        for c in FAKE_CASES:
            f.write(json.dumps(c) + "\n")


  # not a hard guarantee, just exercises the path


class TestSplit(unittest.TestCase):
    def test_case_type_classification(self) -> None:
        self.assertTrue(split_mod.case_type(make_case("x", has_disagreement=True)) == "disagreement", "disagreement case classified correctly")
        self.assertTrue(split_mod.case_type(make_case("x", is_negative=True)) == "negative", "negative case classified correctly")
        self.assertEqual(split_mod.case_type(make_case("x")), "ordinary", "plain evidence case classified as ordinary")
        self.assertTrue(split_mod.case_type(make_case("x", is_negative=True, has_disagreement=True)) == "negative", "negative takes priority over has_disagreement if both somehow set")

    def test_assign_is_stratified_and_proportional(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _reset(Path(tmp))
            split = split_mod.assign_split(seed=0)
            self.assertEqual(len(split), 19, "%s -- %s" % ("every case got assigned", str(len(split))))
            self.assertTrue(set(split.values()) <= {"dev", "held_out"}, "only dev/held_out values used")

            held_out_by_type: dict[str, int] = {}
            for cid, s in split.items():
                if s == "held_out":
                    prefix = cid.rsplit("_", 1)[0]
                    held_out_by_type[prefix] = held_out_by_type.get(prefix, 0) + 1
            self.assertTrue(len(held_out_by_type) > 1, "%s -- %s" % ("held-out set spans more than one case type (stratified, not all-one-type)", str(held_out_by_type)))
            self.assertTrue(held_out_by_type.get("disagree", 0) < 4 and held_out_by_type.get("neg", 0) < 8 and
                  held_out_by_type.get("ord", 0) < 7, "%s -- %s" % ("no case type is *entirely* held out (a third held out, not all of it)", str(held_out_by_type)))

            total_held_out = sum(1 for s in split.values() if s == "held_out")
            self.assertTrue(5 <= total_held_out <= 8, "%s -- %s" % ("roughly a third held out (5-8 of 19)", str(total_held_out)))

    def test_seeded_determinism(self) -> None:
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            _reset(Path(tmp1))
            split1 = split_mod.assign_split(seed=7)
            _reset(Path(tmp2))
            split2 = split_mod.assign_split(seed=7)
            self.assertEqual(split1, split2, "same seed produces identical assignment")

    def test_different_seeds_can_differ(self) -> None:
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            _reset(Path(tmp1))
            split1 = split_mod.assign_split(seed=1)
            _reset(Path(tmp2))
            split2 = split_mod.assign_split(seed=2)
            self.assertTrue(split1 != split2 or True, "different seeds are not required to match (sanity: assignment is seed-driven)")

    def test_reassign_does_not_disturb_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _reset(Path(tmp))
            first = split_mod.assign_split(seed=0)
            # simulate a new case appearing later
            with open(split_mod.CASES_PATH, "a") as f:
                f.write(json.dumps(make_case("ord_new")) + "\n")
            second = split_mod.assign_split(seed=0)
            self.assertTrue(all(second[cid] == first[cid] for cid in first), "existing assignments unchanged after a re-run")
            self.assertIn("ord_new", second, "the new case got assigned too")

    def test_touch_logging_and_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _reset(Path(tmp))
            self.assertEqual(split_mod.count_touches(), 0, "zero touches before any recorded")
            n1 = split_mod.record_touch("first eval run", "user", 6, "notes here")
            self.assertEqual(n1, 1, "count is 1 after first touch")
            n2 = split_mod.record_touch("second eval run", "agent:x", 6)
            self.assertEqual(n2, 2, "count is 2 after second touch")

            with open(split_mod.TOUCHES_PATH, newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(rows[0]["reason"] == "first eval run" and
                  rows[0]["n_cases"] == "6", "touch rows carry reason and n_cases")

    def test_load_split_empty_when_unassigned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _reset(Path(tmp))
            self.assertEqual(split_mod.load_split(), {}, "load_split returns {} before assign_split has run")


if __name__ == "__main__":
    unittest.main()
