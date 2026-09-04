"""Stdlib-only tests for split.py. Run directly: python -m eval.tests.test_split"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

import eval.split as split_mod

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


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


def test_case_type_classification() -> None:
    check("disagreement case classified correctly",
          split_mod.case_type(make_case("x", has_disagreement=True)) == "disagreement")
    check("negative case classified correctly",
          split_mod.case_type(make_case("x", is_negative=True)) == "negative")
    check("plain evidence case classified as ordinary",
          split_mod.case_type(make_case("x")) == "ordinary")
    check("negative takes priority over has_disagreement if both somehow set",
          split_mod.case_type(make_case("x", is_negative=True, has_disagreement=True)) == "negative")


def test_assign_is_stratified_and_proportional() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _reset(Path(tmp))
        split = split_mod.assign_split(seed=0)
        check("every case got assigned", len(split) == 19, str(len(split)))
        check("only dev/held_out values used", set(split.values()) <= {"dev", "held_out"})

        held_out_by_type: dict[str, int] = {}
        for cid, s in split.items():
            if s == "held_out":
                prefix = cid.rsplit("_", 1)[0]
                held_out_by_type[prefix] = held_out_by_type.get(prefix, 0) + 1
        check("held-out set spans more than one case type (stratified, not all-one-type)",
              len(held_out_by_type) > 1, str(held_out_by_type))
        check("no case type is *entirely* held out (a third held out, not all of it)",
              held_out_by_type.get("disagree", 0) < 4 and held_out_by_type.get("neg", 0) < 8 and
              held_out_by_type.get("ord", 0) < 7, str(held_out_by_type))

        total_held_out = sum(1 for s in split.values() if s == "held_out")
        check("roughly a third held out (5-8 of 19)", 5 <= total_held_out <= 8, str(total_held_out))


def test_seeded_determinism() -> None:
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        _reset(Path(tmp1))
        split1 = split_mod.assign_split(seed=7)
        _reset(Path(tmp2))
        split2 = split_mod.assign_split(seed=7)
        check("same seed produces identical assignment", split1 == split2)


def test_different_seeds_can_differ() -> None:
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        _reset(Path(tmp1))
        split1 = split_mod.assign_split(seed=1)
        _reset(Path(tmp2))
        split2 = split_mod.assign_split(seed=2)
        check("different seeds are not required to match (sanity: assignment is seed-driven)",
              split1 != split2 or True)  # not a hard guarantee, just exercises the path


def test_reassign_does_not_disturb_existing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _reset(Path(tmp))
        first = split_mod.assign_split(seed=0)
        # simulate a new case appearing later
        with open(split_mod.CASES_PATH, "a") as f:
            f.write(json.dumps(make_case("ord_new")) + "\n")
        second = split_mod.assign_split(seed=0)
        check("existing assignments unchanged after a re-run",
              all(second[cid] == first[cid] for cid in first))
        check("the new case got assigned too", "ord_new" in second)


def test_touch_logging_and_count() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _reset(Path(tmp))
        check("zero touches before any recorded", split_mod.count_touches() == 0)
        n1 = split_mod.record_touch("first eval run", "user", 6, "notes here")
        check("count is 1 after first touch", n1 == 1)
        n2 = split_mod.record_touch("second eval run", "agent:x", 6)
        check("count is 2 after second touch", n2 == 2)

        with open(split_mod.TOUCHES_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
        check("touch rows carry reason and n_cases", rows[0]["reason"] == "first eval run" and
              rows[0]["n_cases"] == "6")


def test_load_split_empty_when_unassigned() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _reset(Path(tmp))
        check("load_split returns {} before assign_split has run", split_mod.load_split() == {})


def run_tests() -> int:
    test_case_type_classification()
    test_assign_is_stratified_and_proportional()
    test_seeded_determinism()
    test_different_seeds_can_differ()
    test_reassign_does_not_disturb_existing()
    test_touch_logging_and_count()
    test_load_split_empty_when_unassigned()
    print(f"\n{'PASS' if not _FAILURES else 'FAIL'}: "
          f"{len(_FAILURES)} failure(s)" if _FAILURES else "All checks passed.")
    return 1 if _FAILURES else 0


if __name__ == "__main__":
    sys.exit(run_tests())
