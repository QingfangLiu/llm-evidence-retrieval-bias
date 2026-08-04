# Retrieval-bias experiments

Each Cochrane review has its own folder named with the review ID. Completed
experiments keep the review-specific analysis script, curated citation-match
table, and unchanged chatbot answers together. A planned experiment can begin
with a README that fixes the prompts and run protocol before responses are
collected:

```text
retrieval_bias/
├── CD000510/
│   ├── analyze_cd000510_roles.py
│   ├── cd000510_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD001452/
│   ├── analyze_cd001452_roles.py
│   ├── cd001452_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD005354/
│   ├── analyze_cd005354_roles.py
│   ├── cd005354_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD007654/
│   ├── analyze_cd007654_roles.py
│   ├── cd007654_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD007912/
│   ├── analyze_cd007912_roles.py
│   ├── cd007912_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD009532/
│   ├── analyze_cd009532_roles.py
│   ├── cd009532_role_study_matches.csv
│   └── <36 model-role response files>
├── CD009958/
│   ├── analyze_cd009958_roles.py
│   ├── cd009958_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD010051/
│   ├── analyze_cd010051_roles.py
│   ├── cd010051_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD010461/
│   ├── analyze_cd010461_roles.py
│   ├── cd010461_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD012161/
│   ├── analyze_cd012161_roles.py
│   ├── cd012161_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD012751/
│   ├── analyze_cd012751_roles.py
│   ├── cd012751_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD013776/
│   ├── analyze_cd013776_roles.py
│   ├── cd013776_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD015136/
│   ├── analyze_cd015136_roles.py
│   ├── cd015136_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD015156/
│   ├── analyze_cd015156_roles.py
│   ├── cd015156_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD015186/
│   ├── analyze_cd015186_roles.py
│   ├── cd015186_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD015264/
│   ├── analyze_cd015264_roles.py
│   ├── cd015264_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD015898/
│   ├── analyze_cd015898_roles.py
│   ├── cd015898_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD015934/
│   ├── analyze_cd015934_roles.py
│   ├── cd015934_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
├── CD016085/
│   ├── analyze_cd016085_roles.py
│   ├── cd016085_role_study_matches.csv
│   ├── README.md
│   └── <36 model-role response files>
└── CD016104/
    ├── analyze_cd016104_roles.py
    ├── cd016104_role_study_matches.csv
    ├── README.md
    └── <36 model-role response files>
```

For a future review, create a sibling folder such as `CD012345/`, then add its
title and Cochrane source package to `review_registry.py`. Review-specific
candidate extraction remains in each review folder; aggregate analyses and the
demo use the shared registry to discover the current review set and source
artifacts.

## 2026 Issue 7 expansion

Eleven reviews from Cochrane 2026 Issue 7 were staged as retrieval-bias
experiments. Together they cover 215 included primary-study clusters.
All 11 now have complete 36-run user-role experiments and review-specific
analyses.

| Review | Clinical question | Included primary-study clusters | Status |
| --- | --- | ---: | --- |
| `CD000510` | Prophylactic versus selective surfactant in preterm infants | 10 | Complete |
| `CD001452` | Venepuncture versus heel lance in term neonates | 8 | Complete |
| `CD005354` | rFSH versus other gonadotropins in assisted reproduction | 59 | Complete |
| `CD007912` | Exercise for hip osteoarthritis | 18 | Complete |
| `CD010051` | Topical ciclosporine A for dry eye disease | 58 | Complete |
| `CD015156` | Non-surgical treatment of lower-limb apophyseal injuries | 10 | Complete |
| `CD015186` | Minimally invasive trabecular surgery for open-angle glaucoma | 10 | Complete |
| `CD015898` | Larger versus smaller red-cell transfusion volumes | 12 | Complete |
| `CD015934` | Smoking cessation in inpatient psychiatry settings | 10 | Complete |
| `CD016085` | Blood-pressure management after reperfused ischemic stroke | 9 | Complete |
| `CD016104` | Perioperative immunotherapy for localized NSCLC in older adults | 11 | Complete |
| **Total** | **11 reviews** | **215** | **11 complete** |

To validate and regenerate all current citation-match tables, run from the
repository root:

```bash
python3 retrieval_bias/CD000510/analyze_cd000510_roles.py
python3 retrieval_bias/CD001452/analyze_cd001452_roles.py
python3 retrieval_bias/CD005354/analyze_cd005354_roles.py
python3 retrieval_bias/CD007654/analyze_cd007654_roles.py
python3 retrieval_bias/CD007912/analyze_cd007912_roles.py
python3 retrieval_bias/CD009532/analyze_cd009532_roles.py
python3 retrieval_bias/CD009958/analyze_cd009958_roles.py
python3 retrieval_bias/CD010051/analyze_cd010051_roles.py
python3 retrieval_bias/CD010461/analyze_cd010461_roles.py
python3 retrieval_bias/CD012161/analyze_cd012161_roles.py
python3 retrieval_bias/CD012751/analyze_cd012751_roles.py
python3 retrieval_bias/CD013776/analyze_cd013776_roles.py
python3 retrieval_bias/CD015136/analyze_cd015136_roles.py
python3 retrieval_bias/CD015156/analyze_cd015156_roles.py
python3 retrieval_bias/CD015186/analyze_cd015186_roles.py
python3 retrieval_bias/CD015264/analyze_cd015264_roles.py
python3 retrieval_bias/CD015898/analyze_cd015898_roles.py
python3 retrieval_bias/CD015934/analyze_cd015934_roles.py
python3 retrieval_bias/CD016085/analyze_cd016085_roles.py
python3 retrieval_bias/CD016104/analyze_cd016104_roles.py
```

These tables cover the CD000510, CD001452, CD005354, CD007654, CD007912,
CD009532, CD009958, CD010051, CD010461, CD012161, CD012751, CD013776,
CD015136, CD015156, CD015186, CD015264, CD015898, CD015934, CD016085, and
CD016104 role experiments.

The CD000510 experiment uses Claude Sonnet 5 at medium effort with thinking on,
Gemini 3.1 Pro with extended thinking, and ChatGPT 5.5 at high intelligence.
Its prompts ask each chatbot to list primary studies at the end. Only the
dedicated terminal list is counted. The analysis reads the Issue 7 Cochrane
included, excluded, awaiting-classification, and ongoing RIS exports directly
from the source ZIP archive, so no manual extraction is required.

The CD001452 experiment has four responses per model-role cell, but model
versions and settings were not recorded. Its analysis counts only the
dedicated terminal study list and validates included, excluded, and ongoing
labels directly against the source ZIP's RIS exports. The included RIS has
eight study clusters and six explicit PubMed IDs. Eight Claude responses
disclose using review reference lists despite the prompt restriction; the
review-specific README reports the associated sensitivity check.

The CD010051 experiment uses the same model configurations, role conditions,
and repetitions. It also counts only the dedicated final study list, groups
companion publications to the source-package study cluster, and retains
excluded, ongoing, observational, retracted, secondary, and unresolved
candidates in the audit table. Its source RIS contains no explicit PubMed IDs,
so cluster and study-row recall are reported but PMID recall is unavailable.

The CD005354 experiment has four responses per model-role cell, but model
versions and generation settings were not recorded and are not inferred. Its
analysis counts only dedicated terminal study lists, groups companion reports
within a response, and validates included, excluded, awaiting-classification,
and ongoing labels directly against the source-package RIS exports. The
included RIS has no explicit PubMed IDs, so recall is reported at the
study-cluster level. Four Claude responses disclose using secondary citation
trails despite the prompt restriction; the review-specific README reports the
associated sensitivity check.

The CD007912 experiment has four responses per model-role cell, but model
versions and generation settings were not recorded and are not inferred. Its
analysis counts only the dedicated terminal study list, groups companion
reports within a response, and validates included, excluded, and ongoing
labels directly against the source data-package RIS exports. Its included RIS
also has no explicit PubMed IDs, so recall is reported at the study-cluster
level. Nine Claude responses disclose review or secondary-source use despite
the prompt restriction; the review-specific README reports the associated
sensitivity check.

The CD015156 experiment also has four responses per model-role cell with model
versions and settings not recorded. Its analysis identifies studies from the
complete response and validates included, excluded, and ongoing labels against
the source-package RIS exports. The CD015898 experiment uses the recorded
Claude Sonnet 5, Gemini 3.1 Pro, and ChatGPT 5.5 configurations and likewise
uses complete-response identification with source-package label validation.

The CD016104 experiment uses the same three model configurations and four
independent responses per role. Its analysis identifies studies from the
complete response, groups linked reports at the study-cluster level, and
validates included, excluded, and ongoing labels directly against the review
data-package RIS exports in the source ZIP archive.

The CD015186 experiment uses the same configurations and repetitions. Its
analysis identifies studies from the complete response, groups linked reports
at the study-cluster level, and validates included, excluded, ongoing, and
awaiting-classification labels directly against the source data-package RIS
exports.

The CD015934 experiment uses the same configurations and repetitions. Its
analysis likewise identifies studies from the complete response, groups linked
reports at the study-cluster level, and validates included, excluded, and
ongoing labels directly against the source data-package RIS exports. It retains
post-review publications as reports of their corresponding source-package
study labels rather than treating publication date alone as a new study.

The CD016085 experiment uses the same configurations and repetitions. Its
analysis identifies studies from the complete response, groups linked reports
at the study-cluster level, and validates included, excluded,
awaiting-classification, and ongoing labels directly against the source
data-package RIS exports. It counts only the randomized primary-study component
of the combined DETECT publication and retains HOPE's source-package
classification as ongoing.

The CD007654 experiment tests user-role effects with Claude Sonnet 5 at medium
effort with thinking on, Gemini 3.1 Pro with extended thinking, and ChatGPT 5.5
at high intelligence. Its prompt asks each chatbot to list the primary studies
at the end. As in CD012161 and CD012751, its retrieval boundary is only that
dedicated terminal list; narrative and inline citations do not add candidates.
The analysis preserves terminal-list citation errors while resolving and
deduplicating identifiable reports at the study-cluster level.

The CD012751 experiment uses the same three model configurations and four
independent responses per role. Its prompts define the dedicated final study
list as the retrieval boundary. Its analysis preserves explicitly listed
out-of-scope and citation-conflict entries, splits citations that name multiple
distinct trials, and validates included and excluded study labels directly
against the review data-package RIS exports.

The CD012161 experiment uses the same three model configurations and four
independent responses per role. Its prompts define the dedicated final study
list as the retrieval boundary. Its analysis validates included, excluded, and
awaiting-classification labels directly against the review data-package RIS
exports.

The CD009532 experiment tests user-role effects only. It uses Claude Sonnet 5 at
medium effort with thinking on, Gemini 3.1 Pro with extended thinking, and ChatGPT
5.5 at high intelligence. Its analysis resolves study truth directly from the
Cochrane included/excluded RIS exports rather than requiring a `benchmark.json`.

The CD009958 experiment also tests user-role effects only and uses the same three
model configurations and four independent responses per role. Its analysis uses
the complete response to identify retrieved studies and validates Cochrane labels
against the included, excluded, and ongoing RIS exports.

The CD010461, CD013776, CD015136, and CD015264 experiments use Claude Sonnet 5 at
medium effort with thinking on, Gemini 3.1 Pro with extended thinking, and
ChatGPT 5.5 at high intelligence. Each has four independent responses per role.
Their analyses identify studies from the complete response, group linked reports
at the study-cluster level, and validate Cochrane classifications directly against
the review data-package RIS exports.

## Cochrane exclusion reasons among chatbot-cited studies

`analyze_cited_excluded_reasons.py` provides a descriptive, study-cluster-level
audit of the studies that chatbots cited even though the corresponding Cochrane
review explicitly excluded them. Run from the repository root:

```bash
python3 retrieval_bias/analyze_cited_excluded_reasons.py
```

The analysis reads `cochrane_excluded` rows from every registered
`*_role_study_matches.csv`, deduplicates them by review and Cochrane study
label, and joins each cluster to the `N1` exclusion reason in that review's
excluded RIS export. The current inputs contain 856 response-study mentions
representing 142 unique excluded study clusters across all 20 reviews. All 142
clusters resolve to exactly one distinct Cochrane exclusion reason.

The audit artifacts have separate responsibilities:

- `cited_excluded_reason_taxonomy.csv` defines the high-level categories and
  their boundaries.
- `cited_excluded_reason_curation.csv` records only the reviewed category
  decision for each cited excluded study cluster.
- `cited_excluded_study_reason_audit.csv` joins the Cochrane reason, reviewed
  categories, and number of response-study mentions so every classification
  can be checked against its source wording.
- `cited_excluded_reason_counts.csv` counts unique study clusters and
  response-study mentions for each category.
- `cited_excluded_reason_combination_counts.csv` counts mutually exclusive
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

`analyze_role_consistency.py` measures replicate-to-replicate randomness within
each (review, model, role) cell, independent of the review-specific analyses
above. Run from the repository root:

```bash
python3 retrieval_bias/analyze_role_consistency.py
```

For every cell's four replicates, the script computes the pairwise Jaccard
similarity of retrieved-study sets across all six replicate pairs and averages
them into one self-consistency score per cell (1.0 = all four replicates named
the same set, 0.0 = no overlap between any pair). It reports two scopes:
`all_candidates` (every resolved candidate, a measure of raw output stability)
and `included_only` (candidates matched to a Cochrane-included label, a measure
of how consistently a model/role finds the same correct studies). Results are
written to `role_consistency_jaccard.csv`, one row per
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

`analyze_recall_by_characteristic.py` asks what distinguishes studies that no
chatbot ever recalls, or that only one chatbot recalls, from the rest. Run
from the repository root:

```bash
python3 retrieval_bias/analyze_recall_by_characteristic.py
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
- citations per year, from `citation_counts_by_study.csv` (written by
  `fetch_citation_counts.py`, run separately - see below). Publication year
  and sample size are both properties of the review's own data; citations
  per year additionally requires resolving each study's PMID and looking up
  a live citation count, so it is documented as its own step;
- open-access status (`is_open_access`), from the same `citation_counts_by_study.csv`
  row - Semantic Scholar's flag for the same best-matched PMID citation
  counts already use. A binary characteristic, so it is reported as a rate
  with a Fisher's exact test rather than the mean/median/Mann-Whitney
  treatment the numeric characteristics get;
- design, from the curated match tables' `design` field, defined only for
  studies at least one response actually named, so it cannot describe the
  "not recalled" bucket.

Year, sample size, citations per year, and open-access status are all
available regardless of recall pattern; design is not. Results are written
to `recall_pattern_by_characteristic.csv`, one row per review/study with its
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

`fetch_citation_counts.py` resolves each included study's PMID(s) and fetches
citation counts, run separately from (and before) `analyze_recall_by_characteristic.py`
since it makes live network calls:

```bash
python3 retrieval_bias/fetch_citation_counts.py
python3 retrieval_bias/analyze_recall_by_characteristic.py
```

PMID resolution reuses the repository's existing, tested reference-resolution
pipeline in `Cochrane_reviews/benchmark_tools/build_reference_indexing_from_cochrane_ris.py`
(the same module the active benchmark-curation path imports directly) rather
than re-implementing citation matching: explicit PMIDs found anywhere in a
study's RIS record, then a DOI search, then a validated author+title(+journal
+year) citation search that rejects weak or non-article matches (corrections,
errata, retractions). An earlier from-scratch attempt using only a study's
`DO`/`PUBMED` RIS fields reached roughly half this coverage; reusing the
existing pipeline resolved a PMID for 379 of 442 included studies (86%) and
a computable citations-per-year for 366 (83%). Citation counts come from the
Semantic Scholar Graph API's batch endpoint (no API key), matched by PMID; a
study's `citation_count` is the maximum across all of its resolved PMIDs
(usually the main trial report, since companion/follow-up papers are
typically cited less than the original trial), and `citations_per_year`
divides that by years since the study's Cochrane-reported publication year.
Blank values mean PMID resolution or the Semantic Scholar lookup failed, not
zero citations. Results are cached in `pmid_resolution_cache.json` (PubMed)
and `semantic_scholar_cache.json` (Semantic Scholar) so repeat runs do not
re-hit either API, and written to `citation_counts_by_study.csv`, which
includes `citations_per_year`, the raw `citation_count` it is derived from,
and `is_open_access` - Semantic Scholar's open-access flag for that same
best-matched PMID (known for 376 of 442 studies). A cached
Semantic Scholar entry from before `isOpenAccess` was added to the fetched
fields is treated as stale and refetched once, rather than permanently
missing the field. `analyze_recall_by_characteristic.py` reports both:
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

`analyze_recall_logistic_regression.py` fits `logit(recalled) ~ year +
log(sample_size) + log(citations_per_year + 0.01) + is_open_access` to ask
whether each characteristic has an independent effect once the others are
controlled for - the pairwise comparisons and correlation matrix above can
each show a difference, but not whether it survives alongside the others:

```bash
python3 retrieval_bias/analyze_recall_logistic_regression.py
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
`logistic_regression_results.json` and printed as a coefficient table with
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
recall"), reading `logistic_regression_results.json` rather than refitting
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
targeted search. See `unresolved_candidate_fabrication_check.csv` for the
per-entry queries, best matches, and verdicts.

**`identity_issue` is never used to filter or exclude a citation anywhere in
this codebase.** Only the demo builder reads it downstream: `study_rows()`
renders an amber outline and tooltip on affected retrieval-matrix cells, and
`build_citation_issue_summary()` aggregates the reporting count by review.
Every recall percentage, Venn panel, citations-per-answer result,
replicate-consistency Jaccard, characteristic row, and regression is built
from `ground_truth_status` alone and gives a flagged citation the same credit
as a clean one when it resolves to the correct study.
