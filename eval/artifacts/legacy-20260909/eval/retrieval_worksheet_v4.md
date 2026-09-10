# Retrieval set spot-check worksheet

50 of the retrieval set's 111 paragraphs, one per stratum in rotation, sampled at seed
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
python -m eval.make_case_worksheet --summarize eval/retrieval_worksheet_v4.md
```

---

## 1. `PMC6220520:abstract:0`

- **stratum:** abstract  (section title: Background)
- **source:** PMC6220520, abstract [0:408], published 2018
- **anchors:** 'primary resistance', 'osimertinib'

**lexical query** (lexical overlap 0.67)

> How often has primary resistance to osimertinib been reported?

**paraphrased query** (lexical overlap 0.40)

> What is the reported frequency of initial resistance to osimertinib?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Among non-small cell lung cancer (NSCLC) patients with acquired T790 M mutation resistance to first-generation epidermal growth factor receptor-tyrosine kinase inhibitor (EGFR-TKI), 71% are likely to benefit from osimertinib. There have been several reports about the secondary resistance to osimertinib treatment in T790 M-positive patients, while primary resistance to osimertinib has been rarely reported.

- **verdict:** wrong
- **why:** Paraphrased query is just lexical substitution with two synonyms.

---

## 2. `PMC10945882:body:0`

- **stratum:** intro  (section title: INTRODUCTION)
- **source:** PMC10945882, body [0:1160], published 2024
- **anchors:** 'guidelines'

**lexical query** (lexical overlap 0.89)

> What is the status of guidelines for hematologic monitoring, comorbidity mitigation, and leukemia prevention in patients with clonal hematopoiesis?

**paraphrased query** (lexical overlap 0.35)

> Are there any established protocols for surveillance, managing co‑existing conditions, or preventing leukemia in individuals diagnosed with clonal hematopoiesis?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The presence of somatic mutations in a subpopulation of hematopoietic cells in individuals without a morphological diagnosis is known as clonal hematopoiesis (CH). CH includes patients with CH of indeterminate potential (CHIP) and those with clonal cytopenia of undetermined significance (CCUS).
1
 Several studies have shown that CH is associated with comorbidities, such as cardiovascular disease, and with a predisposition to develop secondary hematologic malignancies.
2
, 
3
, 
4
, 
5
 In addition, the presence of pre‐leukemic CH prior to cancer therapy is common in patients, who later develop therapy‐related myeloid disorders,
6
, 
7
, 
8
, 
9
 a phenomenon likely related to increased fitness of the underlying CH.
10
 However, no guidelines exist for hematologic monitoring, comorbidity mitigation, and leukemia prevention in patients with CH. Furthermore, the impact of CH on the outcomes of patients with concomitant underlying malignancies remains unknown. To gain insight into the natural history of CH in this patient population, we analyzed the characteristics and outcomes of a cohort of patients with CH from a single tertiary cancer center.

- **verdict:** valid
- **why:** All criteria met.

---

## 3. `PMC2994899:body:5327`

- **stratum:** methods  (section title: Materials and Methods)
- **source:** PMC2994899, body [5327:6943], published 2010
- **anchors:** 'aUPD-score', 'aUPD regions'

**lexical query** (lexical overlap 0.71)

> How is the aUPD-score calculated in the analysis?

**paraphrased query** (lexical overlap 0.55)

> What method is used to compute the aUPD-score for each sample?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

We conducted analysis to identify genome-wide aUPD regions using data from 700 breast tumor samples and cell lines. The analyses were conducted using AsCNAR/CNAGv3 software (http://genome.umin.jp) [34]. The raw data (CEL files) of the Affymetrix GeneChip DNA-mapping microarrays from six sets of breast cancer samples; GSE3743 [5], GSE7545 [35], GSE10099 [36], GSE16619 [37], GSE19399 [38] and GSE13696) [39] were retrieved from the Gene Expression Omnibus (GEO) database (http://www.ncbi.nih.nlm.gov/geo). The analysis was done by using non-self controls with sex-matched reference samples from HapMap data and from previously published, publicly available datasets; GSE14656 [40], GSE14860 [41], GSE10922 [42], GSE11417 [43], GSE10092 [44], GSE9611 [45], GSE9845 [46], GSE7946 [47], GSE15526 [48], GSE12702 [49] and GSE8333 [50]. The presence of aUPD regions was predicted by using a Hidden-Markov Model with default parameters as previously described Nannya [34], [51]. In the aUPD analyses both the genotype information and the intensity were used [34], [51]. The aUPD-score was calculated by counting the total number of aUPD regions in all chromosomes in each sample. The May 2006 human genome browser (NCBI Build 36/hg18); http://genome.ucsc.edu) was used for identifying gene localization and function. Gene mutation data for this analysis were retrieved from the Catalogue of Somatic Mutations in Cancer (COSMIC) database (http://www.sanger.ac.uk/genetics/CPG/cosmic) and from the study reports of Hu et al., Hollestelle et al., Sjoblom et al., Wood et al., and Stephens et al.
[39], [52], [53], [54], [55].

- **verdict:** valid
- **why:** All criteria met.

---

## 4. `PMC6606020:abstract:259`

- **stratum:** abstract  (section title: none)
- **source:** PMC6606020, abstract [259:910], published 2019
- **anchors:** 'germline BRCA2 mutation', 'pancreatic ACC'

**lexical query** (lexical overlap 0.83)

> What is the prevalence of germline BRCA1/2 mutations in pancreatic ACCs?

**paraphrased query** (lexical overlap 0.31)

> How frequently do pancreatic acinar cell carcinomas carry inherited BRCA1 or BRCA2 alterations?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Molecular analysis revealed a germline BRCA2 (and CHEK2) mutation in a patient with a rare pancreatic ACC with extensive intraductal growth. Somatic loss of the wild-type BRCA2 allele in the tumor indicated the causal relationship of ACC with the germline defect. A thorough literature review identified another nine ACCs associated with germline BRCA2 mutation and two ACCs associated with germline BRCA1 mutation, resulting in a prevalence of BRCA1/2 germline mutations in almost 7% of ACCs. Moreover, somatic BRCA1/2 alterations are reported in 16% of sporadic ACCs. Overall, about one fifth (22%) of all pancreatic ACCs exhibit BRCA1/2 deficiency.

- **verdict:** valid
- **why:** All criteria met.

---

## 5. `PMC4324886:body:0`

- **stratum:** intro  (section title: 1. Introduction)
- **source:** PMC4324886, body [0:695], published 2015
- **anchors:** 'hepatitis B virus', 'hepatitis C virus'

**lexical query** (lexical overlap 0.75)

> What proportion of hepatocellular carcinoma cases is attributable to hepatitis B virus?

**paraphrased query** (lexical overlap 0.50)

> How much of HCC incidence is linked to HBV infection?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Liver cancer is the second leading cause of cancer death in men worldwide [1]. Among primary liver cancers, hepatocellular carcinoma (HCC) is the major histological subtype globally, with 78% of HCC attributable to hepatitis B virus (HBV, 53%) or hepatitis C virus (HCV, 25%) [2, 3]. HCC is typically an aggressive tumor arising from chronic liver disease and liver cirrhosis. Prognosis of HCC remains dismal. The majority of HCC patients are not candidates for curative therapies (surgical resection or liver transplantation) due to advanced or unresectable disease at presentation, and the available therapeutic options include local nonsurgical methods of tumor ablation and systemic therapy.

- **verdict:** valid
- **why:** All criteria met.

---

## 6. `PMC12322399:body:4690`

- **stratum:** methods  (section title: Methods)
- **source:** PMC12322399, body [4690:5206], published 2025
- **anchors:** 'discounted at', 'annual rate'

**lexical query** (lexical overlap 0.78)

> At what percentage were future costs and utilities discounted?

**paraphrased query** (lexical overlap 0.67)

> What discount rate was applied to future expenses and quality-adjusted life years in the model?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

A patient-level simulation model was used to simulate the process starting in year 2023 for women aged 25 years until death or they reach the age of 70 years. The cost calculations were performed from a UK National Health Service (NHS) perspective, including risk assessment costs, cancer prevention and surveillance costs and cancer diagnosis and treatment costs. The health outcomes were measured in terms of quality-adjusted life years (QALY).23 Future costs and utilities were discounted at a 3.5% annual rate.23

- **verdict:** wrong
- **why:** Queries are too generic; "in the model" is not specific to this paper.

---

## 7. `PMC11263413:abstract:0`

- **stratum:** abstract  (section title: Introduction)
- **source:** PMC11263413, abstract [0:581], published 2024
- **anchors:** 'MAGNITUDE trial'

**lexical query** (lexical overlap 0.64)

> What phase was the MAGNITUDE trial that evaluated niraparib plus AAP?

**paraphrased query** (lexical overlap 0.65)

> In which trial stage was the MAGNITUDE study conducted for niraparib combined with abiraterone acetate and prednisone?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Poly(ADP-ribose) polymerase inhibitors (PARPi) are a novel option to treat patients with metastatic castration-resistant prostate cancer (mCRPC). Niraparib plus abiraterone acetate and prednisone (AAP) is indicated for BRCA1/2 mutation-positive mCRPC. Niraparib plus AAP demonstrated safety and efficacy in the phase 3 MAGNITUDE trial (NCT03748641). In the absence of head-to-head studies comparing PARPi regimens, the feasibility of conducting indirect treatment comparisons (ITC) to inform decisions for patients with first-line BRCA1/2 mutation-positive mCRPC has been explored.

- **verdict:** valid
- **why:** All criteria met.

---

## 8. `PMC9289027:body:1134`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC9289027, body [1134:2197], published 2022
- **anchors:** 'tumor mutational burden', 'FoundationOne CDx assay'

**lexical query** (lexical overlap 0.47)

> What is the mutation count threshold per megabase that defines TMB-high using the FoundationOne CDx assay?

**paraphrased query** (lexical overlap 0.76)

> How many mutations per megabase must a tumor have to be classified as high tumor mutational burden by the FoundationOne CDx test?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The advent of immune checkpoint inhibitors (ICIs) has provided substantial opportunities in cancer treatment. However, the proportion of patients who benefit from ICIs varies widely by cancer type,1 and tumor-agnostic biomarkers to identify (un)responsive subsets are strongly desired. A recently established predictive biomarker is the loss of mismatch repair protein in immunohistochemistry or microsatellite instability (MSI-high), which indicates mismatch repair deficiency (MMRd) status.2 MMRd tumors are considered to be highly sensitive to ICI because they carry a large number of tumor-specific neoantigens.3 Another tumor agnostic biomarker recently approved by the Food and Drug Administration (FDA) is tumor mutational burden (TMB)-high status, where tumors have 10 or more mutations per megabase calculated from the FoundationOne CDx assay.4 Despite the approval of TMB as a biomarker, there exist a sufficient number of cases that have modest TMB but respond to ICI,5 6 and more sophisticated methods for identifying such tumors need to be developed.

- **verdict:** valid
- **why:** All criteria met.

---

## 9. `PMC12631009:body:43850`

- **stratum:** methods  (section title: Image Analysis Methods)
- **source:** PMC12631009, body [43850:44885], published 2025
- **anchors:** 'FRET signal value', 'Venus × 0.16'

**lexical query** (lexical overlap 0.86)

> How is the FRET signal value calculated?

**paraphrased query** (lexical overlap 0.79)

> What procedure is used to derive the FRET signal value from the raw fluorescence data?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Data quantitative analysis of fluorescence intensity was performed as previously described.[

18

] For Venus, Cerulean, and mCherry, the average of the raw data without subtracting the background value for each pixel in the cell nucleus detected by DAPI is taken; for FRET, the FRET fluorescence intensity for each pixel in the nucleus is calculated from the FRET fluorescence intensity of the raw data. The FRET signal value was calculated by subtracting Venus × 0.16 and Cerulean × 0.33, which are contributions from the fluorescence of Venus and Cerulean alone, from the FRET fluorescence intensity of the raw data per pixel per nucleus, and the average of these values per nucleus was taken as the FRET signal value. This is used to calculate the average FRET signal to Cerulean Intensity, the average mCherry Intensity, and the mCherry Intensity to FRET signal for a group of cells with a Venus: Cerulean fluorescence intensity ratio of 1:1. FRET signal to Cerulean Intensity and mCherry Intensity to FRET signal were calculated.

- **verdict:** wrong
- **why:** Query is completely generic; FRET is calculated in many contexts.

---

## 10. `PMC4582980:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC4582980, abstract [0:1714], published 2015
- **anchors:** 'F170I mutant', 'cytoplasm'

**lexical query** (lexical overlap 0.62)

> Where does the F170I mutant BAP1 preferentially localize?

**paraphrased query** (lexical overlap 0.55)

> In which cellular compartment is the BAP1 F170I variant mainly found?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

BRCA1-associated protein 1 (BAP1) is a deubiquitinating enzyme that is involved in the regulation of cell growth. Recently, many somatic and germline mutations of BAP1 have been reported in a broad spectrum of tumors. In this study, we identified a novel somatic non-synonymous BAP1 mutation, a phenylalanine-to-isoleucine substitution at codon 170 (F170I), in 1 of 49 patients with esophageal squamous cell carcinoma (ESCC). Multiplex ligation-dependent probe amplification (MLPA) of BAP1 gene in this ESCC tumor disclosed monoallelic deletion (LOH), suggesting BAP1 alterations on both alleles in this tumor. The deubiquitinase activity and the auto-deubiquitinase activity of F170I-mutant BAP1 were markedly suppressed compared with wild-type BAP1. In addition, wild-type BAP1 mostly localizes to the nucleus, whereas the F170I mutant preferentially localized in the cytoplasm. Microarray analysis revealed that expression of the F170I mutant drastically altered gene expression profiles compared with expressed wild-type BAP1. Gene-ontology analyses indicated that the F170I mutation altered the expression of genes involved in oncogenic pathways. We found that one candidate, TCEAL7, previously reported as a putative tumor suppressor gene, was significantly induced by wild-type BAP1 as compared to F170I mutant BAP1. Furthermore, we found that the level of BAP1 expression in the nucleus was reduced in 44% of ESCC examined by immunohistochemistry (IHC). Because the nuclear localization of BAP1 is important for its tumor suppressor function, BAP1 may be functionally inactivated in a substantial portion of ESCC. Taken together, BAP1 is likely to function as a tumor suppressor in at least a part of ESCC.

- **verdict:** valid
- **why:** All criteria met.

---

## 11. `PMC9218467:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC9218467, body [0:1090], published 2022
- **anchors:** '5-year overall survival'

**lexical query** (lexical overlap 0.89)

> What is the 5-year overall survival rate for cholangiocarcinoma?

**paraphrased query** (lexical overlap 0.31)

> How often do patients with bile duct cancer survive five years after diagnosis?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Biliary tract cancers are rare, accounting for less than 1% of all cancers and about 10% to 15% of all primary cancers arising in the liver.
1
 They mostly occur during or after the seventh decade of life,
1
 and are typically diagnosed at a late stage and characterized by poor outcomes.2–4 Cholangiocarcinoma (CCA) is an invasive carcinoma of the biliary tract, arising in the bile duct epithelium.2–4 It is the second most common form of primary liver cancer, accounting for about 10% to 15% of all hepatobiliary malignancies and 3% of all gastrointestinal tumors. Even after complete surgical resection, its recurrence rate remains high, and 5-year overall survival (OS) rates are poor at 20% to 35%.
5
 CCAs can be intrahepatic (ICC) or extrahepatic (ECC).1–3 They are slightly more common in men than women, except among people of Hispanic ethnicity.
3
 Common risk factors include advanced age, chronic inflammation, primary sclerosing cholangitis (PSC), and exposure to chemical agents such as Thorotrast and asbestos; obesity and overweight are considered possible risk factors.2–4

- **verdict:** valid
- **why:** All criteria met.

---

## 12. `PMC8099847:body:3004`

- **stratum:** methods  (section title: Materials and methods)
- **source:** PMC8099847, body [3004:4417], published 2021
- **anchors:** 'Adenoid cystic carcinoma', 'salivary gland'

**lexical query** (lexical overlap 0.69)

> How many adenoid cystic carcinoma cases were identified among the salivary gland carcinomas?

**paraphrased query** (lexical overlap 0.53)

> What is the count of adenoid cystic carcinoma tumors in the examined salivary gland cancer cohort?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The study material comprised the consecutive historical series of primary carcinomas of major and minor salivary glands resected at the Medical University of Gdańsk (Departments of Otolaryngology and Maxillofacial Surgery) between 1992 and 2012. A total of 182 salivary gland carcinomas (Table 1, Supplementary Table S1) was reviewed and reclassified according to the criteria published by WHO in 2017, with application of molecular testing, if necessary [5, 22]. After obtaining preliminary results, seven additional intraductal carcinomas were included into the study as obtained from the collections of some authors (SA, case nos. 1–3; RS, case no. 4; JL, case nos. 5–6; RG, case no. 7).Table 1Salivary gland carcinomas analyzed in the studyHistopathologic typeNumber of cases (%)Adenoid cystic carcinoma61 (33.5%)Mucoepidermoid carcinoma23 (12.6%)Carcinoma ex pleomorphic adenoma24 (13%)Acinic cell carcinoma15 (8.2%)Adenocarcinoma not otherwise specified10 (5.5%)Salivary duct carcinoma10 (5.5%)Polymorphous adenocarcinoma7 (3.8%)Mammary analogue secretory carcinoma7 (3.8%)Epithelial-myoepithelial carcinoma6 (3.3)Basal cell adenocarcinoma4 (2.2%)Undifferentiated carcinoma3 (1.6%)Squamous cell carcinoma3 (1.6%)Myoepithelial carcinoma2 (1.1%)Neuroendocrine carcinoma2 (1.1%)Papillary cystadenocarcinoma2 (1.1%)Lymphoepithelial carcinoma1 (0.5%)Cribriform adenocarcinoma1 (0.5%)Intraductal carcinoma1 (0.5%)

- **verdict:** wrong
- **why:** Queries lack paper-specific context; "the examined cohort" could refer to any paper.

---

## 13. `PMC8566594:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC8566594, abstract [0:1090], published 2021
- **anchors:** 'CREBBP/EP300', 'squamous cell carcinoma'

**lexical query** (lexical overlap 0.85)

> Are mutations in CREBBP/EP300 linked to recurrence after radiation in squamous cell carcinoma?

**paraphrased query** (lexical overlap 0.38)

> Do alterations in the CREBBP and EP300 genes correlate with tumor relapse post‑radiotherapy in SCC patients?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Despite radiation forming the curative backbone of over 50% of malignancies, there are no genomically-driven radiosensitizers for clinical use. Herein we perform in vivo shRNA screening to identify targets generally associated with radiation response as well as those exhibiting a genomic dependency. This identifies the histone acetyltransferases CREBBP/EP300 as a target for radiosensitization in combination with radiation in cognate mutant tumors. Further in vitro and in vivo studies confirm this phenomenon to be due to repression of homologous recombination following DNA damage and reproducible using chemical inhibition of histone acetyltransferase (HAT), but not bromodomain function. Selected mutations in CREBBP lead to a hyperacetylated state that increases CBP and BRCA1 acetylation, representing a gain of function targeted by HAT inhibition. Additionally, mutations in CREBBP/EP300 are associated with recurrence following radiation in squamous cell carcinoma cohorts. These findings provide both a mechanism of resistance and the potential for genomically-driven treatment.

- **verdict:** valid
- **why:** All criteria met.

---

## 14. `PMC10192162:body:830`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC10192162, body [830:1859], published 2023
- **anchors:** 'Peruvian populations', 'EGFRm'

**lexical query** (lexical overlap 0.89)

> What is the frequency of EGFRm in Peruvian populations?

**paraphrased query** (lexical overlap 0.78)

> How common are EGFR mutations among patients from Peru?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Alterations in the epidermal growth factor receptor (EGFR) gene are among the most common oncogenic driver mutations in the pathogenesis of non-small cell lung cancer (NSCLC). Specific mutations in the EGFR gene are associated with increased sensitivity to EGFR tyrosine kinase inhibitors (EGFR-TKI), which offer the best possible results for treatment response in patients with an NSCLC diagnosis and EGFR mutations (EGFRm) [1, 2]. EGFRm presence has been reported in 10–50% of NSCLC cases, almost all in lung adenocarcinomas (LUADs). In addition, significant ethnic variations for EGFRm prevalence have been described, such as 8–15% in LUADs diagnosed in Caucasian patients versus 30–50% in East Asian populations [3, 4]. Among Hispanic populations in Latin America, the frequency of EGFRm in LUADs ranges from 14% in Argentina to 24–35% in Colombia and as high as 50% among Peruvian populations [5–7]. Evaluation of ancestry–mutation association showed that Native American ancestry is positively correlated with EGFRm [8, 9].

- **verdict:** valid
- **why:** All criteria met.

---

## 15. `PMC10945882:body:1161`

- **stratum:** methods  (section title: Study design and participants)
- **source:** PMC10945882, body [1161:2186], published 2024
- **anchors:** 'persistent anemia', 'neutropenia'

**lexical query** (lexical overlap 0.62)

> What hemoglobin threshold defines persistent anemia for CCUS?

**paraphrased query** (lexical overlap 0.50)

> Which hemoglobin cutoff is used to identify ongoing anemia in CCUS patients?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

In this retrospective analysis, we evaluated the characteristics and outcomes of a cohort of patients with CHIP and CCUS actively being observed at The University of Texas MD Anderson Cancer Center. Included were patients in whom one or more somatic mutations was found by next‐generation sequencing (NGS) of their bone marrow or peripheral blood from January 2015 through March 2021. CHIP was defined as the presence of CH with no cytopenia or morphologic findings of hematologic malignancy, while CCUS was defined as the presence of CH with cytopenia, using the established criteria of persistent anemia (hemoglobin <11 g/dL); neutropenia (absolute neutrophil count <1.5 K/μL); or thrombocytopenia (platelets <100 K/μL) for at least 4 months.
11
, 
12
 Excluded were patients, who had morphologic evidence of a myeloid neoplasm, previous history of any myeloid neoplasm, and/or donor‐engrafted CHIP. Patients' comorbidities were assessed according to the validated Adult Comorbidity Evaluation 27 (ACE‐27) score.
13
, 
14



- **verdict:** valid
- **why:** All criteria met.

---

## 16. `PMC7906157:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC7906157, abstract [0:1454], published 2021
- **anchors:** 'late-stage patients'

**lexical query** (lexical overlap 0.77)

> What accuracy did the diagnostic signatures achieve for early- and late-stage COAD patients?

**paraphrased query** (lexical overlap 0.44)

> How effective were the neoantigen‑based diagnostic models at predicting early versus advanced colon adenocarcinoma stages?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Colon adenocarcinoma (COAD) is one of the most common gastrointestinal malignant tumors and is characterized by a high mortality rate. Here, we integrated whole-exome and RNA sequencing data from The Cancer Genome Atlas and investigated the mutational spectra of COAD-overexpressed genes to define clinically relevant diagnostic/prognostic signatures and to unmask functional relationships with both tumor-infiltrating immune cells and regulatory miRNAs. We identified 24 recurrently mutated genes (frequency > 5%) encoding putative COAD-specific neoantigens. Five of them (NEB, DNAH2, ABCA12, CENPF and CELSR1) had not been previously reported as COAD biomarkers. Through machine learning-based feature selection, four early-stage-related (COL11A1, TG, SOX9, and DNAH2) and four late-stage-related (COL11A1, SOX9, TG and BRCA2) candidate neoantigen-encoding genes were selected as diagnostic signatures. They respectively showed 100% and 97% accuracy in predicting early- and late-stage patients, and an 8-gene signature had excellent prognostic performance predicting disease-free survival (DFS) in COAD patients. We also found significant correlations between the 24 candidate neoantigen genes and the abundance and/or activation status of 22 tumor-infiltrating immune cell types and 56 regulatory miRNAs. Our novel neoantigen-based signatures may improve diagnostic and prognostic accuracy and help design targeted immunotherapies for COAD treatment.

- **verdict:** valid
- **why:** All criteria met.

---

## 17. `PMC8410541:body:460`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC8410541, body [460:1573], published 2021
- **anchors:** 'elderly patients'

**lexical query** (lexical overlap 0.73)

> What percentage of elderly patients have myeloid neoplasms with germline predisposition?

**paraphrased query** (lexical overlap 0.40)

> How common are germline‑predisposed myeloid neoplasms among older individuals?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Chronic myeloproliferative neoplasms, myelodysplastic syndromes (MDS), and acute myeloid leukemia (AML) are genetically heterogeneous groups of clonal hematopoietic disorders characterized by morphological changes and ineffective hematopoiesis [1, 2] together referred to as myeloid neoplasms (MN). While MN are mainly sporadic and primarily diseases of the elderly, germline mutations contributing to MN are not well defined. However, in recent years the increasing application of next‐generation sequencing (NGS) has resulted in the recognition of multiple loci (GATA2, RUNX1, CEBPα, DDX41, ETV6, ANKRD26, SRP72, or SAMD9) [3, 4, 5, 6, 7] that the updated 2016 World Health Organization classification of hematopoietic tumors included as a new category named MN with germline predisposition (MNGP) [8]. It seems that they usually appear in 1–2% of elderly patients, and around 4–13% in children, young, and middle‐age adults [9]. Furthermore, the growing interest of the scientific community regarding genetic predisposition of cancer will probably result in the recognition of a higher incidence in the future.

- **verdict:** valid
- **why:** All criteria met.

---

## 18. `PMC12854217:body:3140`

- **stratum:** methods  (section title: Study design and patients)
- **source:** PMC12854217, body [3140:4728], published 2026
- **anchors:** 'SMARCA4 mutations', '80 patients'

**lexical query** (lexical overlap 0.70)

> How many samples were screened from patients with SMARCA4 mutations?

**paraphrased query** (lexical overlap 0.50)

> What total number of specimens were examined for individuals harboring SMARCA4 alterations?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Sequencing data on 2,821 NSCLC cases between June 2018 and December 2023 were retrospectively retrieved from the Jilin Cancer Hospital, including 1,936 paraffin-embedded tumor tissues and 885 circulating tumor DNA (ctDNA) from plasma. A total of 100 samples (65 paraffin-embedded tumor tissues and 35 plasma ctDNA samples) from 80 patients with SMARCA4 mutations were screened. The same NGS panel was used to detect 20 matched tumor tissue and ctDNA. The therapy regimes that patients received are shown in Supplementary Table 1. Patients were excluded if they were diagnosed with a malignancy other than NSCLC, including lung adenocarcinoma (LUAD), lung squamous cell carcinoma (LUSC), and NSCLC-not otherwise specified; absence of clinicopathologic data, including sex and sample type; or age <18 years. The Eastern Cooperative Oncology Group performance score (ranked 0–5 levels) was used to assess health status and treatment tolerance and a higher score indicates poorer status. Response rate (RR) was calculated as complete response + partial response)/number of patients × 100 (%). Survival data included PFS and OS, with commencement of follow-up defined as the time of treatment initiation, and the endpoint defined as treatment progression, death, or the final follow-up. A flowchart of the study design is shown in Figure 1. This study adhered to the ethical principles of the Declaration of Helsinki and was approved by the Medical Ethics Committee of Jilin Cancer Hospital (NO: 202501-005-01). Due to the retrospective nature, the requirement for informed consent was waived.

- **verdict:** wrong
- **why:** Queries lack paper-specific context; many papers screen samples from patients with SMARCA4 mutations.

---

## 19. `PMC6280671:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC6280671, abstract [0:1085], published 2018
- **anchors:** '3q26.3 amplification', 'TP53 mutation'

**lexical query** (lexical overlap 0.80)

> Which cell lines have concurrent 3q26.3 amplification and TP53 mutation?

**paraphrased query** (lexical overlap 0.63)

> In which HPV-negative head and neck cancer cell models are both 3q26.3 copy‑number gains and TP53 alterations observed together?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Cell lines are important tools for biological and preclinical
investigation, and establishing their relationship to genomic alterations in
tumors could accelerate functional and therapeutic discoveries. We conducted
integrated analyses of genomic and transcriptomic profiles of 15 human
papillomavirus (HPV)-negative and 11 HPV-positive head and neck squamous cell
carcinoma (HNSCC) lines to compare with 279 tumors from The Cancer Genome Atlas
(TCGA). We identified recurrent amplifications on chromosomes 3q22–29,
5p15, 11q13/22, and 8p11 that drive increased expression of more than 100 genes
in cell lines and tumors. These alterations, together with loss or mutations of
tumor suppressor genes, converge on important signaling pathways, recapitulating
the genomic landscape of aggressive HNSCCs. Among these, concurrent 3q26.3
amplification and TP53 mutation in most HPV(–) cell
lines reflect tumors with worse survival. Our findings elucidate and validate
genomic alterations underpinning numerous discoveries made with HNSCC lines and
provide valuable models for future studies.

- **verdict:** wrong
- **why:** Paragraph states "most HPV(-) cell lines" but does not explicitly name which cell lines, failing to answer the query.

---

## 20. `PMC5883065:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC5883065, body [0:1335], published 2018
- **anchors:** 'ABC294640'

**lexical query** (lexical overlap 0.73)

> What stage of clinical development is ABC294640 in for pancreatic cancer?

**paraphrased query** (lexical overlap 0.50)

> At what phase are studies evaluating the drug ABC294640 for patients with pancreatic carcinoma?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Sphingosine-1-phosphate (S1P) is a lipid mediator with multiple biological functions. Evidence indicates that S1P plays a significant role in cancer as it promotes cell migration and cell proliferation, prevents cell death, and induces angiogenesis (1, 2). S1P is generated in cells in response to growth factors, cytokines, and other extracellular stimuli through the activation of two isoforms of sphingosine kinase (SPHK1 and SPHK2) (3–5). Upregulated expression of SPHK, particularly SPHK1, and increased levels of S1P have been linked with poor cancer prognosis and resistance to cytotoxic therapy agents in malignant cells from solid tumors, lymphomas, and leukemias (1, 6–8). Selective targeting of either SPHK1 or SPHK2 can effectively inhibit malignant cell growth in culture and in xenograft models and the preferential effect of one isoform over the other appears to be cell type specific (1, 9–15). Nevertheless, an inhibitor of SPHK2, ABC294640, is in early clinical trials for patients with pancreatic cancer and diffuse large B cell lymphomas (clinical trials NCT01488513 and NCT02229981) (16). In addition, safingol, which inhibits SPHK1 and SPHK2, has been used in combination with cisplatin in Phase I clinical trials (clinical trial NCT00084812) for the treatment of locally advanced or metastatic solid tumors (17).

- **verdict:** valid
- **why:** All criteria met.

---

## 21. `PMC6488144:body:1935`

- **stratum:** methods  (section title: Subjects and Methods)
- **source:** PMC6488144, body [1935:3739], published 2019
- **anchors:** 'nationwide cohort', 'Austrian women'

**lexical query** (lexical overlap 0.70)

> How many Austrian women were included in the nationwide cohort?

**paraphrased query** (lexical overlap 0.58)

> What is the total number of participants in the Austrian nationwide study population?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

In Austria, genetic testing for BRCA mutation has been conducted in Vienna General Hospital since 1995. Denaturing high‐performance liquid chromatography (dHPLC) and Sanger sequencing were the molecular diagnostic methods used up to 2007. From 2007 to 2015, Sanger sequencing alone was used in place of dHPLC, and multiplex ligation‐dependent probe amplification (MLPA) was performed subsequently to identify large deletions or duplications. MLPA was also conducted retrospectively on patient samples collected prior to 2007. From 2015 onward, next‐generation sequencing is performed in the General Hospital in place of MLPA/Sanger sequencing. Detected mutations are confirmed by Sanger sequencing and MLPA, respectively. Women are offered testing if their familial history fulfills at least one of the following criteria: (a) three cases of BC below age 60, (b) two cases of BC below age 50, (c) one case of BC below age 35, (d) one BC case below age 50, (e) one case of OC at any age, (f) two cases of OC at any age, and (g) male and female BC. From 2015 onward, germline testing is also offered to all women who were diagnosed with epithelial OC regardless of family history of cancer at no cost.13 To identify these individuals, we searched our nationwide cohort of 6691 Austrian women (as of February 2016) who had fulfilled the selection criteria above, had provided informed consent, had undergone germline BRCA (gBRCA) mutation analysis, and had provided a comprehensive family history at the time of analysis. Patients were followed longitudinally and received regular questionnaires every 2 years in order to identify incident familial breast and ovarian cancers. This study was approved by the Ethics Committee of the Medial University of Vienna in accordance with the Declaration of Helsinki.

- **verdict:** wrong
- **why:** Queries are too generic; "the nationwide cohort" of Austrian women could refer to many different studies.

---

## 22. `PMC5325383:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC5325383, abstract [0:1797], published 2016
- **anchors:** 'TOP1', 'BRCA1-related breast carcinomas'

**lexical query** (lexical overlap 0.83)

> How is TOP1 expression in BRCA1-related breast carcinomas compared to sporadic cases?

**paraphrased query** (lexical overlap 0.53)

> What change in TOP1 levels is observed in tumors from BRCA1 mutation carriers versus non‑hereditary breast cancers?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Breast cancer arising in female BRCA1 mutation carriers is characterized by an aggressive phenotype and early age of onset. We performed tandem mass spectrometry-based proteomics of secretomes and exosome-like extracellular vesicles from BRCA1-deficient and BRCA1-proficient murine breast tumor models to identify extracellular protein biomarkers, which can be used as an adjunct to current diagnostic modalities in patients with BRCA1-deficient breast cancer. We identified 2,107 proteins, of which 215 were highly enriched in the BRCA1-deficient secretome. We demonstrated that BRCA1-deficient secretome proteins could cluster most human BRCA1- and BRCA2-related breast carcinomas at the transcriptome level. Topoisomerase I (TOP1) and P-cadherin (CDH3) expression was investigated by immunohistochemistry on tissue microarrays of a large panel of 253 human breast carcinomas with and without BRCA1/2 mutations. We showed that expression of TOP1 and CDH3 was significantly increased in human BRCA1-related breast carcinomas relative to sporadic cases (p = 0.002 and p < 0.001, respectively). Multiple logistic regression showed that TOP1 (adjusted odds ratio [OR] 3.75; 95% confidence interval [95% CI], 1.85 - 7.71, p < 0.001) as well as CDH3 positivity (adjusted OR 2.45; 95% CI, 1.08 - 5.49, p = 0.032) were associated with BRCA1/2-related breast carcinomas after adjustment for triple-negative phenotype and age. In conclusion, proteome profiling of secretome using murine breast tumor models is a powerful strategy to identify non-invasive candidate biomarkers of BRCA1-deficient breast cancer. We demonstrate that TOP1 and CDH3 are closely associated to BRCA1-deficient breast cancer. These data merit further investigation for early detection of tumors arising in BRCA1 mutation carriers.

- **verdict:** valid
- **why:** All criteria met.

---

## 23. `PMC13314016:body:0`

- **stratum:** intro  (section title: Background)
- **source:** PMC13314016, body [0:1509], published 2023
- **anchors:** 'AI signatures processing techniques', 'diagnostic accuracy'

**lexical query** (lexical overlap 0.69)

> How do AI signatures processing techniques affect diagnostic accuracy in breast cancer imaging?

**paraphrased query** (lexical overlap 0.32)

> In what way do artificial‑intelligence based signature methods improve breast cancer detection performance by lowering false‑positive rates?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Breast cancer is the most common type of cancer in women [1]. Breast cancer develops when the breast’s normal cell tissues divide abnormally and uncontrollably. These abnormal cells accumulate into a mass of tissue that eventually turns into a tumor [2]. Breast abnormalities can, however, be challenging to diagnose. Traditionally, breast cancer diagnosis and treatment have been based on clinical symptoms, tumor shape, and site of origin [3, 4]. To detect breast cancer, many technologies have been developed, including mammography, ultrasound, and thermography [5]. Mammography is the process of using low-energy X-rays to examine the human breast for diagnosis and screening [6]. Since mammography was not very successful for dense breasts, diagnostic models were required [7]. Thermography is a procedure in which a special camera that senses heat is used to record the temperature of the skin that covers the breasts [8]. The most crucial aspect of image-based diagnosis is without a doubt the examination of patient data and expert opinion, but there are numerous other aspects that might influence this kind of diagnosis as well. Image noise, the radiologist’s visual perception skills, inadequate clarity, low contrast, and the radiologists lack of expertise are some of the issues that can impair an image-based diagnosis. In order to diagnose breast cancer, the current study focused on various AI signatures processing techniques that can increase diagnostic accuracy by reducing false positives.

- **verdict:** wrong
- **why:** Paraphrased query gives away the answer ("by lowering false-positive rates").

---

## 24. `PMC11474769:body:9944`

- **stratum:** methods  (section title: Data collection)
- **source:** PMC11474769, body [9944:10840], published 2024
- **anchors:** 'Hebon-CHEK2 study', 'clinical genetic departments'

**lexical query** (lexical overlap 0.79)

> What type of data is collected from clinical genetic departments in the Hebon-CHEK2 study?

**paraphrased query** (lexical overlap 0.43)

> Which information does the Hebon-CHEK2 project obtain from clinical genetics units and patient records?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Available data from our Hebon-CHEK2 study population are described in table 1. For the Hebon-CHEK2 study, we currently have collected data from three main sources: (1) data derived from clinical genetic departments and medical files, including variant status, surveillance advice and pedigrees as part of the selection process; (2) the self-reported Hebon risk factor questionnaire, including detailed questions on height and weight at time of completing the questionnaire, pregnancies, hormonal contraceptive use, tubal ligation, (peri)menopausal status, breast surveillance, cancer diagnosis, smoking and alcohol consumption which was obtained (table 2) and (3) data from the Netherlands Cancer Registry (also including pathology data from PALGA), including data on age and year of breast cancer diagnosis, tumour characteristics, treatment and contralateral breast cancer occurrence (table 3).

- **verdict:** valid
- **why:** All criteria met.

---

## 25. `PMC7487731:abstract:546`

- **stratum:** abstract  (section title: Results)
- **source:** PMC7487731, abstract [546:1161], published 2020
- **anchors:** 'c.5116_5119delAATA', 'North Africa'

**lexical query** (lexical overlap 0.75)

> What is the significance of the BRCA2 mutation c.5116_5119delAATA in North Africa?

**paraphrased query** (lexical overlap 0.53)

> Does the BRCA2 alteration c.5116_5119delAATA exhibit a founder phenomenon among populations from North Africa?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Overall, five BRCA germline mutations were identified (15.1%). The frequency of mutations among patients with family history of breast cancer was 16.7%. Three mutations were found in BRCA1 (9%) and two within the BRCA2 gene (6%). These are three frameshift mutations (c.798_799del, c.2125_2126insA, c.5116_5119delAATA), one missense (c.116G > A) and one nonsense mutation (c.289G > T). The mutation c.5116_5119delAATA has a founder effect in North Africa. Moreover, one variant of unknown significance was identified in BRCA2 (c.4090A > G). Most BRCA mutations carriers (80%) had no family history of breast cancer.

- **verdict:** valid
- **why:** All criteria met.

---

## 26. `PMC12367850:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC12367850, body [0:831], published 2025
- **anchors:** 'familial pituitary tumour', 'missing heritability'

**lexical query** (lexical overlap 0.75)

> What proportion of familial isolated pituitary tumour kindreds lack identifiable causative variants?

**paraphrased query** (lexical overlap 0.29)

> How many families with isolated pituitary tumors do not have a known genetic cause?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Clinically relevant pituitary tumours affect approximately 0.1% of the population, with familial pituitary tumours accounting for 5% of cases [1]. Established heritable causes of pituitary tumours include variants in genes associated with isolated familial pituitary tumours (e.g., AIP, GPR101) and syndromic disease (e.g., MEN1, CDKN1B, PRKAR1A, the SDHx genes) [2]. Germline variants in several of these genes also contribute to sporadic pituitary tumorigenesis [3]. However, there is missing heritability, with approximately 90% of familial isolated pituitary tumour kindreds lacking identifiable causative variants [4]. An improved understanding of germline contributions to pituitary tumorigenesis would facilitate more accurate genetic testing, better elucidate disease pathogenesis and highlight candidate treatment targets.

- **verdict:** valid
- **why:** All criteria met.

---

## 27. `PMC6885888:body:4099`

- **stratum:** methods  (section title: Patients and samples selection)
- **source:** PMC6885888, body [4099:5013], published 2019
- **anchors:** 'primary SDC', 'Department of Pathology'

**lexical query** (lexical overlap 0.82)

> How many primary SDC cases were identified by the Department of Pathology at Thomas Jefferson University Hospital?

**paraphrased query** (lexical overlap 0.47)

> What is the count of initial salivary duct carcinoma specimens collected from the pathology department of Thomas Jefferson University?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Twelve cases of primary SDC from the Department of Pathology at Thomas Jefferson University Hospital and 16 cases of SDC (6 primary cases and 10 recurrent/metastatic SDC cases, including one matched primary and metastatic tumor from the same patient) from Caris Life Sciences met the following inclusion criteria: Confirmed diagnosis of SDC and availability of sufficient formalin‐fixed paraffin‐embedded tissue from the primary and/or recurrent/metastatic tumor for molecular assays. All cases were re‐reviewed by a board‐certified pathologist to confirm the diagnosis and select appropriate slides for molecular profiling. A case was considered as SDC ex PA if histologic evidence of a PA was present in the same specimen, or if there was a clinical history of PA occurring previously in the same site. The Institutional Review Board of the Thomas Jefferson University Hospital approved the study (IRB #18D.142).

- **verdict:** valid
- **why:** All criteria met.

---

## 28. `PMC5919388:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC5919388, abstract [0:1299], published 1994
- **anchors:** 'D17S588', 'cumulative LOD score'

**lexical query** (lexical overlap 0.90)

> What is the cumulative LOD score for D17S588 at θ=0.001?

**paraphrased query** (lexical overlap 0.53)

> What combined LOD value was reported for marker D17S588 with a recombination fraction of 0.001?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

We examined the involvement of BRCA1, which plays a major role in Western breast cancer families, in Japanese breast cancer families. Eleven families, in which at least three individuals within third degree relatives were affected by breast cancer, were collected. Five of them were early‐onset breast cancer families, in which the average age at diagnosis was less than 45 years, and the other six were late‐onset families. Ovarian cancer was observed in one patient in the early‐onset families. Using seven polymorphic markers on chromosome 17q21, D17S250, ERBB2, THRA1, D17S579, D17S588, GIP and NME1, linkage to BRCA1 was analyzed. Linkage was not detected in any single family. Assuming homogeneity in an inherited component that confines the susceptibility to breast cancer in all families, we summed the LOD scores of all families. The cumulative LOD score obtained was –1.86 for D17S588 at θ= 0.001, indicating no linkage with BRCA1. Since the proportion of families linked to BRCA1 is larger in Western early‐onset breast cancer families than in late‐onset ones, we also summed the LOD scores of five early‐onset families. However, again a negative LOD score was obtained. These results suggest that BRCA1 is not a major breast cancer susceptibility gene in Japanese familial breast cancer.

- **verdict:** valid
- **why:** All criteria met.

---

## 29. `PMC13218332:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC13218332, body [0:1726], published 2026
- **anchors:** 'lineage plasticity'

**lexical query** (lexical overlap 0.80)

> What is the definition of lineage plasticity in prostate cancer?

**paraphrased query** (lexical overlap 0.55)

> How is lineage plasticity described in terms of cellular state changes?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Prostate cancer is the most common cancer in men, affecting one in six men in their lifetime. The vast majority present with regionally confined prostate adenocarcinoma that is often managed by active surveillance or local therapy, whereas for men with recurrent or advanced prostate cancer, the standard of care is androgen deprivation therapy (ADT) (Attard et al., 2015; Gelmann, 2002; Shen and Abate-Shen, 2010; Watson et al., 2015). Indeed, the androgen receptor (AR) is the most critical regulator of normal prostate differentiation as well as of all stages of prostate cancer progression (Abate-Shen and Shen, 2000; Gelmann, 2002; Shen and Abate-Shen, 2010). Consequently, prostate cancer treatments have been dominated by approaches to dampen AR signaling (Watson et al., 2015). However, while ADT initially leads to tumor regression, eventually tumors recur as castration-resistant prostate cancer (CRPC), so called because of its continued reliance on AR even in the absence of androgens (Scher and Sawyers, 2005). While further treatment of CRPC with second-generation anti-androgen therapies improves survival, many patients ultimately develop resistance and progress to aggressive disease variants that may no longer be dependent on AR (Watson et al., 2015). It is now well established that aggressive prostate cancer variants, including neuroendocrine prostate cancer (NEPC), arise through lineage plasticity (Beltran et al., 2016; Ku et al., 2017; Mu et al., 2017; Zou et al., 2017), defined as the transition from one differentiated cell state to another (Le Magnen et al., 2018). Thus, elucidating the mechanisms governing this process may improve treatment by overcoming plasticity-associated drug resistance.

- **verdict:** valid
- **why:** All criteria met.

---

## 30. `PMC3660364:body:50548`

- **stratum:** methods  (section title: Materials and Methods)
- **source:** PMC3660364, body [50548:51833], published 2013
- **anchors:** 'DEABM', 'NetLogo 5.0'

**lexical query** (lexical overlap 0.50)

> What software was used to implement the DEABM?

**paraphrased query** (lexical overlap 0.50)

> Which platform served as the implementation environment for the DEABM model?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The Materials & Methods section is divided into a description of the development of the DEABM followed by a description of the simulation experiments carried out using the DEABM. The development of the DEABM followed the general process described in the Overview, Design Concepts, Details (ODD) protocol developed by Grimm, et al. [65], as modified to meet the specific needs of agent-based modeling of biomedical systems [5], [29]–[31], [66]–[69]. Additionally, the iterative nature of model development follows the process described in a series of studies that emphasize the successive addition of model features to match an increasing number of desired observables as a means of enhancing the scope of model representation [32]–[34]. The DEABM was implemented using NetLogo 5.0, which can be obtained online at http://ccl.northwestern.edu/netlogo/
[9]. Description of the simulation experiments include those intended to first test the validity of the DEABM in terms of effectively reproducing normal breast cell population dynamics in response to different normal hormone patterns (cyclical menses and pregnancy) without introducing mutations, then introducing mutations in order to validate the ability of the DEABM to reproduce recognized incidences of breast cancer development.

- **verdict:** valid
- **why:** All criteria met.

---

## 31. `PMC3678719:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC3678719, abstract [0:992], published 2013
- **anchors:** 'ELMO1', 'cellular invasion'

**lexical query** (lexical overlap 0.55)

> What effect do ELMO1 mutations have on cellular invasion in EAC?

**paraphrased query** (lexical overlap 0.46)

> Do alterations in the ELMO1 gene enhance the invasive behavior of esophageal adenocarcinoma cells?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The incidence of esophageal adenocarcinoma (EAC) has risen 600% over the last 30 years. With a five-year survival rate of 15%, identification of new therapeutic targets for EAC is greatly important. We analyze the mutation spectra from whole exome sequencing of 149 EAC tumors/normal pairs, 15 of which have also been subjected to whole genome sequencing. We identify a mutational signature defined by a high prevalence of A to C transversions at AA dinucleotides. Statistical analysis of exome data identified significantly mutated 26 genes. Of these genes, four (TP53, CDKN2A, SMAD4, and PIK3CA) have been previously implicated in EAC. The novel significantly mutated genes include chromatin modifying factors and candidate contributors: SPG20, TLR4, ELMO1, and DOCK2. Functional analyses of EAC-derived mutations in ELMO1 reveal increased cellular invasion. Therefore, we suggest a new hypothesis about the potential activation of the RAC1 pathway to be a contributor to EAC tumorigenesis.

- **verdict:** valid
- **why:** All criteria met.

---

## 32. `PMC10859687:body:0`

- **stratum:** intro  (section title: INTRODUCTION)
- **source:** PMC10859687, body [0:1100], published 2024
- **anchors:** 'systematic analysis'

**lexical query** (lexical overlap 0.82)

> What systematic analysis of RiboSis genes in human cancers is missing?

**paraphrased query** (lexical overlap 0.50)

> Which comprehensive evaluation of ribosome biogenesis genes across cancers has not yet been conducted?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Ribosome biogenesis (RiboSis) is a complex process that generates ribosomes required for protein synthesis in the growth and proliferation of cells [1–3]. It is a tightly coordinated process that involves three RNA polymerases, approximately 80 ribosomal proteins, and approximately 200 non-ribosomal trans-acting factors [4, 5]. RiboSis includes rRNA transcription, rRNA cleavage, rRNA modification, ribosome assembly and export of ribosomal pre-particles [6]. In malignant cells, the genes involved in each substep of RiboSis undergo somatic alterations, resulting in ribosomopathies and an increased risk of carcinogenesis [7, 8]. The concept that ‘ribosomes translate cancer’ has gained increasing recognition [9, 10]. Thus, understanding the contribution of these alterations to pathogenesis will allow for unveiling novel and targetable vulnerabilities in cancer. Owing to large-scale and multi-dimensional open-access data, there are numerous pan-cancer studies relevant to gene signatures [11–16]. However, a systematic analysis of genes involved in RiboSis in human cancers has been lacking.

- **verdict:** wrong
- **why:** The question is a tautology; the paragraph states the analysis itself is missing rather than naming a specific missing analysis.

---

## 33. `PMC4649895:body:23331`

- **stratum:** methods  (section title: Materials)
- **source:** PMC4649895, body [23331:24418], published 2015
- **anchors:** 'Addgene', 'p53'

**lexical query** (lexical overlap 0.71)

> Which p53 plasmids were obtained from Addgene?

**paraphrased query** (lexical overlap 0.44)

> What are the p53 constructs sourced from the Addgene repository?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

RPMI 1640 medium, foetal bovine serum (FBS), penicillin, and streptomycin were obtained from Life Technologies Inc. (Grand Island, NY, USA). Dimethyl sulfoxide (DMSO), RNase A, leupeptin, aprotinin, phenylmethylsulfonylfluoride, selective FAK inhibitor 14 (1,2,4,5-benzenetetramine tetrahydrochloride), and Triton X-100 were purchased from Sigma–Aldrich Co. (St Louis, MO, USA). The pCMV-Neo-Bam p53 R248W, pCMV-Neo-Bam p53 R273H, and pCMV-Neo-Bam p53 wild-type were obtained from Addgene (Cambridge, MA). CellTrackerTM was obtained from Invitrogen (Grand Island, NY, USA). The antibodies anti-p53 (DO-1, sc-126), anti-Akt, anti-focal adhesion kinase (FAK), integrin β4, and anti-β-actin were purchased from Santa Cruz Biotechnology (Santa Cruz, CA, USA). The antibodies anti-phospho-Akt and anti-phospho-FAK were purchased from Cell Signalling Technology (Beverly, MA, USA). Function-blocking antibody against the human integrin β4 was obtained from EMD Millipore (Billerica, MA, USA)53. The PI3K/Akt inhibitor LY294002 and wortmannin were obtained from Calbiochem (San Diego, CA, USA).

- **verdict:** wrong
- **why:** Queries are too generic; many papers source p53 plasmids from Addgene.

---

## 34. `PMC12485667:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC12485667, abstract [0:1358], published 2025
- **anchors:** 'chromothripsis (CT)', 'WGD'

**lexical query** (lexical overlap 0.77)

> What is the reported frequency of chromothripsis (CT) in the studied Japanese tumor genomes?

**paraphrased query** (lexical overlap 0.56)

> How often did chromothripsis occur among the analyzed tumors?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Whole‐genome analyses have revealed that large‐scale structural variations (SVs) such as whole‐genome duplication (WGD) occur early in the development of many cancers. However, the diversity of chromosomal abnormalities within tumors before and after WGD remains poorly understood. Here, we analyzed various types of Japanese tumor genomes via whole‐genome sequencing and examined the diversity of WGD by focusing on large SVs at the chromosomal level. WGD was detected in 52% of cases, while the frequency of chromothripsis (CT) was 20%. Although aneuploidy via deletion of chromosome arms was common in many cancers, in rare ovarian cancers, all chromosomes were near‐haploidy before WGD. Minor allele analysis revealed that many non‐mutated ohnolog genes drifted down chromosome arms after WGD and returned to normal ploidy, but only 17p, including TP53, which is also an ohnolog, underwent loss of heterozygosity due to arm deletion before WGD in most cancers. TP53 mutations were frequently detected in WGD and CT‐positive tumors, and these SVs strongly correlated with homologous recombination deficiency scores. Furthermore, these tumors had many mutations that continued to generate neoantigens and resulted in worse survival outcomes. Diversity analysis of tumors with WGD will provide a new perspective on structural abnormalities in tumor genomes.

- **verdict:** wrong
- **why:** Paraphrased query lost paper-specific context ("among the analyzed tumors" vs "Japanese tumor genomes").

---

## 35. `PMC11884457:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC11884457, body [0:878], published 2025
- **anchors:** 'characteristic tumors', 'CS/PHTS patients'

**lexical query** (lexical overlap 0.78)

> What characteristic tumors are associated with CS/PHTS patients?

**paraphrased query** (lexical overlap 0.56)

> Which specific cancer types are commonly seen in individuals with Cowden syndrome or PTEN hamartoma tumor syndrome?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Cowden syndrome (CS)/PTEN hamartoma tumor syndrome (PHTS) is a hereditary disorder characterized by autosomal dominant inheritance, caused by germline pathogenic variants in phosphatase and tensin homolog (PTEN) gene (1). Many CS/PHTS cases present with macrocephaly, distinctive facial skin lesions, and oral mucosal abnormalities (2), as well as developmental features such as autism spectrum disorders (3). These characteristics often lead to early diagnosis and referral to genetic clinics. However, cases without prominent external features may remain undiagnosed until adulthood. While the detailed mechanisms are not fully elucidated, PTEN loss-of-function leads to carcinogenesis. CS/PHTS patients are at increased risk for characteristic tumors such as breast, endometrial, and follicular thyroid cancer, often presenting at a younger age and potentially proving fatal.

- **verdict:** valid
- **why:** All criteria met.

---

## 36. `PMC6635747:body:12759`

- **stratum:** methods  (section title: Statistical analysis)
- **source:** PMC6635747, body [12759:13442], published 2019
- **anchors:** 'second hit', 'genes'

**lexical query** (lexical overlap 0.86)

> How many tests were performed for genes with more than one second hit event?

**paraphrased query** (lexical overlap 0.50)

> What is the total count of statistical examinations conducted on genes exhibiting multiple second‑hit occurrences?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

A permutation test was implemented to assess the statistical significance of “second hit” events. For each gene and patient we defined the probability of having a “second hit” event as the probability of having one or more mutations in a gene multiplied by the fraction of the genome with copy‐number aberrations in each patient. The mutation probability was calculated based on the size of each gene and the number of mutations in each patient. We performed 109 tests for all genes that showed more than one “second hit” event in our dataset. The resulting p values were adjusted for multiple testing using Benjamini‐Hochberg's method. Only genes with q values <0.1 were considered.

- **verdict:** wrong
- **why:** Queries lack paper-specific context; "in our dataset" could refer to any dataset.

---

## 37. `PMC13298532:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC13298532, abstract [0:731], published 2026
- **anchors:** 'ROS1 exon 35–37', 'EGFR-mutant lung cancer'

**lexical query** (lexical overlap 0.71)

> How many women with EGFR-mutant lung cancer were reported to have the ROS1 exon 35–37 rearrangement?

**paraphrased query** (lexical overlap 0.55)

> What is the count of female patients with EGFR-driven lung tumors who exhibited the rare ROS1 intragenic rearrangement spanning exons 35 to 37?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

We describe three women with EGFR-mutant lung cancer in whom a rare ROS1 exon 35–37 RNA-level intragenic rearrangement was detected after progression on EGFR-targeted therapy. Our series demonstrates that combining two different targeted therapies to block both mutations can lead to long-term survival in one case, but another case may experience significant side effects. When combined therapy is not tolerated, traditional chemotherapy remains a necessary and effective alternative. This study highlights the potential value of advanced molecular testing after treatment failure and underscores the need for individualized treatment strategies and further functional validation when this specific ROS1 rearrangement is detected.

- **verdict:** valid
- **why:** All criteria met.

---

## 38. `PMC12079100:body:2186`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC12079100, body [2186:3249], published 2025
- **anchors:** 'Pembrolizumab', 'CPS ≥1'

**lexical query** (lexical overlap 0.82)

> What combined positive score (CPS) is required for pembrolizumab first-line approval in metastatic or unresectable recurrent HNSCC?

**paraphrased query** (lexical overlap 0.35)

> Which PD‑L1 expression level, expressed as CPS, makes patients eligible for initial pembrolizumab treatment in advanced head‑and‑neck squamous cell carcinoma?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Immune checkpoint inhibitors (ICI) targeting PD-1 and PD-L1 have demonstrated significant survival benefit for various tumor types when compared with standard therapies in prospective randomized clinical trials (2–4). Pembrolizumab (anti–PD-1) is approved by the FDA and European Medicines Agency (EMA) for the first-line treatment of metastatic or unresectable, recurrent HNSCC in combination with platinum and 5-fluorouracil [by the EMA for patients whose tumors express PD-L1 with a combined positive score (CPS) ≥1] or as monotherapy for patients whose tumors express PD-L1 with a CPS ≥1 (5, 6). Pembrolizumab and nivolumab (anti–PD-1) are approved by the FDA and EMA as monotherapy for R/M HNSCC with disease progression on/after platinum-based chemotherapy (pembrolizumab is approved by the EMA for patients whose tumors express PD-L1 with a tumor proportion score ≥50%; refs. 5–8), and in this setting, durvalumab (anti–PD-L1) with/without tremelimumab (anti–cytotoxic T-lymphocyte–associated antigen 4) has demonstrated variable antitumor activity (9–11).

- **verdict:** valid
- **why:** All criteria met.

---

## 39. `PMC4627365:body:2693`

- **stratum:** methods  (section title: Data collection)
- **source:** PMC4627365, body [2693:3886], published 2015
- **anchors:** 'case-control studies', 'XRCC3 Thr241Met polymorphism'

**lexical query** (lexical overlap 0.89)

> How many case-control studies were included in the final meta-analysis of XRCC3 Thr241Met polymorphism and breast cancer risk?

**paraphrased query** (lexical overlap 0.50)

> What is the total count of case-control investigations incorporated in the concluding meta‑analysis examining the XRCC3 Thr241Met variant’s association with breast cancer?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Multiple databases under the NCBI global database and Google Scholar were searched for relevant studies; 23 case-control studies focusing on XRCC3 T241M polymorphism and breast cancer risk were covered in this meta-analysis. For the first-round search, articles were searched with NCBI Global Cross-database, including PubMed, PMC, Gene, PubChem, and Google Scholar, using “XRCC3 polymorphism”, “XRCC3 Thr241Met polymorphism”, and “breast cancer” as key words; 271 results were retrieved. Books and other literature which were not case-control studies were excluded, along with literature published before Jan 1st, 2000, which yielded a total of 65 articles. For the second-round selection, articles which were not aimed at investigating association between XRCC3 Thr241Met polymorphism and breast cancer risk were excluded, which resulted in 20 articles, including 1 meta-analysis article published in 2010. Subsequently, articles without control group information or in which the original data could not be retrieved were excluded. For overlapping studies, we kept the ones that showed the most extensive results. Ultimately, 23 case-control studies were included in the final meta-analysis.

- **verdict:** valid
- **why:** All criteria met.

---

## 40. `PMC12275984:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC12275984, abstract [0:2053], published 2025
- **anchors:** 'peritoneal HGSC', 'salpingo‑oophorectomy'

**lexical query** (lexical overlap 0.91)

> What is the residual risk of peritoneal HGSC after salpingo‑oophorectomy?

**paraphrased query** (lexical overlap 0.82)

> How likely is it that women who undergo salpingo‑oophorectomy still develop peritoneal high‑grade serous carcinoma?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Germline BRCA1/2 pathogenic variant carriers have an increased risk for high‐grade serous carcinoma (HGSC) and are therefore advised to have risk‐reducing salpingo‐oophorectomy around the age of 40. However, a risk of 0.9% to develop peritoneal HGSC remains in these women, which increases to 27.5% when serous tubal intraepithelial carcinoma (STIC) is detected. The pathophysiological mechanism that leads to the development of peritoneal HGSC after salpingectomy or salpingo‐oophorectomy is still largely unknown. In this systematic review, we aim to provide insights into the pathogenic pathways of peritoneal HGSC after salpingectomy or salpingo‐oophorectomy. Therefore, we performed a systematic search for studies investigating pathophysiological mechanisms related to peritoneal HGSC in PubMed and EMBASE. A total of 49 articles were included in this study. Most evidence was found on mechanisms following a tubal origin, such as clonality between STIC and peritoneal HGSC as well as molecular similarities between fallopian tube (FT) epithelium and peritoneal HGSC. Additionally, FT epithelium was shown to adhere to the ovary and could therefore stay present after isolated salpingectomy. There might be a role for the endometrium, as it was observed that serous endometrial intraepithelial carcinoma (SEIC) has a clonal relationship with extra‐uterine HGSC. The role of the ovary seems limited, although some mouse models show a role for follicular fluid in the dissemination of malignant cells on the peritoneum. In conclusion, different mechanisms might be responsible for peritoneal HGSC development after bilateral salpingectomy or salpingo‐oophorectomy. Most available evidence supports the dissemination of precursor cells originating in the FT. Also, a possible role for the endometrium was found. An ovarian origin seems less likely; however, execution of oophorectomy does not seem obsolete in clinical practice as follicular fluid might promote dissemination and residual tubal tissue can be present on the ovary after salpingectomy.

- **verdict:** valid
- **why:** All criteria met.

---

## 41. `PMC7904762:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC7904762, body [0:520], published 2021
- **anchors:** 'ABCB1 gene', 'P-glycoprotein'

**lexical query** (lexical overlap 0.64)

> What molecular alterations of the ABCB1 gene are linked to chemoresistance?

**paraphrased query** (lexical overlap 0.50)

> Which changes in the gene encoding P‑glycoprotein contribute to drug resistance in cancer cells?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

During the acquisition of chemoresistance, many cancer cells upregulate the expression of transporters mediating drug efflux1,2. Research has therefore focussed on strategies to oppose efflux transporter function3,4. Of these transporters, P-glycoprotein (P-gp, MDR1, gene: ABCB1) has received most attention, and overexpression, stabilisation as well as polymorphisms in the ABCB1 gene are associated with chemoresistance4–6. P-gp is involved in efflux of a range of cellular toxins, and also chemotherapeutic drugs7,8.

- **verdict:** valid
- **why:** All criteria met.

---

## 42. `PMC10445354:body:13323`

- **stratum:** methods  (section title: Statistical analysis)
- **source:** PMC10445354, body [13323:13667], published 2023
- **anchors:** 'SPSS V.19.0', 'GraphPad Prism V.7.0'

**lexical query** (lexical overlap 0.67)

> Which statistical software versions were used in the analysis?

**paraphrased query** (lexical overlap 0.55)

> What are the specific versions of the programs employed for data analysis?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Statistical analysis was performed using SPSS V.19.0 and GraphPad Prism V.7.0 (GraphPad Software). All data are presented as mean±SE. Two-tailed Student’s t-tests and one-way analysis of variance tests were used to analyze the data. The log-rank test was used for the survival analysis. P values <0.05 were considered statistically significant.

- **verdict:** wrong
- **why:** Queries are entirely generic ("in the analysis") and not specific to this paper.

---

## 43. `PMC9916715:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC9916715, abstract [0:1605], published 2023
- **anchors:** 'KCNJ14', 'immunological checkpoints'

**lexical query** (lexical overlap 0.71)

> How is KCNJ14 associated with immunological checkpoints?

**paraphrased query** (lexical overlap 0.45)

> What type of relationship does KCNJ14 have with immune checkpoint molecules?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Cancer is a global epidemic that has affected millions of lives. Discovering novel cancer targets is widely viewed as a key step in developing more effective therapies for cancer and other fatal illnesses. More recently, potassium (K+) channels have been studied as a potential biological target for the creation of cancer treatments. Potassium Inwardly Rectifying Channel Subfamily J Member 14 (KCNJ14) is one of the cancer genome’s least investigated genes. This study conducted a comprehensive examination of the relationships between KCNJ14 gene expression analysis, survival, RNA modification, immunotherapy participation, and cancer stemness using several databases. KCNJ14 was shown to be dysregulated in a variety of cancers, including lung, intestinal, head and neck, oesophageal, and stomach. Additionally, KCNJ14 was shown to be linked to RNA and DNA stemness in 18 and 15 different tumour types, respectively. Moreover, KCNJ14 was discovered to be positively linked with immunological checkpoints and suppressor cells and to have a negative immunophenoscore (IPS). KCNJ14 was linked to tumour mutation burden (TMB), microsatellite instability (MSI), neoantigen (NEO), and programmed death ligand 1 (PD-L1); all four are potential targets for immunotherapies. In addition, a favourable relationship between genomic-instability markers such as heterozygosity (LOH), homologous recombination deficiency (HRD), and mutant-allele tumour heterogeneity (MATH) was demonstrated with KCNJ14. Based on these novel findings, KCNJ14 may be a useful independent prognostic biomarker for a range of cancers.

- **verdict:** valid
- **why:** All criteria met.

---

## 44. `PMC9512793:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC9512793, body [0:620], published 2022
- **anchors:** 'cancer death rate', '1991–2018'

**lexical query** (lexical overlap 0.82)

> How has the cancer death rate changed between 1991 and 2018?

**paraphrased query** (lexical overlap 0.43)

> What trend was observed for mortality from cancer over the period from 1991 to 2018?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Cancer is one of the leading causes of death for humans. In 2020, an estimated 19.3 million new cancer cases and 10.0 million cancer deaths occurred worldwide1. China ranked highest with 4.6 million new cases and 3.0 million cancer deaths, accounting for 24% of newly diagnosed cases and 30% of cancer deaths globally2. For the U.S., it is estimated that 1.9 million new cases and 0.6 million cancer deaths have occurred in 2021. However, the cancer death rate has decreased continuously between 1991–2018, which is largely attributed to smoking cessation initiatives and advances in detection and treatment modalities3.

- **verdict:** valid
- **why:** All criteria met.

---

## 45. `PMC6102817:body:5061`

- **stratum:** methods  (section title: Data collection and quality assessment)
- **source:** PMC6102817, body [5061:5601], published 2018
- **anchors:** 'NOS score'

**lexical query** (lexical overlap 0.70)

> What NOS score threshold defines high quality in the assessment?

**paraphrased query** (lexical overlap 0.46)

> At what minimum Newcastle‑Ottawa score is a study classified as high quality?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Then, we carefully extracted the data and listed the basic information (such as method, age, gender, smoking, alcohol, location, ethnicity, and disease type) and genotype frequency in the Tables. E-mails were sent for the missing data. We also evaluated the quality of each study using the NOS (Newcastle-Ottawa quality assessment Scale) system with the score of 1~ 9. The high quality was considered when the NOS score was larger than five. A full discussion was required for a conflicting or controversial issue during quality assessment.

- **verdict:** wrong
- **why:** Query is too generic; many meta-analyses use an NOS score threshold.

---

## 46. `PMC11894594:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC11894594, abstract [0:1970], published 2025
- **anchors:** 'SREBP pathway genes', 'mutant TP53'

**lexical query** (lexical overlap 0.60)

> What effect does silencing SREBP pathway genes have on mutant TP53 expression in HCC cells?

**paraphrased query** (lexical overlap 0.72)

> How does knockdown of SREBP signaling components influence the levels of mutant TP53 transcripts and protein in hepatocellular carcinoma?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Hepatocellular carcinoma (HCC) is a severe disease associated with a poor prognosis. The role of aberrant lipid metabolism in the development and progression of HCC necessitates detailed characterization. Sterol regulatory element-binding proteins (SREBPs), pivotal transcription factors governing lipogenesis, are central to this process. The present study aimed to assess the regulation of HCC by the SREBP signaling pathway, examining the expression levels of genes in this pathway, the clinical implications and its prognostic value using the Kaplan-Meier method. Pearson's correlation coefficient was used to identify the co-expression of SREBP pathway genes in HCC. Genomic analysis examined the frequency of TP53 mutations in groups with and without SREBP pathway alterations. In addition, small interfering RNAs targeting genes of the SREBP pathway were transfected into Huh-7 and HCC-LM3 cell lines. Subsequently, Cell Counting Kit-8 and Transwell assays were carried out to evaluate the viability and invasion of these cells. Reverse transcription-quantitative PCR and western blotting were performed to investigate the expression of TP53 in response to silencing of SREBP pathway genes. Dysregulation of SREBP pathway genes was detected in HCC tissues compared with in normal liver tissues, and predicted a poor prognosis. Silencing these genes reduced the viability and invasion of HCC cells. Furthermore, abnormal SREBP pathway gene expression was associated with poor survival rates, vascular invasion, advanced tumor stage and an increased incidence of TP53 mutations. By contrast, knockdown of SREBP pathway genes decreased mutant TP53 expression at both the mRNA and protein levels in HCC cells. The findings of the present study suggested that SREBP pathway genes could serve as promising prognostic biomarkers for HCC. The combined analysis of individual gene expression levels offers offer novel insights into the pathogenesis and progression of HCC.

- **verdict:** valid
- **why:** All criteria met.

---

## 47. `PMC7572377:body:0`

- **stratum:** intro  (section title: Introduction)
- **source:** PMC7572377, body [0:699], published 2020
- **anchors:** 'pan-cancer analysis', 'TCGA'

**lexical query** (lexical overlap 0.67)

> What proportion of TCGA pan‑cancer cases carried a pathogenic predisposition variant?

**paraphrased query** (lexical overlap 0.44)

> What percentage of patients in the TCGA pan‑cancer cohort had a disease‑causing germline variant?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

The development of cutaneous melanoma is heavily associated with ultraviolet radiation. This environmental influence makes melanoma the most highly mutated cancer type1. A subset of patients harbor germline mutations which increases their susceptibility2. The predominant high-risk familial melanoma genes are CDKN2A and CDK43–5. Pan-cancer analysis of 10,389 patients from The Cancer Genome Atlas (TCGA) reported approximately 8% of cases, across 33 cancer types, carried a pathogenic predisposition variant6. Importantly, they identified shared variants and genes across several cancer types. Few studies have addressed the clinical impact of pathogenic germline mutations on melanoma patients7,8.

- **verdict:** valid
- **why:** All criteria met.

---

## 48. `PMC8086250:body:5601`

- **stratum:** methods  (section title: Sequencing methods)
- **source:** PMC8086250, body [5601:6401], published 2021
- **anchors:** 'target region'

**lexical query** (lexical overlap 0.70)

> How many amplicons were designed to cover the target region?

**paraphrased query** (lexical overlap 0.42)

> What is the total count of amplicons that span the specified target region?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Target sequence enrichment followed by sequencing was performed on the coding sequence and splice-sites of ALKBH3, ANAPC2, BUB1B, C5ORF28, C6, CHEK2, CNKSR1, DNAJB4, DUOX1, EXO1, FANCA, FANCB, FANCC, FANCD2, FANCE, FANCG, FANCI, FBXO10, GANC, GTF2H4, KNTC1, LIG4, MKNK2, MMRN1, NAT10, OSGIN1, PAK4, PALB2, PARP1, PHF20L1, PIK3C2G, POLE, POLK, PSG6, PTGER3, PTX3, RAD52, RAD54B, RDM1, RECQL, REV3L, RIPK3, RNASEL, SLX4, SMC1A, SMG5, SNRNP200, SPHK1, SULT1C2, UHRF2, UPK2, WNT5A, XRCC1 and ZFHX3. The target sequence was identified from the NCBI Reference Sequence Database48.48 Fluidigm access arrays as previously described.6 A total of 1663 amplicons were designed to cover the 159 kb target region. Libraries were sequenced using 150 bp paired-end sequencing on the Illumina HiSeq4000 or HiSeq2500.

- **verdict:** wrong
- **why:** Query is completely generic; does not specify which target region or paper.

---

## 49. `PMC8847983:abstract:0`

- **stratum:** abstract  (section title: none)
- **source:** PMC8847983, abstract [0:1948], published 2022
- **anchors:** 'TP53', 'uterine cervix SCCs'

**lexical query** (lexical overlap 0.67)

> What proportion of uterine cervix SCCs have TP53 mutations?

**paraphrased query** (lexical overlap 0.77)

> How frequently is TP53 altered in small cell carcinoma of the uterine cervix?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

Small cell carcinoma (SCC) of the uterine cervix is a rare and aggressive form of neuroendocrine carcinoma, which resembles small cell lung cancer (SCLC) in its histology and poor survival rate. Here, we sought to define the genetic underpinning of SCCs of the uterine cervix and compare their mutational profiles with those of human papillomavirus (HPV)‐positive head and neck squamous cell carcinomas, HPV‐positive cervical carcinomas, and SCLCs using publicly available data. Using a combination of whole‐exome and targeted massively parallel sequencing, we found that the nine uterine cervix SCCs, which were HPV18‐positive (n = 8) or HPV16‐positive (n = 1), harbored a low mutation burden, few copy number alterations, and other than TP53 in two cases no recurrently mutated genes. The majority of mutations were likely passenger missense mutations, and only few affected previously described cancer‐related genes. Using RNA‐sequencing, we identified putative viral integration sites on 18q12.3 and on 8p22 in two SCCs of the uterine cervix. The overall nonsilent mutation rate of uterine cervix SCCs was significantly lower than that of SCLCs, HPV‐driven cervical adeno‐ and squamous cell carcinomas, or HPV‐positive head and neck squamous cell carcinomas. Unlike SCLCs, which are reported to harbor almost universal TP53 and RB1 mutations and a dominant tobacco smoke‐related signature 4, uterine cervix SCCs rarely harbored mutations affecting these genes (2/9, 22% TP53; 0% RB1) and displayed a dominant aging (67%) or APOBEC mutational signature (17%), akin to HPV‐driven cancers, including cervical adeno‐ and squamous cell carcinomas and head and neck squamous cell carcinomas. Taken together, in contrast to SCLCs, which are characterized by highly recurrent TP53 and RB1 alterations, uterine cervix SCCs were positive for HPV leading to inactivation of the suppressors p53 and RB, suggesting that these SCCs are convergent phenotypes.

- **verdict:** valid
- **why:** All criteria met.

---

## 50. `PMC5683588:body:0`

- **stratum:** intro  (section title: Background)
- **source:** PMC5683588, body [0:418], published 2017
- **anchors:** 'advanced disease', 'new cases'

**lexical query** (lexical overlap 0.60)

> What proportion of new breast cancer cases in Kyrgyzstan are diagnosed at an advanced stage?

**paraphrased query** (lexical overlap 0.41)

> How many percent of newly identified breast cancer patients in Kyrgyzstan present with advanced disease at diagnosis?

**The gold paragraph, read back from the corpus XML at those exact offsets:**

In Kyrgyzstan, breast cancer (BC) appears to be one of the leading cancer localizations in females, remaining the second most prevalent and the third fatal type of cancer. The advanced disease is diagnosed in 40% of new cases, hampering both treatment and cure [1]. Therefore, molecular markers of predisposition to BC may be a cornerstone strategy for early detection and primary prevention of this malignant disease.

- **verdict:** valid
- **why:** All criteria met.

---