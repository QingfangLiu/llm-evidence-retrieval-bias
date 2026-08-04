# Retrieval-bias experiments

Each Cochrane review has its own folder named with the review ID. Completed
experiments keep the review-specific analysis script, README, and unchanged
chatbot answers together. Curated CSV/JSON data artifacts live under `data/`.
Current layout:

```text
./
├── reviews/
│   ├── CD000510/
│   │   ├── analyze_cd000510_roles.py
│   │   ├── README.md
│   │   └── <36 model-role response files>
│   ├── CD001452/
│   ├── ...
│   └── CD016104/
├── data/
│   ├── analysis/
│   ├── cache/
│   ├── curation/
│   └── reviews/
│       ├── CD000510/
│       │   └── cd000510_role_study_matches.csv
│       ├── CD001452/
│       ├── ...
│       └── CD016104/
├── demo/
├── figures/
├── shared/
│   ├── __init__.py
│   └── review_registry.py
├── benchmark_tools/
│   ├── build_reference_indexing_from_cochrane_ris.py
│   ├── cochrane_review_source.py
│   ├── pubmed_utils.py
│   └── reference_indexing_schema.py
└── scripts/
    ├── analyze_*.py
    └── fetch_citation_counts.py
```

## Standalone source inputs

This repository now treats its own top-level directory as the project root.
Scripts that regenerate match tables or rebuild cross-review characteristics
expect Cochrane source packages under `source_reviews/`, preserving the
existing `2026_issue_6/` and `2026_issue_7/` subdirectories recorded in
`shared/review_registry.py`.

`source_reviews/` is intentionally not included in this repository because it
contains Cochrane review data packages, including RIS exports and analysis-data
rows, that are not redistributed here for Cochrane copyright/licensing reasons.
To fully regenerate the analyses, restore `source_reviews/` locally from an
authorized copy of the source material while preserving the paths recorded in
`shared/review_registry.py`.

`benchmark_tools/` contains only the minimal RIS reference-resolution helper
needed by `scripts/fetch_citation_counts.py`: the Cochrane RIS resolver, its
TSV schema helper, a small source-file finder, and PubMed/PMC lookup helpers.

The committed CSV, JSON, figure, and demo artifacts can still be inspected
without `source_reviews/`.

## Review set

The current dataset contains 20 completed Cochrane Issue 6 and Issue 7
user-role experiments, covering 442 included primary-study clusters.

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

Detailed analysis methods, regeneration commands, output descriptions, and
interpretation notes are kept in [docs/analysis.md](docs/analysis.md).
