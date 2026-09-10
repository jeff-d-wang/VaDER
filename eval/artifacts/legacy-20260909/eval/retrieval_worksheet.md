# Retrieval set spot-check worksheet

20 of the retrieval set's 138 paragraphs, one per stratum in rotation, sampled at seed
0. Both queries generated from a paragraph are shown together, because they share its gold
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
python -m eval.make_case_worksheet --summarize eval/retrieval_worksheet.md
```

---

## 1. `PMC9691822:abstract:321`

- **stratum:** abstract  (section title: Methods)
- **source:** PMC9691822, abstract [321:1147], published 2022
- **anchors:** 'KARMA', '66\u202f415 women', '313-SNPs'

**lexical query** (lexical overlap 0.90)

> What is the 5-year breast cancer risk calibration in the KARMA cohort of 66 415 women using a 313-SNPs polygenic risk score?

**paraphrased query** (lexical overlap 0.58)

> How accurately does the 5-year risk model predict cancer in the KARMA study involving 66 415 women when a polygenic score of 313-SNPs is applied?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

We validated BOADICEA (V.6) in the Swedish KARolinska Mammography Project for Risk Prediction of Breast Cancer (KARMA) cohort including 66 415 women of European ancestry (median age 54 years, IQR 45–63; 816 incident breast cancers) without previous cancer diagnosis. We calculated 5-year risks on the basis of questionnaire-based risk factors, pedigree-structured first-degree family history, mammographic density (BI-RADS), a validated breast cancer polygenic risk score (PRS) based on 313-SNPs, and pathogenic variant status in 8 breast cancer susceptibility genes: BRCA1, BRCA2, PALB2, CHEK2, ATM, RAD51C, RAD51D and BARD1. Calibration was assessed by comparing observed and expected risks in deciles of predicted risk and the calibration slope. The discriminatory ability was assessed using the area under the curve (AUC).

- **verdict:** wrong
- **why:** The paragraph states that 5-year risks were calculated using the 313-SNP polygenic risk score (along with other factors) and that calibration was assessed, but it does not actually report the results of that calibration or predictive accuracy (the answer to "How accurately...").[cite: 4]

---

## 2. `PMC7694425:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC7694425, body [0:857], published 2020
- **anchors:** 'bladder cancer', 'muscle-invasive bladder cancer'

**lexical query** (lexical overlap 0.69)

> What is the prognosis and recurrence rate of muscle-invasive bladder cancer compared to bladder cancer?

**paraphrased query** (lexical overlap 0.42)

> How does muscle-invasive bladder cancer differ in aggressiveness and relapse frequency from bladder cancer?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Bladder cancer is one of the most common and highly intratumor heterogeneous malignant tumors of the genitourinary system. Bladder urothelial carcinoma is the most common type, accounting for greater than 90% of all bladder cancers [1]. The majority of bladder cancers occur in men, and there is a wide variation in the incidence and mortality rates worldwide [2]. Based on the degree of tumor invasion, bladder cancers can be categorized as non-muscle-invasive bladder cancer (NMIBC) and muscle-invasive bladder cancer (MIBC). Both NMIBC and MIBC are major sources of morbidity and mortality worldwide. MIBC is associated with greater malignancy, a more diverse mutational spectrum, higher recurrence rate, and worse overall prognosis. Molecular markers have shown potential value in improving diagnostic accuracy of risk stratification of patients [3, 4].

- **verdict:** valid
- **why:** The paragraph explicitly answers the queries by stating MIBC is associated with greater malignancy, a higher recurrence rate, and worse overall prognosis compared to NMIBC. The queries are specific, and the paraphrased version is genuinely reworded ("aggressiveness and relapse frequency" vs "prognosis and recurrence rate").[cite: 4]

---

## 3. `PMC9543999:body:2808`

- **stratum:** methods  (section title: Patients and samples)
- **source:** PMC9543999, body [2808:3582], published 2022
- **anchors:** 'eight CLL patients', 'four patients'

**lexical query** (lexical overlap 0.75)

> How many eight CLL patients had clonally unrelated RS and how many four patients had clonally related RS?

**paraphrased query** (lexical overlap 0.53)

> What are the numbers of unrelated RS transformations among the eight CLL patients compared to the related RS cases among the four patients?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

This study included paired CLL and RS tumour samples from eight CLL patients who transformed into clonally unrelated RS and for whom biological material was longitudinally available. Four patients with clonally related RS were also included for comparative purposes. Diagnosis of RS was assessed by two experienced pathologists (Annalisa Andorno and Renzo Boldorini). Tumour genomic DNA (gDNA) from both the CLL and the RS clone was retrospectively analysed. Patients provided informed consent in accordance with institutional review board requirements and the Declaration of Helsinki. The study was approved by the Ethical Committee of the Ospedale Maggiore della Carità di Novara associated with the Università del Piemonte Orientale (study number CE 67/14 and CE 120/19).

- **verdict:** wrong
- **why:** The queries ask "how many" patients had these respective transformations, but the answers are trivially embedded in the premise of the questions themselves ("eight CLL patients" and "four patients"). This makes the queries tautological rather than answerable questions.[cite: 4]

---

## 4. `PMC3849250:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC3849250, abstract [0:1023], published 2013
- **anchors:** 'BRCA1 5382insC', 'PKC-theta'

**lexical query** (lexical overlap 0.79)

> What is the level of PKC-theta in BRCA1 5382insC mutant iPSCs compared to wild-type iPSCs?

**paraphrased query** (lexical overlap 0.56)

> How does PKC-theta expression differ in iPSC lines carrying the BRCA1 5382insC mutation versus those without the mutation?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Understanding BRCA1 mutant cancers is hampered by difficulties in obtaining primary cells from patients. We therefore generated and characterized 24 induced pluripotent stem cell (iPSC) lines from fibroblasts of eight individuals from a BRCA1 5382insC mutant family. All BRCA1 5382insC heterozygous fibroblasts, iPSCs, and teratomas maintained equivalent expression of both wild-type and mutant BRCA1 transcripts. Although no difference in differentiation capacity was observed between BRCA1 wild-type and mutant iPSCs, there was elevated protein kinase C-theta (PKC-theta) in BRCA1 mutant iPSCs. Cancer cell lines with BRCA1 mutations and hormone-receptor-negative breast cancers also displayed elevated PKC-theta. Genome sequencing of the 24 iPSC lines showed a similar frequency of reprogramming-associated de novo mutations in BRCA1 mutant and wild-type iPSCs. These data indicate that iPSC lines can be derived from BRCA1 mutant fibroblasts to study the effects of the mutation on gene expression and genome stability.

- **verdict:** valid
- **why:** The paragraph answers the query by stating there was "elevated protein kinase C-theta (PKC-theta) in BRCA1 mutant iPSCs" compared to wild-type. The queries are specific to the exact mutation and cell type, and the paraphrased version is sufficiently distinct.[cite: 4]

---

## 5. `PMC3466113:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC3466113, body [0:833], published 2012
- **anchors:** 'EGFR', 'ALK'

**lexical query** (lexical overlap 0.79)

> What is the prevalence of activating mutations in EGFR and ALK fusions in lung squamous cell carcinoma according to the paragraph?

**paraphrased query** (lexical overlap 0.71)

> How common are EGFR activating alterations and ALK rearrangements in lung SqCC as described?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Lung cancer is the leading cause of cancer-related mortality worldwide, leading to an estimated 1.4 million deaths in 20101. The discovery of recurrent mutations in the Epidermal Growth Factor Receptor (EGFR) kinase as well as fusions involving the Anaplastic Lymphoma Kinase (ALK), has led to a dramatic change in the treatment of patients with lung adenocarcinoma, the most common type of lung cancer2–5. More recent data have suggested that targeting mutations in BRAF, AKT1, ERBB2 and PIK3CA and fusions that involve ROS1 and RET may also be successful6,7. Unfortunately, activating mutations in EGFR and ALK fusions are typically not present in the second most common type of lung cancer, lung squamous cell carcinoma (lung SqCC),8 and targeted agents developed for lung adenocarcinoma are largely ineffective against lung SqCC.

- **verdict:** valid
- **why:** The paragraph directly answers the queries by stating these mutations are "typically not present" in lung SqCC. The queries are highly specific to the genetic alterations and cancer subtype, and the paraphrase is distinct.[cite: 4]

---

## 6. `PMC12834284:body:3974`

- **stratum:** methods  (section title: Study Population and Data Collection)
- **source:** PMC12834284, body [3974:4580], published 2026
- **anchors:** 'C-CAT', 'OncoGuide NCC Oncopanel System'

**lexical query** (lexical overlap 0.60)

> Which patients in the C-CAT registry underwent comprehensive genomic profiling using the OncoGuide NCC Oncopanel System?

**paraphrased query** (lexical overlap 0.74)

> What Japanese advanced anal or rectal cancer cases listed in C-CAT were analyzed with the OncoGuide NCC Oncopanel System?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Data were extracted retrospectively for patients with advanced anal or rectal AD who underwent CGP and were registered at the Center for Cancer Genomics and Advanced Therapeutics (C-CAT) in Japan on May 2, 2023 (ver.6.00). The C-CAT database comprehensively aggregates clinical and genomic information on Japanese patients with an advanced malignant tumor who underwent CGP by NGS.11 All these patients had completed or were nearing completion of standard treatment for their tumor. Two different platforms were used for NGS: OncoGuide NCC Oncopanel System12 and FoundationOne CDx Cancer Genomic Profile.13

- **verdict:** valid
- **why:** The paragraph answers the queries by identifying the patients as those with advanced anal or rectal AD who had completed or were nearing completion of standard treatment. The queries are highly specific, and the paraphrase changes the structure and vocabulary.[cite: 4]

---

## 7. `PMC8584247:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC8584247, abstract [0:1487], published 2021
- **anchors:** '64% of TNBC', 'QNBCs'

**lexical query** (lexical overlap 0.62)

> What proportion of TNBC samples lacked AR expression (64% of TNBC) and how does this compare to QNBCs?

**paraphrased query** (lexical overlap 0.44)

> How many triple‑negative breast cancers are AR‑negative (64% of TNBC) and what is their relationship with QNBCs?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Triple-negative breast cancer (TNBC) can be further classified into androgen receptor (AR)-positive TNBC and AR-negative TNBC or quadruple-negative breast cancer (QNBC). Here, we investigated genomic instability in 53 clinical cases by array-CGH and miRNA expression profiling. Immunohistochemical analysis revealed that 64% of TNBC samples lacked AR expression. This group of tumors exhibited a higher level of copy number alterations (CNAs) and a higher frequency of cases affected by CNAs than TNBCs. CNAs in genes of the chromosome instability 25 (CIN25) and centrosome amplification (CA) signatures were more frequent in the QNBCs and were similar between the groups, respectively. However, expression levels of CIN25 and CA20 genes were higher in QNBCs. miRNA profiling revealed 184 differentially expressed miRNAs between the groups. Fifteen of these miRNAs were mapped at cytobands with CNAs, of which eight (miR-1204, miR-1265, miR-1267, miR-23c, miR-548ai, miR-567, miR-613, and miR-943), and presented concordance of expression and copy number levels. Pathway enrichment analysis of these miRNAs/mRNAs pairings showed association with genomic instability, cell cycle, and DNA damage response. Furthermore, the combined expression of these eight miRNAs robustly discriminated TNBCs from QNBCs (AUC = 0.946). Altogether, our results suggest a significant loss of AR in TNBC and a profound impact in genomic instability characterized by CNAs and deregulation of miRNA expression.

- **verdict:** wrong
- **why:** Both queries ask "how many" or "what proportion", but simultaneously provide the exact answer ("64% of TNBC") in the text of the query itself, making them tautological.[cite: 4]

---

## 8. `PMC7596644:body:682`

- **stratum:** intro  (section title: INTRODUCTION)
- **source:** PMC7596644, body [682:3479], published 2020
- **anchors:** 'deep learning', 'H&E-stained'

**lexical query** (lexical overlap 0.91)

> Can deep learning predict molecular alterations from H&E-stained tissue slides?

**paraphrased query** (lexical overlap 0.81)

> Is it possible to infer genetic mutations using deep learning analysis of H&E-stained cancer sections?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Identifying genetic mutations in cancer patients has been increasingly important because mutational status can be very informative to determine the optimal therapeutic strategy[1]. However, molecular analysis is not performed routinely in every cancer patient, since it is not time and cost effective[2]. Thus, cost-effective alternatives for current molecular tests can be helpful in making appropriate treatment decisions. It has long been recognized that the histologic phenotypes reflect the genetic alterations in cancer tissues[3]. Since hematoxylin and eosin (H&E)-stained tissue slides are produced for almost every cancer patient, mutation prediction from the tissue slides can be a time- and cost-effective alternative method for individualized treatment. Thus, researchers attempted to examine the genotype–phenotype relationship in the H&E-stained tissue slides, and some gross tissue patterns related to specific molecular aberrations have been reported[4-9]. However, it remains largely unknown how specific molecular abnormalities are related to the specific histomorphologic findings, as it is not easy to capture the subtle features underlying the specific molecular alterations with the naked eye. To overcome the limitation of visual inspection of tissue structures by pathologists, various image analysis techniques have been applied for many decades to detect the subvisual characteristics of tissue patterns, not discernible to the unaided eyes[1]. Particularly, deep learning has been successfully applied to perform tasks considered too challenging for conventional image analysis techniques because it learns discriminative features directly from the large training dataset for any given task[10]. Therefore, deep learning is increasingly applied for tissue analysis tasks[11]. With the approval to use the digitized whole-slide images (WSIs) for diagnostic purposes, the digitization of tissue slides has been explosively increasing, providing huge digitized tissue data[12]. Combining the routine digitization of tissue slides with deep learning, the computer-aided analysis of WSIs could be adopted to support the evaluation of molecular alterations in H&E-stained cancer tissues in the near future. Although deep learning-based tissue analysis is still in its early phase, few promising results have been published. For example, a recent study reported that deep learning-based molecular cancer subtyping can be performed directly from the standard H&E sections obtained from patients with colorectal cancers (CRCs)[13]. Microsatellite instability can also be predicted from the tissue slides[14]. Furthermore, positive results for the mutation prediction of specific genes from histopathologic images have been reported in patients with various cancer types[3,15-17].

- **verdict:** valid
- **why:** The paragraph answers the queries by citing recent studies reporting positive results for predicting molecular cancer subtyping, microsatellite instability, and specific gene mutations using deep learning on H&E slides. The queries are specific, and the paraphrase is distinct.[cite: 4]

---

## 9. `PMC8086250:body:5601`

- **stratum:** methods  (section title: Sequencing methods)
- **source:** PMC8086250, body [5601:6401], published 2021
- **anchors:** '1663 amplicons', '159 kb'

**lexical query** (lexical overlap 0.71)

> How many amplicons were designed to cover the 159 kb target region, specifically 1663 amplicons?

**paraphrased query** (lexical overlap 0.53)

> What is the count of designed amplicons that span the 159 kb target area, namely 1663 amplicons?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Target sequence enrichment followed by sequencing was performed on the coding sequence and splice-sites of ALKBH3, ANAPC2, BUB1B, C5ORF28, C6, CHEK2, CNKSR1, DNAJB4, DUOX1, EXO1, FANCA, FANCB, FANCC, FANCD2, FANCE, FANCG, FANCI, FBXO10, GANC, GTF2H4, KNTC1, LIG4, MKNK2, MMRN1, NAT10, OSGIN1, PAK4, PALB2, PARP1, PHF20L1, PIK3C2G, POLE, POLK, PSG6, PTGER3, PTX3, RAD52, RAD54B, RDM1, RECQL, REV3L, RIPK3, RNASEL, SLX4, SMC1A, SMG5, SNRNP200, SPHK1, SULT1C2, UHRF2, UPK2, WNT5A, XRCC1 and ZFHX3. The target sequence was identified from the NCBI Reference Sequence Database48.48 Fluidigm access arrays as previously described.6 A total of 1663 amplicons were designed to cover the 159 kb target region. Libraries were sequenced using 150 bp paired-end sequencing on the Illumina HiSeq4000 or HiSeq2500.

- **verdict:** wrong
- **why:** The queries are tautological; they ask "How many amplicons... specifically 1663 amplicons?" and "What is the count... namely 1663 amplicons?" The answer is baked into the question.[cite: 4]

---

## 10. `PMC4519264:abstract:280`

- **stratum:** abstract  (section title: Methods)
- **source:** PMC4519264, abstract [280:651], published 2015
- **anchors:** '359 breast cancer patients', 'National Cancer Center Singapore'

**lexical query** (lexical overlap 0.79)

> What is the number of 359 breast cancer patients accrued at the National Cancer Center Singapore?

**paraphrased query** (lexical overlap 0.77)

> How many 359 breast cancer patients were collected at the National Cancer Center Singapore?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

A total of 359 breast cancer patients, who presented with either a family history (FH) of breast and/or ovarian cancer or early onset breast cancer, were accrued at the National Cancer Center Singapore (NCCS). The relationships between clinico-pathological features and mutational status were calculated using the Chi-squared test and binary logistic regression analysis.

- **verdict:** wrong
- **why:** The queries are tautological ("What is the number of 359 breast cancer patients..."). Furthermore, the paragraph merely describes patient accrual for a methodology, not an empirical finding or result.[cite: 4]

---

## 11. `PMC10859687:body:0`

- **stratum:** intro  (section title: INTRODUCTION)
- **source:** PMC10859687, body [0:1100], published 2024
- **anchors:** 'ribosome biogenesis', 'RiboSis'

**lexical query** (lexical overlap 0.60)

> What is the role of ribosome biogenesis (RiboSis) in cancer according to recent pan‑cancer analyses?

**paraphrased query** (lexical overlap 0.47)

> How does the process of ribosome biogenesis (RiboSis) contribute to tumor development as shown by large‑scale cancer studies?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Ribosome biogenesis (RiboSis) is a complex process that generates ribosomes required for protein synthesis in the growth and proliferation of cells [1–3]. It is a tightly coordinated process that involves three RNA polymerases, approximately 80 ribosomal proteins, and approximately 200 non-ribosomal trans-acting factors [4, 5]. RiboSis includes rRNA transcription, rRNA cleavage, rRNA modification, ribosome assembly and export of ribosomal pre-particles [6]. In malignant cells, the genes involved in each substep of RiboSis undergo somatic alterations, resulting in ribosomopathies and an increased risk of carcinogenesis [7, 8]. The concept that ‘ribosomes translate cancer’ has gained increasing recognition [9, 10]. Thus, understanding the contribution of these alterations to pathogenesis will allow for unveiling novel and targetable vulnerabilities in cancer. Owing to large-scale and multi-dimensional open-access data, there are numerous pan-cancer studies relevant to gene signatures [11–16]. However, a systematic analysis of genes involved in RiboSis in human cancers has been lacking.

- **verdict:** wrong
- **why:** The paragraph mentions that somatic alterations in RiboSis genes increase the risk of carcinogenesis and that "ribosomes translate cancer," but it specifically states that a "systematic analysis of genes involved in RiboSis in human cancers has been lacking." It does not actually provide the results of a recent pan-cancer analysis as requested by the queries.[cite: 4]

---

## 12. `PMC6488144:body:1935`

- **stratum:** methods  (section title: Subjects and Methods)
- **source:** PMC6488144, body [1935:3739], published 2019
- **anchors:** 'BRCA mutation', '6691 Austrian women'

**lexical query** (lexical overlap 0.93)

> What testing methods were used for BRCA mutation in the cohort of 6691 Austrian women?

**paraphrased query** (lexical overlap 0.64)

> Which diagnostic techniques were applied to detect BRCA mutation among the 6691 Austrian women?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

In Austria, genetic testing for BRCA mutation has been conducted in Vienna General Hospital since 1995. Denaturing high‐performance liquid chromatography (dHPLC) and Sanger sequencing were the molecular diagnostic methods used up to 2007. From 2007 to 2015, Sanger sequencing alone was used in place of dHPLC, and multiplex ligation‐dependent probe amplification (MLPA) was performed subsequently to identify large deletions or duplications. MLPA was also conducted retrospectively on patient samples collected prior to 2007. From 2015 onward, next‐generation sequencing is performed in the General Hospital in place of MLPA/Sanger sequencing. Detected mutations are confirmed by Sanger sequencing and MLPA, respectively. Women are offered testing if their familial history fulfills at least one of the following criteria: (a) three cases of BC below age 60, (b) two cases of BC below age 50, (c) one case of BC below age 35, (d) one BC case below age 50, (e) one case of OC at any age, (f) two cases of OC at any age, and (g) male and female BC. From 2015 onward, germline testing is also offered to all women who were diagnosed with epithelial OC regardless of family history of cancer at no cost.13 To identify these individuals, we searched our nationwide cohort of 6691 Austrian women (as of February 2016) who had fulfilled the selection criteria above, had provided informed consent, had undergone germline BRCA (gBRCA) mutation analysis, and had provided a comprehensive family history at the time of analysis. Patients were followed longitudinally and received regular questionnaires every 2 years in order to identify incident familial breast and ovarian cancers. This study was approved by the Ethics Committee of the Medial University of Vienna in accordance with the Declaration of Helsinki.

- **verdict:** valid
- **why:** The paragraph answers the query by detailing the chronological use of dHPLC, Sanger sequencing, MLPA, and next-generation sequencing for the cohort. The queries are specific to the cohort and testing methods, and the paraphrase is distinct.[cite: 4]

---

## 13. `PMC10965219:abstract:0`

- **stratum:** abstract  (section title: PURPOSE)
- **source:** PMC10965219, abstract [0:791], published 2024
- **anchors:** 'PARPi', 'Myriad myChoice', 'high-grade serous ovarian cancer'

**lexical query** (lexical overlap 0.65)

> What clinical benefit do PARPi provide for patients with HRD when assessed by Myriad myChoice in high-grade serous ovarian cancer?

**paraphrased query** (lexical overlap 0.67)

> How effective are PARPi therapies for HRD‑positive high-grade serous ovarian cancer according to the Myriad myChoice assay?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Poly(ADP-ribose) polymerase inhibitors (PARPi) have shown promising clinical results in the treatment of ovarian cancer. Analysis of biomarker subgroups consistently revealed higher benefits for patients with homologous recombination deficiency (HRD). The test that is most often used for the detection of HRD in clinical studies is the Myriad myChoice assay. However, other assays can also be used to assess biomarkers, which are indicative of HRD, genomic instability (GI), and BRCA1/2 mutation status. Many of these assays have high potential to be broadly applied in clinical routine diagnostics in a time-effective decentralized manner. Here, we compare the performance of a multitude of alternative assays in comparison with Myriad myChoice in high-grade serous ovarian cancer (HGSOC).

- **verdict:** wrong
- **why:** The paragraph states that PARPi have shown promising results and higher benefits for HRD patients, but it does not specify what the actual clinical benefit is (e.g., progression-free survival months, hazard ratios). It serves as an introduction to comparing testing assays, not a report on PARPi efficacy.[cite: 4]

---

## 14. `PMC11930871:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC11930871, body [0:931], published 2025
- **anchors:** 'BRCA1/2', '8–14%'

**lexical query** (lexical overlap 0.79)

> What proportion of breast cancer cases in West Africa is estimated to be due to pathogenic variants, with estimates of 8–14% and involving BRCA1/2?

**paraphrased query** (lexical overlap 0.70)

> How many breast cancer occurrences in West African cohorts are linked to germline pathogenic variants, reported at 8–14% and including BRCA1/2?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

There were 11,020 women diagnosed with breast cancer (BC) in South Africa in 2022, making it the commonest cancer in females [1]. A proportion are expected to be attributable to pathogenic or likely pathogenic (P/LP) variants in a germline BC susceptibility gene, such as BRCA1/2. Population-based studies from the USA put this proportion at 5–10% [2, 3]. Similar data from Africa is scarce, but West African studies give estimates of 8–14% [4–6]. P/LP variants in these genes are associated with lifetime risks of BC of 40%–85% for high risk genes and 20%–40% for moderate risk genes, causing significant morbidity and mortality [7]. In addition, the risks of other cancers, such as ovarian and pancreatic cancers, are often also increased in gene carriers. Identifying individuals with these P/LP variants allows intensified surveillance, risk-reducing surgical interventions and modifications to cancer treatment to be made [8].

- **verdict:** wrong
- **why:** The queries are tautological ("What proportion... with estimates of 8-14%").[cite: 4]

---

## 15. `PMC4396398:body:3930`

- **stratum:** methods  (section title: Statistical analyses)
- **source:** PMC4396398, body [3930:4540], published 2015
- **anchors:** 'Kaplan–Meier survival estimator', 'TP53 mutation detection'

**lexical query** (lexical overlap 0.74)

> What statistical method was used to calculate survival analysis and time to mutation detection using the Kaplan–Meier survival estimator and TP53 mutation detection?

**paraphrased query** (lexical overlap 0.65)

> Which analysis technique employed the Kaplan–Meier survival estimator to evaluate overall survival and the timing of identifying new TP53 mutation detection?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Fisher's exact test was used to assess the association between categorical variables. Mann–Whitney test was used to compare the continuous variables. Wilcoxon signed-rank test was used for paired comparison of mutation numbers. Survival analysis and time to mutation detection were calculated using the Kaplan–Meier survival estimator. Overall survival was assessed from the date of diagnosis; only disease-related death was considered as an event. Time to mutation detection was assessed from the date of diagnosis to the date of new TP53 mutation detection (event) or the last TP53-wt examination (censored).

- **verdict:** wrong
- **why:** The lexical query is malformed and tautological ("What statistical method was used... using the Kaplan-Meier survival estimator"). The paragraph also just describes the methods used, not any actual results or findings.[cite: 4]

---

## 16. `PMC1557738:abstract:0`

- **stratum:** abstract  (section title: Introduction)
- **source:** PMC1557738, abstract [0:980], published 2006
- **anchors:** 'exon 6 c.449G>A', 'RAD51-/- mice'

**lexical query** (lexical overlap 0.83)

> What is the reported coding region variant exon 6 c.449G>A in RAD51 and what phenotype is observed in RAD51-/- mice?

**paraphrased query** (lexical overlap 0.64)

> Which mutation exon 6 c.449G>A has been identified in the RAD51 gene and what developmental outcome occurs in organisms lacking RAD51 (RAD51-/- mice)?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Human RAD51 is a homologue of the Escherichia coli RecA protein and is known to function in recombinational repair of double-stranded DNA breaks. Mutations in the lower eukaryotic homologues of RAD51 result in a deficiency in the repair of double-stranded DNA breaks. Loss of RAD51 function would therefore be expected to result in an elevated mutation rate, leading to accumulation of DNA damage and, hence, to increased cancer risk. RAD51 interacts directly or indirectly with a number of proteins implicated in breast cancer, such as BRCA1 and BRCA2. Similar to BRCA1 mice, RAD51-/- mice are embryonic lethal. The RAD51 gene region has been shown to exhibit loss of heterozygosity in breast tumours, and deregulated RAD51 expression in breast cancer patients has also been reported. Few studies have investigated the role of coding region variation in the RAD51 gene in familial breast cancer, with only one coding region variant – exon 6 c.449G>A (p.R150Q) – reported to date.

- **verdict:** valid
- **why:** The paragraph explicitly answers both parts of the queries: it identifies the variant in the context of familial breast cancer and states that RAD51-/- mice are embryonic lethal. The paraphrase is distinct, and the queries are specific.[cite: 4]

---

## 17. `PMC6446860:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC6446860, body [0:647], published 2019
- **anchors:** 'DNA double strand breaks', 'cell fate'

**lexical query** (lexical overlap 0.67)

> What cellular programs are enacted in response to DNA double strand breaks and how is cell fate determined?

**paraphrased query** (lexical overlap 0.53)

> Which repair mechanisms activate after DNA double strand breaks and what outcomes influence cell fate?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The cellular response to DNA double strand breaks (DSBs) involves coordinated expression of several distinct pathways with unique temporal dynamics. The pathways enact cellular programs necessary for DNA repair and for determination of cell fate (Khanna and Jackson, 2001). As an immediate response, repair complexes are rapidly recruited to the sites of breakage (Nakamura et al., 2010; Polo and Jackson, 2011). During the repair process, cells enter a transient state of growth arrest. Depending on the outcome of the repair, cells will either reenter the cell cycle, permanently arrest via senescence, or undergo cell death (Noda et al., 2012).

- **verdict:** valid
- **why:** The paragraph answers the queries by stating that cells enter a state of growth arrest, and depending on repair outcomes, will reenter the cell cycle, permanently arrest via senescence, or undergo cell death. The paraphrase changes the wording effectively.[cite: 4]

---

## 18. `PMC8730771:body:4665`

- **stratum:** methods  (section title: Methods)
- **source:** PMC8730771, body [4665:6767], published 2022
- **anchors:** 'cancereffectsizeR', 'deconstructSigs'

**lexical query** (lexical overlap 0.79)

> How does cancereffectsizeR calculate cancer effect sizes using tumor-specific mutation rates and deconstructSigs weights?

**paraphrased query** (lexical overlap 0.50)

> What method employs cancereffectsizeR to estimate effect sizes by incorporating mutation-rate adjustments and deconstructSigs signature weighting?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The cancer effect sizes for point mutations were calculated using cancereffectsizeR (https://github.com/townsend-lab-yale/cancereffectsizeR, v0.1.1.9010) as previously described11 with the exception that the likelihood of the scaled selection coefficient was maximized based on tumor-specific mutation rates, and only COSMIC14 signatures were used for each tumor type. In summary, the expected frequency μ that nucleotide mutations occur before being acted on by selection over the average amount of time elapsed throughout the evolutionary process driving tumorigenesis (from initialization to surgical resection) was defined by calculating the expected frequency that silent mutations occur at the gene level using dNdScv,19 an R package that calculates the change in non-synonymous divergence (dN) relative to synonymous divergence (dS) informed by mutational covariates (cv). Each possible nucleotide mutation was scaled by a coefficient corresponding to the relative expected frequency within its trinucleotide context given the specific trinucleotide mutation rates in each tumor. The effect of the trinucleotide context was quantified as the product of the mutational signature weights and their relative trinucleotide mutation rates as detected with deconstructSigs.20 deconstructSigs weights for tumors with less than 50 substitutions—below which calculating the exact trinucleotide signatures becomes increasingly error-prone—were assessed as n/50 times the trinucleotide weights of that tumor plus (50 – n)/50 times the average trinucleotide weights of the tumors in that tumor type with greater than 50 substitutions, where n is the number of substitutions in that tumor. Defining the rate of substitution, λ, as the frequency at which genetic variants were observed within sequence data, we corrected λ for the fact that one can only observe one substitution per site, even though a flux of mutations at a given rate will generate a Poisson-distributed number of substitutions.11 False-discovery rates represented as Q values were calculated by dndscv as described by Martincorena et al.19

- **verdict:** valid
- **why:** The paragraph exhaustively details the methodology for calculating the cancer effect sizes, including the use of dNdScv for baseline frequencies and scaling by relative expected frequencies using mutational signature weights from deconstructSigs. The queries are specific, and the paraphrase is distinct.[cite: 4]

---

## 19. `PMC5980867:abstract:0`

- **stratum:** abstract  (section title: Purpose:)
- **source:** PMC5980867, abstract [0:453], published 2018
- **anchors:** 'BRCA1-3’UTR', 'rs8176318G>T', 'Saudi Arabia'

**lexical query** (lexical overlap 0.72)

> What is the association of the BRCA1-3’UTR germline variant rs8176318G>T with breast cancer susceptibility in Saudi Arabia?

**paraphrased query** (lexical overlap 0.67)

> How does the rs8176318G>T change in the BRCA1-3’UTR relate to breast cancer risk among Saudi Arabian women?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The impact of the BRCA1-3’UTR-variant on BRCA1 gene expression and altered responses to external stimuli was previously tested in vitro using a luciferase reporter assay. Its ability to predict breast cancer risk in women was also assessed but the conclusions were inconsistent. The present study concerns the relationship between the BRCA1-3’UTR germline variant rs8176318G>T and susceptibility to Breast cancer in an ethnic population of Saudi Arabia.

- **verdict:** wrong
- **why:** The paragraph only states that the study concerns the relationship between the variant and breast cancer susceptibility in Saudi Arabia. It does not actually provide the result or answer what the association is.[cite: 4]

---

## 20. `PMC12367850:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC12367850, body [0:831], published 2025
- **anchors:** '0.1%', '5% of cases'

**lexical query** (lexical overlap 0.68)

> What proportion of the population is affected by clinically relevant pituitary tumours (0.1%) and what percentage of cases are familial pituitary tumours (5% of cases)?

**paraphrased query** (lexical overlap 0.60)

> How common are clinically relevant pituitary tumors in the general population (0.1%) and what share of them are familial (5% of cases)?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Clinically relevant pituitary tumours affect approximately 0.1% of the population, with familial pituitary tumours accounting for 5% of cases [1]. Established heritable causes of pituitary tumours include variants in genes associated with isolated familial pituitary tumours (e.g., AIP, GPR101) and syndromic disease (e.g., MEN1, CDKN1B, PRKAR1A, the SDHx genes) [2]. Germline variants in several of these genes also contribute to sporadic pituitary tumorigenesis [3]. However, there is missing heritability, with approximately 90% of familial isolated pituitary tumour kindreds lacking identifiable causative variants [4]. An improved understanding of germline contributions to pituitary tumorigenesis would facilitate more accurate genetic testing, better elucidate disease pathogenesis and highlight candidate treatment targets.

- **verdict:** wrong
- **why:** Both queries are completely tautological, providing the exact statistical answers (0.1% and 5%) within the text of the questions themselves.[cite: 4]

---