# CD001452 user-role experiment

This folder contains a three-condition retrieval-bias experiment based on
Cochrane review CD001452, *Venepuncture versus heel lance for blood sampling in
term neonates*.

- Clinical question: venepuncture versus heel lance for blood sampling in term
  neonates
- Included primary-study clusters: 8
- Source review:
  [`CD001452.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD001452.pdf)
- Source data:
  [`CD001452-SUP-06-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD001452-SUP-06-dataPackage.zip)

The substantive request is identical across conditions. Only the opening
sentence, which states the user's role, changes.

## Prompts

### Patient

> I’m a parent of a full-term newborn baby who needs a blood sample.
>
> I’m trying to understand whether taking blood from a vein with a needle
> (venepuncture) is better than using a heel lance for full-term newborn
> babies. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Clinician

> I’m a clinician caring for full-term newborn babies who need blood samples.
>
> I’m trying to understand whether taking blood from a vein with a needle
> (venepuncture) is better than using a heel lance for full-term newborn
> babies. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.
>
> List the primary studies in the end.

### Evidence-synthesis researcher

> I’m an evidence-synthesis researcher studying blood sampling in full-term
> newborn babies.
>
> I’m trying to understand whether taking blood from a vein with a needle
> (venepuncture) is better than using a heel lance for full-term newborn
> babies. Find individual primary studies on this. Do not use systematic
> reviews, meta-analyses, narrative reviews, committee opinions, practice
> guidelines, or editorials/comments.
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

`claude-patient-3.md` begins with search-process-like text concatenated to the
answer, and `claude-researcher-2.md` begins with a search-process handoff.
Eight Claude responses explicitly disclose using Cochrane or other review
reference lists to locate or cross-check studies:
`claude-clinician-2.md`, `claude-clinician-4.md`,
`claude-patient-1.md`, `claude-patient-3.md`,
`claude-researcher-1.md`, `claude-researcher-2.md`,
`claude-researcher-3.md`, and `claude-researcher-4.md`. That conflicts with
the prompt's source restriction. All planned runs remain in the primary
analysis, and the deviation is considered when interpreting Claude's recall.

## Study identification

The retrieved-study set is defined only by entries in a response's dedicated
terminal primary-study or reference-list block. Studies mentioned only in
narrative prose, summary tables, caveats after the list, link definitions, or
`Cited by:` metadata are not counted.

For Gemini, the bibliographic line immediately preceding each `Cited by:` line
in the final reference block is one candidate.
`gemini-clinician-3.md` instead uses four bullets under `Requested Primary
Studies`; those bullets define its terminal list. For GPT, numbered entries
under the last qualifying primary-study heading are candidates. Claude's
numbered entries under its final primary-study or reference heading are
candidates.

`claude-researcher-2.md` has no later consolidated list, so its numbered direct
studies and the explicitly listed Taksande study in the same cohesive
study-list block are retained. Taksande is classified as an ineligible
comparison because it has no heel-lance arm. By contrast, additional studies
mentioned only in post-list appraisal notes are not counted.

Every explicitly listed candidate is retained even when it is
Cochrane-excluded, outside the review set, ineligible for the requested
comparison, or bibliographically inaccurate. The Larsson EMLA trial is kept
separate from the included Larsson comparison because it randomizes EMLA
versus placebo before venepuncture and has no heel-lance arm. Citation
conflicts remain visible in the audit table.

The included RIS contains eight study clusters represented by eight unique
study labels. Included study-row recall and cluster recall are therefore
numerically identical. The RIS has six explicit PubMed IDs across five study
clusters; Larsson 1998 has two IDs across its primary and companion reports.
The PMID metric is cluster-associated coverage, not a claim that a response
cited every companion report or supplied the PMID explicitly.

## Reference data

- Source review:
  [`CD001452.pdf`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD001452.pdf)
- Source data:
  [`CD001452-SUP-06-dataPackage.zip`](../../Cochrane_reviews/source_reviews/2026_issue_7/CD001452-SUP-06-dataPackage.zip)

The analysis reads the included, excluded, and ongoing RIS exports directly
from the ZIP archive. The package contains eight included, four excluded, and
one ongoing study labels. It has no awaiting-classification RIS export.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD001452/analyze_cd001452_roles.py
```

The script validates the 36-file inventory and expected terminal-list entry
counts, requires every listed citation to resolve, validates every
Cochrane-classified label against the RIS exports, and writes
`cd001452_role_study_matches.csv`. The standard match table preserves the raw
reported citation, canonical candidate, source-review status, study label,
design, identity flags, and audit notes.

### Results

The 36 responses contain 214 terminal-list entries, producing 214
response-study rows. No terminal list contains duplicate reports requiring
within-response grouping. Included matches are summed over four runs. Mean
recall uses the eight included Cochrane study clusters as the denominator for
every response. Pooled coverage is the union across the four runs in one
model-role cell.

| Model | Role | List entries | Response-study rows | Included matches over 4 runs | Mean cluster/study-row recall per response | Pooled study coverage | Pooled cluster-associated PMID coverage |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude | Patient | 23 | 23 | 18 | 56.2% | 6/8 | 6/6 |
| Claude | Clinician | 23 | 23 | 17 | 53.1% | 6/8 | 6/6 |
| Claude | Researcher | 29 | 29 | 22 | 68.8% | 7/8 | 6/6 |
| Gemini | Patient | 12 | 12 | 10 | 31.2% | 4/8 | 5/6 |
| Gemini | Clinician | 13 | 13 | 12 | 37.5% | 6/8 | 6/6 |
| Gemini | Researcher | 12 | 12 | 11 | 34.4% | 4/8 | 5/6 |
| GPT | Patient | 33 | 33 | 28 | 87.5% | 7/8 | 6/6 |
| GPT | Clinician | 34 | 34 | 28 | 87.5% | 7/8 | 6/6 |
| GPT | Researcher | 35 | 35 | 28 | 87.5% | 7/8 | 6/6 |

Across roles, Claude averages 59.4% included-study recall per response and
covers seven of eight labels when its 12 runs are pooled. Gemini averages
34.4% and covers six labels. GPT retrieves the same seven included labels in
every run, averaging 87.5%. The union across all 36 responses covers seven of
eight labels. `Alcaraz Sanz 1998` is never retrieved. Because that cluster has
no explicit PMID in the source RIS, the pooled responses still cover all six
PMIDs associated with retrieved included clusters.

The role pattern is descriptive and differs by model. Researcher recall is
higher than patient recall by 12.5 percentage points for Claude and 3.1 points
for Gemini; all three GPT roles have identical recall. Across models, mean
researcher-role recall is 63.5%, compared with 59.4% for clinician and 58.3%
for patient responses. Researcher responses also have the longest terminal
lists: 76 entries, versus 70 for clinician and 68 for patient responses. With
four repetitions per cell, these are retrieval-pattern descriptions, not
evidence of a general causal role effect.

The eight Claude responses disclosing review-reference use retrieve 41 of 64
possible included matches, for 64.1% mean recall. The other four Claude
responses retrieve 16 of 32, for 50.0%. This limited sensitivity check does not
remove the collection-quality concern, and the overall model ordering remains
GPT, Claude, then Gemini.

Retrieval is concentrated in a core set. `Ogawa 2005` appears in all 36
responses, `Larsson 1998` in 33, `Shah 1997` in 30, and `Eriksson 1999` in 25.
The less frequently retrieved included studies are `Saththasivam 2009` in 19,
`Kvist 2002` in 17, and `Shrestha 2012` in 14. The best responses retrieve
seven of eight included clusters; the weakest retrieve two.

The audit table contains 174 included response-study rows, 29
Cochrane-excluded rows, 10 invalid-comparison rows, and one other out-of-set
row. No ongoing study is retrieved. The excluded rows are 16 instances of
`Logan 1999` and 13 of `Correcher 2012`. The invalid comparisons are four
Larsson EMLA citations, four Cavicchiolo sucrose-dose citations, and two
Taksande venepuncture-only citations. The one other out-of-set row is the
Lorey newborn-screening specimen-method study. Four resolved rows have
conflicting issue or page details and are marked with `identity_issue=1`.
