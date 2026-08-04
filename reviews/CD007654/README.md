# CD007654 user-role experiment

This folder is for a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about weight-loss
medicines for people with high blood pressure. The experiment is based on
Cochrane review CD007654, *Long-term effects of weight-reducing drugs in people
with hypertension*.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I have high blood pressure, and I’m considering taking medicine to help me
> lose weight.
>
> I’m trying to understand whether weight-loss medicines improve the health of
> people with high blood pressure. Find individual primary studies on this. Do
> not use systematic reviews, meta-analyses, narrative reviews, committee
> opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for people with high blood pressure who are considering
> taking medicine to help them lose weight.
>
> I’m trying to understand whether weight-loss medicines improve the health of
> people with high blood pressure. Find individual primary studies on this. Do
> not use systematic reviews, meta-analyses, narrative reviews, committee
> opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying weight-loss medicines in people
> with high blood pressure.
>
> I’m trying to understand whether weight-loss medicines improve the health of
> people with high blood pressure. Find individual primary studies on this. Do
> not use systematic reviews, meta-analyses, narrative reviews, committee
> opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

## Run inventory

| Chatbot | Configuration | Available repetitions | Status | Response filenames |
| --- | --- | ---: | --- | --- |
| Claude Sonnet 5 | Medium effort; thinking on | 4 per role | Complete | `claude-<role>-<replicate>.md` |
| Gemini 3.1 Pro | Extended thinking | 4 per role | Complete | `gemini-<role>-<replicate>.md` |
| ChatGPT 5.5 | Intelligence high | 4 per role | Complete | `gpt-<role>-<replicate>.md` |

The role values used in filenames are `patient`, `clinician`, and `researcher`.
The experiment contains 36 response files: four repetitions for every
chatbot and role combination.

Each replicate was generated in a fresh independent chat using the applicable
prompt verbatim. Responses are stored unchanged, without later
corrections or annotations in the raw response files. Model-access details or
generation settings not listed above have not been recorded and should not be
inferred.

## Study identification

For CD007654, the retrieved-study set is defined only by entries in the
response's dedicated primary-study or reference-list block. Studies mentioned
only in narrative prose, tables outside that block, caveats, or suggestions for
additional searches are not counted. External bibliographic sources and the
Cochrane reference set may be used to resolve an entry's identity, but not to add
retrieval candidates that the response did not list.

Claude and ChatGPT study candidates are the numbered or citation-bullet entries
in their dedicated study lists. Gemini study candidates are the bibliographic
citations under its final `References` or `Primary Studies` heading. Gemini
`Cited by:` lines and ChatGPT Markdown link definitions are supporting metadata,
not additional candidates. The Claude researcher replicate 4 response presents
its dedicated citation list under drug-class headings rather than under a final
study-list heading; its citation bullets are candidates, while its trailing
scope notes are not.

Each explicitly listed candidate is retained even when its citation is
incorrect or the claimed study may not exist. Multiple reports of the same
underlying study are grouped into one study cluster per response. Identity
resolution records candidates as verified, verified with a citation conflict,
unresolved, potentially hallucinated, or an invalid publication type. A list
entry that explicitly names multiple distinct primary studies may be split into
separate candidates; otherwise, one list entry begins as one candidate.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD007654/analyze_cd007654_roles.py
```

The script validates the 36-file inventory and the expected terminal-list entry
counts, resolves listed citations to study clusters, validates Cochrane included
and excluded labels directly against the review's RIS exports, and writes
`data/reviews/CD007654/cd007654_role_study_matches.csv`.
When multiple terminal-list citations resolve
to one study cluster, the CSV keeps all of them in `reported_citation`, separated
by ` || `, but credits the cluster only once for that response.

The Cochrane included RIS contains eight study clusters. `identity_issue=1`
marks a resolved citation with conflicting bibliographic details. The
`unresolved` and `invalid_publication_type` values in `ground_truth_status`
identify entries that cannot be resolved to one study or that name a pooled or
otherwise ineligible publication. A potentially hallucinated entry would also
be retained with that status rather than removed; none of these responses met
that classification, and no terminal-list candidate remained unresolved after
bibliographic verification.

### Results

The 380 terminal-list entries become 324 study clusters after within-response
deduplication. The table reports included-study matches summed over four runs,
mean recall against the eight included clusters for one response, and pooled
coverage as the union of included clusters found across the four runs in a cell.

| Model | Role | List entries | Study clusters | Included matches over 4 runs | Mean recall per response | Pooled coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 38 | 29 | 10 | 31.2% | 4/8 |
| Claude | Clinician | 48 | 39 | 19 | 59.4% | 6/8 |
| Claude | Researcher | 51 | 44 | 13 | 40.6% | 5/8 |
| Gemini | Patient | 13 | 11 | 7 | 21.9% | 2/8 |
| Gemini | Clinician | 17 | 12 | 8 | 25.0% | 2/8 |
| Gemini | Researcher | 13 | 13 | 8 | 25.0% | 2/8 |
| GPT | Patient | 55 | 47 | 17 | 53.1% | 5/8 |
| GPT | Clinician | 65 | 56 | 17 | 53.1% | 6/8 |
| GPT | Researcher | 80 | 73 | 21 | 65.6% | 8/8 |

Across roles, Claude averages 43.8% recall per response and covers six of eight
included clusters when all 12 runs are pooled. Gemini averages 24.0% and never
moves beyond STEP 1 and SURMOUNT-1, even when all 12 runs are pooled. GPT
averages 57.3% and covers all eight clusters across its 12 runs.

The role pattern is model-specific. Claude's clinician responses retrieve an
average of 4.75 included studies, compared with 3.25 for researcher and 2.50 for
patient responses. GPT instead favors the researcher role, at 5.25 included
studies versus 4.25 for both patient and clinician. Gemini differs by only 0.25
study between roles. With four repetitions per cell, these are descriptive
differences rather than evidence of a general role effect across models.

Retrieval is also strongly study-specific. Every response lists SELECT, which
the Cochrane package classifies as excluded for this review question, and 35 of
36 list the included SURMOUNT-1 cluster. Claude never retrieves Cocco 2005 or
Guy-Grand 2004. GPT researcher responses are the only model-role cell whose four
runs collectively cover all eight included studies; the best single response is
`gpt-researcher-1.md`, with seven of eight.

The identity audit contains 17 resolved cluster rows with conflicting citation
details: 16 among Claude's 112 clusters, one among GPT's 176, and none among
Gemini's 36. It also retains four invalid pooled analyses. The initially sparse
Lucknow orlistat entry was resolved to the Verma 2014 trial rather than dropped.
Invalid entries remain visible in the audit table but do not receive
included-study credit.
