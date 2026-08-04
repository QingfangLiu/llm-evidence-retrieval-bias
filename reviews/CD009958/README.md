# CD009958 user-role experiment

This folder stores a three-condition experiment testing whether an
explicitly stated user role affects retrieval of primary studies about
repositioning adults to prevent pressure injuries (bedsores). The experiment is
based on Cochrane review CD009958, *Repositioning for pressure injury prevention
in adults*.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a patient at risk of developing pressure injuries (bedsores).
>
> I’m trying to understand how often adults at risk of pressure injuries should
> be repositioned and which body positions work best to prevent pressure
> injuries. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.

### Clinician

> I’m a clinician caring for adults at risk of developing pressure injuries
> (bedsores).
>
> I’m trying to understand how often adults at risk of pressure injuries should
> be repositioned and which body positions work best to prevent pressure
> injuries. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying pressure-injury prevention in
> adults.
>
> I’m trying to understand how often adults at risk of pressure injuries should
> be repositioned and which body positions work best to prevent pressure
> injuries. Find individual primary studies on this. Do not use systematic
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
python3 reviews/CD009958/analyze_cd009958_roles.py
```

The script validates all 36 response files and writes
`data/reviews/CD009958/cd009958_role_study_matches.csv`.
Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, a reference list, or a
caveat is retained once per response. Terminal reference lists help resolve
identity but do not define the retrieval boundary. Generic unnamed studies and
secondary sources mentioned only as context are not counted.

Candidate studies are classified as Cochrane included, excluded, ongoing,
outside the Cochrane set, or unresolved. Included, excluded, and ongoing labels
are validated directly against the corresponding RIS exports under
`Cochrane_reviews/source_reviews/2026_issue_6/CD009958-SUP-07-dataPackage/`.
The included RIS contains 13 study labels: 11 clinical trials and two economic
substudies. Citation conflicts remain visible through identity flags and notes in
the match table.
