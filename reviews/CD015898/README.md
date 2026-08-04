# CD015898 user-role experiment

This folder contains a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about red-blood-cell
volume per transfusion. The experiment is based on Cochrane review CD015898,
*Larger versus smaller red blood cell volume per transfusion in hospitalized
adults, children and preterm neonates*.

- Clinical question: larger versus smaller red-blood-cell volumes per
  transfusion in hospitalized adults, children, and preterm neonates
- Included primary-study clusters: 12
- Source review: [`CD015898.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015898.pdf)
- Source data: [`CD015898-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015898-SUP-07-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a patient who may need a red blood cell transfusion.
>
> I’m trying to understand the benefits and harms of giving a larger or smaller
> amount of red blood cells during each transfusion to hospital patients of any
> age. Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for hospital patients who need red blood cell
> transfusions.
>
> I’m trying to understand the benefits and harms of giving a larger or smaller
> amount of red blood cells during each transfusion to hospital patients of any
> age. Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying red blood cell transfusions in
> hospital patients.
>
> I’m trying to understand the benefits and harms of giving a larger or smaller
> amount of red blood cells during each transfusion to hospital patients of any
> age. Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
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
python3 retrieval_bias/CD015898/analyze_cd015898_roles.py
```

The script validates all 36 response files and writes
`cd015898_role_study_matches.csv`. Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, a citation-link
definition, a search preamble, or a caveat is retained once per response.
Terminal reference lists help resolve identity but do not define the retrieval
boundary. Generic unnamed studies and secondary sources mentioned only as
context are not counted.

Multiple reports from the same trial are represented by one study-cluster
candidate. This grouping includes the Chantepie 2023 protocol, conference
abstract, and full report; the SMaRT registration and Hamm 2021 publication;
the von Lindern follow-up to Khodabux 2009; TRACT reports, including George
2022; and the ENSURE/de Lil/Bosch reports. Threshold trials named only to
distinguish transfusion trigger from transfusion dose are retained as out-of-set
primary studies because the complete response explicitly identifies them.

Candidate studies are classified as Cochrane included, Cochrane excluded,
Cochrane ongoing, or outside the Cochrane set. Cochrane labels are validated
directly against the corresponding RIS exports in the source data-package ZIP.
The package has no awaiting-classification RIS export. Its included RIS contains
12 unique study labels, and all 12 were retrieved in at least one response.
Citation conflicts and uncertain identities remain visible through identity
flags and notes.

### Initial results

The 36 responses produce 390 response-study rows: 187 Cochrane-included
matches, 40 Cochrane-excluded matches, and 163 out-of-set primary-study
matches. No ongoing source-review study was retrieved. Mean recall uses the 12
included Cochrane study clusters as the denominator for each response. Pooled
coverage is the union across the four runs in one model-role cell.

| Model | Role | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude | Patient | 35 | 9 | 18.8% | 7/12 |
| Claude | Clinician | 44 | 16 | 33.3% | 6/12 |
| Claude | Researcher | 52 | 14 | 29.2% | 5/12 |
| Gemini | Patient | 14 | 0 | 0.0% | 0/12 |
| Gemini | Clinician | 13 | 10 | 20.8% | 5/12 |
| Gemini | Researcher | 11 | 9 | 18.8% | 3/12 |
| GPT | Patient | 73 | 46 | 95.8% | 12/12 |
| GPT | Clinician | 73 | 41 | 85.4% | 11/12 |
| GPT | Researcher | 75 | 42 | 87.5% | 11/12 |

Across all 12 runs for each model, Claude averages 27.1% included-study recall,
Gemini averages 13.2%, and GPT averages 89.6%. The role ordering is not
consistent across models: clinician is highest for Claude and Gemini, whereas
patient is highest for GPT. The Gemini patient condition retrieves no included
study, while GPT patient retrieves 46 of 48 possible included-study matches.
With only four repetitions per cell, these differences are descriptive rather
than evidence of a general role effect.

`Lamarche 2019` is least frequently retrieved, appearing in two responses.
`Byun 2023` appears in nine, and `Khodabux 2009` in 10. The most frequently
retrieved included studies are `Berger 2011` (27 responses), `Hamm 2021` (23),
and `Bowman 2019` and `Chantepie 2023` (22 each). Sixteen rows have conflicting
or uncertain citation details and are marked with `identity_issue=1`.
