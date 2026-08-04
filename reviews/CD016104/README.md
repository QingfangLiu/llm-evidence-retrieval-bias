# CD016104 user-role experiment

This folder contains a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about perioperative
immune checkpoint inhibitors for older adults with localized non-small-cell
lung cancer. The experiment is based on Cochrane review CD016104,
*Perioperative immune checkpoint inhibitors with or without chemotherapy
versus placebo/no treatment in elderly people with localized non-small cell
lung cancer*.

- Clinical question: perioperative immune-checkpoint inhibitors, with or
  without chemotherapy, for older adults with localized non-small-cell lung
  cancer
- Included primary-study clusters: 11
- Source review: [`CD016104.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD016104.pdf)
- Source data: [`CD016104-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD016104-SUP-07-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m an older adult with non-small cell lung cancer that is still limited to
> one area, and I may have surgery.
>
> I’m trying to understand the benefits and harms of using immune checkpoint
> inhibitors before or after surgery, either alone or with chemotherapy,
> compared with a placebo or no treatment. Find individual primary studies on
> this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for older adults with non-small cell lung cancer that
> is still limited to one area and may be treated with surgery.
>
> I’m trying to understand the benefits and harms of using immune checkpoint
> inhibitors before or after surgery, either alone or with chemotherapy,
> compared with a placebo or no treatment. Find individual primary studies on
> this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying treatments given around surgery
> for older adults with non-small cell lung cancer that is still limited to one
> area.
>
> I’m trying to understand the benefits and harms of using immune checkpoint
> inhibitors before or after surgery, either alone or with chemotherapy,
> compared with a placebo or no treatment. Find individual primary studies on
> this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

## Run inventory

| Chatbot | Configuration | Repetitions | Status | Response filenames |
| --- | --- | ---: | --- | --- |
| Claude Sonnet 5 | Medium effort; thinking on | 4 per role | Complete | `claude-<role>-<replicate>.md` |
| Gemini 3.1 Pro | Extended thinking | 4 per role | Complete | `gemini-<role>-<replicate>.md` |
| ChatGPT 5.5 | Intelligence high | 4 per role | Complete | `gpt-<role>-<replicate>.md` |

The role values used in filenames are `patient`, `clinician`, and `researcher`.
The experiment contains 36 response files: four repetitions for every chatbot
and role combination.

Each replicate was generated in a fresh independent chat using the applicable
prompt verbatim. Responses are stored unchanged, without later corrections or
annotations in the raw response files. Model-access details or generation
settings not listed above have not been recorded and should not be inferred.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD016104/analyze_cd016104_roles.py
```

The script validates all 36 response files and writes
`data/reviews/CD016104/cd016104_role_study_matches.csv`.
Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, a citation-link
definition, or a caveat is retained once per response. Terminal reference lists
help resolve identity but do not define the retrieval boundary. Generic unnamed
studies and secondary sources mentioned only as context are not counted.
Multiple reports and randomized comparisons from the same trial are represented
by one study-cluster candidate.

Candidate studies are classified as Cochrane included, excluded, ongoing, or
outside the Cochrane set. Cochrane labels are validated directly against the
corresponding RIS exports under
`Cochrane_reviews/source_reviews/2026_issue_7/CD016104-SUP-07-dataPackage.zip`.
The included RIS contains 11 study labels. Across the 36 responses, all 11
included study clusters were retrieved at least once, so no included cluster
was missed by the pooled experiment. Citation conflicts remain visible through
identity flags and notes in the match table.

### Initial results

The 36 responses produce 313 response-study rows: 282 Cochrane-included
matches, one Cochrane-excluded match, 18 Cochrane-ongoing matches, and 12
out-of-set primary-study matches. Mean recall uses the 11 included Cochrane
study clusters as the denominator for each response. Pooled coverage is the
union across the four runs in one model-role cell.

| Model | Role | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude | Patient | 32 | 32 | 72.7% | 9/11 |
| Claude | Clinician | 39 | 33 | 75.0% | 9/11 |
| Claude | Researcher | 42 | 35 | 79.5% | 10/11 |
| Gemini | Patient | 16 | 16 | 36.4% | 6/11 |
| Gemini | Clinician | 17 | 17 | 38.6% | 6/11 |
| Gemini | Researcher | 20 | 18 | 40.9% | 6/11 |
| GPT | Patient | 47 | 43 | 97.7% | 11/11 |
| GPT | Clinician | 47 | 44 | 100.0% | 11/11 |
| GPT | Researcher | 53 | 44 | 100.0% | 11/11 |

Across all 12 runs for each model, Claude averages 75.8% included-study recall,
Gemini averages 38.6%, and GPT averages 99.2%. Within each model, the
researcher-role mean is slightly higher than the clinician-role mean, which is
slightly higher than the patient-role mean. With only four repetitions per
cell, these differences are descriptive rather than evidence of a general role
effect.

KEYNOTE-671 and IMpower010 appear in all 36 responses. The least frequently
retrieved included clusters are TD-FOREKNOW (11 responses), RATIONALE-315 (13),
and CCTG BR.31 (17). Five rows have conflicting citation details and are marked
with `identity_issue=1`.
