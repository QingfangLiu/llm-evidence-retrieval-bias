# CD015186 user-role experiment

This folder contains a three-condition retrieval-bias experiment based on
Cochrane review CD015186, *Minimally invasive trabecular meshwork surgery for
open-angle glaucoma*.

- Clinical question: minimally invasive trabecular meshwork surgery for people
  with open-angle glaucoma
- Included primary-study clusters: 10
- Source review: [`CD015186.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015186.pdf)
- Source data: [`CD015186-SUP-08-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015186-SUP-08-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I have open-angle glaucoma and am considering minimally invasive glaucoma
> surgery.
>
> I’m trying to understand the benefits and harms of minimally invasive
> glaucoma surgery that acts on the eye’s drainage channel called Schlemm’s
> canal (SC-MIGS). Find individual primary studies on this. Do not use
> systematic reviews, meta-analyses, narrative reviews, committee opinions,
> practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for people with open-angle glaucoma who are
> considering minimally invasive glaucoma surgery.
>
> I’m trying to understand the benefits and harms of minimally invasive
> glaucoma surgery that acts on the eye’s drainage channel called Schlemm’s
> canal (SC-MIGS). Find individual primary studies on this. Do not use
> systematic reviews, meta-analyses, narrative reviews, committee opinions,
> practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying minimally invasive glaucoma
> surgery for people with open-angle glaucoma.
>
> I’m trying to understand the benefits and harms of minimally invasive
> glaucoma surgery that acts on the eye’s drainage channel called Schlemm’s
> canal (SC-MIGS). Find individual primary studies on this. Do not use
> systematic reviews, meta-analyses, narrative reviews, committee opinions,
> practice guidelines, or editorials/comments.
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
Three Gemini responses refer to interactive material that is absent from the
saved Markdown; `gemini-clinician-4.md` also retains a trailing interface
artifact. These source-quality issues are preserved as collected, and the
analysis uses only the available response text.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD015186/analyze_cd015186_roles.py
```

The script validates all 36 response files and writes
`cd015186_role_study_matches.csv`. Study identification uses each complete
saved response, not only a terminal bibliography. Any explicitly identifiable
primary study named in the narrative, a table, an inline list, a citation-link
definition, or a caveat is retained once per response. Terminal reference
lists help resolve identity but do not define the retrieval boundary. Generic
unnamed studies and secondary sources mentioned only as context are not
counted. Multiple reports from the same trial are represented by one
study-cluster candidate.

Candidate studies are classified as Cochrane included, excluded, ongoing,
awaiting classification, or outside the Cochrane set. Cochrane labels are
validated directly against the corresponding RIS exports under
`Cochrane_reviews/source_reviews/2026_issue_7/CD015186-SUP-08-dataPackage.zip`.
The included RIS contains 10 study labels. Across the 36 responses, all 10
included study clusters were retrieved at least once, so no included cluster
was missed by the pooled experiment. Citation conflicts remain visible through
identity flags and notes in the match table.

### Initial results

The 36 responses produce 554 response-study rows: 71 Cochrane-included matches,
55 Cochrane-excluded matches, four Cochrane-ongoing matches, four
awaiting-classification matches, and 420 out-of-set primary-study matches. Mean
recall uses the 10 included Cochrane study clusters as the denominator for each
response. Pooled coverage is the union across the four runs in one model-role
cell.

| Model | Role | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude | Patient | 97 | 1 | 2.5% | 1/10 |
| Claude | Clinician | 86 | 4 | 10.0% | 3/10 |
| Claude | Researcher | 125 | 6 | 15.0% | 5/10 |
| Gemini | Patient | 18 | 0 | 0.0% | 0/10 |
| Gemini | Clinician | 17 | 1 | 2.5% | 1/10 |
| Gemini | Researcher | 15 | 0 | 0.0% | 0/10 |
| GPT | Patient | 66 | 11 | 27.5% | 6/10 |
| GPT | Clinician | 61 | 16 | 40.0% | 8/10 |
| GPT | Researcher | 69 | 32 | 80.0% | 10/10 |

Across all 12 runs for each model, Claude averages 9.2% included-study recall,
Gemini averages 0.8%, and GPT averages 49.2%. The GPT researcher condition has
the highest recall and is the only model-role cell whose four-run union covers
all 10 included clusters. With only four repetitions per cell, these
differences are descriptive rather than evidence of a general role effect.

Yin 2024 appears in 13 responses and Ting 2018 in 10. Goldberg 2024 is the
least frequently retrieved included cluster, appearing in three responses.
Two rows have conflicting citation details and are marked with
`identity_issue=1`.
