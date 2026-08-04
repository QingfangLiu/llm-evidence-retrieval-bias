# CD015934 user-role experiment

This folder contains a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about smoking-cessation
programmes started in inpatient psychiatry settings. The experiment is based on
Cochrane review CD015934, *Interventions for smoking cessation in inpatient
psychiatry settings*.

- Clinical question: smoking-cessation interventions for adults receiving
  inpatient psychiatric care
- Included primary-study clusters: 10
- Source review: [`CD015934.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015934.pdf)
- Source data: [`CD015934-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015934-SUP-07-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I smoke and I’m being treated in a hospital psychiatry ward for a mental
> illness.
>
> I’m trying to understand whether quit-smoking programmes started in hospital
> psychiatry wards help adults being treated for mental illness stop smoking.
> Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines, or
> editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for adults who smoke while they are being treated in a
> hospital psychiatry ward.
>
> I’m trying to understand whether quit-smoking programmes started in hospital
> psychiatry wards help adults being treated for mental illness stop smoking.
> Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines, or
> editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying quit-smoking programmes started
> while adults are being treated in hospital psychiatry wards.
>
> I’m trying to understand whether quit-smoking programmes started in hospital
> psychiatry wards help adults being treated for mental illness stop smoking.
> Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines, or
> editorials/comments.
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
python3 retrieval_bias/CD015934/analyze_cd015934_roles.py
```

The script validates all 36 response files and writes
`cd015934_role_study_matches.csv`. Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, a citation-link
definition, or a caveat is retained once per response. Terminal reference lists
help resolve identity but do not define the retrieval boundary. Generic unnamed
studies and secondary sources mentioned only as context are not counted.
Multiple reports from the same trial are represented by one study-cluster
candidate.

Candidate studies are classified as Cochrane included, excluded, ongoing,
outside the Cochrane set, or unresolved. Cochrane labels are validated directly
against the corresponding RIS exports under
`Cochrane_reviews/source_reviews/2026_issue_7/CD015934-SUP-07-dataPackage.zip`.
The included RIS contains 10 study labels. Across the 36 responses, all 10
included study clusters were retrieved at least once, so no included cluster
was missed by the pooled experiment. Citation conflicts and uncertain
identities remain visible through identity flags and notes in the match table.

### Initial results

The 36 responses produce 280 response-study rows: 189 Cochrane-included
matches, 27 Cochrane-excluded matches, 17 Cochrane-ongoing matches, 44
out-of-set primary-study matches, and three unresolved citations. Mean recall
uses the 10 included Cochrane study clusters as the denominator for each
response. Pooled coverage is the union across the four runs in one model-role
cell.

| Model | Role | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude | Patient | 32 | 16 | 40.0% | 5/10 |
| Claude | Clinician | 37 | 15 | 37.5% | 4/10 |
| Claude | Researcher | 39 | 16 | 40.0% | 5/10 |
| Gemini | Patient | 10 | 10 | 25.0% | 4/10 |
| Gemini | Clinician | 12 | 9 | 22.5% | 3/10 |
| Gemini | Researcher | 10 | 9 | 22.5% | 3/10 |
| GPT | Patient | 42 | 39 | 97.5% | 10/10 |
| GPT | Clinician | 48 | 38 | 95.0% | 10/10 |
| GPT | Researcher | 50 | 37 | 92.5% | 10/10 |

Across all 12 runs for each model, Claude averages 39.2% included-study recall,
Gemini averages 23.3%, and GPT averages 95.0%. Patient-role recall is equal to
or slightly higher than the other roles within each model, but with only four
repetitions per cell these differences are descriptive rather than evidence of
a general role effect.

Prochaska 2014 appears in all 36 responses. The least frequently retrieved
included clusters are Chan 2020 (six responses), Akbarpour 2010 and Chen 2013
(12 each), and Gelkopf 2012 and Tavakoli-Ardakani 2023 (13 each). Nineteen rows
have conflicting or corrected citation details and are marked with
`identity_issue=1`; three citations remain unresolved.
