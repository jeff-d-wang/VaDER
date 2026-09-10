# Eval case validation worksheet

8 of the answer set's cases, stratified by type, sampled at seed 0, dev split only.

**What this is for.** Every case in `answer_cases.jsonl` was written by an agent and read by no person. Every number in `docs/RESULTS.md` is graded against these labels. This worksheet asks one question per case: is the gold label actually right?

**You are not grading a system answer here.** There is no system answer in this file. You are checking the ruler, not the measurement.

Fill in the two `___` lines at the end of each case, then run:

```
python make_case_worksheet.py --summarize case_worksheet.md
```

---
## Case 1: `atm_c7570g_c_risk_class_disagree_001`

**Type:** disagreement  |  **Gene:** ATM  |  **Variant:** c.7570G>C  |  **Condition:** breast cancer

**Query the system gets:** What does the literature report about ATM c.7570G>C and breast cancer risk classification?

**Gold direction:** 'high_risk_vs_moderate'
**Gold strength:** 'moderate'

**Gold asserts the sources disagree.** The claimed disagreement, verbatim:

> PMC10092731 (2023) argues that ATM c.7570G>C should be reclassified from the general 'moderate-risk' category to 'high-risk', noting that while ATM is 'generally placed in the moderate-risk category with a combined estimation of 2-fold risk', specific variants like c.7570G>C with dominant-negative effects have 'up to 60% lifetime breast cancer by the age of 70 years'. PMC8973562 (2022) reports overall ATM pathogenic variants show hazard ratio of only 1.32 (95% CI), supporting ATM as moderate-risk. The disagreement is about whether c.7570G>C is a special high-risk variant vs standard moderate-risk ATM variant.

**What to look for:** do the two spans below actually conflict, or do they just share a topic? A newer paper reporting a different endpoint is not a disagreement; a newer paper reporting the opposite result on the same endpoint is.

**Gold spans (2), full source text, untruncated:**

- **Span 1: PMC10092731 / body / chars 11369-11649** (280 chars)

  >  Although collectively considered as moderate breast cancer risk alleles, some of the ATM variants potentially cause higher breast cancer risk. This has previously been demonstrated for ATM c.7271T>G, (p.Val2424Gly), having up to 60% lifetime breast cancer by the age of 70 years.

- **Span 2: PMC8973562 / abstract / chars 465-766** (301 chars)

  > The estimated breast cancer hazard ratio for carriers of pathogenic ATM variants in the ABCFR was 1.32 (95% confidence interval 0.45–3.87; P = 0.6). The estimated cumulative risk of breast cancer to age 80 years for heterozygous ATM pathogenic variant carriers was estimated to be 13% (95% CI 4.6–30).

**Case author's notes:** VUS reclassification disagreement: one source claims specific ATM variant warrants high-risk classification due to dominant-negative effect, other sources treat ATM variants as uniformly moderate-risk. Literature acknowledges controversy over ATM penetrance.

*(written by `agent:disagreement-finder`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** wrong
- **why:** Span 1 attributes the 60% lifetime risk to the c.7271T>G variant, completely failing to support the gold label's claim about c.7570G>C.

---
## Case 2: `chek2_1100delc_prognosis_disagree_001`

**Type:** disagreement  |  **Gene:** CHEK2  |  **Variant:** c.1100delC  |  **Condition:** breast cancer

**Query the system gets:** What does the literature report about CHEK2 c.1100delC carriers and breast cancer prognosis outcomes?

**Gold direction:** 'mixed'
**Gold strength:** 'moderate'

**Gold asserts the sources disagree.** The claimed disagreement, verbatim:

> PMC4150261 (2014) studies survival and contralateral breast cancer in CHEK2 1100delC carriers, finding higher risks in mutation carriers. PMC12702395 (2026) explicitly states 'Against our expectations based on the results from previous studies, CHEK2 c.1100delC associated ER-positive breast cancer patients had similar recurrent disease-free survival, distant disease-free survival, breast cancer-specific survival and overall survival as compared to non-carriers', attributing the discrepancy to modern treatment regimens and HER2-targeted therapy availability since 2006.

**What to look for:** do the two spans below actually conflict, or do they just share a topic? A newer paper reporting a different endpoint is not a disagreement; a newer paper reporting the opposite result on the same endpoint is.

**Gold spans (2), full source text, untruncated:**

- **Span 1: PMC4150261 / abstract / chars 1283-1539** (256 chars)

  > The CHEK2 1100delC-associated breast cancer is associated with a higher contralateral breast cancer rate as well as worse survival measures beyond 6 years after diagnosis. No differential sensitivity to adjuvant chemotherapy was observed in CHEK2 patients.

- **Span 2: PMC12702395 / body / chars 23605-24042** (437 chars)

  > Against our expectations based on the results from previous studies, CHEK2 c.1100delC associated ER-positive breast cancer patients had similar recurrent disease-free survival, distant disease-free survival, breast cancer-specific survival and overall survival as compared to non-carriers. However, when meta-analyzing our results with previous studies, CHEK2 c.1100delC was still associated with a worse breast cancer-specific survival.

**Case author's notes:** Genuine replication failure: older studies reported worse prognosis for CHEK2 c.1100delC carriers, newer study with modern treatment cohorts finds no significant difference. Disagreement is about prognosis/survival outcomes, not pathogenicity classification.

*(written by `agent:disagreement-finder`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** valid
- **why:** Span 1 establishes worse survival for carriers, which is directly contradicted by Span 2 reporting similar survival to non-carriers, confirming a true disagreement.

---
## Case 3: `atm_c2023c_t_breast_neg_001`

**Type:** negative  |  **Gene:** ATM  |  **Variant:** c.2023C>T  |  **Condition:** breast cancer

**Query the system gets:** What does the literature report about ATM c.2023C>T and breast cancer risk?

**This case asserts the corpus contains NO grounding for this pair.** There is no span to read; what you are checking is whether that absence claim is believable.

The case's own completeness claim, verbatim:

> Negative case: ATM c.2023C>T + breast cancer. Variant notations searched: c.2023C>T, c.2023C/T, 2023C>T. Zero matches in full corpus sweep (0 same_paragraph, 0 doc_level_only). Verified complete: no articles in this corpus discuss this variant-condition pair.

**What to look for:** does the list of searched notations cover the forms this variant is actually written in? Protein-level HGVS (`p.Arg675Trp`) and rsIDs are the two most commonly missing, and a paper describing the variant only in prose ("the previously reported truncating variant in exon 10") will not be caught by any notation search. Mark `unsure` if the sweep looks too narrow to trust.

**Case author's notes:** Negative case: ATM c.2023C>T + breast cancer. Variant notations searched: c.2023C>T, c.2023C/T, 2023C>T. Zero matches in full corpus sweep (0 same_paragraph, 0 doc_level_only). Verified complete: no articles in this corpus discuss this variant-condition pair.

*(written by `agent:negative-case-builder-v2`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** unsure
- **why:** The searched notations only sweep for nucleotide-level nomenclature. Omitting protein-level HGVS notations and rsIDs makes the completeness sweep too narrow to trust.

---
## Case 4: `palb2_c1592del4_pancreatic_neg_001`

**Type:** negative  |  **Gene:** PALB2  |  **Variant:** c.1592del4  |  **Condition:** pancreatic cancer

**Query the system gets:** What does the literature report about PALB2 c.1592del4 and pancreatic cancer risk?

**This case asserts the corpus contains NO grounding for this pair.** There is no span to read; what you are checking is whether that absence claim is believable.

The case's own completeness claim, verbatim:

> Negative case: PALB2 c.1592del4 + pancreatic cancer. Variant notations searched: c.1592del4, c.1592_1595del, 1592del4. Zero matches in full corpus sweep (0 same_paragraph, 0 doc_level_only). Verified complete: no articles in this corpus discuss this variant-condition pair.

**What to look for:** does the list of searched notations cover the forms this variant is actually written in? Protein-level HGVS (`p.Arg675Trp`) and rsIDs are the two most commonly missing, and a paper describing the variant only in prose ("the previously reported truncating variant in exon 10") will not be caught by any notation search. Mark `unsure` if the sweep looks too narrow to trust.

**Case author's notes:** Negative case: PALB2 c.1592del4 + pancreatic cancer. Variant notations searched: c.1592del4, c.1592_1595del, 1592del4. Zero matches in full corpus sweep (0 same_paragraph, 0 doc_level_only). Verified complete: no articles in this corpus discuss this variant-condition pair.

*(written by `agent:negative-case-builder-v2`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** unsure
- **why:** The notation sweep only covers nucleotide-level deletion formats. Without checking protein-level variants or rsIDs, the negative completeness claim is unverifiable.

---
## Case 5: `atm_at_lymphoid_tumor_ord_001`

**Type:** ordinary  |  **Gene:** ATM  |  **Variant:** (none, gene-level)  |  **Condition:** lymphoid tumours in ataxia-telangiectasia

**Query the system gets:** What does the literature report about ATM kinase activity level and tumor risk in ataxia-telangiectasia patients?

**Gold direction:** 'increased risk with complete loss of ATM kinase activity; residual kinase activity is protective'
**Gold strength:** 'cohort of 296 genetically confirmed A-T patients from the British Isles and the Netherlands, 66 developed a malignant tumour (47 lymphoid, 19 non-lymphoid)'

**Gold spans (1), full source text, untruncated:**

- **Span 1: PMC3170966 / abstract / chars 617-1157** (540 chars)

  > In childhood, total absence of ATM kinase activity was associated, almost exclusively, with development of lymphoid tumours. There was an overwhelming preponderance of tumours in patients <16 years without kinase activity compared with those with some residual activity, consistent with a substantial protective effect of residual ATM kinase activity against tumour development in childhood. In addition, the presence of eight breast cancers in A-T patients, a 30-fold increased risk, establishes breast cancer as part of the A-T phenotype.

**Case author's notes:** Ordinary evidence case, and a dose-response/graded finding rather than a simple binary risk claim (kinase activity level, not mutation presence/absence, is the reported variable). Span verified against real abstract text.

*(written by `agent:ordinary-case-builder`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** wrong
- **why:** While the text confirms the directional claim regarding kinase activity, it completely lacks the cohort sizing and tumor counts (296 patients, 66 tumors) asserted in the gold strength.

---
## Case 6: `brca2_pancreatic_risk_ord_001`

**Type:** ordinary  |  **Gene:** BRCA2  |  **Variant:** (none, gene-level)  |  **Condition:** pancreatic cancer

**Query the system gets:** What does the literature report about BRCA1/BRCA2 mutations and pancreatic cancer risk?

**Gold direction:** 'increased risk'
**Gold strength:** 'background association; approximately 4-7% of pancreatic cancer patients carry germline BRCA1/2 mutations'

**Gold spans (1), full source text, untruncated:**

- **Span 1: PMC7788890 / abstract / chars 0-632** (632 chars)

  > In addition to ovarian and breast cancers, loss-of-function mutations in BRCA1 and BRCA2 genes are also linked to an increased risk of pancreatic cancer, with ~ 4 to 7% of pancreatic cancer patients harboring germline BRCA mutations. Most BRCA alterations in pancreatic cancer are frame-shifting indels, stop-gain, and splice-site mutations, but single nucleotide substitutions are rare. Recent studies demonstrated a significant progression-free survival (PFS) benefit from maintenance olaparib, a poly (ADP-ribose) polymerase (PARP) inhibitor administered to patients with germline BRCA mutations and metastatic pancreatic cancer.

**Case author's notes:** Ordinary evidence case. This span is the article's own background statement (citing established literature), not its novel finding (a single case report on a somatic BRCA2 variant); still a real, verifiable, on-topic citation for the general gene-condition association. gene field set to BRCA2 since the article's own case is a BRCA2 mutation carrier; background statement covers both BRCA1 and BRCA2. Span verified against real abstract text.

*(written by `agent:ordinary-case-builder`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** valid
- **why:** The span directly confirms the increased risk and explicitly corroborates the 4 to 7% prevalence cited in the gold strength.

---
## Case 7: `brca_prs_ovarian_risk_ord_001`

**Type:** ordinary  |  **Gene:** BRCA1  |  **Variant:** (none, gene-level)  |  **Condition:** ovarian cancer

**Query the system gets:** What does the literature report about polygenic risk score modification of ovarian cancer risk in BRCA1/BRCA2 mutation carriers?

**Gold direction:** 'increased risk with higher polygenic risk score'
**Gold strength:** 'OC risk 6% by age 80 at 10th percentile of OC-PRS vs 19% at 90th percentile, in both BRCA1 and BRCA2 carriers (15,252 BRCA1 and 8,211 BRCA2 carriers)'

**Gold spans (1), full source text, untruncated:**

- **Span 1: PMC5408990 / abstract / chars 1057-1762** (705 chars)

  > Results: The PRS for ER-negative BC displayed the strongest association with BC risk in BRCA1 carriers (HR = 1.27, 95% confidence interval [CI] = 1.23 to 1.31, P = 8.2×10−53). In BRCA2 carriers, the strongest association with BC risk was seen for the overall BC PRS (HR = 1.22, 95% CI = 1.17 to 1.28, P = 7.2×10−20). The OC PRS was strongly associated with OC risk for both BRCA1 and BRCA2 carriers. These translate to differences in absolute risks (more than 10% in each case) between the top and bottom deciles of the PRS distribution; for example, the OC risk was 6% by age 80 years for BRCA2 carriers at the 10th percentile of the OC PRS compared with 19% risk for those at the 90th percentile of PRS.

**Case author's notes:** Ordinary evidence case. Source paper covers both BRCA1 and BRCA2 carriers with separate but consistent findings; gene field set to BRCA1 per the single-gene schema, BRCA2 numbers noted here for completeness: BC PRS HR=1.22 (95% CI 1.17-1.28) in BRCA2 carriers. Span verified against real abstract text.

*(written by `agent:ordinary-case-builder`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** wrong
- **why:** The source span specifically attributes the 6% and 19% risk thresholds solely to BRCA2 carriers, whereas the gold label claims they apply to both BRCA1 and BRCA2. The span also omits the patient cohort sizes (15,252 and 8,211).

---
## Case 8: `palb2_breast_risk_ord_001`

**Type:** ordinary  |  **Gene:** PALB2  |  **Variant:** (none, gene-level)  |  **Condition:** breast cancer

**Query the system gets:** What does the literature report about PALB2 germline mutations and breast cancer risk?

**Gold direction:** 'increased risk'
**Gold strength:** 'moderate overall (OR 5.23, 95% CI 2.84-9.65), higher in women 30 or younger (OR 10.09, 95% CI 3.95-25.79)'

**Gold spans (1), full source text, untruncated:**

- **Span 1: PMC7384117 / abstract / chars 600-1458** (858 chars)

  > A total of 16,501 BRCA1/2‐negative patients with breast cancer were analyzed. Deleterious PALB2 mutation carriers accounted for 0.97% (n = 160) in the breast cancer cohort and for 0.19% (n = 11) in the healthy control cohort. Forty‐one novel PALB2 germline mutations were identified. A high frequency of PALB2 c.751C>T was detected, and it accounted for 10.63% of the PALB2 germline mutations detected (17 of 160). PALB2 mutations were significantly associated with increased breast cancer risk (odds ratio [OR], 5.23; 95% confidence interval [CI], 2.84‐9.65; P < .0001), especially among women 30 years old or younger (OR, 10.09; 95% CI, 3.95‐25.79; P < .0001). Clinical characteristics, including a family history, bigger tumor size, triple‐negative breast cancer, positive lymph nodes, and bilateral breast cancer, were closely related to PALB2 mutations.

**Case author's notes:** Ordinary evidence case (no disagreement, no absence): single large Chinese cohort (16,501 BRCA1/2-negative breast cancer patients, 5,890 controls) reporting a clear, quantified, uncontested PALB2-breast cancer association. Span verified against real abstract text via corpus_text.find_quote.

*(written by `agent:ordinary-case-builder`)*

**Your verdict.** `valid` = the gold label is right and the spans support it. `wrong` = the gold label is wrong, the spans do not support it, or the case is unanswerable as written. `unsure` = you cannot tell without more domain knowledge or more reading; this is a legitimate answer and more useful than a guess.

- **verdict:** valid
- **why:** The span exactly matches the quantitative claims in the gold strength, verifying both the overall OR of 5.23 and the OR of 10.09 for women 30 or younger.

---
