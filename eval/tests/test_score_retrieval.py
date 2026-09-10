"""
The part of phase C's scorer that can silently produce a wrong number: the
mapping from "spans that overlap gold" to "a ranking ir_metrics can score".

Every test here exists because getting it wrong yields a plausible number
rather than an error. Recall 1.0 for a retriever that found nothing looks
exactly like recall 1.0 for one that found everything.
"""
from __future__ import annotations

import unittest
from unittest import mock

from common.corpus_text import Chunk
from eval.score_retrieval import (GOLD_ID, by_overlap, by_stratum, check_index_covers_gold,
                                  hit_at, measure_holes, paired_style_test, rank_of_gold,
                                  sample_one_query_per_paragraph, to_query_result)
from retrieval.bm25 import index_from_chunks
from retrieval.ir_metrics import recall_at_k, reciprocal_rank

GOLD = {"pmcid": "PMC1", "section": "body", "char_start": 100, "char_end": 200}
CASE = {"query_id": "q1", "gold_span": GOLD}


def para(pmcid="PMC1", section="body", start=100, end=200, text="text"):
    """A single-span chunk, the identity-chunker shape. Named `para` because
    every span here is one paragraph."""
    return Chunk(chunk_id=f"{pmcid}:{section}:{start}-{end}", pmcid=pmcid, text=text,
                 source_spans=[{"section": section, "char_start": start, "char_end": end}])


class TestToQueryResult(unittest.TestCase):
    def test_gold_at_rank_three(self):
        hits = [para(pmcid="PMC9"), para(pmcid="PMC8"), para()]
        result = to_query_result(CASE, hits)
        self.assertEqual(result.retrieved[2], GOLD_ID)
        self.assertEqual(recall_at_k(result, 5), 1.0)
        self.assertEqual(recall_at_k(result, 1), 0.0)
        self.assertAlmostEqual(reciprocal_rank(result), 1 / 3)

    def test_no_hit_scores_zero_not_undefined(self):
        result = to_query_result(CASE, [para(pmcid="PMC9"), para(pmcid="PMC8")])
        self.assertEqual(recall_at_k(result, 10), 0.0,
                         "a query whose gold was never retrieved is a miss, not a dropped query")
        self.assertEqual(reciprocal_rank(result), 0.0)

    def test_partial_overlap_counts_as_a_hit(self):
        """Phase D's chunker will not reproduce paragraph boundaries. A chunk
        covering half the gold span found the evidence."""
        result = to_query_result(CASE, [para(start=150, end=400)])
        self.assertEqual(recall_at_k(result, 1), 1.0)

    def test_two_overlapping_hits_cannot_push_recall_over_one(self):
        result = to_query_result(CASE, [para(start=90, end=150), para(start=150, end=250)])
        self.assertEqual(result.retrieved.count(GOLD_ID), 1)
        self.assertEqual(recall_at_k(result, 10), 1.0)

    def test_touching_span_is_not_a_hit(self):
        """The paragraph ending exactly where gold begins is the neighbour,
        not the answer."""
        result = to_query_result(CASE, [para(start=0, end=100)])
        self.assertEqual(recall_at_k(result, 10), 0.0)

    def test_same_offsets_in_another_article_is_not_a_hit(self):
        result = to_query_result(CASE, [para(pmcid="PMC2"), para(section="abstract")])
        self.assertEqual(recall_at_k(result, 10), 0.0)

    def test_non_gold_hits_keep_distinct_ids(self):
        """Two different non-gold paragraphs must not collapse to one id, or
        nDCG's ranking would be computed over a shorter list than was
        actually returned."""
        result = to_query_result(CASE, [para(pmcid="PMC9", start=0), para(pmcid="PMC9", start=300)])
        self.assertEqual(len(set(result.retrieved)), 2)


def result_with(query_id, hit):
    return to_query_result({"query_id": query_id, "gold_span": GOLD},
                           [para()] if hit else [para(pmcid="PMC9")])


class TestPairedStyleTest(unittest.TestCase):
    def cases_and_results(self, pattern):
        """pattern: [(paragraph_id, lexical_hit, paraphrased_hit), ...]"""
        cases, results = [], {}
        for pid, lex, para_hit in pattern:
            for style, hit in (("lexical", lex), ("paraphrased", para_hit)):
                qid = f"{pid}#{style}"
                cases.append({"query_id": qid, "paragraph_id": pid, "style": style,
                              "stratum": "results"})
                results[qid] = result_with(qid, hit)
        return cases, results

    def test_discordant_pairs_counted_in_the_right_direction(self):
        cases, results = self.cases_and_results([
            ("p1", True, False), ("p2", True, False), ("p3", True, True), ("p4", False, True)])
        out = paired_style_test(cases, results, k=10)
        self.assertEqual((out["discordant_b"], out["discordant_c"]), (2, 1))
        self.assertEqual(out["lexical"], 0.75)
        self.assertEqual(out["paraphrased"], 0.5)
        self.assertEqual(out["delta"], 0.25)

    def test_unpaired_paragraph_is_excluded(self):
        cases, results = self.cases_and_results([("p1", True, True)])
        cases = [c for c in cases if c["style"] == "lexical"]
        self.assertIsNone(paired_style_test(cases, results, k=10),
                          "a paragraph with only one style is not a pair and must not be counted")


class TestByOverlap(unittest.TestCase):
    def cases_with(self, overlaps):
        return [{"query_id": f"q{i}", "paragraph_id": f"p{i}", "style": "lexical",
                 "stratum": "results", "lexical_overlap": o}
                for i, o in enumerate(overlaps)]

    def test_bands_are_half_open_so_a_query_lands_in_exactly_one(self):
        cases = self.cases_with([0.5, 0.65, 0.8, 0.9])
        results = {c["query_id"]: result_with(c["query_id"], True) for c in cases}
        out = by_overlap(cases, results, k=10)
        self.assertEqual(sum(b["n"] for b in out.values()), 4)

    def test_overlap_of_one_is_included_not_dropped(self):
        """A query every token of which is in the gold paragraph is the most
        lexically biased case in the set. An exclusive upper bound would drop
        exactly those."""
        cases = self.cases_with([1.0])
        results = {c["query_id"]: result_with(c["query_id"], True) for c in cases}
        self.assertEqual(sum(b["n"] for b in by_overlap(cases, results, k=10).values()), 1)


class TestByStratum(unittest.TestCase):
    def test_refuses_to_report_under_the_floor(self):
        cases = [{"query_id": f"q{i}", "stratum": "methods" if i < 3 else "results"}
                 for i in range(9)]
        results = {c["query_id"]: result_with(c["query_id"], True) for c in cases}
        out = by_stratum(cases, results, k=10)
        self.assertNotIn("methods", out, "n=3 is not a rate")
        self.assertEqual(out["results"]["n"], 6)


class TestIndexCoversGold(unittest.TestCase):
    """The check that found the fragment index. A gold span the index does
    not contain is an unanswerable query, and its miss is not a fact about
    the retriever."""

    def test_present_gold_is_not_reported_missing(self):
        index = index_from_chunks([para(), para(pmcid="PMC9")])
        self.assertEqual(check_index_covers_gold([CASE], index), 0)

    def test_absent_gold_is_counted(self):
        index = index_from_chunks([para(pmcid="PMC9")])
        self.assertEqual(check_index_covers_gold([CASE], index), 1)

    def test_a_fragment_of_the_gold_paragraph_does_not_count_as_covering_it(self):
        """The exact failure: an index of sentence fragments overlaps every
        gold span, so span-overlap scoring produces plausible numbers off it.
        The key match is deliberately exact so that cannot pass."""
        index = index_from_chunks([para(start=100, end=140), para(start=141, end=200)])
        self.assertEqual(check_index_covers_gold([CASE], index), 1)


class TestHoleSample(unittest.TestCase):
    CASES = [{"query_id": f"p{i}#{style}", "paragraph_id": f"p{i}", "style": style}
             for i in range(10) for style in ("lexical", "paraphrased")]

    def test_never_draws_both_styles_of_one_paragraph(self):
        """The two styles of a paragraph ask the same question against the
        same gold span. Counting them as two observations would narrow the
        hole rate's CI on evidence that does not exist."""
        picked = sample_one_query_per_paragraph(self.CASES, 10, seed=0)
        ids = [c["paragraph_id"] for c in picked]
        self.assertEqual(len(ids), len(set(ids)))

    def test_caps_at_the_requested_n(self):
        self.assertEqual(len(sample_one_query_per_paragraph(self.CASES, 4, seed=0)), 4)

    def test_asking_for_more_than_exist_returns_what_exists(self):
        self.assertEqual(len(sample_one_query_per_paragraph(self.CASES, 99, seed=0)), 10)

    def test_seeded(self):
        a = sample_one_query_per_paragraph(self.CASES, 5, seed=1)
        b = sample_one_query_per_paragraph(self.CASES, 5, seed=1)
        self.assertEqual([c["query_id"] for c in a], [c["query_id"] for c in b])


class TestMeasureHoles(unittest.TestCase):
    """The one path that costs real API budget, so it gets checked with a
    stub before it is run for real rather than after."""

    def setUp(self):
        self.gold = para(start=100, end=200, text="the gold paragraph text")
        self.other = para(pmcid="PMC9", start=0, end=50, text="a different paragraph")
        self.index = index_from_chunks([self.gold, self.other])
        self.cases = [{"query_id": "p1#lexical", "paragraph_id": "p1", "style": "lexical",
                       "query": "a query", "gold_span": GOLD}]
        self.results = {"p1#lexical": to_query_result(self.cases[0], [self.other, self.gold])}

    def run_with(self, verdict):
        with mock.patch("eval.score_retrieval.groq_chat_json", return_value=verdict) as call:
            out = measure_holes(self.cases, self.results, self.index, 10, 5, "m", 0)
        return out, call

    def test_a_relevant_non_gold_hit_is_a_hole(self):
        out, call = self.run_with({"answers_the_query": True, "why": "same finding"})
        self.assertEqual((out["value"], out["n"]), (1.0, 1))
        self.assertEqual(out["examples"][0]["why"], "same finding")

    def test_an_irrelevant_non_gold_hit_is_not(self):
        out, _ = self.run_with({"answers_the_query": False, "why": "off topic"})
        self.assertEqual((out["value"], out["n"]), (0.0, 1))

    def test_the_gold_hit_itself_is_never_judged(self):
        """Judging gold against gold would score every query as holed."""
        _, call = self.run_with({"answers_the_query": False, "why": ""})
        self.assertEqual(call.call_count, 1, "only the one non-gold hit should be judged")
        self.assertIn(self.other.text, call.call_args.args[0])

    def test_a_query_whose_gold_is_missing_from_the_index_is_skipped(self):
        index = index_from_chunks([self.other])
        with mock.patch("eval.score_retrieval.groq_chat_json") as call:
            out = measure_holes(self.cases, self.results, index, 10, 5, "m", 0)
        self.assertEqual(out["n"], 0, "no gold text means nothing to compare against")
        call.assert_not_called()


class TestRankOfGold(unittest.TestCase):
    def test_one_indexed(self):
        self.assertEqual(rank_of_gold(to_query_result(CASE, [para()])), 1)

    def test_finds_the_right_position(self):
        result = to_query_result(CASE, [para(pmcid="PMC9"), para(pmcid="PMC8"), para()])
        self.assertEqual(rank_of_gold(result), 3)

    def test_none_when_never_retrieved(self):
        self.assertIsNone(rank_of_gold(to_query_result(CASE, [para(pmcid="PMC9")])))

    def test_agrees_with_hit_at(self):
        """hit@k must be exactly 'rank <= k', or the persisted per-query rank
        would disagree with the aggregate the same run reports."""
        result = to_query_result(CASE, [para(pmcid="PMC9"), para(pmcid="PMC8"), para()])
        rank = rank_of_gold(result)
        for k in range(1, 6):
            self.assertEqual(hit_at(result, k), rank <= k, f"k={k}")


class TestHitAt(unittest.TestCase):
    def test_respects_the_cutoff(self):
        result = to_query_result(CASE, [para(pmcid="PMC9"), para()])
        self.assertTrue(hit_at(result, 2))
        self.assertFalse(hit_at(result, 1))


if __name__ == "__main__":
    unittest.main()
