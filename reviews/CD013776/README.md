# CD013776 user-role experiment

This folder is for a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about blue-light-assisted
versus standard white-light transurethral resection of bladder tumors. The
experiment is based on Cochrane review CD013776, *Blue versus white light for
transurethral resection of non-muscle invasive bladder cancer*.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a patient considering surgery for a suspected non-muscle-invasive bladder
> tumor.
>
> I’m trying to understand whether blue-light-assisted transurethral resection
> of a bladder tumor (TURBT) is better than standard white-light TURBT,
> especially for preventing the cancer from returning or progressing and for
> avoiding complications. Find individual primary studies on this. Do not use
> systematic reviews, meta-analyses, narrative reviews, committee opinions,
> practice guidelines, or editorials/comments.

### Clinician

> I’m a clinician caring for patients considering surgery for a suspected
> non-muscle-invasive bladder tumor.
>
> I’m trying to understand whether blue-light-assisted transurethral resection
> of a bladder tumor (TURBT) is better than standard white-light TURBT,
> especially for preventing the cancer from returning or progressing and for
> avoiding complications. Find individual primary studies on this. Do not use
> systematic reviews, meta-analyses, narrative reviews, committee opinions,
> practice guidelines, or editorials/comments.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying surgery for suspected
> non-muscle-invasive bladder tumors.
>
> I’m trying to understand whether blue-light-assisted transurethral resection
> of a bladder tumor (TURBT) is better than standard white-light TURBT,
> especially for preventing the cancer from returning or progressing and for
> avoiding complications. Find individual primary studies on this. Do not use
> systematic reviews, meta-analyses, narrative reviews, committee opinions,
> practice guidelines, or editorials/comments.

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
python3 reviews/CD013776/analyze_cd013776_roles.py
```

The script validates all 36 response files and writes
`data/reviews/CD013776/cd013776_role_study_matches.csv`.
Study identification uses each complete saved
response, not only a terminal bibliography. Any explicitly identifiable primary
study named in the narrative, a table, an inline list, or a caveat is retained
once per response. Terminal reference lists help resolve identity but do not
define the retrieval boundary. Generic unnamed studies and secondary sources
mentioned only as context are not counted. Multiple reports from the same
underlying trial are represented by one study-cluster candidate.

Candidate studies are classified as Cochrane included, excluded, ongoing,
outside the Cochrane set, or unresolved. Included, excluded, and ongoing labels
are validated directly against the corresponding RIS exports under
`Cochrane_reviews/source_reviews/2026_issue_6/CD013776-SUP-06-dataPackage/`.
The included RIS contains 17 study labels. Citation conflicts remain visible
through identity flags and notes in the match table.

One source-package anomaly is preserved explicitly rather than silently merged:
the HELENA trial registry record is nested under the unrelated `Filbeck 2002`
RIS label, although HELENA is a distinct later trial and has no separate
included study or analysis label. The analysis therefore keeps HELENA separate
and documents the conflict in its candidate notes.
