#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD015934 role experiment.

Each complete chatbot response is curated once at the study-cluster level.
Cochrane labels are validated against the included, excluded, and ongoing RIS
exports supplied with the review data package.
"""

from __future__ import annotations

import csv
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_ZIP = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_7"
    / "CD015934-SUP-07-dataPackage.zip"
)
MATCHES_PATH = REPO_ROOT / "data" / "reviews" / REVIEW_DIR.name / "cd015934_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
VALID_STATUSES = {
    "included",
    "cochrane_excluded",
    "cochrane_ongoing",
    "outside_observational",
    "outside_other",
    "unresolved",
}
RIS_MEMBERS = {
    "included": "CD015934-study-data/CD015934-included.ris",
    "cochrane_excluded": "CD015934-study-data/CD015934-excluded.ris",
    "cochrane_ongoing": "CD015934-study-data/CD015934-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD015934 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 10 Cochrane-included study clusters.
    "akbarpour": CandidateInfo(
        "Akbarpour 2010 bupropion trial",
        "included",
        "Akbarpour 2010",
        "double-blind placebo-controlled RCT",
    ),
    "brown": CandidateInfo(
        "Brown 2021 (Helping HAND 3)",
        "included",
        "Brown 2021",
        "cluster-randomized trial",
        "The Hecht 2019 protocol and Brown 2021 results report are one trial cluster.",
    ),
    "chan": CandidateInfo(
        "Chan 2020 NRT-formulation trial",
        "included",
        "Chan 2020",
        "cluster-randomized parallel study",
    ),
    "chen": CandidateInfo(
        "Chen 2013 nicotine-patch trial",
        "included",
        "Chen 2013",
        "double-blind active-comparator RCT",
    ),
    "gelkopf": CandidateInfo(
        "Gelkopf 2012 behavioral-reduction trial",
        "included",
        "Gelkopf 2012",
        "randomized controlled study",
    ),
    "hickman": CandidateInfo(
        "Hickman 2015 feasibility/replication trial",
        "included",
        "Hickman 2015",
        "randomized feasibility trial",
    ),
    "metse": CandidateInfo(
        "Metse 2017 multisite trial",
        "included",
        "Metse 2017",
        "multisite RCT",
        "The trial registrations, protocol, outcome report, and linked process "
        "analyses are grouped as one study cluster.",
    ),
    "prochaska": CandidateInfo(
        "Prochaska 2014 inpatient-psychiatry trial",
        "included",
        "Prochaska 2014",
        "RCT",
        "The NCT00136812 registry, primary outcome report, and Barnett "
        "cost-effectiveness report are grouped as one study cluster.",
    ),
    "stockings": CandidateInfo(
        "Stockings 2014 postdischarge-support trial",
        "included",
        "Stockings 2014",
        "RCT",
        "The Stockings 2011 protocol and 2014 outcome report are one study cluster.",
    ),
    "tavakoli": CandidateInfo(
        "Tavakoli-Ardakani 2023 cytisine trial",
        "included",
        "Tavakoli-Ardakani 2023",
        "open-label active-comparator RCT",
    ),

    # Study clusters explicitly excluded or still ongoing in CD015934.
    "bennett_stayquit": CandidateInfo(
        "Bennett 2017 / Kacmarek 2026 StayQuit pilot",
        "cochrane_excluded",
        "Bennett 2017",
        "single-arm pilot",
        "The source package excludes the StayQuit registry; several responses "
        "cite its 2026 results publication.",
    ),
    "bruguera_varenicline": CandidateInfo(
        "Bruguera 2018 varenicline trial (NCT03809897)",
        "cochrane_excluded",
        "Bruguera 2018",
        "withdrawn randomized trial registration",
    ),
    "das": CandidateInfo(
        "Das 2017 co-occurring-disorders analysis",
        "cochrane_excluded",
        "Das 2017",
        "pooled secondary analysis",
        "The report pools participant data from the included Hickman 2015 and "
        "Prochaska 2014 trials.",
    ),
    "japuntich_act": CandidateInfo(
        "Japuntich 2019 partial-hospital ACT trial (NCT03911960)",
        "cochrane_excluded",
        "Japuntich 2019",
        "partial-hospital trial registration",
    ),
    "peckham_scimitar": CandidateInfo(
        "SCIMITAR/SCIMITAR+",
        "cochrane_excluded",
        "Peckham 2019",
        "community-based RCT",
    ),
    "petersen_sceptre": CandidateInfo(
        "Petersen Williams 2025 SCEPTRE feasibility study",
        "cochrane_excluded",
        "Petersen Williams 2025",
        "randomized feasibility-study protocol",
    ),
    "prochaska_nct009": CandidateInfo(
        "Prochaska NCT00968513 brief-versus-extended treatment trial",
        "cochrane_excluded",
        "Prochaska 2009",
        "RCT registry/conference report",
    ),
    "schuck": CandidateInfo(
        "Schuck 2016 posthospital NRT analysis",
        "cochrane_excluded",
        "Schuck 2016",
        "secondary cohort analysis",
    ),
    "bennett_digital": CandidateInfo(
        "Bennett 2020 / Bennett 2026 digital-intervention pilot",
        "cochrane_ongoing",
        "Bennett 2020",
        "randomized pilot trial",
        "The source package classifies the registry as ongoing; responses cite "
        "the post-review 2026 results publication.",
    ),

    # Other identifiable primary-study candidates named in the responses.
    "baker_psychotic": CandidateInfo(
        "Baker 2006 psychotic-disorder cessation trial",
        "outside_other",
        design="community-based RCT",
    ),
    "ballbe_quitmental": CandidateInfo(
        "061 QuitMental trial",
        "outside_other",
        design="pragmatic postdischarge RCT",
        note=(
            "The Martínez 2022 participation analysis, trial protocol, and 2024 "
            "outcome report are grouped as one trial."
        ),
    ),
    "brunette_medicaid": CandidateInfo(
        "Brunette 2018 Medicaid-beneficiary trial",
        "outside_other",
        design="community-mental-health RCT",
    ),
    "chen_daycare": CandidateInfo(
        "Chen 2002 psychiatric day-care study",
        "outside_other",
        design="non-equivalent controlled study",
    ),
    "chou_2004": CandidateInfo(
        "Chou 2004 nicotine-patch study",
        "outside_other",
        design="controlled day-care study",
    ),
    "chou_2015": CandidateInfo(
        "Chou 2015 smoking-reduction programme analysis",
        "outside_other",
        design="programme cohort analysis",
        note=(
            "The response notes possible overlap with another Taiwanese "
            "programme, but the exact study-cluster relationship is unresolved."
        ),
    ),
    "duffy_2010": CandidateInfo(
        "Duffy 2010 inpatient Tobacco Tactics study",
        "outside_other",
        design="general-hospital comparative implementation study",
    ),
    "duffy_2015": CandidateInfo(
        "Duffy 2015 psychiatric-inpatient Tobacco Tactics study",
        "outside_other",
        design="nonrandomized implementation study",
    ),
    "evins_bupropion": CandidateInfo(
        "Evins 2004 schizophrenia trial follow-up",
        "outside_other",
        design="follow-up of an outpatient cessation trial",
    ),
    "evins_varenicline": CandidateInfo(
        "Evins varenicline maintenance trial",
        "outside_other",
        design="outpatient relapse-prevention RCT",
    ),
    "ganhao": CandidateInfo(
        "Ganhão 2021 inpatient NRT evaluation",
        "outside_observational",
        design="prospective feasibility evaluation",
    ),
    "hall_outpatient": CandidateInfo(
        "Hall depressed-outpatient cessation trial",
        "unresolved",
        design="outpatient trial",
        note=(
            "The response does not provide enough bibliographic detail to "
            "resolve a unique report."
        ),
    ),
    "hasnaoui": CandidateInfo(
        "Hasnaoui and Ramachandran 2021 NRT-use audit",
        "outside_observational",
        design="retrospective inpatient audit",
    ),
    "helping_hand_1": CandidateInfo(
        "Helping HAND 1",
        "outside_other",
        design="general-hospital RCT",
    ),
    "helping_hand_2": CandidateInfo(
        "Helping HAND 2",
        "outside_other",
        design="general-hospital RCT",
        note=(
            "Responses also identify this trial through the Rigotti 2014 "
            "sustained-care report."
        ),
    ),
    "lappin": CandidateInfo(
        "Lappin 2020 targeted inpatient intervention",
        "outside_other",
        design="pre-post system-change study",
    ),
    "mcfall": CandidateInfo(
        "McFall 2010 PTSD cessation trial",
        "outside_other",
        design="outpatient RCT",
    ),
    "olando": CandidateInfo(
        "Olando 2022 Kenya behavioral-intervention trial",
        "outside_other",
        design="controlled clinical trial",
    ),
    "parker": CandidateInfo(
        "Parker 2012 tailored tobacco-dependence service",
        "outside_other",
        design="pragmatic service pilot",
    ),
    "prochaska_2004": CandidateInfo(
        "Prochaska 2004 inpatient tobacco-treatment audit",
        "outside_observational",
        design="retrospective chart review",
    ),
    "prochaska_2006": CandidateInfo(
        "Prochaska 2006 return-to-smoking cohort",
        "outside_observational",
        design="prospective cohort",
    ),
    "stop_varenicline": CandidateInfo(
        "STOP varenicline trial",
        "outside_other",
        design="general-medical-inpatient trial",
    ),
    "t_susc": CandidateInfo(
        "T-SusC tablet-based sustained-care trial",
        "unresolved",
        design="trial protocol",
        note=(
            "The response gives no registration number or citation from which "
            "to resolve the study."
        ),
    ),
    "wye_implementation": CandidateInfo(
        "Wye 2017 nicotine-treatment implementation trial",
        "outside_other",
        design="clinical-practice-change trial",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Return candidate keys while making duplicate annotations an error."""

    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate candidate key in annotation: {keys}")
    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions(
        "prochaska",
        "metse",
        "stockings",
        "brown",
        "gelkopf",
        "evins_bupropion",
        "petersen_sceptre",
        "ballbe_quitmental",
    ),
    "claude-patient-2": mentions(
        "prochaska",
        "metse",
        "stockings",
        "duffy_2010",
        "das",
        "bennett_digital",
        "peckham_scimitar",
    ),
    "claude-patient-3": mentions(
        "prochaska",
        "stockings",
        "metse",
        "brown",
        "brunette_medicaid",
        "ballbe_quitmental",
        "baker_psychotic",
        "bennett_digital",
        "petersen_sceptre",
        "evins_varenicline",
    ),
    "claude-patient-4": mentions(
        "prochaska",
        "stockings",
        "metse",
        "schuck",
        "brown",
        "prochaska_2004",
        "peckham_scimitar",
    ),
    "claude-clinician-1": mentions(
        "prochaska",
        "stockings",
        "metse",
        "helping_hand_2",
        "brown",
        "bennett_digital",
        "ganhao",
        "baker_psychotic",
        "hall_outpatient",
        "peckham_scimitar",
        "prochaska_nct009",
    ),
    "claude-clinician-2": mentions(
        "prochaska_2004",
        "prochaska",
        "stockings",
        "metse",
        "brown",
        "bennett_digital",
        "ballbe_quitmental",
        "baker_psychotic",
        "mcfall",
        "helping_hand_1",
        "helping_hand_2",
        "peckham_scimitar",
    ),
    "claude-clinician-3": mentions(
        "metse",
        "stockings",
        "prochaska",
        "brown",
        "bennett_digital",
        "ganhao",
        "wye_implementation",
        "t_susc",
    ),
    "claude-clinician-4": mentions(
        "prochaska",
        "stockings",
        "metse",
        "das",
        "ballbe_quitmental",
        "bennett_digital",
    ),
    "claude-researcher-1": mentions(
        "prochaska",
        "metse",
        "stockings",
        "hickman",
        "bennett_digital",
        "prochaska_2004",
        "das",
        "schuck",
        "peckham_scimitar",
        "brunette_medicaid",
    ),
    "claude-researcher-2": mentions(
        "prochaska_2004",
        "prochaska",
        "das",
        "stockings",
        "metse",
        "ganhao",
        "ballbe_quitmental",
        "bruguera_varenicline",
    ),
    "claude-researcher-3": mentions(
        "prochaska",
        "stockings",
        "metse",
        "brown",
        "hickman",
        "schuck",
        "bennett_digital",
        "hasnaoui",
        "ganhao",
        "t_susc",
        "japuntich_act",
        "peckham_scimitar",
        "stop_varenicline",
    ),
    "claude-researcher-4": mentions(
        "prochaska",
        "stockings",
        "metse",
        "parker",
        "lappin",
        "brown",
        "ballbe_quitmental",
        "peckham_scimitar",
    ),
    "gemini-patient-1": mentions("brown", "prochaska"),
    "gemini-patient-2": mentions("brown", "prochaska"),
    "gemini-patient-3": mentions("brown", "metse", "prochaska"),
    "gemini-patient-4": mentions("prochaska", "brown", "stockings"),
    "gemini-clinician-1": mentions("prochaska", "brown", "stockings"),
    "gemini-clinician-2": mentions("prochaska", "brown", "olando"),
    "gemini-clinician-3": mentions("brown", "prochaska", "das"),
    "gemini-clinician-4": mentions("brown", "prochaska", "lappin"),
    "gemini-researcher-1": mentions("brown", "prochaska", "olando"),
    "gemini-researcher-2": mentions("brown", "prochaska", "tavakoli"),
    "gemini-researcher-3": mentions("prochaska", "brown"),
    "gemini-researcher-4": mentions("prochaska", "brown"),
    "gpt-patient-1": mentions(
        "prochaska",
        "metse",
        "brown",
        "stockings",
        "hickman",
        "akbarpour",
        "tavakoli",
        "chen",
        "chan",
        "gelkopf",
    ),
    "gpt-patient-2": mentions(
        "prochaska",
        "metse",
        "brown",
        "stockings",
        "hickman",
        "gelkopf",
        "akbarpour",
        "chen",
        "chan",
        "tavakoli",
    ),
    "gpt-patient-3": mentions(
        "prochaska",
        "stockings",
        "hickman",
        "metse",
        "brown",
        "bennett_digital",
        "akbarpour",
        "chen",
        "chan",
        "tavakoli",
        "gelkopf",
    ),
    "gpt-patient-4": mentions(
        "prochaska",
        "stockings",
        "hickman",
        "metse",
        "brown",
        "bennett_digital",
        "akbarpour",
        "gelkopf",
        "chen",
        "tavakoli",
        "chou_2004",
    ),
    "gpt-clinician-1": mentions(
        "prochaska",
        "metse",
        "brown",
        "stockings",
        "hickman",
        "akbarpour",
        "tavakoli",
        "chen",
        "chou_2004",
        "bennett_digital",
        "bennett_stayquit",
        "gelkopf",
    ),
    "gpt-clinician-2": mentions(
        "prochaska",
        "hickman",
        "stockings",
        "metse",
        "brown",
        "bennett_digital",
        "akbarpour",
        "chen",
        "chan",
        "tavakoli",
        "gelkopf",
    ),
    "gpt-clinician-3": mentions(
        "prochaska",
        "metse",
        "brown",
        "stockings",
        "hickman",
        "akbarpour",
        "gelkopf",
        "chen",
        "chan",
        "tavakoli",
        "bennett_digital",
        "bennett_stayquit",
    ),
    "gpt-clinician-4": mentions(
        "prochaska",
        "stockings",
        "hickman",
        "prochaska_nct009",
        "metse",
        "brown",
        "bennett_digital",
        "prochaska_2006",
        "gelkopf",
        "chen",
        "akbarpour",
        "tavakoli",
        "chou_2004",
    ),
    "gpt-researcher-1": mentions(
        "prochaska",
        "hickman",
        "stockings",
        "metse",
        "brown",
        "gelkopf",
        "chen",
        "akbarpour",
        "tavakoli",
        "chou_2015",
    ),
    "gpt-researcher-2": mentions(
        "prochaska",
        "stockings",
        "hickman",
        "metse",
        "brown",
        "bennett_digital",
        "akbarpour",
        "gelkopf",
        "chen",
        "chan",
        "tavakoli",
        "bennett_stayquit",
        "chou_2004",
        "prochaska_nct009",
    ),
    "gpt-researcher-3": mentions(
        "prochaska",
        "stockings",
        "hickman",
        "metse",
        "brown",
        "bennett_digital",
        "akbarpour",
        "gelkopf",
        "chen",
        "tavakoli",
        "bennett_stayquit",
        "chou_2004",
        "chen_daycare",
    ),
    "gpt-researcher-4": mentions(
        "prochaska",
        "hickman",
        "stockings",
        "metse",
        "brown",
        "bennett_digital",
        "chou_2004",
        "chen",
        "akbarpour",
        "tavakoli",
        "gelkopf",
        "duffy_2015",
        "bennett_stayquit",
    ),
}


IDENTITY_NOTES = {
    ("claude-patient-2", "metse"): (
        "The response attributes the Metse 2017 report to Segan and Bowman; "
        "Metse is the lead author."
    ),
    ("claude-patient-2", "bennett_digital"): (
        "The response attributes the 2026 digital-pilot report to White; "
        "Bennett is the lead author."
    ),
    ("claude-patient-3", "baker_psychotic"): (
        "The response attributes the 2006 psychotic-disorder RCT to White; "
        "Baker is the lead author."
    ),
    ("claude-patient-4", "schuck"): (
        "The response attaches the Schuck 2016 title to a Prochaska/Fletcher/"
        "Prins citation."
    ),
    ("claude-patient-4", "brown"): (
        "The response attributes Helping HAND 3 to Prins and Rogers; Brown is "
        "the lead author."
    ),
    ("claude-clinician-1", "brown"): (
        "The response attributes Helping HAND 3 to Japuntich, Hammett, and "
        "Rogers; Brown is the lead author."
    ),
    ("claude-clinician-1", "bennett_digital"): (
        "The response attributes the 2026 digital-pilot report to White; "
        "Bennett is the lead author."
    ),
    ("claude-clinician-2", "metse"): (
        "The response gives a conflicting author list for the Metse 2017 report, "
        "including Svanes."
    ),
    ("claude-clinician-2", "bennett_digital"): (
        "The response attributes the 2026 digital-pilot report to White; "
        "Bennett is the lead author."
    ),
    ("claude-clinician-3", "bennett_digital"): (
        "The response attributes the 2026 digital-pilot report to White; "
        "Bennett is the lead author."
    ),
    ("claude-clinician-4", "das"): (
        "The response attributes the Das 2017 report to Hickman and gives a "
        "conflicting title, journal, and year."
    ),
    ("claude-researcher-1", "das"): (
        "The response attributes the Das 2017 pooled analysis to Prochaska."
    ),
    ("claude-researcher-2", "das"): (
        "The response attributes the Das 2017 pooled analysis to Prochaska."
    ),
    ("claude-researcher-2", "metse"): (
        "The response gives Nicotine & Tobacco Research as the possible journal "
        "for the Metse 2017 Australian and New Zealand Journal of Psychiatry report."
    ),
    ("claude-researcher-3", "schuck"): (
        "The response attributes the Schuck 2016 report to Prochaska."
    ),
    ("claude-researcher-4", "prochaska"): (
        "The response attributes the Barnett 2015 companion cost-effectiveness "
        "report to Prochaska."
    ),
    ("claude-researcher-4", "brown"): (
        "The response attributes Helping HAND 3 to Rogers; Brown is the lead author."
    ),
    ("gpt-patient-1", "chan"): (
        "The link attached to the Chan 2020 entry resolves to an unrelated article."
    ),
    ("gpt-researcher-2", "chan"): (
        "The link attached to the Chan 2020 entry resolves to a secondary review "
        "rather than the cited primary report."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-patient-2", "metse"): "Segan, Bowman, et al. 2017",
    ("claude-patient-2", "bennett_digital"): "White et al. 2026 digital pilot",
    ("claude-patient-3", "baker_psychotic"): (
        "White et al., A Randomized Controlled Trial of a Smoking Cessation "
        "Intervention Among People With a Psychotic Disorder"
    ),
    ("claude-patient-4", "schuck"): (
        "Prochaska/Fletcher/Prins, Smokers with serious mental illness and "
        "requests for nicotine replacement therapy post-hospitalisation"
    ),
    ("claude-patient-4", "brown"): "Prins/Rogers et al. 2021 Helping HAND 3",
    ("claude-clinician-1", "brown"): "Japuntich, Hammett, Rogers et al. 2021",
    ("claude-clinician-1", "bennett_digital"): "White et al. 2026 digital pilot",
    ("claude-clinician-2", "metse"): "Metse, Wye, Svanes et al. 2017",
    ("claude-clinician-2", "bennett_digital"): "White et al. 2026 digital pilot",
    ("claude-clinician-3", "bennett_digital"): "White et al. 2026 digital pilot",
    ("claude-clinician-4", "das"): (
        "Hickman et al. 2015, Treating Tobacco Dependence in Adults with "
        "Co-Occurring Acute Psychiatric and Addictive Disorders"
    ),
    ("claude-researcher-1", "das"): (
        "Prochaska et al., Treating Smoking in Adults with Co-Occurring Acute "
        "Psychiatric and Addictive Disorders"
    ),
    ("claude-researcher-2", "das"): (
        "Prochaska et al., Treating smoking in adults with co-occurring acute "
        "psychiatric and addictive disorders"
    ),
    ("claude-researcher-2", "metse"): (
        "Metse et al. 2017, Nicotine & Tobacco Research / related journal"
    ),
    ("claude-researcher-3", "schuck"): (
        "Prochaska et al., Smokers with serious mental illness and requests for "
        "nicotine replacement therapy post-hospitalisation"
    ),
    ("claude-researcher-4", "prochaska"): (
        "Prochaska et al., Cost-effectiveness of smoking cessation treatment "
        "initiated during psychiatric hospitalization"
    ),
    ("claude-researcher-4", "brown"): "Rogers et al. 2021 Helping HAND 3",
    ("gpt-patient-1", "chan"): "Chan et al. 2020 with unrelated OUCI link",
    ("gpt-researcher-2", "chan"): (
        "Chan et al. 2020 with a secondary-review ResearchGate link"
    ),
}


def ris_study_labels(member: str) -> set[str]:
    """Read unique Cochrane study labels from an RIS export in the source ZIP."""

    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        text = archive.read(member).decode("utf-8-sig")
    return {
        match.group(1).strip()
        for match in re.finditer(r"^NS  - (.+)$", text, re.MULTILINE)
    }


def validate_inputs() -> None:
    """Validate response coverage, candidate keys, and Cochrane study labels."""

    expected_runs = {
        f"{model}-{role}-{replicate}"
        for model in MODELS
        for role in ROLES
        for replicate in range(1, 5)
    }
    if set(RUN_CANDIDATES) != expected_runs:
        missing = sorted(expected_runs - set(RUN_CANDIDATES))
        extra = sorted(set(RUN_CANDIDATES) - expected_runs)
        raise ValueError(f"Run annotation mismatch; missing={missing}, extra={extra}")

    expected_files = {f"{run_id}.md" for run_id in expected_runs}
    available_files = {
        path.name for path in REVIEW_DIR.glob("*.md") if path.name != "README.md"
    }
    if available_files != expected_files:
        missing = sorted(expected_files - available_files)
        stale = sorted(available_files - expected_files)
        raise ValueError(f"Response file mismatch; missing={missing}, stale={stale}")
    empty_files = sorted(
        filename
        for filename in expected_files
        if not (REVIEW_DIR / filename).read_text(encoding="utf-8").strip()
    )
    if empty_files:
        raise ValueError(f"Empty response files: {empty_files}")

    status_labels = {
        status: ris_study_labels(member) for status, member in RIS_MEMBERS.items()
    }
    for run_id, keys in RUN_CANDIDATES.items():
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate candidate key in {run_id}")
        unknown = sorted(set(keys) - set(CANDIDATES))
        if unknown:
            raise ValueError(f"Unknown candidate keys in {run_id}: {unknown}")

    annotated_pairs = {
        (run_id, key) for run_id, keys in RUN_CANDIDATES.items() for key in keys
    }
    used_candidates = {key for _, key in annotated_pairs}
    unused_candidates = sorted(set(CANDIDATES) - used_candidates)
    if unused_candidates:
        raise ValueError(f"Unused candidate annotations: {unused_candidates}")
    invalid_statuses = sorted(
        {candidate.status for candidate in CANDIDATES.values()} - VALID_STATUSES
    )
    if invalid_statuses:
        raise ValueError(f"Invalid candidate statuses: {invalid_statuses}")
    if set(IDENTITY_NOTES) != set(REPORTED_CITATION_OVERRIDES):
        raise ValueError("Identity notes and reported-citation overrides differ")
    stale_identity_notes = sorted(set(IDENTITY_NOTES) - annotated_pairs)
    if stale_identity_notes:
        raise ValueError(f"Stale identity annotations: {stale_identity_notes}")

    for candidate in CANDIDATES.values():
        if candidate.status in status_labels:
            if candidate.cochrane_label not in status_labels[candidate.status]:
                raise ValueError(
                    f"{candidate.status} label not in RIS: {candidate.cochrane_label}"
                )

    mapped_included = {
        candidate.cochrane_label
        for candidate in CANDIDATES.values()
        if candidate.status == "included"
    }
    if mapped_included != status_labels["included"]:
        missing = sorted(status_labels["included"] - mapped_included)
        stale = sorted(mapped_included - status_labels["included"])
        raise ValueError(
            f"Included candidate coverage mismatch; missing={missing}, stale={stale}"
        )


def build_match_rows() -> list[dict[str, str | int]]:
    """Build one row per unique study-cluster candidate named in each response."""

    validate_inputs()
    rows: list[dict[str, str | int]] = []
    for run_id in sorted(RUN_CANDIDATES):
        model, role_id, replicate_text = run_id.split("-")
        for key in RUN_CANDIDATES[run_id]:
            candidate = CANDIDATES[key]
            identity_note = IDENTITY_NOTES.get((run_id, key), "")
            notes = "; ".join(
                value for value in (identity_note, candidate.note) if value
            )
            rows.append(
                {
                    "run_id": run_id,
                    "model": model,
                    "role_id": role_id,
                    "replicate": int(replicate_text),
                    "source_file": f"reviews/CD015934/{run_id}.md",
                    "reported_citation": REPORTED_CITATION_OVERRIDES.get(
                        (run_id, key), candidate.label
                    ),
                    "canonical_candidate": candidate.label,
                    "ground_truth_status": candidate.status,
                    "cochrane_study_label": candidate.cochrane_label,
                    "design": candidate.design,
                    "identity_issue": int(bool(identity_note)),
                    "notes": notes,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write the non-empty audit table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Regenerate the curated CD015934 study-cluster match table."""

    rows = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    status_counts = Counter(str(row["ground_truth_status"]) for row in rows)
    retrieved_included = {
        str(row["cochrane_study_label"])
        for row in rows
        if row["ground_truth_status"] == "included"
    }
    all_included = ris_study_labels(RIS_MEMBERS["included"])
    print(f"Runs: {len(RUN_CANDIDATES)}")
    print(f"Study-cluster candidates: {len(rows)}")
    print(
        "Statuses: "
        + ", ".join(
            f"{status}={count}" for status, count in sorted(status_counts.items())
        )
    )
    print(
        f"Included study clusters retrieved: {len(retrieved_included)}/"
        f"{len(all_included)}"
    )
    print(
        "Missed included clusters: "
        + (", ".join(sorted(all_included - retrieved_included)) or "none")
    )
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
