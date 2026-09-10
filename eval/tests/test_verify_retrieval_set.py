"""
A checker that cannot fail is worse than no checker: it reports a clean
sheet and stops anyone looking. So every check gets a row built to break it.

That is not a hypothetical concern here. This project has already shipped
one review tool that turned a 45% label error rate into a printed "valid 6
(100%)" (see make_case_worksheet._parse_verdict), and one offset invariant
that passed happily against an index of sentence fragments.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from eval.verify_retrieval_set import check, load_rows

PARAGRAPH_TEXT = ("Among 1,432 carriers of the CHEK2 c.1100delC variant, the hazard ratio "
                  "for contralateral breast cancer was 2.7 in the Dutch cohort.")

ARTICLE = f"""<article>
  <abstract><p>{PARAGRAPH_TEXT}</p></abstract>
  <body><p>Unrelated body paragraph.</p></body>
</article>"""


def rows_for_text(text: str) -> list[dict]:
    from eval.build_retrieval_set import gold_text_digest, lexical_overlap
    queries = {
        "lexical": "hazard ratio for contralateral breast cancer in 1,432 carriers of "
                   "CHEK2 c.1100delC",
        "paraphrased": "do the 1,432 carriers of CHEK2 c.1100delC show a raised chance of a "
                       "tumour in the other breast",
    }
    return [{
        "query_id": f"PMC1:abstract:0#{style}", "paragraph_id": "PMC1:abstract:0",
        "style": style, "query": query,
        "gold_span": {"pmcid": "PMC1", "section": "abstract",
                      "char_start": 0, "char_end": len(text)},
        "stratum": "abstract", "section_title": None, "pub_year": 2021,
        "anchors": ["CHEK2 c.1100delC", "1,432 carriers"],
        "lexical_overlap": round(lexical_overlap(query, text), 4),
        "gold_text_chars": len(text), "gold_text_sha1": gold_text_digest(text),
        "created_by": "test", "model": "test",
        "validated_by": None,
    } for style, query in queries.items()]


class VerifyCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.xml_dir = Path(self.tmp.name)
        (self.xml_dir / "PMC1.xml").write_text(ARTICLE)
        self.rows = rows_for_text(PARAGRAPH_TEXT)

    def tearDown(self):
        self.tmp.cleanup()

    def failures(self, rows):
        return check(rows, self.xml_dir)[0]

    def warnings(self, rows):
        return check(rows, self.xml_dir)[1]

    def assertFailsWith(self, rows, needle):
        found = self.failures(rows)
        self.assertTrue(any(needle in f for f in found),
                        f"expected a failure mentioning {needle!r}, got {found}")


class TestCleanSetPasses(VerifyCase):
    def test_no_failures_on_a_good_set(self):
        self.assertEqual(self.failures(self.rows), [])


class TestGoldSpans(VerifyCase):
    def test_missing_article_is_caught(self):
        (self.xml_dir / "PMC1.xml").unlink()
        self.assertFailsWith(self.rows, "does not resolve")

    def test_an_edit_inside_the_span_is_caught_even_at_identical_length(self):
        """The reason the check is a content hash and not a length. A
        re-pulled article that revises an effect size from 2.7 to 3.9 leaves
        the span exactly as long as it was and pointing at different text.
        A length check sees nothing; every number scored off that row is then
        graded against a paragraph it was not written for."""
        (self.xml_dir / "PMC1.xml").write_text(ARTICLE.replace("was 2.7 in", "was 3.9 in"))
        self.assertFailsWith(self.rows, "the corpus changed under this row")

    def test_text_appended_after_the_span_is_not_a_failure(self):
        """The complement, and the reason this check is on span text rather
        than on the article: a span is a range, so content added past its end
        does not change what the row points at. Flagging that would make the
        verifier cry wolf on every corpus refresh."""
        (self.xml_dir / "PMC1.xml").write_text(
            ARTICLE.replace(PARAGRAPH_TEXT, PARAGRAPH_TEXT + " An added sentence."))
        self.assertEqual(self.failures(self.rows), [])


class TestAnchors(VerifyCase):
    def test_anchor_absent_from_gold_is_caught(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            r["anchors"] = ["CHEK2 c.1100delC", "9,999 carriers"]
            r["query"] += " 9,999 carriers"
        self.assertFailsWith(rows, "no longer in the gold paragraph")

    def test_query_not_echoing_an_anchor_is_not_a_failure(self):
        """v3 dropped the anchor-echo rule deliberately (anchors are metadata, not a
        constraint on the query text), so this checker must not resurrect it. (The
        rewritten query's now-stale lexical_overlap is still, correctly, its own failure;
        this asserts on the anchor check specifically, not on the full failure list.)"""
        rows = copy.deepcopy(self.rows)
        rows[1]["query"] = "do these carriers show a raised chance of a tumour in the other breast"
        self.assertFalse([f for f in self.failures(rows) if "anchor" in f])

    def test_a_row_with_no_hash_cannot_be_checked_and_says_so(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            del r["gold_text_sha1"]
        self.assertFailsWith(rows, "integrity cannot be checked")


class TestStoredOverlap(VerifyCase):
    def test_a_stale_stored_overlap_is_caught(self):
        """lexical_overlap is what every row's bias caveat is read from, and
        it depends on the tokenizer. If the tokenizer changes, the stored
        value silently becomes a claim about code that no longer exists."""
        rows = copy.deepcopy(self.rows)
        rows[0]["lexical_overlap"] = 0.1234
        self.assertFailsWith(rows, "no longer describes this row")


class TestPairing(VerifyCase):
    def test_unpaired_paragraph_is_caught(self):
        self.assertFailsWith(self.rows[:1], "expected both")

    def test_duplicate_query_id_is_caught(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["query_id"] = rows[0]["query_id"]
        self.assertFailsWith(rows, "duplicate query_id")

    def test_two_rows_with_the_same_query_text_is_caught(self):
        rows = copy.deepcopy(self.rows)
        rows[1]["query"] = rows[0]["query"]
        self.assertFailsWith(rows, "duplicate query text")


class TestHeldOutLeak(VerifyCase):
    def test_a_row_citing_a_held_out_article_is_caught(self):
        """Held-out articles are physically absent from the corpus, so a
        query about one cannot be answered by any retriever."""
        import csv as _csv

        from eval import verify_retrieval_set as mod
        held = self.xml_dir / "held_out.csv"
        with open(held, "w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=["pmcid"])
            w.writeheader()
            w.writerow({"pmcid": "PMC1"})
        original = mod.HELD_OUT
        mod.HELD_OUT = held
        try:
            self.assertFailsWith(self.rows, "held-out article")
        finally:
            mod.HELD_OUT = original


class TestConcentration(VerifyCase):
    def test_many_paragraphs_from_one_article_warns_but_does_not_fail(self):
        """Correlated queries narrow every interval computed off the set.
        Worth surfacing, not worth refusing to report over."""
        rows = []
        for i in range(5):
            for r in copy.deepcopy(self.rows):
                r["paragraph_id"] = f"PMC1:abstract:{i}"
                r["query_id"] = f"{r['paragraph_id']}#{r['style']}"
                # Distinct query text per paragraph, with the stored overlap
                # recomputed to match: mutating the query and leaving the old
                # overlap behind is itself a failure the verifier catches, and
                # this test is about concentration, not that.
                r["query"] = f"{r['query']} at {2000 + i} follow-up"
                from eval.build_retrieval_set import lexical_overlap
                r["lexical_overlap"] = round(lexical_overlap(r["query"], PARAGRAPH_TEXT), 4)
                rows.append(r)
        self.assertEqual(self.failures(rows), [])
        self.assertTrue(any("correlated" in w for w in self.warnings(rows)))


class TestLoadRows(unittest.TestCase):
    def test_blank_lines_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.jsonl"
            path.write_text('{"a": 1}\n\n{"a": 2}\n')
            self.assertEqual(len(load_rows(path)), 2)


if __name__ == "__main__":
    unittest.main()
