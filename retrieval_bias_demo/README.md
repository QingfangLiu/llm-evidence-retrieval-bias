# Retrieval Bias Demo

Static study-by-condition views for all 20 balanced chatbot retrieval-bias
audits registered in `llm_evidence_retrieval_bias/review_registry.py`, plus an automatically
generated cross-review summary. The review header switches with the selected
view.

## Build

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
python3 scripts/fetch_citation_counts.py  # network; only needed to refresh citation counts
python3 scripts/analyze_recall_by_characteristic.py
python3 scripts/analyze_recall_logistic_regression.py
python3 scripts/analyze_role_dependence_logistic_regression.py
python3 retrieval_bias_demo/build_demo.py
```

`scripts/fetch_citation_counts.py` makes live PubMed/Semantic Scholar calls and
writes `citation_counts_by_study.csv`, which
`scripts/analyze_recall_by_characteristic.py` requires to exist. It has its own
cache and does not need to be rerun on every build - only when you want
fresher citation counts. Its output also includes `is_open_access`
(Semantic Scholar's open-access flag for the same best-matched PMID
citation counts use), feeding the "Open access by recall pattern" section
below.

`scripts/analyze_recall_logistic_regression.py` requires
`recall_pattern_by_characteristic.csv` (written by
`scripts/analyze_recall_by_characteristic.py`, run just before it) and writes
`logistic_regression_results.json`, which `build_demo.py`
reads to render the "Multiple logistic regression on recall" table.

`scripts/analyze_role_dependence_logistic_regression.py` reads the same
`recall_pattern_by_characteristic.csv` and writes
`role_dependence_logistic_regression_results.json`, which
`build_demo.py` reads to render the "Multiple logistic regression on role
dependence" table - the same model refit on the two role-universality groups
described below instead of on recalled-vs-not.

The analysis commands validate the curated response annotations and rewrite
their respective match tables. For every entry in
`llm_evidence_retrieval_bias/review_registry.py`, the demo builder reads the review's match
table, README, included RIS, excluded RIS, and analysis-data rows. It also
reads:

- `recall_pattern_by_characteristic.csv` (written by
  `scripts/analyze_recall_by_characteristic.py`; feeds the "Study characteristics by
  recall pattern" distribution charts on the Across-reviews tab)
- `logistic_regression_results.json` (written by
  `scripts/analyze_recall_logistic_regression.py`; feeds the "Multiple logistic
  regression on recall" table on the Across-reviews tab)
- `role_dependence_logistic_regression_results.json` (written
  by `scripts/analyze_role_dependence_logistic_regression.py`; feeds the "Multiple
  logistic regression on role dependence" table on the Across-reviews tab)
Study truth for all 20 reviews is prepared directly from their RIS exports;
the demo build does not require or create benchmark JSON files. The builder
writes `retrieval_bias_demo/data.js`, and the browser only renders this prepared
data. The same build automatically recalculates the `Across reviews` tab from
the registry; cross-review values are not entered manually.

CD007654, CD012161, and CD012751 define retrieved studies only from each response's
dedicated final primary-study or reference-list block, as documented in their
experiment READMEs. The other reviews retain their existing response-level
study-identification rules; the demo does not re-extract candidates from raw
answers.

## View

From the repository root:

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/retrieval_bias_demo/
```

The **Across reviews** tab summarizes all 20 balanced experiments (720
responses, 442 included study labels, and 932 excluded study labels). Citation
tables report the mean and sample SD of unique response-study rows per answer
for each chatbot and role, including included, excluded, and out-of-set studies.
The Recall across reviews section begins with overall included-study and
excluded-study recall across all 720 responses (39.2% ± 29.8% and 5.0% ±
9.4%, respectively), computed during the build rather than entered in the
frontend. Its chatbot and role tables then report included-study recall after
normalizing every answer by its review's included-study denominator. All SDs
describe answer-to-answer variability across reviews and use the `n - 1`
denominator. The overview reports the common answer count shared by every
chatbot and role group. All four summaries include horizontal bars for the
means; the two citation plots share a scale, while both recall plots use 0–100%.

The **Across reviews** tab also reports replicate consistency: for every review
× chatbot × role cell, the pairwise Jaccard similarity of retrieved-study sets
is averaged across the cell's six replicate pairs (four replicates), then that
cell-level score is pooled by chatbot and by role across all 20 reviews and
summarized as mean ± sample SD. Two scopes are shown — every named candidate
citation regardless of Cochrane status, and candidates matched to a
Cochrane-included study label only — using the same 0–100% bar scale as the
recall tables. Two empty replicate sets count as fully consistent (Jaccard
1.0) rather than as maximal disagreement. The reusable
`calculate_replicate_consistency` implementation lives in
`retrieval_bias_demo/overlap_metrics.py` alongside the other overlap metrics.

The two recall comparisons use omnibus blocked permutation tests with the range
of the three group means as the statistic. Chatbot labels are shuffled within
each review-by-role block, and role labels are shuffled within each
review-by-chatbot block. Each shuffle retains four answers per label. The tab
reports the group means, observed range, and permutation p-value without
pairwise post-hoc comparisons.

The cross-review Venn panels pool review-namespaced included-study labels, so
identical labels from different reviews cannot merge. Their lower-tail p-values
test whether the observed three-way Jaccard is below the balanced
label-permutation null. The chatbot and role tests use the same review-specific
blocks as the recall analyses. A result is labeled significantly below the null
when the lower-tail p-value is less than 0.05.

Below the aggregated main-effect panels, the **Across reviews** tab also shows
two stratified post-hoc panel groups. **Role overlap by chatbot** holds one
panel per chatbot, comparing patient, clinician, and researcher using only
that chatbot's responses aggregated across all 20 reviews (80 answers per
set); its blocked permutation shuffles role labels within each review's block
for that chatbot alone. **Chatbot overlap by role** is the reverse: one panel
per role, comparing Claude, Gemini, and ChatGPT using only that role's
responses aggregated across all 20 reviews (80 answers per set), with
chatbot labels shuffled within each review's block for that role alone. Both
groups reuse the same review-namespaced included-study pooling, Venn
rendering, and lower-tail permutation test as the main-effect panels, and
leave the main-effect numbers unchanged.

The eight included-only cross-review Venn panels (the two main-effect panels
and all six post-hoc panels) also report a recall-difference test, distinct from the
Jaccard-overlap test above it: the same blocked mean-range permutation test
used in the recall comparison tables ("Recall difference at p<0.05", the
observed range between the panel's set means, and the blocked permutation
p-value). For the two main-effect panels this is the same test already
reported in the recall tables higher up the tab. For the six post-hoc panels
it is new: each one is restricted to that panel's own responses (one
chatbot's three roles, or one role's three chatbots) and blocked by review
only, since there is no other condition left to block on once the panel's
own stratification is fixed. Review pages do not compute this test - only
the cross-review tab has enough reviews to block on.

Below the main-effect panels, the **Across reviews** tab also shows the same
two main-effect comparisons (Chatbot, User role) over two different
universes. **Aggregated main effects — Cochrane excluded studies** repeats
the included-only analysis exactly, but pools each response's Cochrane
*excluded*-study matches instead of its included-study matches, against a
fixed denominator of every excluded study across all 20 reviews (932).
Recall is far lower here (chatbots rarely name a study Cochrane rejected)
but the same Jaccard-overlap and recall-difference tests apply, since there
is a fixed external population to test against, exactly as for included
studies. **Aggregated main effects — all named candidates** instead pools
every study any response named at all, regardless of Cochrane status
(included, excluded, or out-of-set) - the same `canonical_candidate`
identity already used for the "Replicate consistency — all candidates"
metric, so a study is matched consistently across chatbots and reviews even
when it falls outside Cochrane's included/excluded lists. This universe has
no size independent of the panels being compared (there is no external "how
many candidates exist" figure the way there is for Cochrane's 442 included
or 932 excluded studies), so each set's rate is labeled "Share" rather than
"Recall" and is computed against the panel's own pooled union, and there is
no "not recalled"/outside-circle region or surrounding outer-circle frame
(nothing is excluded from a union by construction, so a boundary implying
one would be misleading) and no recall-difference test (there is no fixed
population to test a recall rate against). Both new panel groups still
report the Jaccard-overlap permutation test. Neither is computed on review
pages or extended to the post-hoc panels - only the two main effects, on the
cross-review tab, per the original request.

On each review page, two main-effect panels appear first. The chatbot panel
compares Claude, Gemini, and ChatGPT after aggregating across all three roles,
so each set represents 12 answers. The user-role panel compares patient,
clinician, and researcher after aggregating across all three chatbots, so
each set represents 12 answers. Three exploratory post-hoc panels then retain the
model-stratified role comparisons, with four answers per role set. These are
descriptive retrieval-overlap comparisons rather than causal effect estimates.
The retrieval table shows all four responses for every chatbot and role condition.

All review pages use the same chatbot order: Claude, Gemini, then ChatGPT.
Exact model labels and recorded settings are loaded from each experiment
README; the demo preserves "Not recorded" for experiments whose model version
or settings were not documented.

Each legend reports aggregate recall as the set's distinct recalled
included-study labels. The source denominators are: CD000510 10, CD001452 8,
CD005354 59, CD007654 8, CD007912 18, CD009532 38, CD009958 13, CD010051 58,
CD010461 5, CD012161 15, CD012751 94, CD013776 17, CD015136 21, CD015156 10,
CD015186 10, CD015264 16, CD015898 12, CD015934 10, CD016085 9, and CD016104
11. CD009958's total comprises 11 clinical trials and two economic substudies
represented as separate labels in the included RIS. CD012751 can credit
multiple included labels to one retrieved study cluster when the review
separates induction, non-responder, or maintenance populations. The outer
circle represents the full benchmark set. The count outside the inner circles
reports included studies not recalled by any contributing condition. Each
panel's multi-set Jaccard divides studies shared by every set by their union.
Counts and memberships come from the match annotations; circle areas are
schematic rather than proportional.

Each Venn panel also reports a permutation null distribution generated from 50,000
balanced response-level permutations with seed `20260715`. For each role
experiment's main effects, chatbot labels are shuffled within role blocks and
role labels are shuffled within chatbot blocks. For each post-hoc panel, role
labels are shuffled within that model's 12 answers. Every permutation retains
four responses per label, and each response's included-study set moves intact.
The demo displays the observed multi-set Jaccard, permutation-null mean, and 95%
null interval.

The reusable multi-set Jaccard, balanced label-permutation, and two- and three-set
partition implementations live in `retrieval_bias_demo/overlap_metrics.py`.

The **Study characteristics by recall pattern** section, further down the
Across-reviews tab, shows box-and-whisker charts (interquartile box, median
line, whiskers to the most extreme non-outlier value, individual studies as
jittered dots) for publication year, sample size, citations per year, and
total citations, each compared two ways: studies no chatbot ever recalled
versus studies recalled by at least one, and the exact combination of
chatbot(s) that recalled each study (Claude only, GPT only, Gemini+GPT,
Claude+GPT, All three). Recall-combination groups are mutually exclusive -
unlike a per-chatbot "did this chatbot recall it at least once" grouping,
which would count a study recalled by multiple chatbots in each of their
groups. "Gemini only" and "Claude+Gemini" are omitted from the combination
panels since each has only one study in the current data (those two studies
remain in the "recalled vs. not" comparison). Sample size, citations per
year, and total citations all use a log-scaled axis since each spans several
orders of magnitude; a zero citations-per-year value (no defined log
position) is clamped to the left edge of that axis rather than dropped.
Citations per year and total citations are two views of the same underlying
Semantic Scholar count - the first divides by years since publication so a
study is not penalized just for being too new to have accumulated citations,
the second is the raw, unnormalized count kept alongside it rather than
instead of it, since the two measures can disagree (see
`README.md` for a concrete example). All four metrics and
their coverage are documented in
`scripts/analyze_recall_by_characteristic.py`; the charts render the
box-plot statistics (`characteristicDistributions` in `data.js`) that
`build_demo.py` computes from that script's output CSV.

The four "recalled vs. not" panels show a Mann-Whitney U test (not recalled
vs. recalled), since those two groups are mutually exclusive and therefore an
independent-samples test is valid. The four "by recall combination" panels
show a Kruskal-Wallis H test across all five combination groups - the
rank-based generalization of Mann-Whitney to more than two groups, valid for
the same reason (the groups no longer overlap, unlike the by-chatbot grouping
this replaced).

Below each Kruskal-Wallis result, a table lists all ten pairwise comparisons
among the five recall-combination groups (Dunn's test): mean-rank difference,
z-statistic, raw two-sided p-value, and a Bonferroni-adjusted p-value (raw p
x 10, capped at 1) with significance stars. Dunn's test pools ranks across
all five groups at once - the same ranks the omnibus Kruskal-Wallis test
itself uses - rather than re-ranking within each pair the way ten separate
Mann-Whitney tests would; the Bonferroni adjustment then controls the
family-wise error rate that running ten comparisons at an unadjusted p<0.05
would otherwise inflate. The reusable `calculate_mann_whitney_test`,
`calculate_kruskal_wallis_test`, and `calculate_dunn_posthoc_test`
implementations live alongside the other overlap/permutation metrics in
`retrieval_bias_demo/overlap_metrics.py`.

The **Open access by recall pattern** section, right below it, applies the
same two comparisons (recalled vs. not, and by recall combination) to
`is_open_access` - Semantic Scholar's open-access flag for a study's
best-matched PMID (the same one `citation_count` uses). Unlike the four
characteristics above, this is binary, so each group is shown as a rate bar
(open count / total with a known status) rather than a box plot, and the
statistical tests are the binary-outcome analogs of the ones used above:
Fisher's exact test for the two mutually exclusive recall-status groups
(instead of Mann-Whitney), and a chi-square test of independence for the
five recall-combination groups (instead of Kruskal-Wallis), followed by the
same Bonferroni-adjusted pairwise post-hoc treatment - here using pairwise
Fisher's exact tests instead of Dunn's test, since the outcome is a rate,
not a rank. The reusable `calculate_fisher_exact_test`,
`calculate_chi_square_test`, and `calculate_fisher_posthoc_test`
implementations live alongside the other overlap/permutation metrics in
`retrieval_bias_demo/overlap_metrics.py`.

Open-access status is 45% among not-recalled studies and 56% among recalled
studies; the univariate Fisher's exact p-value is 0.077. It is also not
significant in the multiple logistic regression below once the other
predictors are controlled (see `README.md`, "Multiple
logistic regression", for the full result).

The **Predictor correlations** section, right below it, is a multicollinearity
check for four of those characteristics (design is excluded - it is
categorical, not numeric), styled after a typical R `GGally::ggpairs` plot:
a 4x4 grid with each variable's own row and column. Diagonal cells show each
recall-status group's distribution as overlaid histograms, normalized to
that group's own total so the differently-sized "Not recalled" (n=69) and
"Recalled" (n=261) groups are visually comparable. The lower triangle shows
scatter plots colored by recall status. The upper triangle shows each pair's
Spearman rank correlation as text - overall, then broken down by recall
status - with significance stars (`***` p<0.001, `**` p<0.01, `*` p<0.05,
`.` p<0.1), using the `scipy.stats.spearmanr` p-value rather than a
hand-rolled approximation. All groupings use recall status specifically
(mutually exclusive), not the overlapping by-chatbot groups used elsewhere
in this file, since a per-group correlation with double-counted studies
would be misleading.

Citations per year and total citations correlate strongly with each other
overall (rho=0.80, expected - same underlying count, one divided by years
since publication). Total citations correlate negatively with publication
year (rho=-0.23 overall and -0.27 among recalled studies), while citations
per year correlates positively with year (rho=0.32). Sample size correlates
with citations per year at rho=0.41 and with total citations at rho=0.33.

This section previously mirrored a standalone
`plot_predictor_correlations.py` script producing a plain
(non-grouped, no significance stars) 4x4 scatter matrix PNG. That script has
been removed: once the demo gained group coloring and significance testing,
maintaining a visually simpler static duplicate added no value. The
reusable `calculate_spearman_correlation` implementation (now backed by
scipy for its p-value) lives alongside `calculate_mann_whitney_test` in
`retrieval_bias_demo/overlap_metrics.py`.

The **Multiple logistic regression on recall** section, on the Across-reviews
tab, shows the coefficient table from
`scripts/analyze_recall_logistic_regression.py`: a joint
`logit(recalled) ~ year + log(sample_size) + log(citations_per_year + 0.01) +
is_open_access` model, asking whether each characteristic has an independent
effect on recall once the others are controlled for, rather than the
marginal (one-at-a-time) differences the panels above show. Each row lists the
coefficient, review-clustered standard error and p-value (clustered because
studies nest within 20 reviews), a naive (non-clustered) p-value for
comparison, the odds ratio with its 95% CI, and the Variance Inflation
Factor. The intercept's odds ratio and CI are omitted (shown as "—") since
they describe the odds at year = 0, which is not meaningful. A caption below
the table reports McFadden's pseudo R-squared, the log-likelihood, and the
likelihood-ratio test p-value against the null model. `build_demo.py` reads
the pre-computed JSON directly rather than refitting the model in the
browser - see `README.md` for the full methodology and
result interpretation.

The **Citation issues by chatbot, role, and review** section reports
`identity_issue`-flagged citations: a matched citation with conflicting
bibliographic details, almost always a wrong lead author, year, or journal on
a study that was otherwise correctly identified by its title, PMID, or PMCID.
`build_citation_issue_summary()` computes this in `build_demo.py` from each
review's already-loaded match rows (no new fetch or curation step). It now
prepares `byModel`, `byRole`, and `byModelRole` summaries before the
per-review table. Each group summary reports the row issue rate
(`flaggedCount / matchedCount`, where rows are matched response-study rows)
and the answer issue rate (`affectedAnswerCount / answerCount`, where an
answer is one review/run pair with at least one `identity_issue` row). The
per-review table lists the flagged count, the total matched response-study-row
count, the row rate, and one deterministically-chosen representative example (the
flagged row with the lexicographically smallest model/role/reported-citation,
not a hand-picked one) showing the reported citation text, the study it
actually resolves to, and the curator's note explaining the conflict - plus
an "All reviews" totals row. The section's own explanatory text states
plainly that this is misattribution, not fabrication, and that the flag is a
reporting count only - it is never used to filter or exclude a citation from
any recall, Venn, or regression number shown elsewhere in the demo or in
the analysis. See `README.md`, "Citation issues
(`identity_issue`) are not fabrication," for the full investigation,
including a dedicated check of the rarer case where a citation could not be
resolved to any study at all.

Further down the Across-reviews tab, **Study characteristics by
recall pattern (user role)** and **Open access by recall pattern (user
role)** repeat the two "by recall combination" comparisons above, but
grouped by which user role(s) - patient, clinician, researcher - recalled
each study (`role_recall_pattern`, built the same way as `recall_pattern`
but from each match row's `role_id` instead of its `model`) instead of
which chatbot(s) did. Both are computed by `scripts/analyze_recall_by_characteristic.py`
(added to the same `recall_pattern_by_characteristic.csv` join, alongside
`recalled_by_patient`/`recalled_by_clinician`/`recalled_by_researcher`) and
rendered by `build_role_characteristic_distributions()` and
`build_role_open_access_distribution()` in `build_demo.py`, reusing the same
box-plot, Kruskal-Wallis/Dunn, and chi-square/Fisher machinery as the
chatbot version above. The "recalled vs. not" comparison isn't repeated a
second time here: recall status doesn't depend on which dimension groups
it, so it's identical to the "recalled vs. not" panels already shown in the
chatbot-based sections. These panels focus on researcher contribution:
"Researcher only" (43), "Clinician+Researcher" (28),
"Patient+Researcher" (9), and "All three" (234) are shown. "Clinician only"
(8), "Patient only" (4), and "Patient+Clinician" (2) remain in the shared
"recalled vs. not" comparison but are outside this narrower question.
"All three" is the dominant role pattern by a wide margin.

The four-way researcher-focused split above remains uneven. At the end of the
Across-reviews tab, **Study characteristics
by role dependence**, **Open access by role dependence**, and **Multiple
logistic regression on role dependence** instead pool the three
non-universal groups into one comparator, turning it into a plain two-group
split:

- **Role-agnostic recall** - the study was recalled by all three roles
  (`role_recall_pattern == "All three"`, n=234).
- **Researcher-dependent recall** - the study was recalled by only some of
  the roles, from the same three retained combination groups above
  (Researcher only, Clinician+Researcher, Patient+Researcher pooled, n=80).
  Every one of those three groups includes the researcher role, so
  membership in this pooled group means at least one non-researcher role
  (patient and/or clinician) missed the study even though a researcher-role
  response found it - directly isolating what the researcher role adds
  beyond the patient and clinician roles. Studies never recalled by any
  response, and the three non-researcher-only patterns omitted from the
  combination panels above (Patient only, Clinician only, Patient+Clinician), are excluded
  from both groups here too.

In the current univariate comparisons, researcher-dependent studies have a
smaller median sample size (157 vs. 221.5; p=0.017) and fewer total citations
(43 vs. 75; p=0.005). Citations per year are borderline (4.62 vs. 6.25;
p=0.062), while publication year (p=0.85) and open access (p=1.0) do not
differ.

`ROLE_UNIVERSALITY_GROUPS` in `build_demo.py` defines the pooling;
`build_role_universality_distributions()` and
`build_role_universality_open_access()` compute a two-group Mann-Whitney U
test per characteristic and a Fisher's exact test for open access - the same
two-group machinery `build_characteristic_distributions()` and
`build_open_access_distribution()` already use for "recalled vs. not",
applied to this pooled split instead. `scripts/analyze_role_dependence_logistic_regression.py`
refits the same `logit(P) ~ year + log(sample_size) + log(citations_per_year
+ 0.01) + is_open_access` model as `scripts/analyze_recall_logistic_regression.py`
(review-clustered SEs, naive-p comparison, VIF), but on this two-group
outcome instead of recalled-vs-not: the outcome is coded 1 for
"Researcher-dependent recall," so a positive, significant coefficient means
higher values of that predictor make researcher-dependence more likely -
directly answering what claiming to be a researcher additionally unlocks.
In the current data (n=250 complete-case studies across 20 reviews), none of
the four predictors is independently significant with review-clustered
standard errors: year p=0.62, log sample size p=0.36, log citations per year
p=0.10, and open access p=0.10. The model as a whole is also not significant
against the null (likelihood-ratio p=0.185).
`renderLogisticRegressionSection()` in `app.js` is a shared renderer
parameterized by title and outcome description, reused for both the recall and
role-dependence regression tables rather than duplicated.

## Add another review

After collecting and analyzing another balanced role experiment:

1. Add its per-review folder under `reviews/` and restore its source package locally.
2. Add its ID, title, and source-package path to
   `llm_evidence_retrieval_bias/review_registry.py`.
3. Run the review analyzer and aggregate build commands above.

The individual page and cross-review citation, recall, Venn, and permutation
results are regenerated together.

The Included and Excluded tabs list the Cochrane study sets. Each matrix cell shows
the percentage of repetitions in which that study appeared for one chatbot and
condition. Model and condition headers show the average number of unique study
citations per response across their repetitions. This count includes included,
excluded, and out-of-set studies. Amber outlines flag citation-identity issues -
a matched citation with conflicting bibliographic details (almost always a wrong
lead author on an otherwise correctly-identified study; see
`README.md`, "Citation issues (`identity_issue`) are not
fabrication," for what this flag does and does not capture, current per-review
rates, and a dedicated check of the rarer, more serious "citation resolves to
no real study at all" case). This is a per-cell display flag only - hovering a
flagged cell shows the issue count in its tooltip, and the legend above the
matrix marks it. The Across-reviews citation-issue table aggregates the flag
for reporting, but it does not affect any recall, Venn, or regression number:
a citation with an identity issue still gets full credit for its underlying
study everywhere else in this demo and in the analysis.
