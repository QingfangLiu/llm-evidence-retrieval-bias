# CD005354 user-role experiment

This folder contains a three-condition retrieval-bias experiment based on
Cochrane review CD005354, *Recombinant follicle-stimulating hormone (rFSH)
versus other recombinant or urinary gonadotropins for ovarian stimulation in
assisted reproductive technology cycles*.

- Clinical question: rFSH versus other recombinant or urinary gonadotropins for
  ovarian stimulation in assisted reproduction
- Included primary-study clusters: 59
- Source review: [`CD005354.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD005354.pdf)
- Source data: [`CD005354-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD005354-SUP-07-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a woman undergoing IVF and need hormone treatment to stimulate my
> ovaries.
>
> I’m trying to understand how recombinant follicle-stimulating hormone (rFSH)
> compares with other gonadotropin hormones for stimulating the ovaries during
> IVF. Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for women undergoing IVF who need hormone treatment
> to stimulate their ovaries.
>
> I’m trying to understand how recombinant follicle-stimulating hormone (rFSH)
> compares with other gonadotropin hormones for stimulating the ovaries during
> IVF. Find individual primary studies on this. Do not use systematic reviews,
> meta-analyses, narrative reviews, committee opinions, practice guidelines,
> or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying hormones used to stimulate the
> ovaries during IVF.
>
> I’m trying to understand how recombinant follicle-stimulating hormone (rFSH)
> compares with other gonadotropin hormones for stimulating the ovaries during
> IVF. Find individual primary studies on this. Do not use systematic reviews,
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
and role combination. Responses are stored unchanged, without later
corrections or annotations. Model versions and generation settings were not
recorded in this folder and should not be inferred.

Eight raw Claude files begin with search-process-like text concatenated to the
answer: `claude-clinician-3.md`, `claude-clinician-4.md`,
`claude-patient-1.md`, `claude-patient-2.md`, `claude-patient-4.md`,
`claude-researcher-1.md`, `claude-researcher-3.md`, and
`claude-researcher-4.md`. Four Claude responses explicitly disclose using
secondary citation trails or review/registry references to locate studies:
`claude-patient-2.md`, `claude-patient-4.md`,
`claude-researcher-3.md`, and `claude-researcher-4.md`. That conflicts with
the prompt's source restriction. All planned runs remain in the primary
analysis, and the deviation is considered when interpreting Claude's recall.

## Study identification

The retrieved-study set is defined only by entries in a response's dedicated
final primary-study or reference-list block. Studies mentioned only in
narrative prose, tables, summaries, caveats, link definitions, or `Cited by:`
metadata are not counted.

For Gemini, the bibliographic line immediately preceding each `Cited by:` line
in the final reference block is one candidate. For GPT and most Claude
responses, numbered entries under the last qualifying primary-study heading
are candidates. `claude-clinician-4.md` instead uses bullets in its final
primary-study block, and `claude-patient-3.md` uses a cohesive sequence of
bold study paragraphs; those entries define their terminal lists.

Every explicitly listed candidate is retained even when it is
Cochrane-excluded, awaiting classification, outside the review set, an
ineligible publication type, or bibliographically inaccurate. Companion
reports, follow-up publications, and multiple citations belonging to one
study are grouped into one cluster within a response. Citation conflicts
remain visible in the audit table.

The included RIS contains 59 study clusters but no explicit PubMed
identifiers. Recall is therefore evaluated at the Cochrane study-cluster
level. Each included source label is one study row, so included study-row
recall and cluster recall are numerically identical. PMID recall and
missed-PMID coverage cannot be computed from this source package.

## Reference data

- Source review:
  [`CD005354.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD005354.pdf)
- Source data:
  [`CD005354-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD005354-SUP-07-dataPackage.zip)

The analysis reads the included, excluded, awaiting-classification, and
ongoing RIS exports directly from the ZIP archive. The package contains 59
included, 63 excluded, 30 awaiting-classification, and seven ongoing labels.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD005354/analyze_cd005354_roles.py
```

The script validates the 36-file inventory and expected terminal-list entry
counts, requires every listed citation to resolve, validates every
Cochrane-classified label against the RIS exports, and writes
`data/reviews/CD005354/cd005354_role_study_matches.csv`.
Multiple reports of one study are retained
in `reported_citation`, separated by ` || `, but the study is credited only
once per response. `identity_issue=1` marks an identifiable citation with
conflicting bibliographic details.

### Results

The 507 terminal-list entries resolve to 488 response-study rows after
grouping companion reports within responses. Included matches are summed over
four runs. Mean recall uses the 59 included Cochrane study clusters as the
denominator for every response. Pooled coverage is the union across the four
runs in one model-role cell.

| Model | Role | List entries | Response-study rows | Included matches over 4 runs | Mean cluster/study-row recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 62 | 56 | 27 | 11.4% | 11/59 |
| Claude | Clinician | 59 | 56 | 28 | 11.9% | 18/59 |
| Claude | Researcher | 86 | 79 | 25 | 10.6% | 17/59 |
| Gemini | Patient | 15 | 15 | 8 | 3.4% | 5/59 |
| Gemini | Clinician | 14 | 14 | 9 | 3.8% | 4/59 |
| Gemini | Researcher | 20 | 20 | 11 | 4.7% | 7/59 |
| GPT | Patient | 63 | 63 | 42 | 17.8% | 15/59 |
| GPT | Clinician | 88 | 87 | 61 | 25.8% | 23/59 |
| GPT | Researcher | 100 | 98 | 76 | 32.2% | 31/59 |

Across roles, Claude averages 11.3% included-study recall per response and
covers 24 of 59 labels when its 12 runs are pooled. Gemini averages 4.0% and
covers eight labels. GPT averages 25.3% and covers 32 labels. The union across
all 36 responses covers 40 of 59 included labels. The 19 clusters never
retrieved are `Aboulghar 2010`, `Antoine 2007`, `Balasch 2003`,
`Barakhoeva 2019`, `Dickey 2003`, `Gallego 2003`, `Gholami 2010`,
`Gordon 2001`, `Griesinger 2020`, `Hu 2020`, `Ishihara 2021a`,
`Jansen 1998`, `Moon 2007`, `NCT00257556`, `NCT01687712`, `Nardo 2000`,
`Pasqualini 2021`, `Rashidi 2005`, and `Selman 2002`.

The role pattern differs by model. Researcher-role recall is 14.4 percentage
points higher than patient-role recall for GPT and 1.3 points higher for
Gemini, but 0.8 points lower for Claude. Across models, mean researcher-role
recall is 15.8%, compared with 13.8% for clinician and 10.9% for patient
responses. Researcher responses also have longer terminal lists: 206 entries,
versus 161 for clinician and 140 for patient responses. With four repetitions
per cell, these are retrieval-pattern descriptions, not evidence of a general
causal role effect.

The four Claude responses that disclose secondary citation-trail use retrieve
30 of 236 possible included matches, for 12.7% mean recall, compared with
10.6% across the other eight Claude responses. This limited sensitivity check
does not remove the collection-quality concern, but the model ordering remains
GPT, Claude, then Gemini.

Retrieval is concentrated in a small core. `Andersen 2006` appears in 33
responses, `Devroey 2012` in 21, `Baker 2009` in 19, and `Bosch 2008` in 16.
Thirteen of the 40 retrieved included clusters appear in only one or two
responses. The best single response retrieves 25 of 59 included clusters; the
weakest retrieves one.

The audit table contains 287 included response-study rows, 51
Cochrane-excluded rows, 11 awaiting-classification rows, 111 other out-of-set
rows, 13 out-of-set observational rows, nine invalid-publication-type rows, and
six unresolved out-of-set rows. No ongoing study was retrieved. The invalid
publication types are eight pooled analyses and one review, all in Claude
responses. Nineteen resolved rows have conflicting citation details and are
marked with
`identity_issue=1`. PMID recall is reported as unavailable because the RIS
exports contain no explicit PubMed IDs.
