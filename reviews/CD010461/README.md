# CD010461 user-role experiment

This folder is for a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about advanced sperm
selection techniques in assisted reproduction. The experiment is based on
Cochrane review CD010461, *Advanced sperm selection techniques for assisted
reproduction*.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a patient trying to have a baby through IVF/ICSI.
>
> I’m trying to understand whether advanced sperm selection techniques improve
> the effectiveness of assisted reproduction compared with standard sperm
> selection. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.

### Clinician

> I’m a clinician caring for patients trying to have a baby through IVF/ICSI.
>
> I’m trying to understand whether advanced sperm selection techniques improve
> the effectiveness of assisted reproduction compared with standard sperm
> selection. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying sperm selection in IVF/ICSI.
>
> I’m trying to understand whether advanced sperm selection techniques improve
> the effectiveness of assisted reproduction compared with standard sperm
> selection. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.

## Run inventory

| Chatbot | Configuration | Available repetitions | Status | Response filenames |
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
python3 reviews/CD010461/analyze_cd010461_roles.py
```

The script validates all 36 response files and writes
`cd010461_role_study_matches.csv`. Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, a reference list, or a
caveat is retained once per response. Terminal reference lists help resolve
identity but do not define the retrieval boundary. Generic unnamed studies and
secondary sources mentioned only as context are not counted.

Candidate studies are classified as Cochrane included, excluded, ongoing,
awaiting classification, outside the Cochrane set, or unresolved. Included,
excluded, ongoing, and awaiting-classification labels are validated directly
against the corresponding RIS exports under
`Cochrane_reviews/source_reviews/2026_issue_6/CD010461-SUP-07-dataPackage/`.
The included RIS contains five study labels. Citation conflicts remain visible
through identity flags and notes in the match table.
