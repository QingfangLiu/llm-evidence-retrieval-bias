# Review-source evidence visible in saved responses

This audit addresses the possibility that a chatbot found a Cochrane review
and used its included-studies list instead of finding each primary study
independently. It uses only the 720 saved final answers (20 reviews, three
chatbots, three user roles, four repetitions). The repository does not contain
the interface search histories, returned result lists, or opened-page logs.
Consequently, the audit measures statements and references visible in final
answers. A response with no detected indication cannot establish that the
chatbot did not encounter or consult a review.

## Files and regeneration

`scripts/audit_review_use.py` validates the 720-answer inventory and screens
each answer locally for Cochrane names/identifiers and phrases suggesting
review-source use. Run it from the repository root:

```bash
python3 scripts/audit_review_use.py
```

The script writes `data/analysis/review_use_screen.csv`, one row per flagged
passage, with the source response and line number. All 102 flagged responses
were adjudicated in `data/curation/review_use_decisions.csv`; that file holds
one decision per flagged response. Its evidence line is checked against the
current screen and source file. A generic exclusion statement, a mention of
Cochrane CENTRAL as a database, or a discussion of a non-Cochrane review alone
does not establish Cochrane review lookup or use.

After reviewing or editing decisions, run:

```bash
python3 scripts/audit_review_use.py --finalize
```

This writes `data/analysis/review_use_audit.csv`, one row per saved answer,
and `data/analysis/review_use_by_system.csv`. The latter uses 240 responses
per chatbot as its denominator. Files without a screening cue receive
`not_applicable` / `no_detected` by rule, with `coding=screen_default`;
flagged responses are coded from the decision file. The detailed manual codes
remain in that file as `identity_detail` and `evidence_detail`; the script
groups them into the simpler `identity` and `evidence_level` fields in both
generated outputs. The audit does not read study-match tables or recalculate
recall.

## Coding rules

The generated `identity` field groups the detailed review-identity decisions:

- `matching_2026_cochrane`: the answer identifies or plausibly describes a
  2026 Cochrane review matching the reference topic. It combines the original
  `confirmed_target_2026` and `probable_target_2026` decisions; the label does
  not assert that the page was opened.
- `older_or_unspecified_cochrane`: the answer identifies an older review or
  mentions a Cochrane review whose edition is unclear. It combines
  `named_prior` and `unspecified_cochrane`. A review ID alone does not
  establish the 2026 edition because updates can retain the same ID.
- `not_applicable`: no usable Cochrane-review signal was detected.

The generated `evidence_level` field addresses the study-list concern:

- `used_study_identification`: the answer says it used a review or its
  bibliography to find, identify, or verify primary studies.
- `review_mentioned`: a Cochrane review is referred to, but the answer does
  not explicitly say it used that review to identify studies. This groups
  the original `used_review_information`, `reported_hit`, and `mention_only`
  judgments, including statements that a review surfaced in search or supplied
  other information.
- `no_detected`: the screen/adjudication found no usable Cochrane-review
  signal. This is not evidence of non-use.

Each answer still has one identity and one evidence level, with explicit
study-identification use taking precedence over other mentions. The `note`
field and detailed curation columns preserve the distinctions lost in the
grouped labels. When one answer discusses several reviews or versions, this
response-level pair can collapse them; it does not establish which specific
review supplied any particular study citation.

## Interpretation

The system-level counts are lower bounds on what the final answers visibly
disclose. They are not frequencies of actual Cochrane Library hits or page
visits. The detailed curation records earlier versions and uncertain editions,
while the generated summaries use the broader groups above. No sensitivity
analysis or new recall calculation is part of this audit.
