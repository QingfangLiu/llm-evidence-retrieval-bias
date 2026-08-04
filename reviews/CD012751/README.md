# CD012751 user-role experiment

This folder is for a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about biologic and other
advanced treatments for Crohn's disease. The experiment is based on Cochrane
review CD012751, *Biologic drugs for induction and maintenance of remission in
Crohn's disease: a network meta-analysis*.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I have Crohn's disease and am considering a biologic or other advanced
> treatment.
>
> I'm trying to understand the benefits and harms of biologic or advanced
> treatments for inducing or maintaining remission in people with Crohn's
> disease. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I'm a clinician caring for people with Crohn's disease who are considering a
> biologic or other advanced treatment.
>
> I'm trying to understand the benefits and harms of biologic or advanced
> treatments for inducing or maintaining remission in people with Crohn's
> disease. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I'm an evidence-synthesis researcher studying biologic and other advanced
> treatments for Crohn's disease.
>
> I'm trying to understand the benefits and harms of biologic or advanced
> treatments for inducing or maintaining remission in people with Crohn's
> disease. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.
>
> List the primary studies in the end.

## Run inventory

| Chatbot | Configuration | Repetitions | Status | Response filenames |
| --- | --- | ---: | --- | --- |
| Claude Sonnet 5 | Medium effort; thinking on | 4 per role | Complete | `claude-<role>-<replicate>.md` |
| Gemini 3.1 Pro | Extended thinking | 4 per role | Complete | `gemini-<role>-<replicate>.md` |
| ChatGPT 5.5 | Intelligence high | 4 per role | Complete | `gpt-<role>-<replicate>.md` |

The role values used in filenames are `patient`, `clinician`, and `researcher`.
The experiment contains 36 independent responses: four repetitions for every
chatbot and role combination. Each replicate was generated in a fresh chat
using the applicable prompt verbatim and saved without later
corrections or annotations.

## Study identification

For CD012751, the retrieved-study set is defined only by entries in the
response's dedicated final primary-study or reference-list block. Studies
mentioned only in narrative prose, tables outside that block, caveats, or
suggestions for additional searches are not counted. If a response does not
provide a dedicated end list, it has zero countable retrieved studies under this
rule.

Numbered entries, citation bullets, or bibliographic citations under the final
study-list heading are candidates. Supporting links, link definitions, and
`Cited by:` lines are metadata rather than additional candidates. External
bibliographic sources and the Cochrane reference set may be used to resolve an
entry's identity, but not to add retrieval candidates that the response did not
list.

The Claude researcher replicate 1 response presents its dedicated citation
list under drug-class headings rather than under a final study-list heading.
Its citation bullets from the `Anti-TNF agents` through `Other advanced`
drug-class sections are candidates, while its trailing scope notes are not. The
ulcerative-colitis citations explicitly listed by Claude
researcher replicates 1, 2, and 3 are also candidates under this rule, even when
the response labels them as excluded or cross-references; their out-of-scope
status belongs in the later match analysis rather than in candidate extraction.

Each explicitly listed candidate is retained even when its citation is
incorrect or the claimed study may not exist. Multiple reports of the same
underlying study are grouped into one study cluster per response. A list entry
that explicitly names multiple distinct primary studies may be split into
separate candidates; otherwise, one list entry begins as one candidate.

## Reference data

The Cochrane included and excluded study references are available directly from:

- `Cochrane_reviews/source_reviews/2026_issue_6/CD012751-SUP-07-dataPackage/CD012751-study-data/CD012751-included.ris`
- `Cochrane_reviews/source_reviews/2026_issue_6/CD012751-SUP-07-dataPackage/CD012751-study-data/CD012751-excluded.ris`

## Analysis

Run from the repository root:

```bash
python3 reviews/CD012751/analyze_cd012751_roles.py
```

The script validates the 36-file inventory and expected terminal-list entry
counts, resolves every listed citation to one or more study clusters, validates
Cochrane included and excluded labels directly against the RIS exports, and
writes `data/reviews/CD012751/cd012751_role_study_matches.csv`.
When multiple terminal-list citations
resolve to one study cluster, the CSV keeps all of them in
`reported_citation`, separated by ` || `, but credits the cluster only once per
response.

A publication that explicitly reports multiple distinct trials is split into
one response-study row per trial. A single study cluster can also represent
multiple Cochrane study labels when the review separates induction,
non-responder, or maintenance populations; those labels are retained in
`cochrane_study_label`, separated by ` || `. Recall therefore uses the 94 unique
included Cochrane study labels as its denominator.

`identity_issue=1` marks a resolved citation with conflicting bibliographic or
supporting-link details. Out-of-scope randomized studies, observational studies,
and case reports remain visible under their corresponding
`ground_truth_status` values rather than being discarded. No terminal-list
candidate remained unresolved or potentially hallucinated after bibliographic
resolution.

### Results

The 576 terminal-list entries produce 775 candidate-study assignments after
multi-trial publications are split. Grouping companion reports within each
response leaves 753 response-study rows. The table reports included-label
matches summed over four runs, mean recall against the 94 included labels for
one response, and pooled coverage as the union of included labels found across
the four runs in a cell.

| Model | Role | List entries | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 68 | 89 | 104 | 27.7% | 37/94 |
| Claude | Clinician | 59 | 78 | 97 | 25.8% | 35/94 |
| Claude | Researcher | 80 | 101 | 113 | 30.1% | 38/94 |
| Gemini | Patient | 18 | 33 | 39 | 10.4% | 15/94 |
| Gemini | Clinician | 19 | 39 | 45 | 12.0% | 15/94 |
| Gemini | Researcher | 22 | 38 | 44 | 11.7% | 19/94 |
| GPT | Patient | 85 | 106 | 117 | 31.1% | 34/94 |
| GPT | Clinician | 102 | 123 | 128 | 34.0% | 40/94 |
| GPT | Researcher | 123 | 146 | 173 | 46.0% | 56/94 |

Across roles, Claude averages 27.8% included-label recall per response and
covers 45 of 94 labels when all 12 runs are pooled. Gemini averages 11.3% and
covers 20 labels. GPT averages 37.1% and covers 56 labels. The union across all
36 responses covers 60 of 94 included labels.

The role pattern is model-specific but consistently modest for patient and
clinician prompts relative to GPT's researcher condition. Claude retrieves an
average of 28.25 included labels in researcher responses, 26.0 in patient
responses, and 24.25 in clinician responses. Gemini differs by at most 1.5
labels between roles. GPT's researcher responses retrieve 43.25 included labels
on average, compared with 32.0 for clinician and 29.25 for patient responses.
With four repetitions per cell, these are descriptive differences rather than
evidence of a general role effect.

Retrieval is concentrated in pivotal programs. GEMINI 2 appears in 35 of 36
responses, ADVANCE and MOTIVATE in 34, IM-UNITI in 34, and UNITI-1 and UNITI-2
in 33. The best single response is `gpt-researcher-3.md`, with 51 of 94 included
labels. Thirty-four included labels are never retrieved by any response.

The identity audit contains 13 resolved response-study rows with conflicting
citation details: 10 from Claude and three from GPT. It also retains three
ulcerative-colitis candidates, eight observational-study rows, seven other
out-of-scope primary-study rows, and the Cochrane-excluded WELCOME trial. These
rows remain in the audit table but do not receive included-label credit.
