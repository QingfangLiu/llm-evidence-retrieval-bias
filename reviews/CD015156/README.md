# CD015156 user-role experiment

This folder contains a three-condition retrieval-bias experiment based on
Cochrane review CD015156, *Non-surgical treatment for lower limb apophyseal
injuries*.

- Clinical question: non-surgical treatments for lower-limb apophyseal injuries
  in children and adolescents
- Included primary-study clusters: 10
- Source review: [`CD015156.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015156.pdf)
- Source data: [`CD015156-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD015156-SUP-07-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a parent of a child with growth-plate pain (apophysitis) in the hip,
> knee, or foot.
>
> I’m trying to understand which nonsurgical treatments work best for children
> and adolescents with lower-limb growth-plate pain (apophysitis). Find
> individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for children and adolescents with lower-limb
> growth-plate pain (apophysitis).
>
> I’m trying to understand which nonsurgical treatments work best for children
> and adolescents with lower-limb growth-plate pain (apophysitis). Find
> individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying nonsurgical treatments for
> lower-limb growth-plate pain (apophysitis) in children and adolescents.
>
> I’m trying to understand which nonsurgical treatments work best for children
> and adolescents with lower-limb growth-plate pain (apophysitis). Find
> individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
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
and role combination.

Each replicate was generated in a fresh independent chat using the applicable
prompt verbatim. Responses are stored unchanged, without later corrections or
annotations in the raw response files. Model versions and generation settings
were not recorded in this folder and should not be inferred. Ten of the 12
Claude responses retain concatenated search-process narration before the final
answer; this source-quality issue is preserved as collected, and the analysis
uses the complete available text.

## Analysis

Run from the repository root:

```bash
python3 retrieval_bias/CD015156/analyze_cd015156_roles.py
```

The script validates all 36 response files and writes
`cd015156_role_study_matches.csv`. Study identification uses each complete
saved response, not only a terminal bibliography. Any explicitly identifiable
primary study named in the narrative, a table, an inline list, a citation-link
definition, a search preamble, or a caveat is retained once per response.
Terminal reference lists help resolve identity but do not define the retrieval
boundary. Generic unnamed studies and secondary sources mentioned only as
context are not counted. Multiple reports from the same study are represented
by one study-cluster candidate.

Candidate studies are classified as Cochrane included, excluded, ongoing,
outside the Cochrane set, or unresolved. Cochrane labels are validated directly
against the corresponding RIS exports in the source data-package ZIP. The
included RIS contains 10 study labels. Across the 36 responses, all 10 included
study clusters were retrieved at least once, so no included cluster was missed
by the pooled experiment.

The 2016 abstract and 2020 report of the Nakase trial are grouped together, as
are the James protocol and results reports, the Alfaro-Santafé registry and
publication, and the Sweeney conference and journal reports. The included
Perhamre 2011a crossover trial and Perhamre 2012 heel-pad study remain separate
from the excluded Perhamre 2011b insole cohort, following the source-package
study labels. SOGOOD remains classified as Cochrane ongoing because that is its
source-package status, even when a response cites the 2025 conference-abstract
results. Citation conflicts and uncertain identities remain visible through
identity flags and notes in the match table.

### Initial results

The 36 responses produce 465 response-study rows: 231 Cochrane-included
matches, 67 Cochrane-excluded matches, 27 Cochrane-ongoing matches, 138
out-of-set primary-study matches, and two unresolved citations. Mean recall
uses the 10 included Cochrane study clusters as the denominator for each
response. Pooled coverage is the union across the four runs in one model-role
cell.

| Model | Role | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: |
| Claude | Patient | 58 | 22 | 55.0% | 9/10 |
| Claude | Clinician | 65 | 33 | 82.5% | 10/10 |
| Claude | Researcher | 62 | 29 | 72.5% | 8/10 |
| Gemini | Patient | 16 | 10 | 25.0% | 7/10 |
| Gemini | Clinician | 13 | 7 | 17.5% | 6/10 |
| Gemini | Researcher | 18 | 13 | 32.5% | 6/10 |
| GPT | Patient | 86 | 38 | 95.0% | 10/10 |
| GPT | Clinician | 72 | 39 | 97.5% | 10/10 |
| GPT | Researcher | 75 | 40 | 100.0% | 10/10 |

Across all 12 runs for each model, Claude averages 70.0% included-study recall,
Gemini averages 25.0%, and GPT averages 97.5%. The clinician role has the
highest mean for Claude, while the researcher role has the highest mean for
Gemini and GPT. With only four repetitions per cell, these differences are
descriptive rather than evidence of a general role effect.

Wiegerinck 2016 appears in 30 responses and James 2016 in 29. Reesman 2024 is
the least frequently retrieved included cluster, appearing in 12 responses.
Twelve rows have conflicting or uncertain citation details and are marked with
`identity_issue=1`; the two unresolved rows are generic references to a
"Bourke" orthotic study without enough bibliographic information to identify a
specific publication.
