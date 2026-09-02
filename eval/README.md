# eval/: M1 eval-set construction tooling

Early Tier 1 (M1) tooling for building the `answer` eval set (`PROJECT_PLAN.md` M1). Not the eval harness or scorer themselves, those are a separate, larger discussion (see `docs/DECISION_LOG.md`
for the rubric decisions so far: four sub-scores per case, pass/partial/fail grading, a
methods-extraction stratum alongside the evidence cases). This directory currently holds the
tool that finds candidate source material for two of the harder case types.

## find_coverage.py

A recall-oriented full-corpus sweep: given a gene/variant and a condition, find **every** article
in `../corpus/` that covers it, not just the top few. It exists for two specific jobs:

1. **Negative-case construction** (property 4, "says not found in this corpus"): before holding
   out a variant-condition pair's articles to build a true-negative eval case, you need to know
   every article that covers it. Miss one and the case is silently invalid, the corpus still
   grounds it somewhere, so a system that finds it and answers correctly would score as a false
   failure.
2. **Disagreement-candidate discovery** (property 3, "surfaces disagreement"): find every article
   covering a pair, then read the candidates and judge whether any genuinely conflict (replication
   failure, VUS reclassification, population-specific effect vs. no effect). **This tool finds
   candidates. It does not judge disagreement**: that call needs a human or an agent reading the
   actual text, not a keyword match.

It is deliberately not `service/search.py`: that one title-prefilters and caps scanning for
low-latency serving. This one scans every article's title/abstract/body in full, on purpose,
because the whole point here is recall. It's an offline tool you run on demand, not a live
endpoint.

### Term matching is not smart, by design

You supply gene/variant/condition term lists yourself (aliases, HGVS notations, synonyms). The
tool does case-insensitive whole-word matching, AND across categories: **when you supply a
variant, the variant term is the subject requirement, on its own.** Gene names are not a
substitute. Give it `--gene BRCA1 --variant "c.68_69delAG"` and it requires `c.68_69delAG`
specifically to appear, not just `BRCA1`. Omit `--variant` (a gene-level query) and it falls back
to matching on the gene names. Two match strengths get reported per article:

- **`same_paragraph`**: the subject term (variant, or gene if no variant given) and a condition
  term appear in the same paragraph. Likely real coverage.
- **`doc_level_only`**: both appear somewhere in the document, but never together in one
  paragraph. Weaker signal, e.g. one paragraph about the gene's structure, an unrelated paragraph
  about the condition's epidemiology. Read these before trusting them.

**A bug lived here until 2026-09-01** (see `docs/DECISION_LOG.md`): genes and variants used to be
OR'd together into one subject pattern, so an article mentioning the *gene* near the condition,
without the specific variant ever appearing, still counted as coverage. A negative-case build
using this bug held out 247 articles across 8 supposedly-narrow variant pairs; re-run with the
fix, all 8 pairs came back with **zero** genuine matches, none of those 247 articles actually
mentioned the specific variant. If you're reading old output from before this date, distrust it.

**Even with the fix, a single variant notation is weak evidence of true absence.** Papers describe
the same variant differently: cDNA HGVS, protein-level HGVS, an rsID, legacy nomenclature, or just
prose ("the previously reported truncating variant in exon 10"). Supply every notation form you
know for a variant as separate entries in the `variants` list (they're OR'd with each other, only
AND'd against genes/conditions), and treat a low match count as suggestive, not proof, full recall
against narrative-only mentions isn't achievable by keyword search alone.

**Pick specific pairs, not broad ones**, and let the tool tell you when you haven't: pass
`--warn-threshold` (default 20) and it prints a loud `[WARN]` banner on stderr for any pair whose
`same_paragraph` count exceeds it. `BRCA1` + `breast cancer` alone matched 3,391 of 7,863 articles
in about 7 seconds against the real corpus, useless as a negative-case candidate list, it's too
common to ever be absent. If you see the warning while building a negative case, **do not proceed
to `hold_out_case.py`**, narrow the pair and re-run instead.

### Usage

One pair:
```
python find_coverage.py --pair-id brca1_hboc --gene BRCA1 \
    --condition "breast cancer" --condition "ovarian cancer" --condition HBOC
```

Many pairs in one corpus pass, cheaper than looping the corpus once per pair since every article
is parsed once and tested against all term sets (see `term_sets.example.csv` for the format):
```
python find_coverage.py --term-sets-csv term_sets.example.csv
```

Both write `coverage_candidates.csv` (override with `--out`): one row per `(pair_id, pmcid)`
match, `same_paragraph` rows sorted before `doc_level_only`, with the matched terms and a
400-character snippet so you can eyeball relevance without opening the XML.

Runs in a few seconds per term set against the full 7,863-article corpus (multiprocessed across
CPU cores; `--workers` to override, default is `os.cpu_count()`).

### Test it

```
python test_find_coverage.py
```

Synthetic 5-article corpus built fresh per run, covers the word-boundary regex behavior
(`BRCA1` must not match inside `subBRCA1xyz`), the `same_paragraph` vs `doc_level_only`
classification, a manifest row whose XML is missing on disk, and both CLI modes end to end via
subprocess (exercises the real multiprocessing path, not a mock of it).

## hold_out_case.py

The mechanical half of negative-case construction (property 4). Given a verified-complete list of
PMCIDs covering a narrow variant-condition pair, moves their XML out of `../corpus/xml/` into
`held_out/xml/` and records the move in `held_out/held_out_pmcids.csv`. Does **not** touch
`corpus/manifest.csv`, the Step 0b pull's immutable reproducibility record.

**This tool trusts you (or the agent invoking it) to have already verified completeness with
`find_coverage.py`.** It has one built-in safety check: a PMCID already held out under a different
`pair_id` is refused, not silently reassigned, so a held-out article always has exactly one owning
negative case.

```
python hold_out_case.py --pair-id palb2_pancreatic --gene PALB2 --condition "pancreatic cancer" \
    --pmcid PMC1234567 --pmcid PMC7654321

python hold_out_case.py --list                              # see everything currently held out
python hold_out_case.py --pair-id palb2_pancreatic --restore  # undo, fully reversible
```

Tests: `python test_hold_out_case.py` (19 assertions: hold-out, idempotency, cross-pair conflict,
a missing source file, restore, all via the real CLI).

## The eval case format

`answer_cases.example.jsonl` is the target schema, worked examples, one JSON object per line.
`answer_cases.jsonl` is the canonical, real file: 12 cases as of 2026-09-01 (4 disagreement, 8
negative), verified
(see `docs/DECISION_LOG.md`). Fields:

| Field | Meaning |
|---|---|
| `case_id` | unique string |
| `stratum` | `"evidence"` or `"methods_extraction"` |
| `is_negative_case` | true only for property-4 cases (empty `gold_spans`, populated `held_out_pmcids`) |
| `gene`, `variant`, `condition` | the subject of the query; `variant` optional |
| `query` | free text, as a user would type it |
| `gold_spans` | list of `{pmcid, section, char_start, char_end}`, the `(pmcid, section_id, char_start, char_end)` schema `CLAUDE.md` requires. Empty for negative cases. |
| `gold` | stratum-dependent. Evidence: `{direction, strength, has_disagreement, disagreement_note, expected_not_found}`. Methods-extraction: `{parameter, expected_value}`. |
| `held_out_pmcids` | for negative cases only, must match `held_out/held_out_pmcids.csv` exactly |
| `notes`, `created_by`, `created_at_utc` | provenance; `created_by` is `"user"` or `"agent:<name>"` so you can tell which cases need a second read |

Row 1 in the example file is real, verified data (matches the actual Step 0c smoke-test output
for `PMC6896150`). Rows 2-4 are explicitly marked `TEMPLATE`, placeholders showing the shape, not
cases to ship as-is; row 3 in particular predates the `find_coverage.py` gene/variant matching
fix below and should not be treated as a model of how many articles a real negative case holds
out (see the warning below, it should usually be far fewer than that template implies).

## Handing this to another agent

**Isolate your output.** If more than one agent is working in `eval/` at once, write to your own
file (e.g. `answer_cases.<your-task>.jsonl`), not directly to the shared `answer_cases.jsonl` or
`held_out/held_out_pmcids.csv`. Whoever is coordinating merges the isolated files in afterward.
Writing straight to the shared files caused a coordination failure once already (2026-09-01, see
`docs/DECISION_LOG.md`): no data was lost that time, but nothing stopped it from happening.

If you're an agent picking up **disagreement-pair discovery** (property 3): run `find_coverage.py`
for your candidate pairs first, then read the `same_paragraph` rows' snippets (open the full
article by `pmcid` in `../corpus/xml/` if a snippet alone isn't enough context) and judge whether
any two articles actually conflict, not just whether they both mention the pair. A shared topic is
not a disagreement. Write results as rows matching the schema above (`stratum: "evidence"`,
`gold.has_disagreement: true`, `gold.disagreement_note` stating precisely what the two sources
disagree about, ideally with a short quote from each), not a bare PMCID list, so the disagreement
itself is checkable by whoever reviews the case next. Set `created_by` to `"agent:<your name>"`.

If you're an agent picking up **negative-case construction** (property 4): pick a *narrow* pair, a
specific variant, not a whole gene. Give `find_coverage.py` every notation form you know for that
variant (cDNA HGVS, protein HGVS, rsID, legacy naming) as separate `--variant` entries, it needs
the exact notation to match. Watch for the `[WARN]` banner: if a pair's `same_paragraph` count
exceeds `--warn-threshold` (default 20), **do not proceed to `hold_out_case.py`**, narrow the pair
and re-run. Only once the candidate list is small enough that you've actually read every row and
are confident it's complete, run `hold_out_case.py` with that verified PMCID list, and write the
case (`is_negative_case: true`, `gold_spans: []`, `gold.expected_not_found: true`,
`held_out_pmcids` matching the registry exactly, and `notes` stating which variant notations you
searched, so a reviewer knows what "verified complete" actually covered).
