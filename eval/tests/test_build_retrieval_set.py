"""
The filters are the whole quality mechanism of the retrieval set, so they
get the tests. Each one here is a way a generated item goes wrong that would
otherwise land in the set looking fine: a specific-sounding anchor the
paragraph never contained, a query that dropped its anchors and became
generic, two "different" queries that are the same string.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eval.build_retrieval_set import (MAX_RAREST_TERM_DF, answer_share_in_query, build,
                                      classify_section, lexical_overlap, rarest_term_df,
                                      rows_for, validate)

PARAGRAPH = ("Among 1,432 carriers of the CHEK2 c.1100delC variant, the hazard ratio for "
             "contralateral breast cancer was 2.7 compared with non-carriers in the Dutch cohort.")

GOOD = {
    "anchors": ["CHEK2 c.1100delC", "1,432 carriers"],
    # The shortest answering span, as the prompt demands: the queries supply
    # "hazard ratio for contralateral breast cancer", the paragraph supplies
    # the value. Writing the whole clause here instead is the mistake the
    # filter exists to catch, and it caught this fixture first.
    "answer_quote": "2.7",
    "lexical_query": "hazard ratio for contralateral breast cancer among 1,432 carriers of "
                     "CHEK2 c.1100delC",
    "paraphrased_query": "Do the 1,432 carriers of CHEK2 c.1100delC face a raised chance of a "
                         "second tumour in the opposite breast?",
}


def with_(**overrides):
    return {**GOOD, **overrides}


class TestValidate(unittest.TestCase):
    def test_a_good_item_passes(self):
        self.assertIsNone(validate(GOOD, PARAGRAPH))

    def test_a_hallucinated_anchor_never_survives_into_the_row(self):
        """Anchors are metadata, but metadata that lies is still a defect: an
        anchor records what the question is about, so one the paragraph never
        contained is a false claim about the row."""
        item = with_(anchors=["CHEK2 c.1100delC", "1,432 carriers", "9,000 carriers"])
        self.assertIsNone(validate(item, PARAGRAPH))
        self.assertEqual(item["anchors"], ["CHEK2 c.1100delC", "1,432 carriers"])

    def test_an_anchor_absent_from_the_queries_is_no_longer_fatal(self):
        """Measured 2026-09-06: requiring anchors verbatim in both queries
        accepted 3 of 20 paragraphs, dropping the requirement accepted 14 of
        19, and the recovered items were the exact ones a human had marked
        wrong, now correctly formed. The rule cost two thirds of the yield
        and bought no quality. Anchors are metadata now."""
        item = with_(anchors=["CHEK2 c.1100delC", "1,432 carriers", "Dutch cohort"])
        self.assertIsNone(validate(item, PARAGRAPH))
        self.assertIn("Dutch cohort", item["anchors"])

    def test_an_over_long_anchor_is_pruned_not_fatal(self):
        item = with_(anchors=["CHEK2 c.1100delC", "1,432 carriers",
                              "hazard ratio for contralateral breast cancer"])
        self.assertIsNone(validate(item, PARAGRAPH))
        self.assertEqual(len(item["anchors"]), 2)

    def test_unicode_dashes_do_not_cause_a_false_rejection(self):
        """A real rejection: the model returned an anchor carrying U+2011
        where the paragraph had U+002D. Same string to a reader, different
        bytes to a substring check."""
        para = PARAGRAPH + " Testing used next\u2011generation sequencing throughout."
        item = with_(anchors=["CHEK2 c.1100delC", "next-generation sequencing"],
                     lexical_query="what hazard ratio did next-generation sequencing find for "
                                   "CHEK2 c.1100delC carriers in this cohort",
                     paraphrased_query="using next-generation sequencing, what risk was seen for "
                                       "people carrying CHEK2 c.1100delC in these data")
        self.assertIsNone(validate(item, para))
        self.assertIn("next-generation sequencing", item["anchors"])

    def test_identical_queries_rejected(self):
        self.assertIn("identical",
                      validate(with_(paraphrased_query=GOOD["lexical_query"].upper()), PARAGRAPH))

    def test_too_short_query_rejected(self):
        bad = with_(anchors=["CHEK2", "2.7"], lexical_query="CHEK2 2.7",
                    paraphrased_query="a query about CHEK2 and the figure 2.7 in carriers")
        self.assertIn("tokens", validate(bad, PARAGRAPH))

    def test_missing_query_rejected(self):
        self.assertIn("missing", validate(with_(paraphrased_query=None), PARAGRAPH))

    def test_anchor_matching_ignores_case_and_whitespace(self):
        """The model reformats whitespace freely; that is not a defect worth
        discarding a paragraph over."""
        self.assertIsNone(validate(with_(anchors=["chek2  C.1100DELC", "1,432 carriers"]),
                                   PARAGRAPH))


class TestAnswerQuote(unittest.TestCase):
    """The two filters added after a human review found 11 of 20 paragraphs
    defective under retrieval_qgen_v1, with two systematic causes."""

    def test_a_query_containing_its_own_answer_is_rejected(self):
        """Cause 1, 6 of the 11. The anchor was the finding, and anchors are
        held verbatim in both queries, so the answer rode into the question:
        "How many amplicons... specifically 1663 amplicons?" """
        bad = with_(lexical_query="What was the hazard ratio for contralateral breast cancer "
                                  "among 1,432 carriers of CHEK2 c.1100delC, namely 2.7?")
        self.assertIn("tautological", validate(bad, PARAGRAPH))

    def test_a_paragraph_that_states_no_finding_is_rejected(self):
        """Cause 2, 5 of the 11. The query asked about the topic a paragraph
        announces rather than anything it states. A fact the paragraph does
        not contain cannot be quoted from it."""
        self.assertIn("declined", validate(with_(answer_quote=""), PARAGRAPH))

    def test_a_declination_is_reported_as_such_not_as_malformed_output(self):
        """The model returns an empty object when it declines, so a check on
        anchors would fire first and label it "fewer than 2 anchors". A build's
        reject histogram would then hide the most important number about the
        sampling frame: how many sampled paragraphs contain no askable fact."""
        declined = {"anchors": [], "answer_quote": "", "lexical_query": "",
                    "paraphrased_query": ""}
        self.assertIn("declined", validate(declined, PARAGRAPH))

    def test_an_answer_not_in_the_paragraph_is_rejected(self):
        bad = with_(answer_quote="hazard ratio for contralateral breast cancer was 9.9")
        self.assertIn("not verbatim", validate(bad, PARAGRAPH))

    def test_a_whole_sentence_answer_is_rejected(self):
        """The share test only discriminates when the answer is the shortest
        answering span. A sentence restates the question's framing, so a
        perfectly good query shares most of its tokens."""
        long_answer = ("Among 1,432 carriers of the CHEK2 c.1100delC variant, the hazard ratio "
                       "for contralateral breast cancer was 2.7 compared with non-carriers")
        self.assertIn("shortest answering span", validate(with_(answer_quote=long_answer),
                                                          PARAGRAPH))

    def test_the_good_case_still_passes(self):
        self.assertIsNone(validate(GOOD, PARAGRAPH))


class TestAnswerShareInQuery(unittest.TestCase):
    def test_answer_fully_present_is_one(self):
        self.assertEqual(answer_share_in_query("1663 amplicons",
                                               "how many 1663 amplicons were used"), 1.0)

    def test_withheld_answer_scores_below_the_threshold(self):
        """The query says "amplicons" but not the number, which is the whole
        difference between a question and a statement."""
        self.assertEqual(answer_share_in_query("1663 amplicons",
                                               "how many amplicons were used"), 0.5)

    def test_empty_answer_is_treated_as_fully_present(self):
        """So a blank answer can never slip through the tautology gate as if
        it were maximally informative."""
        self.assertEqual(answer_share_in_query("", "anything at all"), 1.0)


class TestSpecificity(unittest.TestCase):
    """The mechanical replacement for anchors. Anchors asked the model to copy
    distinctive strings into its queries and it would not comply; this asks
    the corpus how distinctive the query actually is."""

    # Every token of the test queries must appear, as it would in a real
    # corpus, or the absent ones would be ignored and the fixture would not
    # exercise what it claims to.
    COMMON = {"what": 300_000, "is": 340_000, "the": 340_000, "of": 330_000, "in": 335_000,
              "general": 60_000, "population": 70_000, "risk": 90_000, "breast": 50_000,
              "cancer": 200_000, "hazard": 20_000, "ratio": 40_000, "for": 300_000,
              "contralateral": 3_000, "among": 80_000, "1": 90_000, "432": 5_000,
              "carriers": 12_000, "chek2": 4_000, "do": 90_000, "face": 9_000,
              "a": 340_000, "raised": 8_000, "chance": 9_000, "second": 40_000,
              "tumour": 30_000, "opposite": 6_000}
    RARE = {**COMMON, "c.1100delc": 3}

    def test_a_generic_query_is_rejected(self):
        """Measured: queries whose rarest term is in over 1000 paragraphs
        score recall@10 0.562 against 0.972 for those under 10. Such a query
        cannot single out one gold paragraph, so its miss says nothing about
        the retriever."""
        item = with_(lexical_query="what is the risk of breast cancer in the general population",
                     answer_quote="2.7")
        self.assertIn("generic", validate(item, PARAGRAPH, doc_freq=self.COMMON))

    def test_a_query_with_one_rare_term_passes(self):
        self.assertIsNone(validate(dict(GOOD), PARAGRAPH, doc_freq=self.RARE))

    def test_the_check_is_off_when_no_table_is_supplied(self):
        """Off rather than wrong: unit tests and offline re-scoring have no
        corpus to consult, and silently treating every term as rare would be
        a check that always passes."""
        item = with_(lexical_query="what is the risk of breast cancer in the general population",
                     answer_quote="2.7")
        self.assertIsNone(validate(item, PARAGRAPH))

    def test_a_term_absent_from_the_corpus_is_ignored_not_treated_as_rare(self):
        """It matches no paragraph, so it cannot help find the gold one
        either. Counting it as the query's most distinctive term would wave
        every misspelling through as maximally specific."""
        self.assertEqual(rarest_term_df("brca1 zzzqqq", {"brca1": 500}), 500)

    def test_a_query_matching_nothing_at_all_fails(self):
        self.assertGreater(rarest_term_df("zzzqqq wwwvvv", {"brca1": 500}), MAX_RAREST_TERM_DF)

    def test_rarest_not_average(self):
        """One distinctive handle is enough; the common words around it do
        not dilute it."""
        self.assertEqual(rarest_term_df("the risk of c.1100delc", self.RARE), 3)


class TestClassifySection(unittest.TestCase):
    def test_abstract_ignores_any_title(self):
        self.assertEqual(classify_section("abstract", "Results"), "abstract")

    def test_specific_rules_beat_general_ones(self):
        self.assertEqual(classify_section("body", "Statistical analysis"), "methods")
        self.assertEqual(classify_section("body", "Results and discussion"), "results")

    def test_boilerplate_is_dropped_not_bucketed(self):
        for title in ("Acknowledgements", "Funding", "Data availability statement",
                      "Competing interests"):
            self.assertIsNone(classify_section("body", title), title)

    def test_untitled_body_paragraph_is_kept(self):
        self.assertEqual(classify_section("body", None), "body_other")

    def test_unrecognised_title_is_kept(self):
        self.assertEqual(classify_section("body", "Case presentation"), "body_other")


class TestLexicalOverlap(unittest.TestCase):
    def test_full_containment_is_one(self):
        self.assertEqual(lexical_overlap("CHEK2 c.1100delC carriers", PARAGRAPH), 1.0)

    def test_nothing_in_common_is_zero(self):
        self.assertEqual(lexical_overlap("zebrafish embryo development", PARAGRAPH), 0.0)

    def test_repeated_query_word_counted_once(self):
        """Type overlap, not token overlap: 'carriers carriers zebrafish' is
        two distinct types, one of which is present."""
        self.assertEqual(lexical_overlap("carriers carriers zebrafish", PARAGRAPH), 0.5)

    def test_empty_query_does_not_divide_by_zero(self):
        self.assertEqual(lexical_overlap("", PARAGRAPH), 0.0)


class TestRowsFor(unittest.TestCase):
    def test_pair_shares_a_paragraph_id_and_gold_span(self):
        cand = {"paragraph_id": "PMC1:body:100", "text": PARAGRAPH, "stratum": "results",
                "section_title": "Results",
                "gold_span": {"pmcid": "PMC1", "section": "body",
                              "char_start": 100, "char_end": 300}}
        rows = rows_for(cand, GOOD, 2021, "test-model")
        self.assertEqual([r["style"] for r in rows], ["lexical", "paraphrased"])
        self.assertEqual({r["paragraph_id"] for r in rows}, {"PMC1:body:100"})
        self.assertEqual(len({r["query_id"] for r in rows}), 2)
        self.assertEqual([r["gold_span"] for r in rows], [cand["gold_span"]] * 2)
        self.assertGreater(rows[0]["lexical_overlap"], rows[1]["lexical_overlap"],
                           "the wording-reusing query should overlap gold more than the paraphrase")


class TestResume(unittest.TestCase):
    """The build is rate-limited into multi-day territory by the free tier's
    200k-tokens-per-day cap, so resuming is not a convenience, it is how the
    set ever gets finished. A silent failure to skip finished paragraphs
    would spend a whole day's budget regenerating what already exists."""

    def paragraph_rows(self, paragraph_id, stratum):
        cand = {"paragraph_id": paragraph_id, "text": PARAGRAPH, "stratum": stratum,
                "section_title": None,
                "gold_span": {"pmcid": "PMC1", "section": "body",
                              "char_start": 0, "char_end": 10}}
        return rows_for(cand, GOOD, 2020, "test-model")

    def test_finished_paragraphs_are_not_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "cases.jsonl"
            existing = self.paragraph_rows("PMC1:body:0", "abstract")
            out.write_text("".join(json.dumps(r) + "\n" for r in existing))

            sampled = {s: [] for s in ("abstract", "intro", "methods", "results",
                                       "discussion", "body_other")}
            sampled["abstract"] = [{"paragraph_id": "PMC1:body:0", "text": PARAGRAPH,
                                    "stratum": "abstract", "section_title": None,
                                    "gold_span": {"pmcid": "PMC1", "section": "body",
                                                  "char_start": 0, "char_end": 10}}]
            with mock.patch("eval.build_retrieval_set.sample_paragraphs", return_value=sampled), \
                 mock.patch("eval.build_retrieval_set.load_manifest_years", return_value={}), \
                 mock.patch("eval.build_retrieval_set.groq_chat_json") as call:
                build(out, quota=1, seed=0, model="m", limit=None, max_articles=1,
                      oversample=1.0)
            call.assert_not_called()
            self.assertEqual(len(out.read_text().strip().splitlines()), 2,
                             "the resumed file must not gain duplicate rows")


if __name__ == "__main__":
    unittest.main()
