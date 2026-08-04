# CD016085 user-role experiment

This folder contains a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about blood-pressure
management after reperfusion treatment for ischemic stroke. The experiment is
based on Cochrane review CD016085, *Blood pressure management in reperfused
ischemic stroke*.

- Clinical question: intensive versus conventional systolic blood-pressure
  targets after reperfusion treatment for ischemic stroke
- Included primary-study clusters: 9
- Source review: [`CD016085.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD016085.pdf)
- Source data: [`CD016085-SUP-08-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD016085-SUP-08-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’ve had an ischemic stroke and received treatment to reopen a blocked artery
> in my brain.
>
> I’m trying to understand the benefits and risks of lowering blood pressure
> more intensively compared with standard blood pressure control after treatment
> to restore blood flow following a stroke. Find individual primary studies on
> this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for people who have received treatment to reopen a
> blocked brain artery after an ischemic stroke.
>
> I’m trying to understand the benefits and risks of lowering blood pressure
> more intensively compared with standard blood pressure control after treatment
> to restore blood flow following a stroke. Find individual primary studies on
> this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying blood pressure control after
> treatment to restore blood flow following an ischemic stroke.
>
> I’m trying to understand the benefits and risks of lowering blood pressure
> more intensively compared with standard blood pressure control after treatment
> to restore blood flow following a stroke. Find individual primary studies on
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
python3 retrieval_bias/CD016085/analyze_cd016085_roles.py
```

The script validates all 36 response files and writes
`cd016085_role_study_matches.csv`. Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, a citation-link
definition, a search preamble, or a caveat is retained once per response.
Terminal reference lists help resolve identity but do not define the retrieval
boundary. Generic unnamed studies and secondary sources mentioned only as
context are not counted. Multiple reports from the same trial, including the
OPTIMAL-BP one-year report, are represented by one study-cluster candidate.

Candidate studies are classified as Cochrane included, excluded, awaiting
classification, ongoing, outside the Cochrane set, or unresolved. Cochrane
labels are validated directly against the corresponding RIS exports in the
source data-package ZIP. The included RIS contains nine study labels. Across
the 36 responses, eight included study clusters were retrieved at least once;
`Avidzba 2024` was never retrieved.

DETECT is counted from the original randomized component of its combined
feasibility-trial and meta-analysis publication. The match table retains HOPE's
source-package classification as ongoing even when a response cites its June
2026 primary-results publication. Citation conflicts and uncertain identities
remain visible through identity flags and notes.

### Initial results

The 36 responses produce 231 response-study rows: 199 Cochrane-included
matches, three Cochrane-excluded matches, five awaiting-classification matches,
17 Cochrane-ongoing matches, and seven out-of-set primary-study matches. Mean
recall uses the nine included Cochrane study clusters as the denominator for
each response. Pooled coverage is the union across the four runs in one
model-role cell.

| Model | Role | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude | Patient | 28 | 24 | 66.7% | 7/9 |
| Claude | Clinician | 30 | 22 | 61.1% | 7/9 |
| Claude | Researcher | 29 | 22 | 61.1% | 8/9 |
| Gemini | Patient | 14 | 14 | 38.9% | 5/9 |
| Gemini | Clinician | 16 | 16 | 44.4% | 4/9 |
| Gemini | Researcher | 16 | 16 | 44.4% | 5/9 |
| GPT | Patient | 33 | 29 | 80.6% | 8/9 |
| GPT | Clinician | 32 | 28 | 77.8% | 7/9 |
| GPT | Researcher | 33 | 28 | 77.8% | 7/9 |

Across all 12 runs for each model, Claude averages 63.0% included-study recall,
Gemini averages 42.6%, and GPT averages 78.7%. Within-model role differences
are small and inconsistent: the patient role is highest for Claude and GPT,
while the clinician and researcher roles are tied above the patient role for
Gemini. With only four repetitions per cell, these differences are descriptive
rather than evidence of a general role effect.

ENCHANTED2/MT and OPTIMAL-BP appear in all 36 responses. The least frequently
retrieved included clusters are CLEVER (three responses), IDENTIFY (17), and
DETECT (18). Four rows have conflicting or uncertain citation details and are
marked with `identity_issue=1`.
