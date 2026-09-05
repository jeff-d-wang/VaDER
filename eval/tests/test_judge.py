"""
Tests for judge.py that need no network and no real API key.

Why this file exists: the package restructure on 2026-09-04 rewrote
module-level imports and missed two DEFERRED ones inside GroqJudge's
methods (`from llm_client import ...`, nested in a function so the httpx
dependency is only paid when the real judge is used). All 19 test modules
still passed, because every test grades with FakeJudge and nothing ever
constructed the real one. The break surfaced only when a scoring run was
launched against the live API.

So the point here is narrow and specific: construct the real judge and
touch its deferred imports, without calling out to anything.

    python -m eval.tests.test_judge
"""
from __future__ import annotations

import os
import unittest

from eval.judge import FakeJudge, make_judge


class TestMakeJudge(unittest.TestCase):
    def test_fake_judge_needs_no_key(self):
        self.assertIsInstance(make_judge("fake"), FakeJudge)

    def test_groq_judge_constructs_and_its_deferred_imports_resolve(self):
        """The regression. GroqJudge.__init__ imports llm_client lazily; a
        stale module path there is invisible until a real scoring run."""
        had = os.environ.get("GROQ_API_KEY")
        os.environ["GROQ_API_KEY"] = "test-key-not-used-for-any-request"
        try:
            judge = make_judge("groq")
            self.assertEqual(type(judge).__name__, "GroqJudge")
        finally:
            if had is None:
                os.environ.pop("GROQ_API_KEY", None)
            else:
                os.environ["GROQ_API_KEY"] = had

    def test_groq_judge_fails_loudly_without_a_key(self):
        """Better a clear error at construction than a silent fall back to
        the fake judge, which would produce numbers that look real."""
        had = os.environ.pop("GROQ_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                make_judge("groq")
        finally:
            if had is not None:
                os.environ["GROQ_API_KEY"] = had

    def test_unknown_judge_name_is_rejected(self):
        with self.assertRaises(Exception):
            make_judge("no-such-judge")


class TestFakeJudgeIsNotAccidentallyReal(unittest.TestCase):
    def test_fake_judge_grades_deterministically_offline(self):
        judge = FakeJudge()
        a = judge.grade_claim_groundedness("carriers had higher risk",
                                           "carriers had higher risk of disease")
        b = judge.grade_claim_groundedness("carriers had higher risk",
                                           "carriers had higher risk of disease")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
