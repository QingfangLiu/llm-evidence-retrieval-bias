# Retrieval-bias paper figures

Run from the repository root:

```bash
MPLCONFIGDIR=/private/tmp/retrieval-bias-matplotlib \
XDG_CACHE_HOME=/private/tmp/retrieval-bias-cache \
  python3 figures/make_paper_figures.py
```

The script writes each figure in editable vector and high-resolution raster
formats.

Figure 1:

- `figure_1_retrieval_recall_by_chatbot_and_role.pdf`
- `figure_1_retrieval_recall_by_chatbot_and_role.svg`
- `figure_1_retrieval_recall_by_chatbot_and_role.png` (600 dpi)

Figure 2:

- `figure_2_study_overlap.pdf`
- `figure_2_study_overlap.svg`
- `figure_2_study_overlap.png` (600 dpi)

Figure 3:

- `figure_3_cited_excluded_reasons.pdf`
- `figure_3_cited_excluded_reasons.svg`
- `figure_3_cited_excluded_reasons.png` (600 dpi)

Figure 4:

- `figure_4_candidate_status_composition.pdf`
- `figure_4_candidate_status_composition.svg`
- `figure_4_candidate_status_composition.png` (600 dpi)

Figure 5:

- `figure_5_proportional_venn_overlap.pdf`
- `figure_5_proportional_venn_overlap.svg`
- `figure_5_proportional_venn_overlap.png` (600 dpi)

Figure 1 reads the marginal mean response-level recall from the current
`retrieval_bias_demo/data.js` artifact. It validates the stored means and sample
SDs against response-level recall reconstructed from the 20 committed
`*_role_study_matches.csv` tables. A grayscale 3 × 3 heatmap with square cells
shows the mean response-level recall for each chatbot–user-role combination.
The chatbot marginal means are aligned above the heatmap columns, and the
user-role marginal means are aligned as horizontal bars beside the heatmap
rows. The top-right panel reads `role_consistency_jaccard.csv` and shows the
included-study replicate-consistency marginals: mean pairwise Jaccard
similarity across the four replicate responses in each review, chatbot, and
user-role cell, summarized separately by chatbot and user role. Its error bars
are percentile 95% review-clustered bootstrap confidence intervals using the
same fixed review resampling scheme as the recall margins.

Marginal error bars are percentile 95% review-clustered bootstrap confidence
intervals. Each of 50,000 fixed-seed bootstrap samples resamples the 20 reviews
with replacement and retains all responses within every sampled review. The
interval endpoints are the 2.5th and 97.5th percentiles of the resulting
marginal means. The fixed random seed is `20260727`.

The pairwise brackets use two-sided blocked permutation tests. Chatbot labels
are permuted within each review-by-role block, and role labels are permuted
within each review-by-chatbot block. Every permutation preserves four
responses per compared group. Each pair uses 50,000 permutations, and the
three p-values within each marginal dimension are adjusted using Holm's
method.

Figure 2 reads the four cross-review included- and excluded-study overlap
panels from the same demo artifact and renders them as UpSet plots by chatbot
and user role. Each panel includes all seven non-empty three-set intersections,
the three marginal set sizes and recall percentages, and the known-universe
complement. The excluded-study not-cited bars are truncated with break marks
so the smaller intersection counts remain legible; their labels report the
full count of 789 studies not cited by any chatbot or role.

Figure 3 reads `cited_excluded_reason_counts.csv` and
`cited_excluded_study_reason_audit.csv`. It ranks the non-mutually-exclusive
reason categories by their unique cited excluded study count and prints both
the count and percentage of the 142-study denominator. For each category, it
selects up to three studies with the largest `response_study_mentions` value;
ties are resolved by review ID and study label. The concise display wording is
kept separately in `figure_3_example_annotations.csv`. The figure build
validates that this file covers exactly the deterministically selected studies,
with no missing or stale annotations.

Figure 4 reads all 20 curated `*_role_study_matches.csv` tables and assigns
each distinct response-study match to one mutually exclusive category:
`included`, `cochrane_excluded`, or other. Other combines every remaining
status, including Cochrane ongoing or awaiting-classification studies,
out-of-set studies, and unresolved studies. The plotted estimand is the
mean within-response proportion, so each of the 720 chatbot responses receives
equal weight rather than allowing responses with longer study lists to
dominate. Panels show the overall composition and breakdowns by chatbot, user
role. Bar length encodes each group's mean number of studies per response
on one shared scale across all three panels, so composition (segment color)
and retrieval volume (bar length) are both visible in the same bars. Segments
too narrow to hold an inside percentage label are instead named in the row's
trailing annotation, alongside the number of responses and mean studies
per response.

Figure 5 reads the same four cross-review overlap panels as Figure 2 but
renders them as three-set Venn diagrams. Circle areas are proportional within
each panel to the number of studies cited by each chatbot or role; Venn-region
labels report the exact study counts from the demo artifact. The geometry is
therefore a proportional set-size display with exact count labels, not an
area-exact encoding of every intersection. Each region label is placed at the
geometric centroid of its region, computed by dense grid sampling over the
panel's actual (variably sized) circles, so labels stay inside their region
regardless of how unevenly the three circles are sized. The bounding box
around each panel's circles denotes the full benchmark study count (the N
reported in the panel subtitle). Each panel's summary column lists the
per-chatbot or per-role cited counts under a "Studies cited (of N)" header,
where N is that same full benchmark count; this is a different denominator
from the overlap percentages below it. That second block, headed "Overlap (%
of N cited)", reports the three-way Jaccard index (intersection over union)
and all three pairwise Jaccard indices, computed from the same region counts
shown in the diagram. The header states the three-way union count, which is
the three-way index's denominator; each pairwise index instead uses that
pair's own two-set union.
