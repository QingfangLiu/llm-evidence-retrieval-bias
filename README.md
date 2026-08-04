# Retrieval-bias experiments

Each Cochrane review has its own folder named with the review ID. Completed
experiments keep the review-specific analysis script, README, and unchanged
chatbot answers together. Curated CSV/JSON data artifacts live under `data/`.
A planned experiment can begin with a README that fixes the prompts and run
protocol before responses are collected:

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
├── retrieval_bias_demo/
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

For a future review, create a sibling folder such as `reviews/CD012345/`, then
add its title and Cochrane source package to
`shared/review_registry.py`.
Review-specific candidate extraction remains in each review folder; aggregate
analyses and the demo use the shared registry to discover the current review
set and source artifacts.

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
Other benchmark-building, review-plan extraction, audit, and update scripts
from the former parent repository are intentionally not included because this
standalone repo does not call them.

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

To validate and regenerate all current citation-match tables, run from the
repository root:

```bash
python3 reviews/CD000510/analyze_cd000510_roles.py
python3 reviews/CD001452/analyze_cd001452_roles.py
python3 reviews/CD005354/analyze_cd005354_roles.py
python3 reviews/CD007654/analyze_cd007654_roles.py
python3 reviews/CD007912/analyze_cd007912_roles.py
python3 reviews/CD009532/analyze_cd009532_roles.py
python3 reviews/CD009958/analyze_cd009958_roles.py
python3 reviews/CD010051/analyze_cd010051_roles.py
python3 reviews/CD010461/analyze_cd010461_roles.py
python3 reviews/CD012161/analyze_cd012161_roles.py
python3 reviews/CD012751/analyze_cd012751_roles.py
python3 reviews/CD013776/analyze_cd013776_roles.py
python3 reviews/CD015136/analyze_cd015136_roles.py
python3 reviews/CD015156/analyze_cd015156_roles.py
python3 reviews/CD015186/analyze_cd015186_roles.py
python3 reviews/CD015264/analyze_cd015264_roles.py
python3 reviews/CD015898/analyze_cd015898_roles.py
python3 reviews/CD015934/analyze_cd015934_roles.py
python3 reviews/CD016085/analyze_cd016085_roles.py
python3 reviews/CD016104/analyze_cd016104_roles.py
```

## Cochrane exclusion reasons among chatbot-cited studies

`scripts/analyze_cited_excluded_reasons.py` provides a descriptive, study-cluster-level
audit of the studies that chatbots cited even though the corresponding Cochrane
review explicitly excluded them. Run from the repository root:

```bash
python3 scripts/analyze_cited_excluded_reasons.py
```

The analysis reads `cochrane_excluded` rows from every registered
`data/reviews/*/*_role_study_matches.csv`, deduplicates them by review and Cochrane study
label, and joins each cluster to the `N1` exclusion reason in that review's
excluded RIS export. The current inputs contain 856 response-study mentions
representing 142 unique excluded study clusters across all 20 reviews. All 142
clusters resolve to exactly one distinct Cochrane exclusion reason.

The audit artifacts have separate responsibilities:

- `data/curation/cited_excluded_reason_taxonomy.csv` defines the high-level categories and
  their boundaries.
- `data/curation/cited_excluded_reason_curation.csv` records only the reviewed category
  decision for each cited excluded study cluster.
- `data/analysis/cited_excluded_study_reason_audit.csv` joins the Cochrane reason, reviewed
  categories, and number of response-study mentions so every classification
  can be checked against its source wording.
- `data/analysis/cited_excluded_reason_counts.csv` counts unique study clusters and
  response-study mentions for each category.
- `data/analysis/cited_excluded_reason_combination_counts.csv` counts mutually exclusive
  category combinations.

Reason categories are multi-label because Cochrane can identify more than one
eligibility problem for a study. Category-level counts therefore overlap and
do not sum to 142; category-combination counts are mutually exclusive and do.
`response_study_mentions` is the number of match-table rows, where a resolved
study cluster appears at most once per chatbot response. The script fails if a
current cited excluded study lacks a curation decision, a curation row is
stale, a category is undefined, or the RIS join does not produce exactly one
reason. This analysis is descriptive and runs no statistical model.

## Cross-review role consistency

`scripts/analyze_role_consistency.py` measures replicate-to-replicate randomness within
each (review, model, role) cell, independent of the review-specific analyses
above. Run from the repository root:

```bash
python3 scripts/analyze_role_consistency.py
```

For every cell's four replicates, the script computes the pairwise Jaccard
similarity of retrieved-study sets across all six replicate pairs and averages
them into one self-consistency score per cell (1.0 = all four replicates named
the same set, 0.0 = no overlap between any pair). It reports two scopes:
`all_candidates` (every resolved candidate, a measure of raw output stability)
and `included_only` (candidates matched to a Cochrane-included label, a measure
of how consistently a model/role finds the same correct studies). Results are
written to `data/analysis/role_consistency_jaccard.csv`, one row per
review/model/role/scope.

The committed aggregate contains 360 rows: 20 reviews × 3 chatbots × 3 roles
× 2 scopes. Aggregated across all 20 reviews and three roles, ChatGPT is the
most self-consistent chatbot on both scopes (mean Jaccard 0.651
all-candidates, 0.804 included-only). Claude averages 0.442 and 0.610;
Gemini averages 0.422 and 0.555. Several Gemini cells retrieve only a few
candidates per response, so their Jaccard values are especially sensitive to
one study. Differences between roles within a chatbot remain smaller than the
differences between chatbots.

## Recall pattern by study characteristic

`scripts/analyze_recall_by_characteristic.py` asks what distinguishes studies that no
chatbot ever recalls, or that only one chatbot recalls, from the rest. Run
from the repository root:

```bash
python3 scripts/analyze_recall_by_characteristic.py
```

For the 20 reviews with a balanced user-role experiment, it labels every
Cochrane-included study by which of Claude, Gemini, and GPT retrieved it at
least once across that review's 12 responses per chatbot, then joins five
characteristics:

- publication year, from the included RIS export, available for 426 of 442
  included studies regardless of recall pattern;
- sample size, from each review's own analysis data
  (`<REVIEW>-analysis-data/<REVIEW>-data-rows.csv`), the same per-study rows
  that produce the review's forest plots. For each study this is the largest
  (Experimental N + Control N) seen across its analysis rows — Cochrane's own
  analyzed sample size, which can run a little below a study's originally
  enrolled total when an outcome had missing data, so the maximum across a
  study's rows is used as the closest available proxy for its total. This
  covers 388 of 442 included studies (88%) with no network dependency. A
  live PubMed abstract fetch was tried first and reached only ~15-20%
  coverage with meaningfully more uncertainty per value (PMID resolution
  fails for studies with no DOI/PMID on record, and even a resolved abstract
  often never states a single overall N), so it was replaced entirely by this
  local source;
- citations per year, from `data/analysis/citation_counts_by_study.csv` (written by
  `scripts/fetch_citation_counts.py`, run separately - see below). Publication year
  and sample size are both properties of the review's own data; citations
  per year additionally requires resolving each study's PMID and looking up
  a live citation count, so it is documented as its own step;
- open-access status (`is_open_access`), from the same `data/analysis/citation_counts_by_study.csv`
  row - Semantic Scholar's flag for the same best-matched PMID citation
  counts already use. A binary characteristic, so it is reported as a rate
  with a Fisher's exact test rather than the mean/median/Mann-Whitney
  treatment the numeric characteristics get;
- design, from the curated match tables' `design` field, defined only for
  studies at least one response actually named, so it cannot describe the
  "not recalled" bucket.

Year, sample size, citations per year, and open-access status are all
available regardless of recall pattern; design is not. Results are written
to `data/analysis/recall_pattern_by_characteristic.csv`, one row per review/study with its
recall pattern, year, sample size, citations per year, open-access status,
and design category.

Publication year, sample size, citations per year, and total citations all
show univariate recall differences. Not-recalled studies have a median year
of 2009 (n=109) versus 2014 among recalled studies (n=317; Mann-Whitney
p=0.00058). Their median analyzed sample size is 97 (n=91) versus 195
(n=297; p=3.4e-08), and median citations per year are 2.33 (n=79) versus
5.50 (n=287; p=4.3e-07). Total citations also differ (median 28.5 vs. 63.5;
p=7.3e-06). Open access is 45% among not-recalled studies (36/80) and 56%
among recalled studies (167/296), but this larger dataset no longer gives a
conventional univariate signal (Fisher's exact p=0.077). Design remains
mainly descriptive because it is defined only for recalled studies:
213 are parallel-group/unspecified RCTs and 96 are cluster-randomized, with
19 studies spread across eight smaller categories.

### Citations per year (fetched from PubMed and Semantic Scholar)

`scripts/fetch_citation_counts.py` resolves each included study's PMID(s) and fetches
citation counts, run separately from (and before) `scripts/analyze_recall_by_characteristic.py`
since it makes live network calls:

```bash
python3 scripts/fetch_citation_counts.py
python3 scripts/analyze_recall_by_characteristic.py
```

PMID resolution reuses the retained RIS reference-resolution pipeline in
`benchmark_tools/build_reference_indexing_from_cochrane_ris.py` rather than
re-implementing citation matching: explicit PMIDs found anywhere in a study's
RIS record, then a DOI search, then a validated author+title(+journal+year)
citation search that rejects weak or non-article matches (corrections, errata,
retractions). An earlier from-scratch attempt using only a study's
`DO`/`PUBMED` RIS fields reached roughly half this coverage; reusing this
pipeline resolved a PMID for 379 of 442 included studies (86%) and
a computable citations-per-year for 366 (83%). Citation counts come from the
Semantic Scholar Graph API's batch endpoint (no API key), matched by PMID; a
study's `citation_count` is the maximum across all of its resolved PMIDs
(usually the main trial report, since companion/follow-up papers are
typically cited less than the original trial), and `citations_per_year`
divides that by years since the study's Cochrane-reported publication year.
Blank values mean PMID resolution or the Semantic Scholar lookup failed, not
zero citations. Results are cached in `data/cache/pmid_resolution_cache.json` (PubMed)
and `data/cache/semantic_scholar_cache.json` (Semantic Scholar) so repeat runs do not
re-hit either API, and written to `data/analysis/citation_counts_by_study.csv`, which
includes `citations_per_year`, the raw `citation_count` it is derived from,
and `is_open_access` - Semantic Scholar's open-access flag for that same
best-matched PMID (known for 376 of 442 studies). A cached
Semantic Scholar entry from before `isOpenAccess` was added to the fetched
fields is treated as stale and refetched once, rather than permanently
missing the field. `scripts/analyze_recall_by_characteristic.py` reports both:
citations per year as the primary impact measure, and total citations as a
secondary, unnormalized view kept alongside it rather than instead of it. The
two can disagree; in this dataset both distinguish recalled from
not-recalled studies, with p=7.3e-06 for total citations and p=4.3e-07 for
citations per year.

### Predictor correlations (multicollinearity check)

Before treating year, sample size, citations per year, and total citations
as independent predictors (e.g. in a multiple logistic regression on recall
pattern), it is worth checking how correlated they actually are. This
analysis is built and rendered entirely in the demo now (a ggpairs-style
4x4 matrix - overlaid per-group histograms on the diagonal, colored scatter
in the lower triangle, Spearman rho with significance stars in the upper
triangle, both overall and split by recall status) rather than as a
separate script; see the "Predictor correlations" section of
`retrieval_bias_demo/README.md` for how to view and reproduce it. An
earlier standalone `plot_predictor_correlations.py` script producing a
plain (non-grouped, no significance stars) static PNG has been removed,
since the demo version is now a strict superset of what it showed.

Using the 330 included studies with all four numeric values present,
publication year correlates weakly with sample size (rho=0.15), moderately
with citations per year (0.32), and negatively with total citations
(-0.23). Sample size correlates with citations per year at rho=0.41 and
with total citations at 0.33. Citations per year and total citations are
strongly related (rho=0.80), as expected because one is derived from the
other. The regression therefore uses citations per year but not total
citations. VIFs for the fitted predictors remain low (1.19-1.54).

### Multiple logistic regression

`scripts/analyze_recall_logistic_regression.py` fits `logit(recalled) ~ year +
log(sample_size) + log(citations_per_year + 0.01) + is_open_access` to ask
whether each characteristic has an independent effect once the others are
controlled for - the pairwise comparisons and correlation matrix above can
each show a difference, but not whether it survives alongside the others:

```bash
python3 scripts/analyze_recall_logistic_regression.py
```

Uses the same 330 of 442 studies with all four predictors present (adding
open-access status as a required field does not narrow the population
further: it comes from the same best-matched PMID as citations per year, so
a study with one has the other), fit with `statsmodels.Logit` (a hand-rolled
implementation would be easy to get subtly wrong for something this
sensitive to correct inference) and standard errors clustered by review (20
clusters), since studies nest within reviews and that mildly violates the
independence assumption a plain logistic regression relies on. Total
citations is excluded from the model entirely (not just deprioritized)
given its rho=0.80 with citations per year. Results are written to
`data/analysis/logistic_regression_results.json` and printed as a coefficient table with
clustered and naive p-values, odds ratios with 95% CIs, Variance Inflation
Factors, and fit statistics.

**Once the predictors are modeled jointly, sample size is the only
significant predictor.** Its odds ratio is 1.80 per unit increase in
log(sample size) (95% CI 1.37-2.36, clustered p=2.3e-05). Publication year
(OR=1.02, p=0.35), citations per year (OR=1.35, p=0.057), and open access
(OR=0.90, p=0.69) are not independently significant. McFadden pseudo
R-squared is 0.134 and the likelihood-ratio p-value against the null model
is 3.4e-09.

This coefficient table is also rendered directly in the demo's Across-reviews
tab (see `retrieval_bias_demo/README.md`, "Multiple logistic regression on
recall"), reading `data/analysis/logistic_regression_results.json` rather than refitting
the model in the browser.

## Citation issues (`identity_issue`) are not fabrication

Each review's analysis script flags a matched citation with `identity_issue=1`
when it resolves to a correctly-identified real study but has conflicting
bibliographic details - almost always a wrong lead author on an otherwise
correctly-matched title, e.g. "The title identifies Bakris 2002, but the
response supplies Sharma and Golay as authors." or "The response attributes
IronWoMan to Baart et al." Other variants include a wrong year, wrong
journal, wrong page range, or results from one real study misattributed to
a different real study ("The response assigns Papanikolaou 2005 results to
Bungum 2003"). Across the 20 reviews in the demo, 232 of 7,676 matched
citation rows (3.0%) carry this flag.

**This is misattribution, not fabrication.** The study itself was correctly
identified (by title, PMID, or PMCID); only a surrounding detail is wrong.
A dedicated check of the much rarer `unresolved`/`outside_unresolved` status
now covers all 23 such rows. Twenty-two resolve to real papers or protocols,
although several conflate an author, comparator, intervention, or secondary
source; only one - a "Ratner RE" citation for a lispro-vs-regular-insulin
trial in CD012161 - could not be matched to a real publication despite
targeted search. See `data/analysis/unresolved_candidate_fabrication_check.csv` for the
per-entry queries, best matches, and verdicts.

**`identity_issue` is never used to filter or exclude a citation anywhere in
this codebase.** Only the demo builder reads it downstream: `study_rows()`
renders an amber outline and tooltip on affected retrieval-matrix cells, and
`build_citation_issue_summary()` aggregates the reporting count by review.
Every recall percentage, Venn panel, citations-per-answer result,
replicate-consistency Jaccard, characteristic row, and regression is built
from `ground_truth_status` alone and gives a flagged citation the same credit
as a clean one when it resolves to the correct study.
