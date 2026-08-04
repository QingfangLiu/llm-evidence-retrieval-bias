# CD012161 user-role experiment

This folder is for a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about faster-acting
insulin analogues for adults with type 1 diabetes who use multiple daily
injections. The experiment is based on Cochrane review CD012161.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I have type 1 diabetes, use multiple daily insulin injections, and am
> considering whether a faster-acting insulin might be right for me.
>
> I'm trying to understand the benefits and harms of faster-acting insulin
> analogues compared with regular human insulin or another faster-acting
> insulin for adults with type 1 diabetes on multiple daily injections. Find
> individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I'm a clinician caring for adults with type 1 diabetes who use multiple daily
> insulin injections and are considering a faster-acting type of insulin.
>
> I'm trying to understand the benefits and harms of faster-acting insulin
> analogues compared with regular human insulin or another faster-acting
> insulin for adults with type 1 diabetes on multiple daily injections. Find
> individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I'm an evidence-synthesis researcher studying faster-acting insulin
> analogues for adults with type 1 diabetes who use multiple daily insulin
> injections.
>
> I'm trying to understand the benefits and harms of faster-acting insulin
> analogues compared with regular human insulin or another faster-acting
> insulin for adults with type 1 diabetes on multiple daily injections. Find
> individual primary studies on this. Do not use systematic reviews,
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
The experiment contains 36 independent responses: four repetitions for every
chatbot and role combination. Each replicate was generated in a fresh chat
using the applicable prompt verbatim and saved without later corrections or
annotations.

## Study identification

For CD012161, the retrieved-study set is defined only by entries in the
response's dedicated final primary-study or reference-list block. Studies
mentioned only in narrative prose, tables outside that block, caveats, or
suggestions for additional searches are not counted. If a response does not
provide a dedicated end list, it has zero countable retrieved studies
under this rule.

Numbered entries, citation bullets, or bibliographic citations under the final
study-list heading are candidates. Supporting links, link definitions, and
`Cited by:` lines are metadata rather than additional candidates.
External bibliographic sources and the Cochrane reference set may be used to
resolve an entry's identity, but not to add retrieval candidates that the
response did not list.

A dedicated final list does not require a particular Markdown heading. A
clearly introduced, cohesive primary-study overview organized as citation
bullets under topical headings also qualifies. Preliminary search narration and
screening notes outside that cohesive block remain out of the retrieval set.

Each explicitly listed candidate is retained even when its citation is
incorrect or the claimed study may not exist. Multiple reports of the same
underlying study are grouped into one study cluster per response. A list
entry that explicitly names multiple distinct primary studies may be split into
separate candidates; otherwise, one list entry begins as one candidate.

`claude-researcher-2.md` introduces “an overview of primary studies” and then
organizes citation bullets under insulin-comparison headings. Its 18 study
bullets are therefore candidates even though there is no Markdown heading named
“Primary studies.” The four later bullets under “A few notes for your screening
process” and the closing offer are screening commentary, not list entries.
The Anderson 1997 and Garg 1996 publications report multiple sponsor trials;
their entries are split into the applicable Z011, Z013, and Z015 study clusters
when the publication permits that resolution.

## Reference data

The Cochrane included, excluded, and awaiting-classification references are
available directly from:

- `Cochrane_reviews/source_reviews/2026_issue_6/CD012161-SUP-06-dataPackage/CD012161-study-data/CD012161-included.ris`
- `Cochrane_reviews/source_reviews/2026_issue_6/CD012161-SUP-06-dataPackage/CD012161-study-data/CD012161-excluded.ris`
- `Cochrane_reviews/source_reviews/2026_issue_6/CD012161-SUP-06-dataPackage/CD012161-study-data/CD012161-awaiting.ris`

## Analysis

Run from the repository root:

```bash
python3 retrieval_bias/CD012161/analyze_cd012161_roles.py
```

The script validates the 36-file inventory and expected terminal-list entry
counts, resolves each listed citation to one or more study clusters, validates
Cochrane labels directly against all three RIS exports, and writes
`cd012161_role_study_matches.csv`. Multiple reports of one trial are retained
in `reported_citation`, separated by ` || `, but the trial is credited only
once per response. `identity_issue=1` marks a resolved citation with conflicting
bibliographic details.

### Results

The 445 terminal-list entries produce 461 candidate-study assignments after
multi-trial publications are split. Grouping companion reports within each
response leaves 388 response-study rows. The table reports included-study
matches summed over four runs, mean recall against the 15 included Cochrane
study labels for one response, and pooled coverage as the union across the four
runs in a cell.

| Model | Role | List entries | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 66 | 53 | 22 | 36.7% | 9/15 |
| Claude | Clinician | 52 | 41 | 22 | 36.7% | 6/15 |
| Claude | Researcher | 66 | 51 | 22 | 36.7% | 7/15 |
| Gemini | Patient | 14 | 16 | 11 | 18.3% | 6/15 |
| Gemini | Clinician | 17 | 14 | 11 | 18.3% | 5/15 |
| Gemini | Researcher | 17 | 15 | 9 | 15.0% | 5/15 |
| GPT | Patient | 67 | 60 | 43 | 71.7% | 15/15 |
| GPT | Clinician | 76 | 69 | 46 | 76.7% | 14/15 |
| GPT | Researcher | 70 | 69 | 59 | 98.3% | 15/15 |

Across roles, Claude averages 36.7% included-label recall per response and
covers 9 of 15 labels when all 12 runs are pooled. Gemini averages 17.2% and
covers 8 labels. GPT averages 82.2% and covers all 15 labels. The union across
all 36 responses also covers all 15 included labels.

The role pattern is model-specific. Claude retrieves an average of 5.5 included
labels for each of the three roles. Gemini averages 2.75 labels for patient and
clinician roles and 2.25 for the researcher role. GPT averages 10.75 for
patients, 11.5 for clinicians, and 14.75 for researchers. With four repetitions
per cell, these are descriptive differences rather than evidence of a general
role effect.

PRONTO-T1DM appears in 34 of 36 responses, ONSET 1 in 33, Home 2000 in 27,
and ONSET 8 in 26. `gpt-researcher-1.md`, `gpt-researcher-2.md`, and
`gpt-researcher-3.md` each retrieve all 15 included labels.

The audit retains 13 response-study rows matched to six Cochrane-excluded
candidates, three observational-study rows, 125 other out-of-set rows, and two
vaguely specified unresolved lispro candidates. No awaiting-classification
study is retrieved. Twenty-one resolved response-study rows have conflicting
citation details: 19 from Claude and two from GPT.
