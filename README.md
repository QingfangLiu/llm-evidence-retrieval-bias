# Retrieval-bias experiments

## Paper

This repository accompanies the following paper, which was accepted for an
oral presentation at the [Pacific Symposium on Biocomputing 2027 (PSB
2027)](https://psb.stanford.edu/):

**Do AI chatbots find what experts would? Effects of model, user role, and
sample size on study retrieval for medical questions**

**Preprint:** [arXiv:2608.13786](https://arxiv.org/abs/2608.13786)

**Authors:** Qingfang Liu<sup>1</sup>, Qiao Jin<sup>2</sup>, Joe D.
Menke<sup>3</sup>, Thorsten Kahnt<sup>1</sup>, and Zhiyong Lu<sup>2</sup>

1. National Institute on Drug Abuse Intramural Research Program, National
   Institutes of Health, Baltimore, MD, USA
2. National Library of Medicine, National Institutes of Health, Bethesda, MD,
   USA
3. School of Information Sciences, University of Illinois Urbana–Champaign,
   Champaign, IL, USA

## Supplementary materials

The supplementary file referenced in the paper is available here:
[PSB 2027 Supplementary Materials (PDF)](PSB2027_Supplementary_Materials_Liu_et_al.pdf).

## Online interactive demo

Use the [online interactive demo](https://qingfangliu.github.io/llm-evidence-retrieval-bias/demo/)
to explore which studies each chatbot retrieved for patient, clinician, and
researcher prompts across the 20 Cochrane reviews. You can also view
across-review summaries of recall and overlap.

## Cochrane reviews included in the study

The current dataset contains 20 completed Cochrane Issue 6 and Issue 7
user-role experiments.

| Issue | Review | Clinical question | Included clusters |
| --- | --- | --- | ---: |
| 6 | `CD007654` | Weight-reducing drugs in people with hypertension | 8 |
| 6 | `CD009532` | Iron supplementation for blood donors | 38 |
| 6 | `CD009958` | Repositioning for pressure injury prevention | 13 |
| 6 | `CD010461` | Advanced sperm selection techniques for assisted reproduction | 5 |
| 6 | `CD012161` | Short-acting insulin analogues for type 1 diabetes | 15 |
| 6 | `CD012751` | Biologic drugs for Crohn's disease | 94 |
| 6 | `CD013776` | Blue versus white light for bladder-cancer resection | 17 |
| 6 | `CD015136` | Telepharmacy services for non-communicable diseases | 21 |
| 6 | `CD015264` | Vitamin B12 supplementation in children | 16 |
| **6 total** | **9 reviews** |  | **227** |
| 7 | `CD000510` | Prophylactic versus selective surfactant in preterm infants | 10 |
| 7 | `CD001452` | Venepuncture versus heel lance in term neonates | 8 |
| 7 | `CD005354` | rFSH versus other gonadotropins in assisted reproduction | 59 |
| 7 | `CD007912` | Exercise for hip osteoarthritis | 18 |
| 7 | `CD010051` | Topical ciclosporine A for dry eye disease | 58 |
| 7 | `CD015156` | Non-surgical treatment of lower-limb apophyseal injuries | 10 |
| 7 | `CD015186` | Minimally invasive trabecular surgery for open-angle glaucoma | 10 |
| 7 | `CD015898` | Red-cell transfusion volume | 12 |
| 7 | `CD015934` | Smoking cessation in inpatient psychiatry settings | 10 |
| 7 | `CD016085` | Blood-pressure management after reperfused ischemic stroke | 9 |
| 7 | `CD016104` | Perioperative immunotherapy for localized NSCLC in older adults | 11 |
| **7 total** | **11 reviews** |  | **215** |
| **All** | **20 reviews** |  | **442** |

## Data availability and reproducibility

### What is available in this repository

The committed CSV and JSON results, figures, and interactive demo can be
inspected without any additional source files. Detailed analysis methods,
regeneration commands, output descriptions, and interpretation notes are in
[docs/analysis.md](docs/analysis.md).

### What is required for full regeneration

Fully regenerating the analyses requires an authorized copy of the Cochrane
source packages. These packages contain RIS exports and analysis-data rows and
are not redistributed here because of Cochrane copyright and licensing
restrictions.

Place the authorized packages in `source_reviews/` at the repository root,
preserving the `2026_issue_6/` and `2026_issue_7/` subdirectories specified in
`shared/review_registry.py`. Run the regeneration commands from the repository
root.

### Included helper code

`benchmark_tools/` contains the RIS reference-resolution code used by
`scripts/fetch_citation_counts.py`: the Cochrane RIS resolver, TSV schema
helper, source-file finder, and PubMed/PMC lookup helpers.

## Repository maintainer

This repository is maintained by **Qingfang Liu**. For questions, contact
[psychliuqf@gmail.com](mailto:psychliuqf@gmail.com).
