# CD015136 user-role experiment

This folder is for a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about telepharmacy for
people with long-term health conditions who receive care outside a hospital.
The experiment is based on Cochrane review CD015136, *Clinical effectiveness of
telepharmacy services in patients with non-communicable diseases in ambulatory
care settings*.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a patient living with a long-term health condition and receiving care
> outside a hospital.
>
> I’m trying to understand whether remote pharmacy care (telepharmacy) works
> better than usual care for people with long-term health conditions who are not
> in hospital. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.

### Clinician

> I’m a clinician caring for people with long-term health conditions outside a
> hospital.
>
> I’m trying to understand whether remote pharmacy care (telepharmacy) works
> better than usual care for people with long-term health conditions who are not
> in hospital. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying telepharmacy for people with
> long-term health conditions outside a hospital.
>
> I’m trying to understand whether remote pharmacy care (telepharmacy) works
> better than usual care for people with long-term health conditions who are not
> in hospital. Find individual primary studies on this. Do not use systematic
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
python3 reviews/CD015136/analyze_cd015136_roles.py
```

The script validates all 36 response files and writes
`data/reviews/CD015136/cd015136_role_study_matches.csv`.
Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, or a caveat is retained
once per response. Terminal reference lists help resolve identity but do not
define the retrieval boundary. Generic unnamed studies and secondary sources
mentioned only as context are not counted. Multiple reports from the same
underlying trial are represented by one study-cluster candidate.

Candidate studies are classified as Cochrane included, excluded, ongoing,
awaiting classification, outside the Cochrane set, or unresolved. Cochrane
labels are validated directly against the corresponding RIS exports under
`Cochrane_reviews/source_reviews/2026_issue_6/CD015136-SUP-08-dataPackage/`.
The included RIS contains 21 study labels. Across the 36 responses, 17 included
study clusters were retrieved; the four missed clusters were `Alsabbagh 2012`,
`Powers 1983`, `Salmany 2018`, and `Scala 2018`. Citation conflicts remain
visible through identity flags and notes in the match table.
