# CD010051 user-role experiment

This folder contains a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about topical ciclosporine
A for dry eye disease. The experiment is based on Cochrane review CD010051,
*Topical ciclosporine A therapy for dry eye disease*.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I have dry eye disease and am considering cyclosporine A eye drops.
>
> I’m trying to understand the benefits and harms of cyclosporine A (CsA) eye
> drops for people with dry eye disease. Find individual primary studies on
> this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for people with dry eye disease who are considering
> cyclosporine A eye drops.
>
> I’m trying to understand the benefits and harms of cyclosporine A (CsA) eye
> drops for people with dry eye disease. Find individual primary studies on
> this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying cyclosporine A eye drops for
> people with dry eye disease.
>
> I’m trying to understand the benefits and harms of cyclosporine A (CsA) eye
> drops for people with dry eye disease. Find individual primary studies on
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
The experiment contains 36 independent responses: four repetitions for every
chatbot and role combination. Responses are retained unchanged.

`claude-researcher-3.md` explicitly says it used systematic-review reference
lists to identify additional primary trials. That conflicts with the prompt's
instruction not to use systematic reviews. The response remains in the primary
analysis because all planned runs are retained unchanged; this protocol
deviation should be considered when interpreting its recall.

## Study identification

The retrieved-study set is defined only by entries in a response's dedicated
final primary-study or reference-list block. Studies mentioned only in
narrative prose, evidence summaries, caveats, link definitions, or `Cited by:`
metadata are not counted.

For Gemini, the bibliographic line immediately preceding each `Cited by:` line
in the final reference block is one candidate. For Claude and GPT, numbered
entries under the last qualifying primary-study heading are candidates.
`claude-researcher-1.md` is the only special case: its bullet entries from
`Landmark/pivotal trials` through the final ongoing-trial section form one
cohesive study list because it has no later consolidated list.

Every explicitly listed candidate is retained even when it is excluded,
ongoing, observational, retracted, secondary, outside the Cochrane set, or
bibliographically inaccurate. Companion reports are grouped into one study
cluster per response. One entry that explicitly combines ESSENCE-1 and
ESSENCE-2 is split into two distinct included clusters. The excluded RIS
duplicates one report under `Lee 2016` and `Lee 2016a`; the audit table retains
both source labels but credits the report only once per response.

The included RIS contains 58 study clusters but no explicit PubMed identifiers.
Recall is therefore evaluated at the Cochrane study-cluster level. Each
included source label is one study row, so included study-row recall and
cluster recall are numerically identical. PMID recall and missed-PMID coverage
cannot be computed from this source package.

## Reference data

- Source review:
  [`CD010051.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD010051.pdf)
- Source data:
  [`CD010051-SUP-07-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD010051-SUP-07-dataPackage.zip)

The analysis reads the included, excluded, awaiting-classification, and ongoing
RIS exports directly from the ZIP archive. The package contains 58 included,
88 excluded, 10 awaiting-classification, and 41 ongoing labels.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD010051/analyze_cd010051_roles.py
```

The script validates the 36-file inventory and expected terminal-list entry
counts, resolves all listed citations, validates every Cochrane-classified
label against the RIS exports, and writes
`cd010051_role_study_matches.csv`. Multiple reports of one study are retained
in `reported_citation`, separated by ` || `, but the study is credited only
once per response. `identity_issue=1` marks an identifiable citation with
conflicting bibliographic details.

### Results

The 562 terminal-list entries produce 563 candidate-study assignments after
the combined ESSENCE entry is split. Grouping companion reports within each
response leaves 484 response-study rows. Included matches are summed over four
runs. Mean recall uses the 58 included Cochrane study clusters as the
denominator for every response. Pooled coverage is the union across the four
runs in one model-role cell.

| Model | Role | List entries | Response-study rows | Included matches over 4 runs | Mean cluster/study-row recall per response | Pooled study coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 61 | 54 | 35 | 15.1% | 17/58 |
| Claude | Clinician | 74 | 62 | 42 | 18.1% | 18/58 |
| Claude | Researcher | 91 | 80 | 45 | 19.4% | 21/58 |
| Gemini | Patient | 14 | 13 | 11 | 4.7% | 5/58 |
| Gemini | Clinician | 19 | 19 | 19 | 8.2% | 7/58 |
| Gemini | Researcher | 17 | 17 | 17 | 7.3% | 7/58 |
| GPT | Patient | 65 | 52 | 45 | 19.4% | 14/58 |
| GPT | Clinician | 92 | 77 | 59 | 25.4% | 21/58 |
| GPT | Researcher | 129 | 110 | 73 | 31.5% | 26/58 |

Across roles, Claude averages 17.5% included-study recall per response and
covers 26 of 58 labels when its 12 runs are pooled. Gemini averages 6.8% and
covers nine labels. GPT averages 25.4% and covers 29 labels. The union across
all 36 responses covers 35 of 58 included labels, so 23 included clusters are
never retrieved:

`Agarwal 2019`, `Altiparmak 2010`, `Barreto 2009`, `Chung 2013`,
`Demiryay 2011`, `Fan 2003`, `Guzey 2009`, `Gündüz 1994`, `Hao 2024`,
`Jung 2023`, `Kim 2023`, `Kudyar 2018`, `Liew 2012`, `NCT01319773`,
`NCT04734197`, `Priani 2023`, `Rajpoot 2022`, `Rhim 2022`, `Sall 2006`,
`Schrell 2012`, `Shen 2020`, `Wu 2009`, and `Xu 2023`.

The role pattern is descriptive but consistent in direction for Claude and
GPT: researcher-role responses have higher recall than patient-role responses.
The difference is 4.3 percentage points for Claude and 12.1 points for GPT.
Gemini's clinician role is highest, while its researcher role still exceeds
its patient role by 2.6 points. Across models, researcher responses also
produce substantially longer final lists: 237 entries, versus 185 for
clinician and 140 for patient responses. Their broader retrieval comes with
more out-of-set material; only 64.9% of researcher response-study rows are
Cochrane-included, compared with 76.0% for clinician and 76.5% for patient
rows. With four repetitions per cell, these are retrieval-pattern
descriptions, not evidence of a general causal role effect.

Retrieval is strongly concentrated in a small modern/pivotal core. `Sall 2000`
appears in all 36 responses, followed by `Goldberg 2019` in 30,
`Leonardi 2016` in 29, `Stevenson 2000` in 27, and `Tauber 2018` in 26.
Seven included clusters appear only once. The best single response retrieves
21 of 58 clusters; the weakest retrieves two.

The audit table contains 346 included response-study rows, 34
Cochrane-excluded rows, five ongoing rows, no awaiting-classification rows, 32
outside observational rows, 56 other out-of-set rows, four retracted-report
rows, six secondary-analysis rows, and one explicitly unresolved
head-to-head-trial row. Twenty-four resolved rows have conflicting citation
details. The script prints each run's cluster and study-row recall, then the
pooled missed included labels. PMID recall is reported as unavailable because
the RIS exports contain no PubMed IDs.
