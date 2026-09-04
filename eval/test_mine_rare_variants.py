"""
Tests for mine_rare_variants.py, concentrated on gene attribution, since
that is where the first version of this script was wrong for 4 of 8
checked candidates.

    python test_mine_rare_variants.py
"""
from __future__ import annotations

import unittest

import mine_rare_variants as mrv


def _attribute(paragraph: str, variant: str):
    return mrv.attribute_gene(paragraph, paragraph.index(variant))


class TestHGVSPattern(unittest.TestCase):
    def test_matches_the_notation_forms_the_corpus_uses(self):
        for notation in ("c.9275A>G", "c.4484+2T>C", "c.4777-1G>C", "c.2502_2503insA",
                         "c.826_827GC>AT", "c.1592delT", "c.6393_6396del", "c.1408dupG"):
            self.assertEqual(mrv.HGVS.findall(f"the {notation} variant"), [notation], notation)

    def test_does_not_match_bare_positions_or_prose(self):
        self.assertEqual(mrv.HGVS.findall("exon 11 of the gene"), [])
        self.assertEqual(mrv.HGVS.findall("c.1592 was reported"), [])


class TestGeneAttribution(unittest.TestCase):
    def test_simple_gene_then_variant(self):
        gene, _ = _attribute("BRCA2 c.9275A>G (p.Tyr3092Cys) was detected", "c.9275A>G")
        self.assertEqual(gene, "BRCA2")

    def test_colon_form(self):
        gene, _ = _attribute("two genes (BRCA2: c.6037A > T and ATM: c.2502_2503insA)",
                             "c.2502_2503insA")
        self.assertEqual(gene, "ATM")

    def test_parenthesised_form(self):
        gene, _ = _attribute("variants in PALB2 (c.1221del), PMS2 (c.1919C>A; p.Ser640*)",
                             "c.1919C>A")
        self.assertEqual(gene, "PMS2")

    def test_the_four_real_misattributions_are_fixed(self):
        """Every one of these came back with the wrong gene under the
        original first-gene-in-paragraph rule. Verbatim shapes from the
        source articles."""
        cases = [
            ("three patients had 2 pathogenic variants in 2 different genes "
             "(BRCA2: c.6037A > T and CFTR: c.1521_1523delCCT; BRCA2: 8954_8955delTTinsAA "
             "and ATM: c.2502_2503insA)", "c.2502_2503insA", "ATM"),
            ("co-occurrence of pathogenic variants in PALB2 (c.1221del; p.Thr408fs*40), "
             "ATM (c.8545C>T; p.Arg2849*), PMS2 (c.1919C>A; p.Ser640*)", "c.1919C>A", "PMS2"),
            ("3. patient: BRCA2 c.3042T>G het, p.Asn1014Lys and ATM c.5890A>G het",
             "c.5890A>G", "ATM"),
        ]
        for paragraph, variant, expected in cases:
            gene, _ = _attribute(paragraph, variant)
            self.assertEqual(gene, expected, f"{variant} in: {paragraph[:60]}...")

    def test_a_following_gene_symbol_does_not_win(self):
        """The failure mode directly: the next item in a list is not this
        variant's gene."""
        gene, _ = _attribute("ATM c.1234A>G and BRCA2 c.9999T>C", "c.1234A>G")
        self.assertEqual(gene, "ATM")

    def test_returns_none_when_no_symbol_is_close_enough(self):
        far = "BRCA1" + " padding" * 30 + " c.1234A>G"
        gene, distance = _attribute(far, "c.1234A>G")
        self.assertIsNone(gene)
        self.assertEqual(distance, -1)

    def test_reports_distance_so_a_weak_match_is_visible(self):
        _gene, distance = _attribute("BRCA2 (NM_000059.4) c.9275A>G", "c.9275A>G")
        self.assertGreater(distance, 0)
        self.assertLess(distance, mrv.ATTRIBUTION_WINDOW)


if __name__ == "__main__":
    unittest.main(verbosity=2)
