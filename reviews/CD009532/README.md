# CD009532 user-role experiment

This folder stores unchanged chatbot responses for a three-condition experiment
testing whether an explicitly stated user role affects study retrieval for Cochrane
review CD009532.

## Run inventory

| Chatbot | Configuration | Available repetitions | Status | Response filenames |
| --- | --- | ---: | --- | --- |
| Claude Sonnet 5 | Medium effort; thinking on | 4 per role | Complete | `claude-<role>-<replicate>.md` |
| Gemini 3.1 Pro | Extended thinking | 4 per role | Complete | `gemini-<role>-<replicate>.md` |
| ChatGPT 5.5 | Intelligence high | 4 per role | Complete | `gpt-<role>-<replicate>.md` |

The role values used in filenames are `patient`, `clinician`, and `researcher`.
The folder contains 36 response files in total: four repetitions for every chatbot
and role combination.

Model access details or generation settings not listed above have not been recorded
and should not be inferred. The response files should remain unchanged; experiment
metadata and documentation belong in this README rather than in the raw responses.

## Prompts

### Patient

> I’m a blood donor who has been told that my iron level is low or that I may not
> be able to donate because of low iron. I’m trying to understand whether taking
> iron supplements can improve iron stores and reduce the chance of being unable
> to donate because of low iron. Find individual primary studies on this. Do not
> use systematic reviews, meta-analyses, narrative reviews, committee opinions,
> practice guidelines, or editorials/comments.

### Clinician

> I’m a clinician caring for blood donors who have low iron levels or are deferred
> from donation because of low hemoglobin or iron deficiency. I’m trying to
> understand whether taking iron supplements can improve iron stores and reduce
> the chance of being unable to donate because of low iron. Find individual primary
> studies on this. Do not use systematic reviews, meta-analyses, narrative reviews,
> committee opinions, practice guidelines, or editorials/comments.

### Researcher

> I’m an evidence-synthesis researcher studying iron supplementation in blood
> donors. I’m trying to understand whether taking iron supplements can improve iron
> stores and reduce the chance of being unable to donate because of low iron. Find
> individual primary studies on this. Do not use systematic reviews, meta-analyses,
> narrative reviews, committee opinions, practice guidelines, or
> editorials/comments.

## Analysis

Run from the repository root:

```bash
python3 reviews/CD009532/analyze_cd009532_roles.py
```

The script validates all 36 response files and writes
`cd009532_role_study_matches.csv`. Citations are deduplicated at the Cochrane study
cluster level, so multiple reports from HEIRS, STRIDE, or another trial count once
per response. Included and excluded status is validated directly against
`CD009532-included.ris` and `CD009532-excluded.ris`; no `benchmark.json` is required
for this experiment. Study candidates listed as ongoing in the Cochrane data
package, including FORTE, are retained in the audit table but are not credited as
included-study retrievals.
