# CD000510 user-role experiment

This folder contains a three-condition experiment testing whether an explicitly
stated user role affects retrieval of primary studies about prophylactic versus
selective surfactant administration for preterm infants at risk of respiratory
distress syndrome. The experiment is based on Cochrane review CD000510.

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a parent of a preterm baby at risk of respiratory distress syndrome.
>
> I’m trying to understand the benefits and harms of giving surfactant
> preventively (prophylactic use) versus only after respiratory distress
> syndrome develops (selective use). Find individual primary studies on this.
> Do not use systematic reviews, meta-analyses, narrative reviews, committee
> opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for preterm infants at risk of respiratory distress
> syndrome.
>
> I’m trying to understand the benefits and harms of giving surfactant
> preventively (prophylactic use) versus only after respiratory distress
> syndrome develops (selective use). Find individual primary studies on this.
> Do not use systematic reviews, meta-analyses, narrative reviews, committee
> opinions, practice guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying surfactant use in preterm
> infants at risk of respiratory distress syndrome.
>
> I’m trying to understand the benefits and harms of giving surfactant
> preventively (prophylactic use) versus only after respiratory distress
> syndrome develops (selective use). Find individual primary studies on this.
> Do not use systematic reviews, meta-analyses, narrative reviews, committee
> opinions, practice guidelines, or editorials/comments.
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
chatbot and role combination.

Three retained Claude responses explicitly say that they used a Cochrane review
or its reference list to identify studies: `claude-clinician-2.md`,
`claude-clinician-3.md`, and `claude-researcher-4.md`. This conflicts with the
prompt's instruction not to use systematic reviews. They remain in the primary
analysis because all planned runs are retained unchanged; this protocol
deviation should be considered when interpreting Claude's recall.

## Study identification

For CD000510, the retrieved-study set is defined only by entries in the
response's dedicated final primary-study or reference-list block. Studies
mentioned only in narrative prose, tables outside that block, caveats, link
definitions, or `Cited by:` metadata are not counted.

For Gemini responses, the bibliographic line immediately preceding each
`Cited by:` line in the final reference block is one candidate. For Claude and
GPT responses, numbered entries under the last qualifying primary-study heading
are candidates. `claude-researcher-4.md` is the only special case: its
numbered `Core trials` and `CPAP-era trials` sections and its one study citation
under `Additional retrospective/observational comparative studies` form one
cohesive final list because the response does not provide a later consolidated
list.

Each explicitly listed candidate is retained even when it is excluded,
awaiting classification, ongoing, observational, otherwise outside the
Cochrane set, or bibliographically inaccurate. Multiple reports of the same
underlying study are grouped into one study cluster per response. A list entry
that explicitly names two distinct trials is split into two candidates.

The included RIS contains 10 study clusters and 14 explicit PubMed IDs across
their primary and companion reports. Recall is analyzed primarily at the
Cochrane study-cluster level. The script also reports the PubMed IDs associated
with retrieved and missed clusters; this is cluster-associated PMID coverage,
not a claim that a response cited every companion report individually.

## Reference data

- Source review:
  [`CD000510.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD000510.pdf)
- Source data:
  [`CD000510-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD000510-dataPackage.zip)

The script reads the included, excluded, awaiting-classification, and ongoing
RIS exports directly from the ZIP archive with Python's `zipfile` module.
Manual extraction is not required.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD000510/analyze_cd000510_roles.py
```

The script validates the 36-file inventory and expected terminal-list entry
counts, resolves every listed citation, validates all Cochrane-classified study
labels against the four RIS exports, and writes
`cd000510_role_study_matches.csv`. Multiple reports of one study are retained
in `reported_citation`, separated by ` || `, but the study is credited only
once per response. `identity_issue=1` marks an identifiable citation with
conflicting bibliographic details.

### Results

The 385 terminal-list entries produce 386 candidate-study assignments after
one entry naming both Bevilacqua trials is split. Grouping companion reports
within each response leaves 351 response-study rows. Included matches are
summed over four runs. Mean recall uses the 10 included Cochrane study clusters
as the denominator for each response. Pooled coverage is the union across the
four runs in one model-role cell.

| Model | Role | List entries | Response-study rows | Included matches over 4 runs | Mean recall per response | Pooled study coverage | Pooled cluster-associated PMID coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 40 | 40 | 27 | 67.5% | 10/10 | 14/14 |
| Claude | Clinician | 52 | 52 | 29 | 72.5% | 10/10 | 14/14 |
| Claude | Researcher | 51 | 51 | 34 | 85.0% | 10/10 | 14/14 |
| Gemini | Patient | 13 | 12 | 7 | 17.5% | 3/10 | 4/14 |
| Gemini | Clinician | 15 | 14 | 10 | 25.0% | 4/10 | 5/14 |
| Gemini | Researcher | 14 | 14 | 8 | 20.0% | 4/10 | 5/14 |
| GPT | Patient | 60 | 47 | 34 | 85.0% | 9/10 | 13/14 |
| GPT | Clinician | 63 | 56 | 36 | 90.0% | 9/10 | 13/14 |
| GPT | Researcher | 77 | 65 | 37 | 92.5% | 10/10 | 14/14 |

Across roles, Claude averages 75.0% included-study recall per response and
covers all 10 study labels when its 12 runs are pooled. Gemini averages 20.8%
and covers four labels. GPT averages 89.2% and covers all 10 labels. The union
across all 36 responses covers all 10 included labels and all 14 PubMed IDs
associated with those clusters.

The role pattern is model-specific. Claude's researcher-role recall is higher
than its patient-role recall, but the review-use deviations are unevenly
distributed: two clinician runs, one researcher run, and no patient runs are
affected. Excluding the three deviating runs reduces Claude's overall
included-study recall from 75.0% (90/120) to 71.1% (64/90), without changing
the broad model ordering. With only four planned repetitions per cell, these
differences are descriptive rather than evidence of a general role effect.

Dunn 1991 appears in 32 of 36 responses and Kendig 1991 in 33. Bevilacqua 1997
is the least frequently retrieved included cluster, appearing in 9 responses.
It is the only included cluster missed by the pooled GPT patient and clinician
cells. Gemini misses six included clusters even after all 12 of its runs are
pooled: Bevilacqua 1996, Bevilacqua 1997, Kattwinkel 1993, Merritt 1991,
SUPPORT 2010, and Walti 1995.

The audit table contains 222 included response-study rows, 45 rows matched to
four Cochrane-excluded studies, 16 awaiting-classification POPART rows, seven
ongoing pro.LISA rows, 34 other observational-study rows, 26 other out-of-set
rows, and one unresolved click-test study. Fourteen resolved rows have
conflicting citation details.
