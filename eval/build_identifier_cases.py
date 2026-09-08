"""
Assemble the exact-identifier failure case (phase D) from mined notation
equivalences.

`mine_notation_pairs.py` produced `notation_case_candidates.csv`: corpus
paragraphs that mention exactly one of two same-variant notations. This
script takes a hand-picked subset (`SELECTIONS` below, curated by reading
each paragraph against its source), and for each builds a PAIRED retrieval
case: one query using the notation the gold paragraph contains (`matched`),
one using the equivalent notation it never uses (`mismatched`), same gold
span, same query. The only thing that varies is the identifier surface form.
That isolates what BM25 does when a query names a variant a different way
than the document does.

The query is keyword-style, `"{gene} {form} variant"`: a gene symbol (rare
enough to narrow), the identifier (the token under test), and one topic
anchor. The first run used a sentence stem ("What does the literature report
about the {form} variant?") and its filler words ("literature", "report")
were matching unrelated review chunks harder than the one rare-identifier
hit in a long merged chunk, so a matched query missed 60% of the time. See
`docs/DECISION_LOG.md`, "BM25 on the exact-identifier failure case".

`present_min_token_df` is stored per row: the smallest corpus document
frequency among the present form's tokens, read from the BM25 index. It is
what BM25 actually leans on. It turned out NOT to be the binding constraint
(every present form here has a token in <= 25 chunks), but it belongs on the
row so later analysis can condition on it.

Output: `data/identifier_cases.jsonl`. `validated_by` stays null. This
project's base rate for unreviewed agent labels is about 50% wrong, so the
number off this set is provisional until a person has read the cases.

    python -m eval.build_identifier_cases
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from common.corpus_text import load_span_text
from eval.strata import load_manifest_years
from retrieval.bm25 import BM25Index, tokenize

EVAL_DIR = Path(__file__).parent
CANDIDATES = EVAL_DIR / "runs" / "notation_case_candidates.csv"
INDEX = EVAL_DIR / "runs" / "bm25_index.pkl"
OUT = EVAL_DIR / "data" / "identifier_cases.jsonl"
MAX_PRESENT_MIN_TOKEN_DF = 60  # a guard against a genuinely non-specific form, not a tuned filter

# (pair_id, pmcid, gene), curated from notation_case_candidates.csv by reading
# each gold paragraph against its source. `gene` is None where the span names
# several genes and attribution is not certain. Axis spread: cdna<->protein,
# cdna<->legacy, cdna<->cdna (transcript version), rsid<->cdna/protein.
SELECTIONS = [
    ("c.556C>T__p.Arg186*", "PMC3555982", None),        # cdna<->protein, BRCA1/BARD1 LOH (gene ambiguous in span)
    ("c.104T>C__p.L35P", "PMC5519427", "PALB2"),        # cdna<->protein, PALB2 VUS
    ("c.2369C>T__p.T790M", "PMC11846000", "EGFR"),      # cdna<->protein, EGFR T790M
    ("c.355T>C__p.Cys119Arg", "PMC3326673", None),      # protein<->cdna, novel missense, gene ambiguous (abstract)
    ("c.1624G>A__p.E542K", "PMC9636515", "PIK3CA"),     # cdna<->protein, PIK3CA hotspot
    ("c.6775G>T__p.Glu2183X", "PMC2092410", "BRCA2"),   # protein<->cdna, BRCA2 (abstract)
    ("c.5062_5064del__1688del", "PMC9626413", "BRCA1"), # cdna<->legacy, BRCA1 second hit
    ("c.329_331delGTC__110del", "PMC7788890", "TP53"),  # cdna<->legacy, TP53 R110del somatic
    ("c.5222_5225del__5450delGTAA", "PMC12011969", "BRCA2"),  # cdna<->legacy, BRCA2 male BC
    ("c.1380dup__1499insA", "PMC10883683", "BRCA1"),    # cdna<->legacy, BRCA1 Sicilian founder
    ("c.4035delA__c.4153delA", "PMC11949239", "BRCA1"), # cdna<->cdna transcript version, BRCA1 founder
    ("c.1592delT__rs180177102", "PMC7736877", "PALB2"), # rsid<->cdna, PALB2 Finnish-enriched
    ("c.4327C>T__rs41293455", "PMC8286662", "BRCA1"),   # rsid<->cdna, BRCA1 stop-gain TNBC
    ("c.35delG__rs80338939", "PMC12522356", "GJB2"),    # cdna<->rsid, GJB2 c.35delG
    ("c.1765G>A__rs1047840", "PMC4014567", "EXO1"),     # rsid<->cdna, EXO1 K589E meta-analysis
    ("c.4837A>T__rs1799966", "PMC7141151", "BRCA1"),    # cdna<->rsid, BRCA1 S1613G polymorphism
    ("c.-24C>T__rs717620", "PMC5341838", "ABCC2"),      # cdna<->rsid, ABCC2 chemo response (abstract)
]


def _axis(present: str, absent: str) -> str:
    def kind(f: str) -> str:
        if f.startswith("rs"):
            return "rsid"
        if f.startswith("p."):
            return "protein"
        return "cdna"  # includes legacy names, which are cDNA-position shorthand
    a, b = sorted((kind(present), kind(absent)))
    return f"{a}<->{b}" if a != b else "cdna<->cdna"


def _query(gene: str | None, form: str) -> str:
    return f"{gene} {form} variant" if gene else f"{form} variant"


def _overlap(query: str, gold_text: str) -> float:
    q = set(tokenize(query))
    if not q:
        return 0.0
    g = set(tokenize(gold_text))
    return round(len(q & g) / len(q), 4)


def _min_token_df(form: str, doc_freq: dict[str, int]) -> int:
    toks = tokenize(form)
    return min((doc_freq.get(t, 0) for t in toks), default=0)


def main() -> int:
    # Several candidate paragraphs can share a (pair_id, pmcid). Prefer an
    # abstract, then the rarest present form, then the shortest span: that is
    # the most likely to be a real "about this variant" paragraph rather than
    # a genotyping list.
    rows: dict[tuple[str, str], dict] = {}
    for r in csv.DictReader(CANDIDATES.open()):
        key = (r["pair_id"], r["pmcid"])
        rank = (r["section"] != "abstract", int(r["present_df_paragraphs"]),
                int(r["char_end"]) - int(r["char_start"]))
        if key not in rows or rank < rows[key][0]:
            rows[key] = (rank, r)
    rows = {k: v[1] for k, v in rows.items()}

    if not INDEX.exists():
        raise SystemExit(f"{INDEX} not found; build it first (see eval/README.md)")
    doc_freq = BM25Index.load(INDEX).doc_freq
    years = load_manifest_years()
    xml_dir = EVAL_DIR.parent / "corpus" / "xml"
    out_lines: list[str] = []
    for pair_id, pmcid, gene in SELECTIONS:
        r = rows.get((pair_id, pmcid))
        if r is None:
            raise SystemExit(f"{pair_id} / {pmcid} not in {CANDIDATES.name}; regenerate it")
        present, absent = r["form_present"], r["form_absent"]
        section = r["section"]
        cs, ce = int(r["char_start"]), int(r["char_end"])
        gold_text, err = load_span_text(xml_dir, pmcid, section, cs, ce)
        if err:
            raise SystemExit(f"{pair_id} / {pmcid}: gold span does not resolve ({err})")
        if present not in gold_text:
            raise SystemExit(f"{pair_id} / {pmcid}: present form {present!r} not in the gold span")
        if absent in gold_text:
            # substring, not token match: the mismatched form leaks in via a
            # longer token (1688del inside c.1688delA). Drop it, a clean test
            # needs the mismatched identifier genuinely absent.
            print(f"  skip {pair_id} / {pmcid}: absent form {absent!r} appears in the gold span")
            continue
        min_df = _min_token_df(present, doc_freq)
        if min_df > MAX_PRESENT_MIN_TOKEN_DF:
            print(f"  skip {pair_id} / {pmcid}: present form {present!r} has no token "
                  f"rarer than {min_df} chunks")
            continue
        case_id = f"{pmcid}:{section}:{cs}"
        gold_span = {"pmcid": pmcid, "section": section, "char_start": cs, "char_end": ce}
        sha1 = hashlib.sha1(gold_text.encode()).hexdigest()[:12]
        for style, form in (("matched", present), ("mismatched", absent)):
            query = _query(gene, form)
            out_lines.append(json.dumps({
                "query_id": f"{case_id}#{style}",
                "case_id": case_id,
                "pair_id": pair_id,
                "style": style,
                "gene": gene,
                "query": query,
                "gold_span": gold_span,
                "notation_present": present,
                "notation_absent": absent,
                "notation_axis": _axis(present, absent),
                "present_min_token_df": min_df,
                "pub_year": years.get(pmcid),
                "lexical_overlap": _overlap(query, gold_text),
                "gold_text_chars": len(gold_text),
                "gold_text_sha1": sha1,
                "created_by": "agent:build_identifier_cases",
                "validated_by": None,
            }))
    OUT.write_text("\n".join(out_lines) + "\n")
    print(f"Wrote {len(out_lines)} queries over {len(out_lines) // 2} cases to {OUT} "
          f"({len(SELECTIONS) - len(out_lines) // 2} selections skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
