"""
Phase C: build the n>=300 `retrieval` eval set.

The answer set is 17 hand-checked cases and n=8 on the scored properties,
where one case is 12.5 points. Every retrieval ablation from phase D on
(chunker, dense, hybrid, reranker) turns on deltas of a few points, which
that set cannot see at all. This module builds the set that can.

Construction, decided in docs/DECISION_LOG.md, "the n>=300 retrieval eval
set, built as paired queries over sampled paragraphs", before any of this
was written:

  1. Sample paragraphs, seeded, from corpus articles minus eval/held_out/
     (those files are physically absent, so a query about them is
     unanswerable by construction). Bucket by section type and fill roughly
     equal per-stratum quotas.
  2. One LLM call per paragraph returns ANCHORS plus TWO queries: a
     wording-reusing one and a de-lexicalized paraphrase of the same fact.
  3. Mechanical filters reject the ways that call goes wrong.
  4. The paragraph's own source span is the gold label, per standing rule 5.

Two things this set is not, both worth knowing before reading a number off
it. It is **section-balanced, not corpus-proportional**: quotas are equal
per stratum so methods is reportable on its own, which means no row here is
"recall on this corpus". And its judgments are **single-gold**: another
paragraph may answer a query just as well and will score as a miss. The
size of that second problem is measured, not assumed, by
`eval.score_retrieval --measure-holes`.

Usage:
    python -m eval.build_retrieval_set --limit 4 --out runs/smoke.jsonl   # smoke test
    python -m eval.build_retrieval_set                                    # the real build
    python -m eval.build_retrieval_set --calibrate-overlap                # vs BEIR queries
    python -m eval.build_retrieval_set --worksheet 20                     # hand spot-check
    python -m eval.make_case_worksheet --summarize retrieval_worksheet.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

from common.corpus_text import (iter_paragraphs_from_root, load_span_text, parse_root,
                                section_titles_from_root)
from eval.llm_client import DEFAULT_MODEL, groq_chat_json
from eval.strata import load_manifest_years
from retrieval.bm25 import tokenize

EVAL_DIR = Path(__file__).parent
CORPUS_XML = EVAL_DIR.parent / "corpus" / "xml"
MANIFEST = EVAL_DIR.parent / "corpus" / "manifest.csv"
HELD_OUT = EVAL_DIR / "held_out" / "held_out_pmcids.csv"
DEFAULT_OUT = EVAL_DIR / "data" / "retrieval_cases.jsonl"

PROMPT_VERSION = "retrieval_qgen_v3"
# The free tier caps this key at 8,000 tokens per minute, and the default
# spends 730 of them per call on reasoning tokens for a task that is copying
# anchors out of a paragraph and writing two sentences. At "low" a call costs
# 799 tokens instead of 1,402, measured 2026-09-05, with no quality
# difference visible in the smoke output.
REASONING_EFFORT = "low"

# Equal quotas, not corpus proportions: see the module docstring. 55 x 6 = 330
# paragraphs, 660 paired queries, comfortably over the plan's n>=300.
STRATA = ("abstract", "intro", "methods", "results", "discussion", "body_other")
DEFAULT_QUOTA = 55

# First matching substring wins, so order matters: "statistical analysis" must
# be tested before a bare "analysis" would be, and "results and discussion"
# lands in results rather than discussion.
_TITLE_RULES = (
    ("introduction", "intro"), ("background", "intro"),
    ("statistical", "methods"), ("method", "methods"), ("material", "methods"),
    ("patients and", "methods"), ("study design", "methods"), ("data collection", "methods"),
    ("result", "results"), ("finding", "results"),
    ("discussion", "discussion"), ("conclusion", "discussion"), ("limitation", "discussion"),
)

# Sections that are not about the science and would produce a query no
# retriever should be asked to answer.
_EXCLUDE_TITLE = ("acknowledg", "funding", "conflict", "competing interest",
                  "author contribution", "availability", "abbreviation",
                  "supplementary", "ethic", "consent", "reference", "declaration")

MIN_TOKENS = 50     # under this a paragraph cannot carry two real anchors
MAX_TOKENS = 600    # over this it is not one retrievable unit
MIN_QUERY_TOKENS = 5
MAX_QUERY_TOKENS = 60
# Anchors are held verbatim in both query styles, so a long anchor is a long
# stretch of the paragraph's own wording that the paraphrase cannot vary. The
# first smoke run produced anchors like "recurrence following radiation" and
# "squamous cell carcinoma cohorts", which left the two styles nearly
# identical (overlap 0.86 against 0.79) and the contrast measuring almost
# nothing. Capped so de-lexicalization has prose to work on.
MAX_ANCHOR_WORDS = 4

# A human review of 20 paragraphs built by retrieval_qgen_v1 found 11 wrong
# (55%, 95% CI [34%, 74%]), with two systematic causes. Both are addressed by
# requiring an `answer_quote` and by the two constants below.
#
#   1. TAUTOLOGY (6 of 11). The anchor was the finding rather than an
#      identifier ("1663 amplicons", "64% of TNBC", "8-14%"), and since the
#      rules hold anchors verbatim in both queries, the question carried its
#      own answer: "How many amplicons were designed... specifically 1663
#      amplicons?" Caught now by MAX_ANSWER_IN_QUERY: if most of the answer's
#      tokens are already in the query, the query answers itself.
#   2. THE PARAGRAPH DOES NOT ANSWER (5 of 11). The query asked about the
#      topic the paragraph announces rather than anything it states: a
#      paragraph saying a systematic analysis "has been lacking" produced
#      "What is the role of RiboSis in cancer according to recent pan-cancer
#      analyses?" Caught now by requiring a verbatim answer_quote: a fact the
#      paragraph does not contain cannot be quoted from it.

# Share of the answer's tokens that may already appear in the query before it
# counts as answering itself.
#
# This works only because answer_quote is required to be the SHORTEST span
# that answers the question. A first version asked for a whole sentence and
# was useless: "We designed 1663 amplicons to cover the 159 kb target region"
# shares 82% of its tokens with the perfectly good question "How many
# amplicons were designed to cover the 159 kb target region?", because a
# sentence restates the question's own framing and only "1663" is the answer.
# Narrowed to "1663 amplicons", the good query shares 50% (it says
# "amplicons", not "1663") and the tautological one shares 100%.
MAX_ANSWER_IN_QUERY = 0.7
MAX_ANSWER_TOKENS = 12  # forces the shortest answering span, not its sentence

# A query must contain at least one term appearing in fewer than this many
# corpus paragraphs, or it cannot single out one paragraph even in principle
# and a miss against it says nothing about the retriever.
#
# The threshold is set on eval-validity grounds, not by tuning: 1,000 of
# 344,900 paragraphs is 0.3% of the corpus, and a query whose rarest term is
# commoner than that has at least a thousand equally-matching candidates.
# Measured recall@10 on the 2026-09-05 set, by the rarest term's document
# frequency: under 10 paragraphs 0.972, 10-100 0.860, 100-1000 0.802, and
# 1000-10000 0.562. The collapse in the last band is the single-gold
# assumption failing, not retrieval failing.
#
# NOTE, because it would be easy to misreport: filtering these out RAISES
# measured recall. That is a change in what is being measured, not an
# improvement in retrieval, and both numbers belong in any write-up.
MAX_RAREST_TERM_DF = 1000

QGEN_PROMPT = """You are building a retrieval evaluation set from biomedical literature.

Below is one paragraph from a cancer-genomics article. Write two search queries that this
paragraph, and ideally only this paragraph, answers.

First pick ANCHORS: 2 to 4 strings copied EXACTLY from the paragraph that say what the question
is ABOUT. Each anchor must be AT MOST 4 words, and shorter is better.

An anchor names a thing: a variant (BRCA2 c.9275A>G), a gene, an rsID, a named cohort, study,
assay or software, a named population or disease subtype.

An anchor is NEVER the finding itself. If the paragraph reports "1663 amplicons covered the
target region", then "target region" is an anchor and "1663 amplicons" is the ANSWER, not an
anchor. Do not use a count, percentage, effect size or result as an anchor unless it identifies
the study rather than answering it.

Then pick the ANSWER_QUOTE: the SHORTEST run of words copied EXACTLY from the paragraph that
answers the questions you are about to write. Usually a few words, not a sentence: for "how many
amplicons covered the region" the answer_quote is "1663 amplicons", not the whole sentence
around it. It must appear word for word in the paragraph above.

A finding does not have to be a number. A stated method, a definition, a described mechanism, a
named characteristic or a reported relationship all count, so long as the paragraph states it
rather than merely referring to it.

But if the paragraph only announces a topic, states an aim, or says that something "has been
studied", "shows promise" or "remains unknown" WITHOUT stating what was found, then it answers
nothing: return "answer_quote": "" and write no queries.

Then write two queries about the SAME fact from the paragraph:

- "lexical_query": phrased using the paragraph's own wording, the way someone would search
  after skimming it.
- "paraphrased_query": the same information need said differently, as someone would ask it who
  had never seen this paragraph. Use synonyms for every non-anchor word you can, change the
  sentence structure, change the register. Apart from the anchors themselves, it should share as
  few words with the paragraph as possible.

Rules, both queries must obey:
- A natural question or search phrase, 5 to 40 words.
- Answered by the answer_quote, from this paragraph alone.
- **The query must NOT contain its own answer.** Ask for the finding; do not state it. Write
  "How many amplicons covered the target region?", never "How many amplicons covered the target
  region, specifically 1663 amplicons?"

Paragraph:
\"\"\"{paragraph}\"\"\"

Respond with strict JSON:
{{
  "anchors": ["...", "..."],
  "answer_quote": "...",
  "lexical_query": "...",
  "paraphrased_query": "..."
}}"""


def load_cases(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def gold_text_digest(text: str) -> str:
    """Short content hash of a gold paragraph.

    The row already records the paragraph's length, and length is nearly
    useless as an integrity check: a span is read by slicing
    section_text[start:end], so it returns the recorded length whenever the
    section is at least that long. Append a sentence to the article and the
    slice silently returns different text of identical length. The hash is
    what actually says "this row still points at the text it was written
    against", which is standing rule 5's whole premise."""
    return hashlib.sha1(text.encode()).hexdigest()[:12]


# Biomedical XML is full of typographic variants of the same character, and
# the model reproduces whichever it saw. A real rejection was caused by the
# anchor "next-generation sequencing" carrying U+2011 (non-breaking hyphen)
# where the check had U+002D. Folded here rather than in common/corpus_text,
# whose _PUNCT_MAP exists to keep OFFSETS exact and must not grow entries
# that change string lengths.
_DASHES = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2212"})


def normalize(text: str) -> str:
    """Casefolded, whitespace-collapsed, dashes folded to ASCII, for the
    substring checks only. Never used to compute an offset."""
    return " ".join(text.lower().translate(_DASHES).split())


def classify_section(section: str, title: str | None) -> str | None:
    """The stratum a paragraph belongs to, or None if it should be skipped.

    Untitled body paragraphs fall to `body_other` rather than being dropped:
    plenty of articles put real content outside a titled <sec>, and a set
    that silently excluded them would flatter any retriever that happens to
    like well-structured articles."""
    if section == "abstract":
        return "abstract"
    if title is None:
        return "body_other"
    low = title.lower()
    if any(bad in low for bad in _EXCLUDE_TITLE):
        return None
    for needle, stratum in _TITLE_RULES:
        if needle in low:
            return stratum
    return "body_other"


def load_pmcid_pool(seed: int) -> list[str]:
    """Corpus pmcids minus the held-out articles, shuffled once with `seed`.
    Shuffled rather than sorted so the quota fill below walks a random slice
    of the corpus instead of the alphabetically first few hundred."""
    held_out = set()
    if HELD_OUT.exists():
        with open(HELD_OUT) as f:
            held_out = {row["pmcid"] for row in csv.DictReader(f)}
    with open(MANIFEST) as f:
        pmcids = [row["pmcid"] for row in csv.DictReader(f) if row["pmcid"] not in held_out]
    random.Random(seed).shuffle(pmcids)
    return pmcids


def candidate_paragraphs(pmcid: str) -> list[dict]:
    """Every paragraph of one article that is eligible to be sampled, with
    its span, stratum and raw section title."""
    root = parse_root(CORPUS_XML / f"{pmcid}.xml")
    if root is None:
        return []
    out = []
    for section in ("abstract", "body"):
        paragraphs = list(iter_paragraphs_from_root(root, section))
        titles = section_titles_from_root(root, section)
        for (text, start, end), title in zip(paragraphs, titles):
            stratum = classify_section(section, title)
            if stratum is None or not (MIN_TOKENS <= len(tokenize(text)) <= MAX_TOKENS):
                continue
            out.append({
                "paragraph_id": f"{pmcid}:{section}:{start}",
                "gold_span": {"pmcid": pmcid, "section": section,
                              "char_start": start, "char_end": end},
                "stratum": stratum, "section_title": title, "text": text,
            })
    return out


def sample_paragraphs(quota: int, seed: int, max_articles: int,
                      oversample: float) -> dict[str, list[dict]]:
    """Candidates per stratum, shuffled, `oversample` times the quota deep.

    Deep because the filters reject: the first smoke runs threw out about a
    third of generated items, mostly hallucinated anchors. Sampling exactly
    the quota would silently deliver a two-thirds-size set, so build() draws
    from this list until the quota is ACCEPTED and the depth is what it has
    to draw from.

    Walk shuffled articles, pooling candidates, and stop as soon as every
    stratum has enough. At most one paragraph per article per stratum: an
    article's results section can be fifteen paragraphs, and without the cap
    a handful of long articles would supply most of the set, making the
    queries correlated in a way the per-query bootstrap CI assumes they are
    not."""
    pool: dict[str, list[dict]] = {s: [] for s in STRATA}
    seen_article_stratum: set[tuple[str, str]] = set()
    depth = max(1, int(quota * oversample))
    scanned = 0
    for pmcid in load_pmcid_pool(seed)[:max_articles]:
        scanned += 1
        for cand in candidate_paragraphs(pmcid):
            key = (pmcid, cand["stratum"])
            if key in seen_article_stratum:
                continue
            seen_article_stratum.add(key)
            pool[cand["stratum"]].append(cand)
        if all(len(v) >= depth * 2 for v in pool.values()):
            break

    rng = random.Random(seed)
    sampled = {}
    for stratum in STRATA:
        available = pool[stratum]
        if len(available) < quota:
            print(f"  [warn] stratum {stratum}: only {len(available)} candidates for a "
                  f"quota of {quota}", file=sys.stderr)
        sampled[stratum] = rng.sample(available, min(depth, len(available)))
    print(f"  scanned {scanned} articles; pool sizes "
          + ", ".join(f"{s}={len(pool[s])}" for s in STRATA))
    return sampled


def lexical_overlap(query: str, paragraph: str) -> float:
    """Fraction of the query's distinct tokens that occur in the gold
    paragraph. This is the per-row lexical-bias number START_HERE's phase C
    line asks for: 1.0 means every word of the query is in the target and
    BM25 has been handed the answer.

    Type overlap, not token overlap, so a query repeating a word does not
    count it twice. Same tokenizer BM25 itself uses, so the number describes
    the retriever's actual view of the text, not a second tokenization that
    could disagree with it."""
    q = set(tokenize(query))
    if not q:
        return 0.0
    return len(q & set(tokenize(paragraph))) / len(q)


def rarest_term_df(query: str, doc_freq: dict[str, int]) -> int:
    """Corpus document frequency of the query's rarest term.

    This is the specificity measure that replaced anchors. Anchors asked the
    model to copy distinctive strings into its queries and it would not
    comply; this asks the corpus how distinctive the query actually is, which
    needs no compliance from anyone.

    Terms absent from the corpus are IGNORED, not treated as maximally rare.
    That looks wrong for a second and is the whole point: a term matching no
    paragraph cannot help find the gold paragraph either, because the gold
    paragraph is in the corpus. A misspelling would otherwise score as the
    most distinctive term in the query and wave a generic query through. If
    every term is absent, the query matches nothing at all, which is the least
    specific outcome available, so it returns a value that always fails."""
    present = [doc_freq[t] for t in set(tokenize(query)) if doc_freq.get(t)]
    return min(present) if present else 1 << 30


def answer_share_in_query(answer_quote: str, query: str) -> float:
    """Share of the answer's distinct tokens that already appear in the query.

    This is the tautology test, and it is one rule rather than a list of
    interrogative patterns because it targets the defect directly: a query
    that already contains its own answer is not a question. It subsumes the
    specific shape the human review found (the anchor WAS the finding, and
    anchors are held verbatim in both queries, so the answer rode into the
    question on the anchor), without needing to enumerate the ways a
    quantity can be asked for."""
    tokens = set(tokenize(answer_quote))
    if not tokens:
        return 1.0
    return len(tokens & set(tokenize(query))) / len(tokens)


def validate(out: dict, paragraph: str, doc_freq: dict[str, int] | None = None) -> str | None:
    """The mechanical filters. Returns a rejection reason, or None if the
    generated item is usable.

    Two of them do the real work, and both come from a human review that
    found 11 of 20 paragraphs defective under v1:

      answer_quote must be verbatim in the paragraph, which is how a
      paragraph that only announces a topic gets rejected. It cannot supply
      a quote for a fact it does not state.

      the query must not already contain that answer, which is how a
      question that answers itself gets rejected.

    Everything else here is shape checking."""
    # Checked first, and named for what it is. The model is instructed to
    # return nothing when a paragraph states no finding, so a declination
    # arrives as an empty object. Reported as a malformed-output error it
    # would hide the single most important number about the sampling frame:
    # what share of sampled paragraphs contain no askable fact at all.
    answer = out.get("answer_quote")
    if not isinstance(answer, str) or not answer.strip():
        return "declined: the model reports this paragraph states no askable finding"

    norm_para = normalize(paragraph)
    # The grounding filter, and the reason failure mode 2 is catchable at all:
    # a paragraph that merely announces a topic cannot supply a verbatim quote
    # for a fact it never states.
    if normalize(answer) not in norm_para:
        return "answer_quote is not verbatim in the paragraph"
    if len(tokenize(answer)) > MAX_ANSWER_TOKENS:
        return (f"answer_quote is {len(tokenize(answer))} tokens; it should be the shortest "
                f"answering span, not its sentence")

    queries_raw = {style: out.get(f"{style}_query") for style in ("lexical", "paraphrased")}
    for style, query in queries_raw.items():
        if not isinstance(query, str) or not query.strip():
            return f"{style}_query missing"

    # Anchors are metadata, not a gate. They steer the generator toward a
    # specific question and they record what the question is about; nothing
    # checks them against the queries any more.
    #
    # Measured, on 19 paragraphs from one shared set of generations
    # (2026-09-06): requiring every anchor verbatim in both queries accepted
    # 3 of 20, requiring merely one anchor per query accepted 5, and dropping
    # the requirement entirely accepted 14 of 19 (74%). The recovered items
    # are not marginal, they are the exact paragraphs whose v1 output a human
    # marked wrong, now correctly formed: "How many amplicons were designed
    # to cover the target region?" with the answer 1663 held back. So the
    # rule cost two thirds of the yield and bought no quality; what buys
    # quality is answer_quote plus the tautology check below.
    #
    # Specificity is not left unguarded, it moves to where it was always
    # going to be measured: score_retrieval.py --measure-holes puts an LLM on
    # the top non-gold hits and reports how often another paragraph answers
    # the query just as well. That was the design the user approved on
    # 2026-09-05 ("anchors, and measure the residual"); this only removes the
    # half of it that did not work.
    out["anchors"] = [a for a in (out.get("anchors") or [])
                      if isinstance(a, str) and a.strip()
                      and len(a.split()) <= MAX_ANCHOR_WORDS
                      and normalize(a) in norm_para]

    queries = queries_raw
    for style, query in queries.items():
        n_tokens = len(tokenize(query))
        if not (MIN_QUERY_TOKENS <= n_tokens <= MAX_QUERY_TOKENS):
            return f"{style}_query is {n_tokens} tokens"
        share = answer_share_in_query(answer, query)
        if share > MAX_ANSWER_IN_QUERY:
            return (f"{style}_query already contains {share:.0%} of its own answer "
                    f"(tautological)")
        if doc_freq is not None:
            df = rarest_term_df(query, doc_freq)
            if df > MAX_RAREST_TERM_DF:
                return (f"{style}_query is generic: its rarest term is in {df} paragraphs, "
                        f"over the {MAX_RAREST_TERM_DF} limit")
    if normalize(queries["lexical"]) == normalize(queries["paraphrased"]):
        return "the two queries are identical"
    # Same check one level down: two queries differing only in word order, or
    # only inside the anchors, are one query written twice. Note this enforces
    # the CONSTRUCTION (the styles must differ in prose) and not the OUTCOME
    # (how much that changes recall), which is the thing being measured and
    # must not be filtered on.
    anchor_words = {w for a in out["anchors"] for w in tokenize(a)}
    if ({w for w in tokenize(queries["lexical"]) if w not in anchor_words}
            == {w for w in tokenize(queries["paraphrased"]) if w not in anchor_words}):
        return "the two queries differ only inside their anchors"
    return None


def rows_for(cand: dict, out: dict, year: int | None, model: str) -> list[dict]:
    """Two rows, one per style, sharing a paragraph_id and a gold span. The
    shared id is what makes the styles a PAIRED comparison rather than two
    marginal rates."""
    return [{
        "query_id": f"{cand['paragraph_id']}#{style}",
        "paragraph_id": cand["paragraph_id"],
        "style": style,
        "query": out[f"{style}_query"].strip(),
        "gold_span": cand["gold_span"],
        "stratum": cand["stratum"],
        "section_title": cand["section_title"],
        "pub_year": year,
        "anchors": out["anchors"],
        "answer_quote": out["answer_quote"].strip(),
        "lexical_overlap": round(lexical_overlap(out[f"{style}_query"], cand["text"]), 4),
        "gold_text_chars": len(cand["text"]),
        "gold_text_sha1": gold_text_digest(cand["text"]),
        "created_by": f"agent:build_retrieval_set/{PROMPT_VERSION}",
        "model": model,
        "validated_by": None,
    } for style in ("lexical", "paraphrased")]


def load_doc_freq(path: Path | None) -> dict[str, int] | None:
    """The term -> document-frequency table, for the specificity check.

    A separate small file rather than the BM25 index itself: the index is
    575MB on disk and about 1.7GB resident, and a build runs for hours on a
    machine where that has already caused swap thrashing. The table alone is
    a few tens of MB."""
    if path is None:
        return None
    if not path.exists():
        raise SystemExit(
            f"{path} does not exist. Build it from the BM25 index:\n"
            f"  python -c \"import json; from pathlib import Path; "
            f"from retrieval.bm25 import BM25Index; "
            f"json.dump(BM25Index.load(Path('eval/runs/bm25_index.pkl')).doc_freq, "
            f"open('{path}','w'))\"")
    with open(path) as f:
        return json.load(f)


def build(out_path: Path, quota: int, seed: int, model: str, limit: int | None,
          max_articles: int, oversample: float, doc_freq: dict[str, int] | None = None) -> int:
    done: set[str] = set()
    accepted: dict[str, int] = {s: 0 for s in STRATA}
    if out_path.exists():
        with open(out_path) as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row["paragraph_id"] not in done:
                        done.add(row["paragraph_id"])
                        accepted[row["stratum"]] = accepted.get(row["stratum"], 0) + 1
        if done:
            print(f"  resuming: {len(done)} paragraphs already in {out_path}")

    pools = sample_paragraphs(quota, seed, max_articles, oversample)
    years = load_manifest_years()
    rejected: dict[str, int] = {}
    written = attempted = 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a") as f:
        for stratum in STRATA:
            for cand in pools[stratum]:
                if accepted[stratum] >= quota or (limit and attempted >= limit):
                    break
                if cand["paragraph_id"] in done:
                    continue
                attempted += 1
                try:
                    out = groq_chat_json(QGEN_PROMPT.format(paragraph=cand["text"]),
                                         model=model, reasoning_effort=REASONING_EFFORT,
                                         max_retries=10)
                except Exception as exc:  # a dead call costs one paragraph, not the run
                    key = f"call failed ({type(exc).__name__})"
                    rejected[key] = rejected.get(key, 0) + 1
                    continue
                reason = validate(out, cand["text"], doc_freq=doc_freq)
                if reason:
                    key = reason.split(":")[0]
                    rejected[key] = rejected.get(key, 0) + 1
                    continue
                for row in rows_for(cand, out, years.get(cand["gold_span"]["pmcid"]), model):
                    f.write(json.dumps(row) + "\n")
                    written += 1
                f.flush()  # long, rate-limited run: never lose finished work
                accepted[stratum] += 1
                if attempted % 25 == 0:
                    print(f"  {attempted} attempted, {written} queries written, "
                          + " ".join(f"{s}={accepted[s]}" for s in STRATA), flush=True)
            print(f"  {stratum}: {accepted[stratum]}/{quota} accepted", flush=True)

    print(f"\nWrote {written} queries to {out_path} "
          f"({attempted} paragraphs attempted this run)")
    short = [s for s in STRATA if accepted[s] < quota]
    if short:
        print("Short of quota (rerun to top up, or raise --oversample): "
              + ", ".join(f"{s}={accepted[s]}/{quota}" for s in short))
    if rejected:
        print("Rejected:")
        for reason, count in sorted(rejected.items(), key=lambda kv: -kv[1]):
            print(f"  {count:4d}  {reason}")
    return 0


WORKSHEET_HEADER = """# Retrieval set spot-check worksheet

{n} of the retrieval set's {total} paragraphs, one per stratum in rotation, sampled at seed
{seed}. Both queries generated from a paragraph are shown together, because they share its gold
span and a defect in one is usually a defect in both.

**What this is for.** `PROJECT_PLAN.md`'s phase C asks for about 20 of these read by a person.
The mechanical filters can prove an anchor came from the paragraph; they cannot tell whether the
query is a question anyone would ask, or whether the paragraph really answers it. This project's
measured base rate for unreviewed agent-written labels is about 50% defective (4 of 8 in phase
A1, 5 of 11 on the strength pass), so until this is filled in, every number scored off this set
is provisional.

**Three questions per paragraph**, in order of how badly a "no" damages the set:

1. Does the paragraph below actually answer both queries?
2. Is each query specific enough that you would be annoyed to be handed a different paragraph?
   (A different paper's paragraph on the same topic is the failure mode.)
3. Is the paraphrased query genuinely differently worded, not the lexical one with two synonyms?

Mark `valid` only if all three hold. `wrong` if any fails, and say which in the why line.

Fill in the two `___` lines under each paragraph, then run:

```
python -m eval.make_case_worksheet --summarize {out}
```

---

"""


def render_worksheet(pairs: list[list[dict]], n_total: int, seed: int, out: str) -> str:
    """Rendered so eval/make_case_worksheet.py's existing --summarize parses
    it unchanged: the same '## N. `id`' heading and the same verdict/why
    lines. One filled-in-worksheet parser for this project, not two, and it
    is the one whose failure modes are already known (see that module's
    _parse_verdict, which once reported a 45% error rate as a clean sheet)."""
    out_lines = [WORKSHEET_HEADER.format(n=len(pairs), total=n_total, seed=seed, out=out)]
    for i, rows in enumerate(pairs, start=1):
        first = rows[0]
        span = first["gold_span"]
        out_lines.append(f"## {i}. `{first['paragraph_id']}`\n\n")
        out_lines.append(
            f"- **stratum:** {first['stratum']}"
            f"  (section title: {first['section_title'] or 'none'})\n"
            f"- **source:** {span['pmcid']}, {span['section']} "
            f"[{span['char_start']}:{span['char_end']}], published {first['pub_year']}\n"
            f"- **anchors:** {', '.join(repr(a) for a in first['anchors'])}\n\n")
        for row in sorted(rows, key=lambda r: r["style"]):
            out_lines.append(f"**{row['style']} query** (lexical overlap "
                             f"{row['lexical_overlap']:.2f})\n\n> {row['query']}\n\n")
        text, error = load_span_text(CORPUS_XML, span["pmcid"], span["section"],
                                     span["char_start"], span["char_end"])
        # Untruncated, deliberately. Truncating span display to a few hundred
        # characters is exactly the bug that contaminated this project's first
        # kappa pass; the sentence that decides the verdict is usually past
        # the cutoff.
        out_lines.append(f"**The gold paragraph, read back from the corpus XML at those exact "
                         f"offsets:**\n\n{text or f'(could not load: {error})'}\n\n")
        out_lines.append("- **verdict:** ___   (valid / wrong / unsure)\n")
        out_lines.append("- **why:** ___\n\n---\n\n")
    return "".join(out_lines)


def make_worksheet(cases_path: Path, n: int, seed: int, out: str) -> int:
    """Samples paragraphs, not queries, one per stratum in rotation so a
    20-paragraph sheet covers all six rather than landing in whichever
    stratum the shuffle favoured."""
    by_paragraph: dict[str, list[dict]] = {}
    for row in load_cases(cases_path):
        by_paragraph.setdefault(row["paragraph_id"], []).append(row)

    by_stratum: dict[str, list[list[dict]]] = {}
    for rows in by_paragraph.values():
        by_stratum.setdefault(rows[0]["stratum"], []).append(rows)
    rng = random.Random(seed)
    for pool in by_stratum.values():
        pool.sort(key=lambda rows: rows[0]["paragraph_id"])
        rng.shuffle(pool)

    picked: list[list[dict]] = []
    strata = sorted(by_stratum)
    while len(picked) < n and any(by_stratum[s] for s in strata):
        for stratum in strata:
            if by_stratum[stratum] and len(picked) < n:
                picked.append(by_stratum[stratum].pop())

    Path(out).write_text(render_worksheet(picked, len(by_paragraph), seed, out))
    counts: dict[str, int] = {}
    for rows in picked:
        counts[rows[0]["stratum"]] = counts.get(rows[0]["stratum"], 0) + 1
    print(f"Wrote {out}: {len(picked)} paragraphs of {len(by_paragraph)} "
          f"({', '.join(f'{v} {k}' for k, v in sorted(counts.items()))}).")
    print(f"Fill it in, then: python -m eval.make_case_worksheet --summarize {out}")
    return 0


def calibrate_overlap(cases_path: Path) -> int:
    """Our queries' lexical overlap against BEIR's human-written ones.

    The bias is known: a query written while looking at a paragraph reuses
    its wording. This says by how much, relative to queries written by
    people who were not looking at the passage, which is the only reference
    point that makes our number mean anything."""
    from statistics import mean, median

    from eval.benchmarks.loader import load_benchmark

    def report(label: str, values: list[float]) -> None:
        if not values:
            return
        share = sum(1 for v in values if v >= 0.9) / len(values)
        print(f"  {label:28s} mean {mean(values):.3f}  median {median(values):.3f}  "
              f"fully-contained {share:.0%}  n={len(values)}")

    by_style: dict[str, list[float]] = {}
    for row in load_cases(cases_path):
        by_style.setdefault(row["style"], []).append(row["lexical_overlap"])
    for style, values in sorted(by_style.items()):
        report(f"ours ({style})", values)

    for name in ("scifact", "nfcorpus"):
        data = load_benchmark(name)
        qrels: dict[str, list[str]] = {}
        for j in data.judgments:
            if j.relevance > 0:
                qrels.setdefault(j.query_id, []).append(j.doc_id)
        values = []
        for qid, doc_ids in qrels.items():
            doc = data.documents.get(doc_ids[0])
            if doc is not None:
                values.append(lexical_overlap(data.queries[qid].text, f"{doc.title} {doc.text}"))
        report(f"{name} (human-written)", values)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--quota", type=int, default=DEFAULT_QUOTA,
                        help="paragraphs per section stratum")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, help="smoke test: only this many paragraphs")
    parser.add_argument("--max-articles", type=int, default=1500,
                        help="cap on articles scanned while pooling candidates")
    parser.add_argument("--oversample", type=float, default=2.0,
                        help="candidates drawn per stratum, as a multiple of the quota, to "
                             "absorb the filters' reject rate")
    parser.add_argument("--calibrate-overlap", action="store_true",
                        help="compare this set's lexical overlap against BEIR queries, then exit")
    parser.add_argument("--worksheet", type=int, metavar="N",
                        help="render N paragraphs for a human spot-check, then exit")
    parser.add_argument("--out-worksheet", default="retrieval_worksheet.md")
    parser.add_argument("--df-table", type=Path,
                        help="term -> document-frequency JSON, enabling the specificity check. "
                             "Without it a generic query is accepted, and a generic query cannot "
                             "identify one gold paragraph (measured recall@10 0.562 against 0.972)")
    args = parser.parse_args(argv)

    if args.calibrate_overlap:
        return calibrate_overlap(args.out)
    if args.worksheet:
        return make_worksheet(args.out, args.worksheet, args.seed, args.out_worksheet)
    doc_freq = load_doc_freq(args.df_table)
    if doc_freq is None:
        print("  [warn] no --df-table: the specificity check is OFF and generic queries will "
              "be accepted. See --help.", file=sys.stderr)
    return build(args.out, args.quota, args.seed, args.model, args.limit,
                 args.max_articles, args.oversample, doc_freq)


if __name__ == "__main__":
    sys.exit(main())
