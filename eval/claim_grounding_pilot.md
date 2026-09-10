# Blind claim-grounding rubric pilot

Label whether each complete cited span supports the entire claim. Use only the shown span. Every material entity, variant, condition, direction, magnitude, population, time and uncertainty qualifier must be supported. Topic overlap is insufficient.

Use `unclear` when the written rule cannot decide the pair. Explain why. We will resolve those examples and freeze the rubric before measuring judge agreement.

---

## Pair 1: atm_at_lymphoid_tumor_ord_001 claim 1

**Query:** What does the literature report about ATM kinase activity level and tumor risk in ataxia-telangiectasia patients?

**Claim:** Absence of ATM kinase activity is associated with childhood tumor development in A‑T patients.

**Citation:** `PMC3170966`, `body`, characters 19870:21091

**Complete cited source span:**

> We show here that development of childhood tumours (lymphoid and brain) in A-T patients is associated almost exclusively with absence of ATM kinase activity. Conversely our findings suggest that expression of some residual ATM kinase activity has a strongly protective effect against tumour development in A-T in childhood. The source of the residual ATM kinase activity was a low level of either normal ATM or mutant ATM. The origin of the retained kinase activity in 25 patients (median age, 29 years) was the presence of the IVS40-1050A>G splice site mutation (McConville et al, 1996; Stewart et al, 2001; Sutton et al, 2004) expressing a low level (∼5%) of normal ATM. Despite the protection against tumour development provided by retained ATM kinase activity, two developed tumours, although significantly only in adulthood (one patient had a T-ALL at 17 years of age; the other patient had a testicular seminoma at an age of 27 years and a cerebral diffuse large B-cell lymphoma at an age of 34 years). This apparent contradiction may be reconciled if the level of ATM kinase activity in these IVS40-1050A>G-carrying patients is close to a threshold of ATM kinase activity that would normally be tumour suppressive.

**Your label:** `supported`

**Your rationale:**
The cited span explicitly confirms that childhood tumor development in A-T patients is associated almost exclusively with an absence of ATM kinase activity.

---

## Pair 2: atm_c4777minus1g_c_pancreatic_neg_001 claim 1

**Query:** What does the literature report about ATM c.4777-1G>C and pancreatic cancer risk?

**Claim:** ATM mutations are reported to predispose to pancreatic cancer.

**Citation:** `PMC5760284`, `body`, characters 16319:17592

**Complete cited source span:**

> After BRCA2, ATM was the most common breast cancer risk gene in which PVs were identified. Eight individuals were identified as carrying a PV in ATM, six of whom were FPC. While there is growing consensus in the pancreatic cancer genetics literature that germline mutations in ATM can predispose to pancreatic cancer, there are also caveats. ATM is a large gene, and little is known about the genetic epidemiology of ATM with respect to PDAC. ATM localizes to chromosome 11q and was named for its association with ataxia telangiectasia.22 It belongs to the protein family of PI3K-related protein kinases and plays an important role in DNA repair. In 2012, ATM was reported as a predisposition gene for familial pancreatic adenocarcinoma.13 Heterozygous, constitutional ATM mutations were identified in whole-genome and whole-exome sequencing performed on 2 kindreds with familial pancreatic cancer. When the analysis was expanded to consider an additional 166 familial pancreatic cancer patients, an additional 4 patients were found to have deleterious mutations of ATM, compared to none in 190 spouse controls (p=0.046).13 Along with others,7,12 our study has found numerous VUSs in ATM, and this may indicate that these do not represent putative disease-causing variants.

**Your label:** `supported`

**Your rationale:**
The text explicitly notes a growing consensus that ATM germline mutations predispose to pancreatic cancer and was reported as a predisposition gene in 2012.

---

## Pair 3: atm_c7570g_c_risk_class_disagree_001 claim 1

**Query:** What does the literature report about ATM c.7570G>C and breast cancer risk classification?

**Claim:** ATM c.7570G>C is associated with a significantly increased breast cancer risk

**Citation:** `PMC10092731`, `abstract`, characters 1:1307

**Complete cited source span:**

> ATM is generally described as a moderate‐risk breast cancer susceptibility gene. However, some of ATM variants might encounter higher risk. ATM c.7570G>C, p.Ala2524Pro, (rs769142993) is a pathogenic Finnish founder variant causative for recessively inherited ataxia‐telangiectasia. At cellular level, it has been reported to have a dominant‐negative effect. ATM c.7570G>C has recurrently been described in Finnish breast cancer families and unselected case cohorts collected from different parts of the country, but the rarity of the allele (MAF 0.0002772 in Finns) and lack of confirming segregation analyses have prevented any conclusive risk estimates. Here, we describe seven families from genetic counseling units with ATM c.7570G>C variant showing co‐segregation with breast cancer. Further analysis of the unselected breast cancer cohort from Northern Finland (n = 1822), a geographical region previously indicated to have enrichment of the variant, demonstrated that c.7570G>C significantly associates with breast cancer, and the risk is estimated as high (odds ratio [OR] = 8.5, 95% confidence interval [CI] = 1.04‐62.46, P = .018). Altogether, these results place ATM c.7570G>C variant among the high‐risk alleles for breast cancer, which should be taken into consideration in genetic counseling.

**Your label:** `supported`

**Your rationale:**
The span directly states the variant significantly associates with breast cancer and that the risk is estimated as high.

---

## Pair 4: atm_variants_controversy_disagree_001 claim 1

**Query:** What does the literature report about the overall role of ATM variants in breast cancer susceptibility and what is the level of evidence for ATM as a breast cancer gene?

**Claim:** ATM is frequently involved as a low‑penetrance breast cancer susceptibility gene with contradictory evidence

**Citation:** `PMC2386480`, `abstract`, characters 0:211

**Complete cited source span:**

> The ATM gene has been frequently involved in hereditary breast cancer as a low-penetrance susceptibility gene but evidence regarding the role of ATM as a breast cancer susceptibility gene has been contradictory.

**Your label:** `supported`

**Your rationale:**
The claim is a direct restatement of the span, noting ATM's frequent involvement as a low-penetrance gene alongside contradictory evidence.

---

## Pair 5: brca1_c4484plus2t_c_prostate_neg_001 claim 1

**Query:** What does the literature report about BRCA1 c.4484+2T>C and prostate cancer risk?

**Claim:** BRCA1 c.4484+2T>C is reported as a spliceogenic variant with no mention of prostate cancer risk

**Citation:** `PMC12805630`, `body`, characters 29767:30584

**Complete cited source span:**

> Conversely, 25 +2T > C variants induced complete anomalous splicing patterns without any trace of the corresponding mgFL‐transcript (nonleaky variants; Table 1; supplementary material, Table S1). These totally spliceogenic variants typically present two or more additional nt‐changes with respect to the 5'ss consensus sequence (MAGgtragt), except for BRCA1 c.4484+2T > C and PALB2 c.3201+2T > C, which differ in only one nt (Table 1, Figure 3B). Therefore, fully spliceogenic +2T >C variants are associated with weaker GT‐donor sites. Indeed, the original GT‐5'ss of these fully spliceogenic +2T > C variants averaged an MES score of 8.0 [22]. BRCA1 nonleaky variants c.4986+2T > C, c.5074+2T > C, and c.5152+2T > C were formerly identified as nonfunctional alleles [36, 38], lending further support for our results.

**Your label:** `unsupported`

**Your rationale:**
The span supports that BRCA1 c.4484+2T>C is spliceogenic, but silence in this excerpt cannot
support a scientific claim about prostate cancer risk. Because the compound claim is not fully
supported, the verdict is unsupported.

---

## Pair 6: brca2_pancreatic_risk_ord_001 claim 1

**Query:** What does the literature report about BRCA1/BRCA2 mutations and pancreatic cancer risk?

**Claim:** Both BRCA1 and BRCA2 mutations increase pancreatic cancer risk compared with non‑carriers.

**Citation:** `PMC5155186`, `body`, characters 6908:7717

**Complete cited source span:**

> Association of BRCA1/2 mutations with susceptibility to breast and ovarian cancer has been investigated for years. It is estimated that about 60% of women with BRCA1/2 mutations have developed breast cancer[14]. A woman who carries a germline BRCA1/2 mutation could be 5 times more likely to develop breast cancer than one who does not carry any BRCA1/2 mutation[15]. Men who have BRCA1/2 mutations are more likely to have prostate or pancreatic cancers. Men are 3.5 times and 8.6 times more likely to develop prostate cancer for BRCA1 and BRCA2 mutation carriers by age 65, respectively[16]. Similar to prostate cancer, BRCA1/2 poses a risk of pancreatic cancer development. Overall, BRCA1 mutation increases the risk by 0- to 4.11-fold, while the BRCA2 mutation increases the risk by 2.13- to 21.7-fold[17].

**Your label:** `supported`

**Your rationale:**
The span explicitly states that BRCA1/2 mutations pose a risk for pancreatic cancer development and details the fold-increases for both.

---

## Pair 7: brca_prs_ovarian_risk_ord_001 claim 1

**Query:** What does the literature report about polygenic risk score modification of ovarian cancer risk in BRCA1/BRCA2 mutation carriers?

**Claim:** Polygenic risk scores stratify ovarian cancer risk in BRCA2 carriers, with higher PRS percentiles showing higher cumulative risk

**Citation:** `PMC8904525`, `body`, characters 34991:35191

**Complete cited source span:**

> Figure S2:Cumulative risk of ovarian cancer risk in BRCA2 carriers by polygenic risk score percentiles. The lasso (A) and elastic net (B) penalized regression models were applied to individual level g

**Your label:** `unsupported`

**Your rationale:**
The span describes a figure showing cumulative risk by polygenic risk score percentiles but omits the specific directional finding that higher percentiles show higher cumulative risk.

---

## Pair 8: chek2_1100delc_prognosis_disagree_001 claim 1

**Query:** What does the literature report about CHEK2 c.1100delC carriers and breast cancer prognosis outcomes?

**Claim:** Some studies report a worse prognosis for CHEK2 c.1100delC carriers

**Citation:** `PMC7763663`, `body`, characters 35733:37148

**Complete cited source span:**

> Breast cancer in the carriers of pathogenic germline CHEK2 mutations has several recurrently reported clinicopathological characteristics. The most striking is the development of bilateral breast cancer, as shown in some studies (Table 1). A recent meta-analysis by Akdeniz and colleagues [181] computed the relative risk of contralateral breast cancer development as 2.68 (95% CI 1.69–3.65) for c.1100delC mutation carriers versus noncarriers (which was fully comparable with that in BRCA2 mutation carriers: RR = 2.75; 95% CI 1.77–4.29). A significantly younger cancer onset in CHEK2 mutation carriers has been reported less consistently [152,154,182]. Published studies have also pointed out a worse breast cancer prognosis for c.1100delC mutation carriers [183,184,185,186] but not for p.I157T carriers [187]. Since the first studies, CHEK2 germline mutations have frequently been associated (in 85–90% of cases) with estrogen receptor positive (ER+) breast cancer subtypes [115,126,139,183,188,189]. Consistent with that, no CHEK2 mutation carriers were observed in an analysis of 1824 triple negative breast cancer patients [190]. A large analysis conducted by the BCAC consortium estimated the cumulative risk of developing ER+ and ER− breast cancer by the age of 80 for c.1100delC mutation carriers at 20% and 3%, respectively, compared with 9% and 2%, respectively, in the general British population [155].

**Your label:** `supported`

**Your rationale:**
The text directly notes that published studies have pointed out a worse breast cancer prognosis for carriers of this mutation.

---

## Pair 9: palb2_breast_risk_ord_001 claim 1

**Query:** What does the literature report about PALB2 germline mutations and breast cancer risk?

**Claim:** PALB2 germline mutations increase breast cancer risk overall

**Citation:** `PMC7384117`, `abstract`, characters 1459:1774

**Complete cited source span:**

> This study revealed a comprehensive spectrum of PALB2 germline mutations and characteristics of PALB2‐related breast cancer in China. PALB2 germline mutations confer a moderately increased risk for breast cancer but profoundly increase breast cancer risk for those 30 years old or younger in the Chinese population.

**Your label:** `supported`

**Your rationale:**
The span explicitly confirms that these germline mutations confer a moderately increased risk for breast cancer overall.

---

## Pair 10: tp53_chondrosarcoma_survival_ord_001 claim 1

**Query:** What does the literature report about TP53 mutations and survival outcomes in chondrosarcoma?

**Claim:** TP53 mutations are mentioned in chondrosarcoma cell lines but no survival outcome is reported.

**Citation:** `PMC3484068`, `body`, characters 26196:26985

**Complete cited source span:**

> We report the establishment and molecular, genetic and functional characterization of one grade III (L835) and two dedifferentiated chondrosarcoma (L2975 and L3252) cell lines. This represents a substantial addition to the already existing panel of chondrosarcoma cell lines, which together may reflect their heterogeneity. In addition to the existing cell lines these cell lines present the field with an extensive model system as heterogeneous in IDH1 and IDH2 and TP53 mutations as the tumors they are derived from. This panel can be implemented in studies ascertaining human chondrosarcoma tumorigenesis, should provide useful tools in the ongoing search for new targeted therapies, and aid in expanding our knowledge on the role of IDH1 and IDH2 mutations in chondrosarcoma formation.

**Your label:** `unsupported`

**Your rationale:**
The span mentions TP53 mutations in chondrosarcoma cell lines, but its silence about survival
cannot support a claim that no survival outcome was reported. Because the compound claim is not
fully supported, the verdict is unsupported.

---

## Pair 11: atm_at_lymphoid_tumor_ord_001 claim 2

**Query:** What does the literature report about ATM kinase activity level and tumor risk in ataxia-telangiectasia patients?

**Claim:** Expression of residual ATM kinase activity has a protective effect against tumor development in A‑T.

**Citation:** `PMC3170966`, `body`, characters 19870:21091

**Complete cited source span:**

> We show here that development of childhood tumours (lymphoid and brain) in A-T patients is associated almost exclusively with absence of ATM kinase activity. Conversely our findings suggest that expression of some residual ATM kinase activity has a strongly protective effect against tumour development in A-T in childhood. The source of the residual ATM kinase activity was a low level of either normal ATM or mutant ATM. The origin of the retained kinase activity in 25 patients (median age, 29 years) was the presence of the IVS40-1050A>G splice site mutation (McConville et al, 1996; Stewart et al, 2001; Sutton et al, 2004) expressing a low level (∼5%) of normal ATM. Despite the protection against tumour development provided by retained ATM kinase activity, two developed tumours, although significantly only in adulthood (one patient had a T-ALL at 17 years of age; the other patient had a testicular seminoma at an age of 27 years and a cerebral diffuse large B-cell lymphoma at an age of 34 years). This apparent contradiction may be reconciled if the level of ATM kinase activity in these IVS40-1050A>G-carrying patients is close to a threshold of ATM kinase activity that would normally be tumour suppressive.

**Your label:** `unsupported`

**Your rationale:**
The span strictly qualifies the protective effect as occurring "in childhood," whereas the claim generalizes the effect by omitting this required time qualifier from claim_grounding_pilot.md.

---

## Pair 12: atm_c7570g_c_risk_class_disagree_001 claim 2

**Query:** What does the literature report about ATM c.7570G>C and breast cancer risk classification?

**Claim:** The variant is classified as a high‑risk allele for breast cancer

**Citation:** `PMC10092731`, `body`, characters 3614:4227

**Complete cited source span:**

> As ATM c.7570G>C is recurrently encountered in the genetic counseling units in patients with increased risk for breast cancer, there is a need for clearer risk estimates. Here, using both selected breast cancer families from the clinics and so far the largest Northern Finnish unselected breast cancer case cohort (n = 1822), we show that c.7570G>C significantly associates with breast cancer and the risk is estimated as high. This is the first allele‐specific breast cancer risk estimation for ATM c.7570G>C variant in Finnish population, and the result should be taken into consideration in genetic counseling.

**Your label:** `supported`

**Your rationale:**
The span explicitly states the risk is estimated as high for this specific variant.

---
