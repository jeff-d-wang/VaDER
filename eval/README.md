# eval/

The evaluation harness: the eval set, the scorer and its judge, the baselines, and the tooling
that keeps the gold labels honest.

**Everything here runs as a module from the repo root**, not as a script from this directory:

```
python -m eval.score --answers runs/bm25_only_answers.jsonl --judge groq
python -m unittest discover             # every test in the project
```

## Layout

| Path | What it is |
|---|---|
| `data/` | the eval set itself: `answer_cases.jsonl`, the dev/held-out split, the touch log |
| `score.py`, `judge.py`, `labels.py` | the scorer, the LLM judge behind groundedness and disagreement, and the controlled vocabulary that grades direction/strength in code |
| `split.py` | dev/held-out enforcement, with a touch log that makes exposure visible |
| `baselines/` | the generators the scorer grades: no-retrieval, BM25-only, oracle-span. `_runner.py` holds the shared prompt and citation mapping |
| `benchmarks/` | SciFact and NFCorpus, for checking the harness against known-good labels |
| `find_coverage.py`, `hold_out_case.py`, `mine_rare_variants.py` | building cases |
| `verify_spans.py`, `check_gold_claims.py`, `verify_negative_cases.py` | keeping answer cases honest |
| `build_retrieval_set.py`, `score_retrieval.py`, `verify_retrieval_set.py` | the phase C retrieval set: build it, score a retriever on it, keep it honest |
| `make_case_worksheet.py` | putting cases in front of a human to validate |
| `kappa.py` | judge calibration statistic |
| `compare_runs.py` | paired McNemar between two scored runs |
| `held_out/` | articles physically removed from the corpus to make negative cases true |
| `runs/`, `_archive/` | generated outputs (git-ignored); retired cases kept for the trail |

Retrieval itself lives in `retrieval/`, not here: eval measures retrieval, and the dependency runs
one way. Corpus access (XML to text, sections, char offsets) lives in `common/`.

**Four checks worth running after touching either eval set**, all fast:

```
python -m eval.verify_spans            # do gold spans resolve, and are they about the right variant
python -m eval.check_gold_claims       # does a gold label assert numbers its spans don't contain
python -m eval.verify_negative_cases   # are the negative cases still negative
python -m eval.verify_retrieval_set    # does the retrieval set still point at the text it was built on
```

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
python -m eval.find_coverage --pair-id brca1_hboc --gene BRCA1 \
    --condition "breast cancer" --condition "ovarian cancer" --condition HBOC
```

Many pairs in one corpus pass, cheaper than looping the corpus once per pair since every article
is parsed once and tested against all term sets (see `term_sets.example.csv` for the format):
```
python -m eval.find_coverage --term-sets-csv term_sets.example.csv
```

Both write `coverage_candidates.csv` (override with `--out`): one row per `(pair_id, pmcid)`
match, `same_paragraph` rows sorted before `doc_level_only`, with the matched terms and a
400-character snippet so you can eyeball relevance without opening the XML.

Runs in a few seconds per term set against the full 7,863-article corpus (multiprocessed across
CPU cores; `--workers` to override, default is `os.cpu_count()`).

### Test it

```
python -m eval.tests.test_find_coverage
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
python -m eval.hold_out_case --pair-id palb2_pancreatic --gene PALB2 --condition "pancreatic cancer" \
    --pmcid PMC1234567 --pmcid PMC7654321

python -m eval.hold_out_case --list                              # see everything currently held out
python -m eval.hold_out_case --pair-id palb2_pancreatic --restore  # undo, fully reversible
```

Tests: `python -m eval.tests.test_hold_out_case` (19 assertions: hold-out, idempotency, cross-pair conflict,
a missing source file, restore, all via the real CLI).

## The eval case format

`answer_cases.example.jsonl` is the target schema, worked examples, one JSON object per line.
`answer_cases.jsonl` is the canonical, real file: **17 cases as of 2026-09-04** (4 disagreement, 6
negative, 7 ordinary evidence), 12 dev / 5 held-out.

**Read `docs/DECISION_LOG.md`'s two phase A1 entries before trusting or extending this file.** A
human validation pass over 8 of the previous 19 cases found 4 defective. Three were repaired
against source, one was retired as invalid, and all 7 remaining search-built negative cases were
retired and replaced by 6 built by hold-out. The set is smaller than it was and much further from
`PROJECT_PLAN.md`'s 50-80 target, which the v4 audit already judged the right direction: the
n>=300 retrieval set is the better use of hours, and a smaller set that is right beats a larger
one that is half wrong. Fields:

| Field | Meaning |
|---|---|
| `case_id` | unique string |
| `stratum` | `"evidence"` or `"methods_extraction"` |
| `is_negative_case` | true only for property-4 cases (empty `gold_spans`, populated `held_out_pmcids`) |
| `gene`, `variant`, `condition` | the subject of the query; `variant` optional |
| `query` | free text, as a user would type it |
| `gold_spans` | list of `{pmcid, section, char_start, char_end}`, the `(pmcid, section_id, char_start, char_end)` schema `CLAUDE.md` requires. Empty for negative cases. |
| `gold` | stratum-dependent. Evidence: `{direction, strength, strength_detail, qualifier, has_disagreement, disagreement_note, expected_not_found}`. `direction` and `strength` are **closed vocabularies** (see `labels.py`); `strength_detail` and `qualifier` are free text and **not scored**. Methods-extraction: `{parameter, expected_value}`. |
| `earliest_evidence_year` | derived by `strata.py` from the Step 0b manifest: the earliest year among the articles the answer rests on. Used for date stratification. |
| `held_out_pmcids` | for negative cases only, must match `held_out/held_out_pmcids.csv` exactly |
| `notes`, `created_by`, `created_at_utc` | provenance; `created_by` is `"user"` or `"agent:<name>"` so you can tell which cases need a second read |

Row 1 in the example file is real, verified data (matches the actual Step 0c smoke-test output
for `PMC6896150`). Rows 2-4 are explicitly marked `TEMPLATE`, placeholders showing the shape, not
cases to ship as-is; row 3 in particular predates the `find_coverage.py` gene/variant matching
fix below and should not be treated as a model of how many articles a real negative case holds
out (see the warning below, it should usually be far fewer than that template implies).

**Gold spans get verified against the source, not trusted on sight.** A `gold_span`'s
`char_start`/`char_end` is a claim, "this exact range supports this quote," and round-number
offsets (`0:305`, `950:1450`) are the signature of a guess, not a measurement. Run
`python -m eval.verify_spans [--fix]` after adding any case whose `disagreement_note` quotes a source:
it searches the real article text for each quoted phrase (tolerant of whitespace and curly-quote
drift, falling back to individual sentences if the whole quote doesn't match byte-exact) and
rewrites the offsets to where the quote actually is, widened to the containing paragraph. A span
whose note has no literal quote to check is reported as `NO_QUOTE_TO_VERIFY` and left alone, that
needs a human to locate and confirm by hand (see `corpus_text.py`'s `extract_section_text`, and
`docs/DECISION_LOG.md`, "Gold-span verification found guessed offsets").

## score.py: the scorer

Grades a *system answer* against `answer_cases.jsonl` per the rubric in `docs/DECISION_LOG.md`
("Answer-set scoring rubric" and "M1 scorer architecture" entries): four pass/partial/fail
sub-scores for evidence cases (direction/strength, groundedness, surfaces disagreement,
says-not-found), two for methods_extraction cases (parameter accuracy, citation). It never talks
to a live system; it grades a JSONL of already-generated answers against the schema below.

### The system-answer schema

One JSON object per `case_id`, own file, e.g. `runs/no_retrieval_answers.jsonl`:

```json
{"case_id": "chek2_1100delc_prognosis_disagree_001",
 "direction": "mixed, worse in older cohorts vs. no difference in modern-treatment cohort",
 "strength": "moderate",
 "not_found": false,
 "answer_text": "Older studies (PMC4150261) found ... but a 2026 study (PMC12702395) found no significant difference, attributing this to modern treatment ...",
 "claims": [
   {"text": "CHEK2 1100delC carriers had higher contralateral breast cancer rates",
    "cited_pmcid": "PMC4150261", "cited_section": "abstract", "cited_char_start": 1283, "cited_char_end": 1539}
 ]}
```

`claims` is what groundedness (property 2) scores: each claim's cited span is pulled from the real
XML via `corpus_text.load_span_text` and checked against the claim text. A claim whose citation
doesn't resolve (missing file, offsets out of range) counts as unsupported, not a crash. An answer
with no claims at all fails groundedness outright (`note: "empty_claims"`), not silently N/A: no
citations is not neutral, it's the specific failure this property exists to catch. For
`methods_extraction` cases, use `parameter_value` and `cited_pmcid` instead; `gold.expected_value`
and `gold.expected_pmcids` are what they're checked against.

### Judges

`--judge fake`: no network, deterministic word-overlap grading. Only for testing the scorer's own
logic (bucket thresholds, N/A handling), see `eval/test_score.py`. Not a real evaluation.

`--judge groq`: the real judge, Groq's free tier (`llama-3.3-70b-versatile`, matching the model
already decided in `docs/DECISION_LOG.md`). Needs `GROQ_API_KEY` in the environment (free key at
https://console.groq.com/keys); fails loudly at construction if it's missing rather than silently
using the fake judge.

### Usage

```
python -m eval.score --answers runs/no_retrieval_answers.jsonl --judge groq --out runs/no_retrieval_scores.json
```

Prints each property's `n` / pass / partial / fail / pass_rate, N/A cases excluded from `n` rather
than counted against the score. No single blended per-case verdict, by design, see the rubric
decision's own reasoning against a holistic score.

### baselines/no_retrieval.py

The first of `PROJECT_PLAN.md` M1's three required baselines: answers each evidence-stratum query
from the model's parametric knowledge alone, no corpus context in the prompt. `claims` is always
empty (there's no retrieval step to cite from), so it fails groundedness by construction, that's
the measurement, not a bug: it's the "how much does retrieval buy you over the model alone, and
how much of that is memorization" question `PROJECT_PLAN.md` names explicitly. Needs
`GROQ_API_KEY`. Writes an answers JSONL plus a `.meta.json` (model, prompt version, git SHA)
alongside it.

```
python -m eval.baselines.no_retrieval --out runs/no_retrieval_answers.jsonl
```

### bm25.py: hand-built retrieval for the second baseline

Okapi BM25 from scratch, no ranking library (see `docs/DECISION_LOG.md`, "BM25-only baseline,
hand-built"). Indexes every abstract/body paragraph in the corpus with real
`(pmcid, section, char_start, char_end)` provenance, same offset convention as `corpus_text.py`.
Build once, reuse:

```
python -c "
import csv
from pathlib import Path
from retrieval.bm25 import build_index
pmcids = [r['pmcid'] for r in csv.DictReader(open('corpus/manifest.csv'))]
build_index(Path('corpus/xml'), pmcids).save(Path('eval/runs/bm25_index.pkl'))
"
```

Takes about 35 seconds over the full 7,863-article corpus (344,900 paragraphs), single-process. The
resulting `.pkl` is about 575 MB, git-ignored under `eval/runs/`, rebuild rather than expect it to
already exist.

**Rebuild it after any change to `common/corpus_text.py`, and do not trust one you did not build.**
The index is a cache, and an audit of code does not reach a cache. The pickle in place until
2026-09-05 held 436,834 records built by a `"\n"`-join/split round trip that treated JATS line
wrapping inside a `<p>` as a paragraph boundary, so it was an index of **sentence fragments**:
2,273 of them for one article the current extractor reads as 186 paragraphs. Nothing caught it for
fourteen hours because the fragments' offsets were *correct*, so every offset check in the repo
passed. `score_retrieval.py` now refuses to report a number when a gold span is missing from the
index it was handed, which is the check that finally found it. `baselines/bm25_only.py --index runs/bm25_index.pkl --out runs/bm25_only_answers.jsonl`
retrieves top-8 paragraphs per query and asks the model to answer from only those, citing them by
index, mapped back to real spans before scoring, same schema and scorer as `no_retrieval.py`.

### compare_runs.py: paired comparison between two score.py runs

`RESULTS.md`'s own rule: comparisons are paired, not two marginal rates. Runs McNemar's exact test
per property on binary pass/not-pass (partial counts as not-pass):

```
python -m eval.compare_runs --a runs/no_retrieval_scores.json --b runs/bm25_only_scores.json \
    --label-a no_retrieval --label-b bm25_only
```

Reusable for any future two-config comparison (M3 retrieval, M6 chunking ablations, ...), not
specific to these two baselines.

### A free-tier limit you'll hit running any of the above

Groq's free tier caps `openai/gpt-oss-120b` at roughly 8,000 tokens/minute. Running the judge over
even 19 cases (multiple grading calls per case) plus a baseline generation pass in the same session
hits it routinely. `llm_client.groq_chat_json` retries on 429 automatically (reads the server's own
`Retry-After` header, up to 5 attempts), so a run just gets slower under load, it doesn't fail; if
you see `[rate limited, waiting Ns]` lines on stderr, that's expected, let it finish.

### split.py: dev/held-out, enforced not just documented

`PROJECT_PLAN.md`'s rule: hold out roughly a third of the answer set from day one, touched at most
three times across the whole project, so a small set run repeatedly over months doesn't quietly
become a training set. `dev_held_out_split.csv` (committed, source of truth) assigns each case,
stratified by type (disagreement/negative/ordinary) and seeded, so the held-out third isn't
accidentally all-one-type at small n:

```
python -m eval.split assign --seed 0   # one-shot; re-run later to place newly-added cases only
python -m eval.split list              # see assignments and the current touch count
```

`score.py` defaults to `--held-out exclude` (dev split only, currently 13 of 19 cases), the safe
default. Using `--held-out include` or `--held-out only` requires `--touch-reason "..."` and
appends a row to `held_out_touches.csv` (also committed, the audit log), printing a warning if the
count exceeds 3. Don't run the held-out split casually, this cost is real: once an answer to a
held-out case has been seen, that exposure can't be un-seen.

### ir_metrics.py: retrieval metrics, hand-written

recall@k, MRR, nDCG@k, and a query-level percentile bootstrap CI. No IR library, same rule
`bm25.py` was built under. The module docstring writes out each definition and the two choices
that matter: a query with no relevant documents is **undefined** for recall and nDCG (dropped from
the mean, not scored 0 or 1, either of which would misreport a query no system could answer), and
unjudged retrieved documents count as gain 0, the standard BEIR treatment. `evaluate()` returns
every metric with its own CI and its own `n`, because those `n`s differ.

Tests (`python -m retrieval.tests.test_ir_metrics`, 20 assertions) check the nDCG worked example against arithmetic
written out by hand in the test docstring, not against another implementation's output. A test that
asserts "matches whatever the library said" would defend nothing, which is the point of hand-writing
the module at all.

### benchmarks/run_benchmark.py: is the harness broken?

`PROJECT_PLAN.md` M1's first instruction, and the one that had been skipped: run the harness
against free labeled data before trusting it on your own. Points `bm25.py` at a BEIR benchmark via
`loader.py` and scores it with `ir_metrics.py`, printing each metric against the published
Pyserini BM25 reference and against a bug threshold (60% of reference) registered in
`docs/DECISION_LOG.md` before the first run.

```
python -m eval.benchmarks.run_benchmark --dataset scifact --out ../runs/scifact_bm25.json
python -m eval.benchmarks.run_benchmark --dataset nfcorpus --limit-queries 20   # smoke test, refuses to write output
```

Both datasets run in a few seconds. Result (2026-09-03): nDCG@10 at 89-90% of the published
reference on both, well clear of the bug threshold. Full numbers and the sub-prediction that missed
are in `docs/RESULTS.md` and `docs/DECISION_LOG.md`.

### make_case_worksheet.py: validating the cases themselves

Not judge calibration. Kappa asks whether the judge grades like a human; this asks the question
underneath it, **is the gold label right at all**. Every case in `answer_cases.jsonl` carries
`created_by: agent:*` and none had been read by a person, so both the judge and any human rater
were grading against unchecked ground truth.

```
python -m eval.make_case_worksheet --n 8 --seed 0 --out case_worksheet.md
# a person fills in the verdict/why lines
python -m eval.make_case_worksheet --summarize case_worksheet.md
```

Samples stratified by case type (taking at least one of each before filling up, so a small `n`
cannot skip the negative and disagreement cases, which are the ones most likely to be subtly
wrong), dev split only by default. Renders each gold span's **full** source text: truncating span
display is exactly the bug that contaminated the first kappa pass, and `test_make_case_worksheet.py`
regression-tests against it. For negative cases there is no span, so it renders the case's own
completeness claim and asks whether the notation sweep was wide enough to believe.

The worksheet is git-ignored. The durable record of a validation pass is a `DECISION_LOG.md` entry
plus `validated_by` / `validated_at_utc` written back onto the cases themselves, next to
`created_by`.

### check_gold_claims.py: does the gold label assert numbers its spans don't contain?

The deterministic half of catching **citation drift**, the failure mode the phase A1 validation
pass found in the gold set: a label asserting something more specific than, or misattributed
relative to, the span recorded next to it. Two of the four defects were purely numeric (gold
asserted cohort figures that sat in the same abstract but outside the cited span), and those are
catchable with arithmetic: pull every number out of `gold.direction` + `gold.strength`, pull every
number out of the text the gold spans point at, report the difference.

No LLM, no judgment. Variant notations and gene symbols are stripped first, since `c.7570G>C` and
`BRCA1/2` carry digits that are positions and names, not findings. It is a **precision** tool: a
missing number is strong evidence of a real problem, a clean result only means the numbers line
up. `brca_prs_ovarian_risk_ord_001`'s other defect, attributing a BRCA2-only finding to both
genes, involves no numbers and this cannot see it.

```
python -m eval.check_gold_claims
python -m eval.check_gold_claims --case-id brca_prs_ovarian_risk_ord_001
```

### verify_negative_cases.py: are the negative cases still negative?

Negative cases are now built by **hold-out**, not by failed search (see `docs/DECISION_LOG.md`,
"negative cases rebuilt by hold-out"). The old method asserted absence from a search that found
nothing, which is not proof: notation space is unbounded and prose descriptions escape any
notation list. One case built that way asserted an absence three corpus articles contradicted.

Each rebuilt case names a variant that appeared in exactly one corpus article, and that article is
held out, so absence is true by construction. This script confirms the construction still holds:
the notation appears in zero remaining articles, the claimed held-out article is in the registry
and gone from the corpus, and the case is marked `construction: hold_out` at all. About 9 seconds
over the full corpus.

```
python -m eval.verify_negative_cases
```

It cannot prove no article discusses the same variant under a different name; no keyword method
can. That is exactly why hold-out rather than search is what makes these cases sound, and this
script is a regression guard on the construction, not a proof of absence.

### mine_rare_variants.py: finding hold-out candidates

The provenance of the current negative cases, kept in the repo so their "document frequency 1"
claim is reproducible rather than asserted. Scans every paragraph that mentions a condition, pulls
out HGVS notations, and reports those appearing in at most `--max-df` articles.

```
python -m eval.mine_rare_variants --max-df 1
python -m eval.mine_rare_variants --max-df 2 --condition "ovarian cancer" --out candidates.csv
```

**The `gene?` column is a hint, not a finding.** The first version of this script assigned each
variant the first gene symbol in the paragraph, and 4 of 8 shortlisted candidates turned out
misattributed (`c.2502_2503insA` is ATM not BRCA2, `c.1919C>A` is PMS2 not PALB2). Attribution is
now nearest-preceding-symbol within 60 characters, with the distance reported so a weak match is
visible, and `test_mine_rare_variants.py` pins all four real misattributions as regressions. It is
still a hint: read the source for any candidate before building a case on it.

### labels.py: the direction and strength vocabularies

`direction` and `strength` are **closed vocabularies graded in code, not by a judge** (since
2026-09-05; see `docs/DECISION_LOG.md`, "direction property redesign").

| Field | Values |
|---|---|
| `direction` | `increased`, `decreased`, `none`, `mixed` — exact match, no partial credit |
| `strength` | `high`, `moderate`, `low`, `none`, `disputed`, `unstated` — one tier off on low<moderate<high is `partial`, everything else is `fail` |

Why it changed: gold used to be free text, and eleven evidence cases carried nine distinct
`direction` strings (`'mixed'` and `'mixed_evidence'` being the same concept twice) while four
`strength` values contained no strength at all, just cohort descriptions and bare percentages. A
finding was published off that property and then withdrawn. Removing the judge here also ends the
same model grading its own output on the two properties where that mattered most; the judge still
handles groundedness and disagreement, where free text has to be read.

**Two rules the strength labels follow**, both learned the hard way in the 2026-09-05 review that
found 45% of the first pass wrong:

1. **`disputed` means the sources conflict on *magnitude*, not on direction.** If no source reports
   an effect size, they cannot conflict about it, and the value is `unstated`. Direction-level
   disagreement is already carried by `direction: mixed` and the disagreement property.
2. **Strength is read at the granularity the query asks about.** A gene-level query takes the
   source's gene-level claim; a variant-level query takes that variant's reported effect. Numbers
   at the other granularity belong in `strength_detail`. See `docs/DECISION_LOG.md`, "strength is
   matched to the granularity of the query", including the cost of the rule.

Also worth stating because it caused two of the five errors: a **prevalence is not an effect size**
(4-7% of patients carrying a mutation says nothing about magnitude, so that is `unstated`), and a
pair of raw percentages needs the **ratio computed** before it is placed on the scale (67-83% vs
16-25% is roughly 3-4x, which is `moderate`, not `high`).

The detail that used to be crammed into `strength` now lives in two **unscored** fields:
`strength_detail` (odds ratios, prevalences, cohort sizes) and `qualifier` (modifiers like
"HER2-positive subtype specifically" or "prognostic, not susceptibility"). They are preserved for a
human reader and for `check_gold_claims.py`, which scans `strength_detail` but deliberately not
`qualifier`, since the years and subtype names in a qualifier are not quantitative claims.

**Read every direction number against the majority-class baseline.** The set is currently 8 of 11
`increased`, so a system that always answers "increased" scores 73%. `score.py` prints that
baseline under the direction line so the number cannot be quoted without it. The fix is more
`none`, `decreased` and `mixed` cases, not a different metric.

### baselines/oracle_spans.py: perfect retrieval, as a control

Phase A3. Supplies exactly the case's gold spans as context, so retrieval is perfect by
construction, with the same model, prompt shape and citation mechanism as `bm25_only`. The only
variable between the two runs is which passages reached the model.

It stands in for `PROJECT_PLAN.md`'s whole-document-in-context baseline, which is blocked on Groq's
free tier: gold articles run 3k-20k tokens against a hard 8,000 TPM per-request ceiling, and a
probe returned HTTP 413. See `docs/DECISION_LOG.md` for the measurement and the alternatives.

```
python -m eval.baselines.oracle_spans --out eval/runs/oracle_spans_answers.jsonl
python -m eval.score --answers eval/runs/oracle_spans_answers.jsonl --judge groq --out eval/runs/oracle_spans_scores.json
python -m eval.compare_runs --a eval/runs/bm25_only_scores.json --b eval/runs/oracle_spans_scores.json \
    --label-a bm25_only --label-b oracle_spans
```

Result: groundedness and refusal go to 100%, and **direction does not move at all** (3/8 both
ways), so retrieval is not what limits the direction score. Read the correction in
`docs/RESULTS.md` before going further than that sentence: an initial reading of *why* direction
fails was withdrawn on 2026-09-05, because most of those failures turned out to be artifacts of an
under-specified direction property rather than reading failures.

### strata.py: date stratification

`docs/RESULTS.md` requires the no-retrieval baseline to always be reported per date-stratum,
because PMC full text is in every model's pretraining and a good no-retrieval score may just be
memorization. This derives each case's `earliest_evidence_year` from the immutable Step 0b manifest
and reports the split.

```
python -m eval.strata                # report the distribution
python -m eval.strata --annotate     # write earliest_evidence_year into the cases
```

A case's year is the **earliest** article its answer rests on, not the latest: if any supporting
article predates the cutoff, memorization is possible, so a case is post-cutoff only when
everything it rests on is. The cutoff is a parameter, not a hardcoded claim; `gpt-oss-120b`'s
training cutoff is not published anywhere citable.

On the current set the post-cutoff stratum holds **1 case**, so the rule is not computable and the
tool says so rather than printing a rate. Growing the answer set should deliberately target
post-2024 articles until that stratum reaches 5.

### kappa.py: judge calibration

`PROJECT_PLAN.md` M1: "Measure Cohen's kappa between judge and you on a sample... If kappa comes
back low, the rubric is underspecified, not the judge." `kappa.py` is the hand-built statistic:
unweighted and linearly-weighted Cohen's kappa, weighted because the rubric's pass/partial/fail
scale is ordinal, so a pass-vs-partial miss should count less than pass-vs-fail. Feed it two
same-order lists of verdicts.

The worksheet generator and worksheet parser that used to sit alongside it were deleted
2026-09-05. Two of the four properties they calibrated (`direction`, `strength`) are now graded in
code by `labels.py` and have no judge left to calibrate, the human calibration is deliberately
skipped for M1 (`docs/DECISION_LOG.md`), and `make_case_worksheet.py` already renders and parses
worksheets of both shapes. Recover them from git history if a real person sits down to rate.

## The retrieval set (phase C)

`data/retrieval_cases.jsonl`, built by `build_retrieval_set.py` and scored by
`score_retrieval.py`. This is `PROJECT_PLAN.md`'s **n>=300 `retrieval` set**, the one every
retrieval ablation from phase D on gets measured against. The answer set cannot do that job: at
n=8 on the scored properties one case is 12.5 points, and a chunker or a reranker moves recall by
three.

**One paragraph, two queries.** Each sampled corpus paragraph goes to the model once and comes
back as *anchors* plus two queries about the same fact: a `lexical` one phrased in the paragraph's
own wording, and a `paraphrased` one saying it differently. Both rows carry the same
`paragraph_id` and the same gold span, so the pair is a paired comparison and the lexical bias
this construction is known to have becomes a measured gap instead of a caveat. The anchors are
held **verbatim** in both, so the contrast isolates prose wording; varying the identifier form
(`c.1100delC` against `1100delC` against an rsID) is phase D's exact-identifier case, deliberately
separate.

| Field | Meaning |
|---|---|
| `query_id`, `paragraph_id`, `style` | `paragraph_id` joins the pair; `style` is `lexical` or `paraphrased` |
| `query` | what the retriever is given |
| `gold_span` | `{pmcid, section, char_start, char_end}`, the paragraph itself, per standing rule 5 |
| `stratum`, `section_title` | `abstract`, `intro`, `methods`, `results`, `discussion`, `body_other`, and the raw JATS `<sec>` title it was derived from |
| `pub_year`, `anchors`, `gold_text_chars` | from the Step 0b manifest; the anchors the filters checked; paragraph length |
| `lexical_overlap` | share of the query's distinct tokens present in the gold paragraph. **This is the per-row lexical-bias number.** 1.0 means BM25 was handed the answer |
| `created_by`, `model`, `validated_by` | provenance. `validated_by` stays null until a person has read the row in a worksheet |

**Three things to know before reading a number off this set.**

1. **It is section-balanced, not corpus-proportional.** Equal quotas per stratum, so methods is
   reportable on its own. No row here is "recall on this corpus"; it is recall on a
   section-balanced probe of it.
2. **Judgments are single-gold.** Another paragraph may answer a query as well as the gold one and
   scores as a miss. `score_retrieval.py --measure-holes N` measures how often, with a CI. Recall
   off this set is a lower bound by roughly that much.
3. **The queries were written by a model looking at the answer.** That is the whole lexical-bias
   problem, and `--calibrate-overlap` puts our overlap distribution next to SciFact's and
   NFCorpus's human-written queries so the number has a reference point.

```
python -m eval.build_retrieval_set --limit 4 --out runs/smoke.jsonl   # smoke test, 4 paragraphs
python -m eval.build_retrieval_set                                    # the real build, resumable
python -m eval.build_retrieval_set --calibrate-overlap                # overlap vs BEIR queries
python -m eval.build_retrieval_set --worksheet 20                     # the hand spot-check
python -m eval.make_case_worksheet --summarize retrieval_worksheet.md # ... once it is filled in
python -m eval.score_retrieval --out runs/retrieval_bm25.json --measure-holes 40
```

**The build is slow and that is the free tier, not the code.** Groq caps this key at 8,000 tokens
per minute, so a few hundred generation calls take hours. It is resumable by design: rows are
flushed as they are accepted and a rerun skips paragraphs already in the output file, so an
interrupted build costs nothing but the call in flight.

**`verify_retrieval_set.py` is the standing check**, and it is not the same thing as the
build-time filters. Those run once, against the model's output, and never again. This one re-checks
the file against the corpus as it is now: every gold span still resolves to the same text (by
content **hash**, not length, because a span is read by slicing and a same-length edit inside it
would otherwise be invisible), every anchor is still in the paragraph and in both queries, every
stored `lexical_overlap` still recomputes to its stored value (it depends on the BM25 tokenizer,
so a tokenizer change silently invalidates every one of them), pairs are complete, and no row
cites a held-out article. It also warns when one article supplies many paragraphs, because those
queries are correlated and the per-query bootstrap CI assumes they are not.

**It is not validated until a person has read some of it.** `--worksheet 20` renders paragraphs
with both their queries and the real source text, for the review `PROJECT_PLAN.md`'s phase C asks
for. The mechanical filters can prove an anchor came from the paragraph; they cannot tell whether
the query is one anyone would ask. Unreviewed agent-written labels have run about 50% defective
twice in this project, so treat every number off this set as provisional until that sheet is
filled in.

## TODO: growing the answer set

**Not started, and deliberately not started.** The set is 17 cases against `PROJECT_PLAN.md`'s
50-80 target, and n=8 on the scored properties means one case is 12.5 points. That is the obvious
thing to fix and it is the wrong thing to fix next, because the binding constraint here is label
correctness, not count.

**The measured base rate for unreviewed labels in this project is about half.** Agent-built gold,
phase A1: 4 of 8 defective. The strength labels an agent assigned on 2026-09-05: 5 of 11 wrong.
Two corrected labels out of eight then flipped a published conclusion. **A larger set of unreviewed
labels is strictly worse than the small reviewed one.** Label error does not average out with n the
way sampling error does: a systematic mistake ("a prevalence is an effect size") repeats on every
case that shares its shape.

So: grow the set only in a session where a human is also reviewing. When you do:

1. **Target the gaps, not the easy cases.** Two composition requirements are already measured:
   - **Class balance.** Direction gold is currently 8 `increased` to 3 `mixed`, so the
     majority-class baseline is 75% and a system that always answers "increased" beats both real
     retrieval baselines. Build `none` and `mixed` cases. `eval/runs/polarity_candidates.csv` has
     84 mined candidates, high recall and low precision, and a caveat worth reading first: most
     `decreased` hits are about modifiers (parity, oophorectomy, early pregnancy) rather than the
     variant, so `decreased` may be close to unpopulatable in a corpus of cancer-predisposition
     genes. Prefer `none`; the clean ones there are PMC9501803 and PMC5200636.
   - **Date stratification.** Only 1 of 8 scored dev cases is post-2024, so `RESULTS.md`'s
     per-stratum rule is uncomputable and the memorization question stays unanswered. Sample
     post-2024 articles deliberately until that stratum reaches 5. `python -m eval.strata` reports
     where it stands. 1,569 corpus articles are post-2024, so the material exists.
2. **Write the case**, following "The eval case format" above and the `labels.py` vocabularies.
   Two rules that caused most of the known label errors: `disputed` means the sources conflict on
   *magnitude* (no effect size reported means `unstated`, not `disputed`), and strength is read at
   the granularity the query asks about.
3. **Run the three mechanical checks**, all fast:
   `python -m eval.verify_spans`, `python -m eval.check_gold_claims`,
   `python -m eval.verify_negative_cases`.
4. **Put it in front of a person.** `python -m eval.make_case_worksheet --focus strength` for the
   labels, plain `--focus case` for whole-case validity, then
   `python -m eval.make_case_worksheet --summarize <worksheet>`. A case is not usable until its
   labels have been reviewed; record that in `validated_by` / `strength_validated_by`, next to
   `created_by`, so a future reader can tell which cases were checked.
5. **Assign the split** with `python -m eval.split assign --seed 0`, which places new cases only.
6. **Re-run the baselines and supersede the rows** in `docs/RESULTS.md`. Changing the set changes
   every number computed against it.

Rough cost, from the two passes done so far: about 2 minutes of review per label, plus the
authoring time. The review is the part that cannot be delegated to an agent, which is the whole
reason this is a TODO and not a task an agent should quietly pick up.

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
