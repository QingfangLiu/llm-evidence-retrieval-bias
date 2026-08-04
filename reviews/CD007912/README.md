# CD007912 user-role experiment

This folder contains a three-condition retrieval-bias experiment based on
Cochrane review CD007912, *Exercise for osteoarthritis of the hip*.

- Clinical question: land-based exercise for people with hip osteoarthritis
- Included primary-study clusters: 18
- Source review: [`CD007912.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD007912.pdf)
- Source data: [`CD007912-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD007912-SUP-07-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I have hip osteoarthritis and am considering exercise to help manage it.
>
> I’m trying to understand whether land-based exercise reduces pain and
> improves joint function in adults with hip osteoarthritis. Find individual
> primary studies on this. Do not use systematic reviews, meta-analyses,
> narrative reviews, committee opinions, practice guidelines, or
> editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for adults with hip osteoarthritis who are considering
> exercise.
>
> I’m trying to understand whether land-based exercise reduces pain and
> improves joint function in adults with hip osteoarthritis. Find individual
> primary studies on this. Do not use systematic reviews, meta-analyses,
> narrative reviews, committee opinions, practice guidelines, or
> editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying land-based exercise for adults
> with hip osteoarthritis.
>
> I’m trying to understand whether land-based exercise reduces pain and
> improves joint function in adults with hip osteoarthritis. Find individual
> primary studies on this. Do not use systematic reviews, meta-analyses,
> narrative reviews, committee opinions, practice guidelines, or
> editorials/comments.
>
> List the primary studies in the end.

## Run inventory

| Chatbot | Configuration | Repetitions | Status | Response filenames |
| --- | --- | ---: | --- | --- |
| Claude | Not recorded | 4 per role | Complete | `claude-<role>-<replicate>.md` |
| Gemini | Not recorded | 4 per role | Complete | `gemini-<role>-<replicate>.md` |
| GPT | Not recorded | 4 per role | Complete | `gpt-<role>-<replicate>.md` |

The role values used in filenames are `patient`, `clinician`, and `researcher`.
The experiment contains 36 response files: four repetitions for every chatbot
and role combination. Responses are stored unchanged, without later
corrections or annotations. Model versions and generation settings were not
recorded in this folder and should not be inferred.

Two raw Claude files, `claude-clinician-1.md` and
`claude-researcher-2.md`, begin with process-like text concatenated to the
answer. Nine Claude responses explicitly report using or reconstructing
citations from reviews or other secondary sources:
`claude-clinician-1.md`, `claude-clinician-2.md`,
`claude-clinician-4.md`, `claude-patient-1.md`, `claude-patient-3.md`,
`claude-patient-4.md`, `claude-researcher-1.md`,
`claude-researcher-2.md`, and `claude-researcher-4.md`. That conflicts with
the prompt's source restriction. All planned runs remain in the primary
analysis, and the deviation is considered when interpreting Claude's recall.

## Study identification

The retrieved-study set is defined only by entries in a response's dedicated
final primary-study or reference-list block. Studies mentioned only in
narrative prose, tables, summaries, caveats, link definitions, or `Cited by:`
metadata are not counted.

For Gemini, the bibliographic line immediately preceding each `Cited by:` line
in the final reference block is one candidate. For Claude and GPT, numbered
entries under the last qualifying primary-study heading are candidates.
`claude-researcher-1.md`, `claude-researcher-3.md`, and
`claude-researcher-4.md` have no conventional final heading, so all numbered
entries in each response's cohesive study-list section are used.

Every explicitly listed candidate is retained even when it is
Cochrane-excluded, ongoing, outside the review set, an ineligible publication
type, or bibliographically inaccurate. Companion reports, protocols, and
follow-up publications belonging to one study are grouped into one cluster
within a response. Citation conflicts remain visible in the audit table.

The included RIS contains 18 study clusters but no explicit PubMed
identifiers. Recall is therefore evaluated at the Cochrane study-cluster
level. Each included source label is one study row, so included study-row
recall and cluster recall are numerically identical. PMID recall and
missed-PMID coverage cannot be computed from this source package.

## Reference data

- Source review:
  [`CD007912.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD007912.pdf)
- Source data:
  [`CD007912-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD007912-SUP-07-dataPackage.zip)

The analysis reads the included, excluded, awaiting-classification, and
ongoing RIS exports directly from the ZIP archive. The package contains 18
included, 80 excluded, nine awaiting-classification, and 10 ongoing labels.

## Analysis

Run from the repository root:

```bash
python3 retrieval_bias/CD007912/analyze_cd007912_roles.py
```

The script validates the 36-file inventory and expected terminal-list entry
counts, requires every listed citation to resolve, validates every
Cochrane-classified label against the RIS exports, and writes
`cd007912_role_study_matches.csv`. Multiple reports of one study are retained
in `reported_citation`, separated by ` || `, but the study is credited only
once per response. `identity_issue=1` marks an identifiable citation with
conflicting bibliographic details.

### Results

The 392 terminal-list entries each resolve to one candidate study. Grouping
companion reports within each response leaves 363 response-study rows.
Included matches are summed over four runs. Mean recall uses the 18 included
Cochrane study clusters as the denominator for every response. Pooled coverage
is the union across the four runs in one model-role cell.

| Model | Role | List entries | Response-study rows | Included matches over 4 runs | Mean cluster/study-row recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 42 | 35 | 21 | 29.2% | 9/18 |
| Claude | Clinician | 34 | 30 | 22 | 30.6% | 10/18 |
| Claude | Researcher | 61 | 53 | 32 | 44.4% | 13/18 |
| Gemini | Patient | 16 | 15 | 11 | 15.3% | 6/18 |
| Gemini | Clinician | 14 | 14 | 8 | 11.1% | 5/18 |
| Gemini | Researcher | 14 | 14 | 9 | 12.5% | 4/18 |
| GPT | Patient | 54 | 53 | 37 | 51.4% | 13/18 |
| GPT | Clinician | 60 | 57 | 40 | 55.6% | 14/18 |
| GPT | Researcher | 97 | 92 | 53 | 73.6% | 15/18 |

Across roles, Claude averages 34.7% included-study recall per response and
covers 13 of 18 labels when its 12 runs are pooled. Gemini averages 13.0% and
covers seven labels. GPT averages 60.2% and covers 15 labels. The union across
all 36 responses covers 15 of 18 included labels. The three clusters never
retrieved are `Sandal 2019`, `Weber 2024`, and `de Sire 2023`.

The role pattern is descriptive and differs by model. Researcher-role recall
is higher than patient-role recall by 15.2 percentage points for Claude and
22.2 points for GPT, but 2.8 points lower for Gemini. Across models, mean
researcher-role recall is 43.5%, compared with 32.4% for clinician and 31.9%
for patient responses. Researcher responses also have longer terminal lists:
172 entries versus 108 for clinician and 112 for patient responses. With four
repetitions per cell, these are retrieval-pattern descriptions, not evidence
of a general causal role effect.

The nine Claude responses that disclose review or secondary-source use account
for most Claude runs. As a limited sensitivity check, the three Claude
responses without a disclosed deviation retrieve 16 of 54 possible included
matches, for 29.6% mean recall, compared with 34.7% across all 12 Claude
responses. This check does not remove the collection-quality concern, but the
model ordering remains GPT, Claude, then Gemini.

Retrieval is concentrated in a small core. `Fernandes 2010` appears in 29
responses, `French 2013` in 26, `Krauß 2014` in 25, and `Juhakoski 2011` and
`Thompson 2020` in 21 each. At the other end, `Bendrik 2021` appears in two
responses and `Chopp-Hurley 2017` in three. The best single response retrieves
14 of 18 included clusters; the weakest retrieves one.

The audit table contains 233 included response-study rows, 76
Cochrane-excluded rows, three ongoing rows, 49 other out-of-set rows, and two
invalid-publication-type rows. No awaiting-classification or unresolved rows
remain. The invalid publication types are a systematic review listed as a
primary study and a single-patient case report. Twenty-one resolved rows have
conflicting citation details and are marked with `identity_issue=1`. PMID
recall is reported as unavailable because the RIS exports contain no explicit
PubMed IDs.
