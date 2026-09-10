# Retrieval set spot-check worksheet

6 of the retrieval set's 6 paragraphs, one per stratum in rotation, sampled at seed
0. Both queries generated from a paragraph are shown together, because they share its gold
span and a defect in one is usually a defect in both.

**What this is for.** `PROJECT_PLAN.md`'s phase C asks for about 20 of these read by a person.
The mechanical filters can prove an anchor came from the paragraph; they cannot tell whether the
query is a question anyone would ask, or whether the paragraph really answers it. This project's
measured base rate for unreviewed agent-written labels is about 50% defective (4 of 8 in phase
A1, 5 of 11 on the strength pass), so until this is filled in, every number scored off this set
is provisional.

**A bare number sitting alone in the paragraph text below, often on its own line, is a citation
marker** (JATS renders `<xref ref-type="bibr">` inline with no separator, e.g. "were poor.
5

CCAs can be..."), not a reported figure. The queries were generated from a version with these
stripped; the paragraph shown below is deliberately the raw, unedited span exactly as retrieval
would return it, so you can also catch an offset bug, not just a query defect.

**Three questions per paragraph**, in order of how badly a "no" damages the set:

1. Does the paragraph below actually answer both queries?
2. Is each query specific enough that you would be annoyed to be handed a different paragraph?
   (A different paper's paragraph on the same topic is the failure mode.)
3. Is the paraphrased query genuinely differently worded, not the lexical one with two synonyms?

Mark `valid` only if all three hold. `wrong` if any fails, and say which in the why line.

Fill in the two `___` lines under each paragraph, then run:

```
python -m eval.make_case_worksheet --summarize eval/retrieval_worksheet_v5.md
```

---

## 1. `PMC8904525:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC8904525, abstract [0:1820], published 2022
- **anchors:** 'S4 model', 'European ancestries'

**lexical query** (lexical overlap 0.82)

> What is the odds ratio per unit standard deviation for the S4 model in women of European ancestries?

**paraphrased query** (lexical overlap 0.41)

> How strong is the association measured by the S4 polygenic risk score for non‑mucinous ovarian cancer among European‑origin participants, expressed as an odds ratio per SD?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Polygenic risk scores (PRS) for epithelial ovarian cancer (EOC) have the potential to improve risk stratification. Joint estimation of Single Nucleotide Polymorphism (SNP) effects in models could improve predictive performance over standard approaches of PRS construction. Here, we implemented computationally efficient, penalized, logistic regression models (lasso, elastic net, stepwise) to individual level genotype data and a Bayesian framework with continuous shrinkage, “select and shrink for summary statistics” (S4), to summary level data for epithelial non-mucinous ovarian cancer risk prediction. We developed the models in a dataset consisting of 23,564 non-mucinous EOC cases and 40,138 controls participating in the Ovarian Cancer Association Consortium (OCAC) and validated the best models in three populations of different ancestries: prospective data from 198,101 women of European ancestries; 7,669 women of East Asian ancestries; 1,072 women of African ancestries, and in 18,915 BRCA1 and 12,337 BRCA2 pathogenic variant carriers of European ancestries. In the external validation data, the model with the strongest association for non-mucinous EOC risk derived from the OCAC model development data was the S4 model (27,240 SNPs) with odds ratios (OR) of 1.38 (95% CI: 1.28–1.48, AUC: 0.588) per unit standard deviation, in women of European ancestries; 1.14 (95% CI: 1.08–1.19, AUC: 0.538) in women of East Asian ancestries; 1.38 (95% CI: 1.21–1.58, AUC: 0.593) in women of African ancestries; hazard ratios of 1.36 (95% CI: 1.29–1.43, AUC: 0.592) in BRCA1 pathogenic variant carriers and 1.49 (95% CI: 1.35–1.64, AUC: 0.624) in BRCA2 pathogenic variant carriers. Incorporation of the S4 PRS in risk prediction models for ovarian cancer may have clinical utility in ovarian cancer prevention programs.

- **verdict:** valid
- **why:** All criteria met.

---

## 2. `PMC9636504:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC9636504, abstract [0:1630], published 2022
- **anchors:** 'initial curative treatment'

**lexical query** (lexical overlap 0.71)

> What prognosis do HNSCC patients have who remain ctDNA negative after initial curative treatment?

**paraphrased query** (lexical overlap 0.35)

> How does survival outlook compare for head and neck cancer patients with persistent ctDNA negativity following their first definitive therapy?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

There is no useful biomarker to evaluate treatment response and early relapse in head and neck squamous cell carcinoma (HNSCC). Circulating tumor DNA (ctDNA) is a promising biomarker for detecting minimal residual diseases and monitoring treatment effect. We investigated whether individualized ctDNA analysis could help monitor treatment response and relapse in HNSCC. Mutation analysis of tumor and peripheral blood mononuclear cell (PBMC) DNAs of 26 patients with HNSCC was performed using a custom squamous cell carcinoma (SCC) panel. The identified individualized mutated genes were defined as ctDNA candidates. We investigated whether frequent ctDNA monitoring via digital PCR (dPCR) is clinically valid for HNSCC patients. TP53 was the most frequently mutated gene and was detected in 14 of 24 cases (58.2%), wherein two cases were excluded owing to the absence of tumor‐specific mutations in the SCC panel. Six cases were excluded because of undesignable and unusable primer‐probes for dPCR. Longitudinal ctDNA was monitored in a total of 18 cases. In seven cases, ctDNA tested positive again or did not test negative, and all seven cases relapsed after initial curative treatment. In 11 cases, after initial curative treatment, ctDNA remained negative and patients were alive without recurrence. Patients who remained negative for ctDNA during follow‐up after initial curative treatment (n = 11) had a significantly better prognosis than those who reverted to ctDNA positivity (n = 7; p < 0.0001; log‐rank test). Individualized ctDNA monitoring using SCC panel and dPCR might be a novel and promising biomarker for HNSCC.

- **verdict:** valid
- **why:** All criteria met.

---

## 3. `PMC10993710:abstract:320`

- **stratum:** abstract  (section title: Methods)
- **source:** PMC10993710, abstract [320:699], published 2024
- **anchors:** 'ovarian cancer patients', 'olaparib or niraparib'

**lexical query** (lexical overlap 0.75)

> How many ovarian cancer patients received olaparib or niraparib in the study?

**paraphrased query** (lexical overlap 0.44)

> What is the total number of ovarian cancer cases treated with olaparib or niraparib in this Japanese cohort?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

This retrospective study included 181 ovarian cancer patients who received olaparib or niraparib at two independent hospitals in Japan between May 2018 and December 2022. Clinical information and blood sampling data were collected. Patient characteristics, treatment history, and predictability of treatment duration based on blood data before treatment initiation were examined.

- **verdict:** wrong
- **why:** Queries lack paper-specific context ("in the study", "in this Japanese cohort" are too vague).

---

## 4. `PMC8566594:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC8566594, abstract [0:1090], published 2021
- **anchors:** 'CREBBP/EP300', 'squamous cell carcinoma'

**lexical query** (lexical overlap 0.69)

> What is the association between CREBBP/EP300 mutations and recurrence after radiation in squamous cell carcinoma?

**paraphrased query** (lexical overlap 0.31)

> Do alterations in CREBBP or EP300 correlate with post‑radiotherapy relapse in SCC patients?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Despite radiation forming the curative backbone of over 50% of malignancies, there are no genomically-driven radiosensitizers for clinical use. Herein we perform in vivo shRNA screening to identify targets generally associated with radiation response as well as those exhibiting a genomic dependency. This identifies the histone acetyltransferases CREBBP/EP300 as a target for radiosensitization in combination with radiation in cognate mutant tumors. Further in vitro and in vivo studies confirm this phenomenon to be due to repression of homologous recombination following DNA damage and reproducible using chemical inhibition of histone acetyltransferase (HAT), but not bromodomain function. Selected mutations in CREBBP lead to a hyperacetylated state that increases CBP and BRCA1 acetylation, representing a gain of function targeted by HAT inhibition. Additionally, mutations in CREBBP/EP300 are associated with recurrence following radiation in squamous cell carcinoma cohorts. These findings provide both a mechanism of resistance and the potential for genomically-driven treatment.

- **verdict:** valid
- **why:** All criteria met.

---

## 5. `PMC8584247:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC8584247, abstract [0:1487], published 2021
- **anchors:** 'TNBC samples', 'AR expression'

**lexical query** (lexical overlap 0.75)

> What percentage of TNBC samples lacked AR expression?

**paraphrased query** (lexical overlap 0.42)

> How often is androgen receptor absent in triple‑negative breast cancer specimens?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Triple-negative breast cancer (TNBC) can be further classified into androgen receptor (AR)-positive TNBC and AR-negative TNBC or quadruple-negative breast cancer (QNBC). Here, we investigated genomic instability in 53 clinical cases by array-CGH and miRNA expression profiling. Immunohistochemical analysis revealed that 64% of TNBC samples lacked AR expression. This group of tumors exhibited a higher level of copy number alterations (CNAs) and a higher frequency of cases affected by CNAs than TNBCs. CNAs in genes of the chromosome instability 25 (CIN25) and centrosome amplification (CA) signatures were more frequent in the QNBCs and were similar between the groups, respectively. However, expression levels of CIN25 and CA20 genes were higher in QNBCs. miRNA profiling revealed 184 differentially expressed miRNAs between the groups. Fifteen of these miRNAs were mapped at cytobands with CNAs, of which eight (miR-1204, miR-1265, miR-1267, miR-23c, miR-548ai, miR-567, miR-613, and miR-943), and presented concordance of expression and copy number levels. Pathway enrichment analysis of these miRNAs/mRNAs pairings showed association with genomic instability, cell cycle, and DNA damage response. Furthermore, the combined expression of these eight miRNAs robustly discriminated TNBCs from QNBCs (AUC = 0.946). Altogether, our results suggest a significant loss of AR in TNBC and a profound impact in genomic instability characterized by CNAs and deregulation of miRNA expression.

- **verdict:** wrong
- **why:** Queries lack paper-specific context; the percentage of TNBC samples lacking AR expression is measured in many studies.

---

## 6. `PMC9582144:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC9582144, abstract [0:1928], published 2022
- **anchors:** 'C2 subtype', 'IC50 values'

**lexical query** (lexical overlap 0.89)

> What is the IC50 values level for the C2 subtype?

**paraphrased query** (lexical overlap 0.67)

> How does the C2 subtype compare in drug sensitivity measured by IC50?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Copper (Cu) is an essential element of organisms, which can affect the survival of cells. However, the role of copper metabolism and cuproptosis on hepatic carcinoma is still unclear. In this study, the TCGA database was used as the test set, and the ICGC database and self-built database were used as the validation set. We screened out a class of copper metabolism and cuproptosis-related genes (CMCRGs) that could influence hepatic carcinoma prognosis by survival analysis and differential comparison. Based on CMCRGs, patients were divided into two subtypes by cluster analysis. The C2 subtype was defined as the high copper related subtype, while the C1 subtype was defied as the low copper related subtype. At the clinical level, compared with the C1 subtype, the C2 subtype had higher grade pathological features, risk scores, and worse survival. In addition, the immune response and metabolic status also differed between C1 and C2. Specifically, C2 subtype had a higher proportion of immune cell composition and highly expressed immune checkpoint genes. C2 subtype had a higher TIDE score with a higher proportion of tumor immune dysfunction and exclusion. At the molecular level, the C2 subtype had a higher frequency of driver gene mutations (TP53 and OBSCN). Mechanistically, the single nucleotide polymorphisms of C2 subtype had a very strong transcriptional strand bias for C>A mutations. Copy number variations in the C2 subtype were characterized by LOXL3 CNV gain, which also showed high association with PDCD1/CTLA4. Finally, drug sensitivity responsiveness was assessed in both subtypes. C2 subtype had lower IC50 values for targeted and chemotherapeutic agents (sorafenib, imatinib and methotrexate, etc.). Thus, CMCRGs related subtypes showed poor response to immunotherapy and better responsiveness to targeted agents, and the results might provide a reference for precision treatment of hepatic carcinoma.

- **verdict:** wrong
- **why:** Queries are completely lacking in context; "C2 subtype" without specifying the disease or classification system is too generic.

---