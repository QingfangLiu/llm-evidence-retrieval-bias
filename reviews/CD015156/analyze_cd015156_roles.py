#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD015156 role experiment.

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
    / "CD015156-SUP-07-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd015156_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
RIS_MEMBERS = {
    "included": "CD015156-study-data/CD015156-included.ris",
    "cochrane_excluded": "CD015156-study-data/CD015156-excluded.ris",
    "cochrane_ongoing": "CD015156-study-data/CD015156-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD015156 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 10 Cochrane-included study clusters.
    "alfaro": CandidateInfo(
        "Alfaro-Santafé 2021",
        "included",
        "Alfaro-Santafa 2021",
        "RCT",
        "The registry record and journal report are one study cluster.",
    ),
    "james": CandidateInfo(
        "James 2016",
        "included",
        "James 2016",
        "factorial RCT",
        "The 2010 protocol, 2015 baseline analysis, conference report, and 2016 "
        "results paper are represented by one study cluster.",
    ),
    "kuyucu": CandidateInfo(
        "Kuyucu 2017",
        "included",
        "Kuyucu 2017",
        "sham-controlled RCT",
    ),
    "nakase": CandidateInfo(
        "Nakase 2020",
        "included",
        "Nakase 2020",
        "double-blind RCT",
        "The 2016 conference abstract and 2020 full report are represented by "
        "one study cluster.",
    ),
    "perhamre_2011a": CandidateInfo(
        "Perhamre 2011a heel-cup crossover trial",
        "included",
        "Perhamre 2011a",
        "randomized crossover trial",
    ),
    "perhamre_2012": CandidateInfo(
        "Perhamre 2012 heel-pad study",
        "included",
        "Perhamre 2012",
        "comparative mechanistic study",
    ),
    "reesman": CandidateInfo(
        "Reesman 2024 (NCT03606980)",
        "included",
        "Reesman 2024",
        "terminated three-arm RCT",
    ),
    "sweeney": CandidateInfo(
        "Sweeney 2023 barefoot-athlete brace trial",
        "included",
        "Sweeney 2023",
        "RCT",
        "The 2022 conference report and 2023 journal report are one study cluster.",
    ),
    "topol": CandidateInfo(
        "Topol 2011",
        "included",
        "Topol 2011",
        "randomized comparative trial",
    ),
    "wiegerinck": CandidateInfo(
        "Wiegerinck 2016",
        "included",
        "Wiegerinck 2016",
        "three-arm pragmatic RCT",
    ),

    # Cochrane-excluded studies retrieved in at least one response.
    "feyzioglu": CandidateInfo(
        "Feyzioğlu custom-insole study",
        "cochrane_excluded",
        "Feyzioğlu 2018",
        "single-group pre/post study",
        "The 2018 registry record and 2021 publication are one study cluster.",
    ),
    "gerulis": CandidateInfo(
        "Gerulis 2004",
        "cochrane_excluded",
        "Gerulis 2004",
        "nonrandomized comparative cohort",
    ),
    "lucciani": CandidateInfo(
        "Lucciani cast-versus-rest trial (NCT02824172)",
        "cochrane_excluded",
        "Lucciani 2016",
        "unreported RCT",
    ),
    "perhamre_2011b": CandidateInfo(
        "Perhamre 2011b insole study",
        "cochrane_excluded",
        "Perhamre 2011 (b)",
        "cohort study",
    ),
    "rathleff_2020": CandidateInfo(
        "Rathleff 2020 activity-modification cohort",
        "cochrane_excluded",
        "Rathleff 2020",
        "prospective cohort",
        "The 2024 prognostic reanalysis of the Osgood-Schlatter cohort is grouped "
        "with the original 2020 study.",
    ),
    "university_delaware": CandidateInfo(
        "Hanlon 2026 Sever-disease feasibility cohort (NCT04816188)",
        "cochrane_excluded",
        "University  of Delaware 2021",
        "single-cohort feasibility study",
        "The 2026 publication reports the cohort registered in 2021.",
    ),
    "wu": CandidateInfo(
        "Wu 2022",
        "cochrane_excluded",
        "Wu 2022",
        "double-blind RCT",
    ),

    # Cochrane-ongoing studies retrieved in at least one response.
    "carl": CandidateInfo(
        "Carl 2025 (NCT01826071)",
        "cochrane_ongoing",
        "Carl 2025",
        "registered three-arm RCT",
    ),
    "krommes": CandidateInfo(
        "Krommes 2025 SOGOOD trial",
        "cochrane_ongoing",
        "Krommes 2025",
        "RCT reported as a conference abstract",
        "The source package classifies SOGOOD as ongoing even though responses "
        "cite its 2025 conference-abstract results.",
    ),

    # Identifiable primary-study candidates outside the Cochrane study set.
    "aiis_series": CandidateInfo(
        "Anterior inferior iliac spine avulsion five-case series",
        "outside_observational",
        design="case series",
    ),
    "bezuglov": CandidateInfo(
        "Bezuglov 2020 youth-soccer cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "bone_stimulation": CandidateInfo(
        "Iliac-crest apophysitis bone-stimulation case report",
        "outside_observational",
        design="two-patient case report",
    ),
    "canale": CandidateInfo(
        "Canale and Williams 1992 Iselin-disease series",
        "outside_observational",
        design="case series",
    ),
    "clancy": CandidateInfo(
        "Clancy and Foltz 1976 iliac-apophysitis series",
        "outside_observational",
        design="case series",
    ),
    "danneberg": CandidateInfo(
        "Danneberg 2017 autologous-conditioned-plasma cases",
        "outside_observational",
        design="two-patient case report",
    ),
    "duperron": CandidateInfo(
        "Duperron 2016 cast-immobilization cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "egorova": CandidateInfo(
        "Egorova 2025 osteopathic-treatment study",
        "outside_other",
        design="randomized study",
    ),
    "emelin": CandidateInfo(
        "Emelin 2025 iontophoresis/interferential-therapy study",
        "outside_other",
        design="randomized three-group study",
    ),
    "gazya": CandidateInfo(
        "Abo Gazya 2014 shock-wave-versus-interferential study",
        "outside_other",
        design="comparative intervention study",
    ),
    "guszczyn_2023": CandidateInfo(
        "Guszczyn 2023 LR-PRP cohort",
        "outside_observational",
        design="prospective cohort",
    ),
    "guszczyn_2024": CandidateInfo(
        "Guszczyn 2024 LR-PRP duration study",
        "outside_observational",
        design="observational treatment study",
    ),
    "ikeda": CandidateInfo(
        "Ikeda 2026 passive-movement experiment",
        "outside_other",
        design="randomized within-person experiment",
    ),
    "kaya": CandidateInfo(
        "Kaya 2013 long-term Osgood-Schlatter study",
        "outside_observational",
        design="comparative cohort",
    ),
    "kimura": CandidateInfo(
        "Kimura 2019 greater-trochanter series",
        "outside_observational",
        design="four-patient case series",
    ),
    "levine": CandidateInfo(
        "Levine and Kashyap 1981 conservative-treatment study",
        "outside_observational",
        design="older comparative study",
    ),
    "lohrer_osd": CandidateInfo(
        "Lohrer 2012 Osgood-Schlatter ESWT study",
        "outside_observational",
        design="retrospective pilot study",
    ),
    "lohrer_sever": CandidateInfo(
        "Lohrer 2015 calcaneal-apophysitis ESWT study",
        "outside_observational",
        design="case series",
    ),
    "micheli": CandidateInfo(
        "Micheli and Ireland 1987 calcaneal-apophysitis series",
        "outside_observational",
        design="retrospective case series",
    ),
    "nct06993363": CandidateInfo(
        "NCT06993363 Osgood-Schlatter kinesiotaping trial",
        "outside_other",
        design="registered RCT",
    ),
    "nikpay": CandidateInfo(
        "Nikpay 2026 Iselin-disease cohort",
        "outside_observational",
        design="prospective nonrandomized cohort",
    ),
    "quadriceps_release": CandidateInfo(
        "2025 quadriceps-release rehabilitation cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "rectus_femoris_avulsion": CandidateInfo(
        "Rectus-femoris-origin avulsion seven-case series",
        "outside_observational",
        design="case series",
    ),
    "sailly": CandidateInfo(
        "Sailly 2015 pubic-apophysitis series",
        "outside_observational",
        design="retrospective case series",
    ),
    "shafshak": CandidateInfo(
        "Shafshak and Amer 2023 focused-ESWT series",
        "outside_observational",
        design="retrospective case series",
        note="One mixed cohort included 15 Osgood-Schlatter and seven "
        "Sever-disease patients.",
    ),
    "sullivan": CandidateInfo(
        "Sullivan 2025 iliac-crest injury case",
        "outside_observational",
        design="case report",
    ),
    "sylvester": CandidateInfo(
        "Sylvester and Hennrikus 2015 Iselin-disease series",
        "outside_observational",
        design="retrospective case series",
    ),
    "thapa": CandidateInfo(
        "Thapa 2025 PRP-versus-dextrose study",
        "outside_observational",
        design="retrospective comparative cohort",
    ),
    "valentino": CandidateInfo(
        "Valentino 2012 Sinding-Larsen-Johansson case",
        "outside_observational",
        design="case report",
    ),
    "van_leeuwen": CandidateInfo(
        "van Leeuwen 2021 general-practice cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "volpi": CandidateInfo(
        "Volpi 2021 lesser-trochanter avulsion series",
        "outside_observational",
        design="retrospective case series",
    ),
    "vomer": CandidateInfo(
        "Vomer 2026 iliac-apophysitis case",
        "outside_observational",
        design="case report",
    ),
    "yachaoui": CandidateInfo(
        "Yachaoui 2024 calcaneal-apophysitis case",
        "outside_observational",
        design="case report",
    ),
    "young": CandidateInfo(
        "Young and Safran 2015 greater-trochanter case",
        "outside_observational",
        design="case report",
    ),

    # Citation too incomplete to resolve confidently.
    "bourke": CandidateInfo(
        "Bourke custom-orthotic study",
        "unresolved",
        design="reported orthotic comparison",
        note="No title, year, or other bibliographic details were supplied.",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first substantive appearance in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions(
        "rathleff_2020",
        "krommes",
        "quadriceps_release",
        "topol",
        "nakase",
        "wu",
        "guszczyn_2023",
        "guszczyn_2024",
        "thapa",
        "wiegerinck",
        "james",
        "alfaro",
        "sweeney",
        "aiis_series",
        "rectus_femoris_avulsion",
    ),
    "claude-patient-2": mentions(
        "nakase",
        "wu",
        "rathleff_2020",
        "krommes",
        "guszczyn_2023",
        "guszczyn_2024",
        "thapa",
        "quadriceps_release",
        "wiegerinck",
        "james",
        "alfaro",
        "sweeney",
    ),
    "claude-patient-3": mentions(
        "krommes",
        "rathleff_2020",
        "wu",
        "nakase",
        "topol",
        "guszczyn_2023",
        "thapa",
        "alfaro",
        "james",
        "clancy",
        "rectus_femoris_avulsion",
    ),
    "claude-patient-4": mentions(
        "krommes",
        "rathleff_2020",
        "bezuglov",
        "wu",
        "guszczyn_2023",
        "guszczyn_2024",
        "thapa",
        "danneberg",
        "egorova",
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "james",
        "wiegerinck",
        "alfaro",
        "sweeney",
        "kuyucu",
        "bourke",
        "shafshak",
        "bone_stimulation",
    ),
    "claude-clinician-1": mentions(
        "krommes",
        "wu",
        "nakase",
        "topol",
        "lohrer_osd",
        "shafshak",
        "gazya",
        "wiegerinck",
        "james",
        "alfaro",
        "perhamre_2011a",
        "perhamre_2011b",
        "perhamre_2012",
        "sweeney",
    ),
    "claude-clinician-2": mentions(
        "bourke",
        "krommes",
        "topol",
        "nakase",
        "wu",
        "guszczyn_2023",
        "guszczyn_2024",
        "lohrer_osd",
        "shafshak",
        "wiegerinck",
        "james",
        "perhamre_2011a",
        "kuyucu",
        "gazya",
        "alfaro",
        "perhamre_2011b",
        "perhamre_2012",
        "sweeney",
    ),
    "claude-clinician-3": mentions(
        "wiegerinck",
        "james",
        "alfaro",
        "sweeney",
        "nakase",
        "wu",
        "topol",
        "guszczyn_2023",
        "guszczyn_2024",
        "danneberg",
        "thapa",
        "krommes",
        "lohrer_osd",
        "shafshak",
        "carl",
        "reesman",
    ),
    "claude-clinician-4": mentions(
        "wu",
        "nakase",
        "topol",
        "guszczyn_2023",
        "guszczyn_2024",
        "thapa",
        "rathleff_2020",
        "bezuglov",
        "krommes",
        "alfaro",
        "james",
        "wiegerinck",
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "sweeney",
        "kuyucu",
    ),
    "claude-researcher-1": mentions(
        "wu",
        "nakase",
        "guszczyn_2023",
        "thapa",
        "rathleff_2020",
        "quadriceps_release",
        "bezuglov",
        "krommes",
        "kaya",
        "alfaro",
        "perhamre_2011a",
        "perhamre_2011b",
        "perhamre_2012",
        "james",
        "wiegerinck",
        "sweeney",
        "guszczyn_2024",
    ),
    "claude-researcher-2": mentions(
        "wu",
        "nakase",
        "lohrer_osd",
        "gazya",
        "shafshak",
        "krommes",
        "wiegerinck",
        "james",
        "alfaro",
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "sweeney",
    ),
    "claude-researcher-3": mentions(
        "wu",
        "nakase",
        "krommes",
        "guszczyn_2023",
        "guszczyn_2024",
        "thapa",
        "lohrer_osd",
        "shafshak",
        "gazya",
        "nct06993363",
        "wiegerinck",
        "james",
        "alfaro",
        "perhamre_2011a",
        "perhamre_2011b",
        "perhamre_2012",
        "sweeney",
        "lohrer_sever",
    ),
    "claude-researcher-4": mentions(
        "wu",
        "nakase",
        "krommes",
        "gazya",
        "lohrer_osd",
        "nct06993363",
        "alfaro",
        "perhamre_2011a",
        "perhamre_2012",
        "perhamre_2011b",
        "wiegerinck",
        "sweeney",
        "kuyucu",
        "james",
    ),
    "gemini-patient-1": mentions("wiegerinck", "sweeney", "krommes"),
    "gemini-patient-2": mentions(
        "wiegerinck", "alfaro", "kuyucu", "rathleff_2020"
    ),
    "gemini-patient-3": mentions(
        "perhamre_2011a",
        "james",
        "wiegerinck",
        "topol",
        "perhamre_2011b",
    ),
    "gemini-patient-4": mentions(
        "rathleff_2020", "perhamre_2011a", "volpi", "canale"
    ),
    "gemini-clinician-1": mentions("perhamre_2012", "topol"),
    "gemini-clinician-2": mentions(
        "wiegerinck", "alfaro", "rathleff_2020", "guszczyn_2024"
    ),
    "gemini-clinician-3": mentions("krommes", "james"),
    "gemini-clinician-4": mentions(
        "james", "perhamre_2011b", "kuyucu", "wu", "guszczyn_2024"
    ),
    "gemini-researcher-1": mentions(
        "sweeney", "yachaoui", "wu", "rathleff_2020"
    ),
    "gemini-researcher-2": mentions(
        "rathleff_2020", "perhamre_2011a", "wiegerinck"
    ),
    "gemini-researcher-3": mentions(
        "wiegerinck",
        "james",
        "perhamre_2011a",
        "sweeney",
        "van_leeuwen",
        "nakase",
    ),
    "gemini-researcher-4": mentions(
        "wiegerinck", "alfaro", "james", "sweeney", "nakase"
    ),
    "gpt-patient-1": mentions(
        "james",
        "wiegerinck",
        "alfaro",
        "perhamre_2011a",
        "perhamre_2011b",
        "perhamre_2012",
        "kuyucu",
        "sweeney",
        "micheli",
        "rathleff_2020",
        "krommes",
        "topol",
        "nakase",
        "reesman",
        "valentino",
        "sylvester",
        "clancy",
        "kimura",
        "young",
        "sullivan",
        "vomer",
    ),
    "gpt-patient-2": mentions(
        "topol",
        "nakase",
        "rathleff_2020",
        "reesman",
        "krommes",
        "valentino",
        "perhamre_2011b",
        "perhamre_2011a",
        "james",
        "wiegerinck",
        "kuyucu",
        "alfaro",
        "sweeney",
        "sylvester",
        "nikpay",
        "clancy",
        "sailly",
        "young",
        "kimura",
        "sullivan",
        "vomer",
    ),
    "gpt-patient-3": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "james",
        "wiegerinck",
        "kuyucu",
        "alfaro",
        "sweeney",
        "topol",
        "lohrer_osd",
        "nakase",
        "rathleff_2020",
        "wu",
        "krommes",
        "emelin",
        "thapa",
        "ikeda",
        "valentino",
        "sylvester",
        "young",
        "kimura",
        "sullivan",
        "nikpay",
    ),
    "gpt-patient-4": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "wiegerinck",
        "james",
        "kuyucu",
        "alfaro",
        "feyzioglu",
        "sweeney",
        "university_delaware",
        "topol",
        "nakase",
        "rathleff_2020",
        "reesman",
        "krommes",
        "valentino",
        "sylvester",
        "young",
        "kimura",
        "sullivan",
        "vomer",
    ),
    "gpt-clinician-1": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "james",
        "wiegerinck",
        "kuyucu",
        "alfaro",
        "sweeney",
        "levine",
        "topol",
        "duperron",
        "nakase",
        "rathleff_2020",
        "reesman",
        "krommes",
        "valentino",
    ),
    "gpt-clinician-2": mentions(
        "perhamre_2011a",
        "perhamre_2012",
        "james",
        "wiegerinck",
        "kuyucu",
        "alfaro",
        "sweeney",
        "topol",
        "nakase",
        "rathleff_2020",
        "reesman",
        "guszczyn_2023",
        "guszczyn_2024",
        "krommes",
        "thapa",
        "sylvester",
        "nikpay",
    ),
    "gpt-clinician-3": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "wiegerinck",
        "james",
        "kuyucu",
        "alfaro",
        "sweeney",
        "university_delaware",
        "topol",
        "nakase",
        "rathleff_2020",
        "bezuglov",
        "reesman",
        "krommes",
        "emelin",
        "egorova",
        "sylvester",
        "nikpay",
    ),
    "gpt-clinician-4": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "wiegerinck",
        "james",
        "kuyucu",
        "alfaro",
        "sweeney",
        "topol",
        "lohrer_osd",
        "duperron",
        "nakase",
        "rathleff_2020",
        "bezuglov",
        "wu",
        "reesman",
        "krommes",
        "thapa",
        "sylvester",
        "valentino",
        "sullivan",
    ),
    "gpt-researcher-1": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "wiegerinck",
        "james",
        "kuyucu",
        "alfaro",
        "sweeney",
        "topol",
        "nakase",
        "rathleff_2020",
        "reesman",
        "krommes",
    ),
    "gpt-researcher-2": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "wiegerinck",
        "james",
        "kuyucu",
        "alfaro",
        "sweeney",
        "topol",
        "nakase",
        "rathleff_2020",
        "krommes",
        "reesman",
        "sylvester",
        "valentino",
        "sullivan",
    ),
    "gpt-researcher-3": mentions(
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "james",
        "wiegerinck",
        "kuyucu",
        "alfaro",
        "sweeney",
        "gerulis",
        "topol",
        "lohrer_osd",
        "gazya",
        "duperron",
        "lucciani",
        "nakase",
        "rathleff_2020",
        "wu",
        "reesman",
        "krommes",
        "emelin",
        "thapa",
    ),
    "gpt-researcher-4": mentions(
        "wiegerinck",
        "james",
        "alfaro",
        "perhamre_2011b",
        "perhamre_2011a",
        "perhamre_2012",
        "kuyucu",
        "sweeney",
        "topol",
        "nakase",
        "rathleff_2020",
        "krommes",
        "reesman",
        "bezuglov",
        "duperron",
        "lucciani",
        "levine",
        "guszczyn_2023",
        "thapa",
        "sylvester",
        "nikpay",
        "valentino",
        "kimura",
        "sullivan",
        "vomer",
    ),
}


IDENTITY_NOTES = {
    ("claude-patient-1", "rathleff_2020"): (
        "The response gives Sports Health as the journal; the study was published "
        "in Orthopaedic Journal of Sports Medicine."
    ),
    ("claude-patient-1", "guszczyn_2024"): (
        "The response lists Maciąg as the lead author; the publication lists "
        "Guszczyn as lead author."
    ),
    ("claude-patient-4", "bourke"): (
        "The response provides only 'Bourke et al.' and a generic custom-orthotic "
        "comparison; it cannot be matched confidently to a specific publication."
    ),
    ("claude-clinician-2", "bourke"): (
        "The search preamble names a 'Bourke orthotics trial' without enough "
        "bibliographic detail to resolve its identity."
    ),
    ("claude-clinician-4", "topol"): (
        "The response gives the correct title but attributes the study to an "
        "incorrect author list and journal; the supplied RIS identifies Topol "
        "et al. in Pediatrics."
    ),
    ("claude-clinician-4", "kuyucu"): (
        "The response gives the correct title but lists several incorrect "
        "coauthors; the supplied RIS lists Gülenç, Biçer, and Erdil."
    ),
    ("claude-researcher-2", "wu"): (
        "The response gives the Wu trial title and online-publication year but "
        "attributes the study to Nakase."
    ),
    ("claude-researcher-4", "wu"): (
        "The response gives the Wu trial title and online-publication year but "
        "attributes the study to Nakase."
    ),
    ("gpt-clinician-2", "perhamre_2011a"): (
        "The response gives the included crossover-trial title and DOI but uses "
        "the author list from the excluded Perhamre insole study."
    ),
    ("gpt-researcher-4", "perhamre_2011a"): (
        "The response paraphrases the crossover-trial title as a clinical study "
        "of two heel cups; its DOI resolves to the included heel-cup-versus-wedge "
        "trial."
    ),
    ("gpt-researcher-4", "duperron"): (
        "The response identifies the 30-patient Duperron cohort but links it to "
        "the separate NCT02824172 randomized trial."
    ),
    ("gpt-researcher-4", "lucciani"): (
        "NCT02824172 appears only as the link attached to the Duperron cohort "
        "citation; the source package identifies the registry as Lucciani 2016."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-patient-1", "rathleff_2020"): (
        "Rathleff et al. Activity Modification and Knee Strengthening; "
        "reported as Sports Health 2020"
    ),
    ("claude-patient-1", "guszczyn_2024"): (
        "Maciąg et al. The Effectiveness of Treating Osgood-Schlatter Disease "
        "with LR-PRP"
    ),
    ("claude-patient-4", "bourke"): (
        "Bourke et al. custom orthotics versus heel lifts"
    ),
    ("claude-clinician-2", "bourke"): "Bourke orthotics trial",
    ("claude-clinician-4", "topol"): (
        "Topol, Reeves, and Hassanein; Arch Phys Med Rehabil 2011"
    ),
    ("claude-clinician-4", "kuyucu"): (
        "Kuyucu, Bülbül, Kara, Koçyiğit, and Erdil 2017"
    ),
    ("claude-researcher-2", "wu"): (
        "Nakase et al. Hyperosmolar dextrose injection for Osgood-Schlatter "
        "disease; Arch Orthop Trauma Surg 2021"
    ),
    ("claude-researcher-4", "wu"): (
        "Nakase et al. Hyperosmolar dextrose injection for Osgood-Schlatter "
        "disease; Arch Orthop Trauma Surg 2021"
    ),
    ("gpt-clinician-2", "perhamre_2011a"): (
        "Perhamre, Janson, Norlin, and Klässbo; heel-cup crossover title/DOI"
    ),
    ("gpt-researcher-4", "perhamre_2011a"): (
        "Perhamre et al. clinical study of two types of heel cups; "
        "DOI 10.1111/j.1600-0838.2010.01140.x"
    ),
    ("gpt-researcher-4", "duperron"): (
        "Duperron et al. cast-immobilization cohort; linked to NCT02824172"
    ),
    ("gpt-researcher-4", "lucciani"): (
        "ClinicalTrials.gov NCT02824172 linked from the Duperron citation"
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
                    "source_file": f"reviews/CD015156/{run_id}.md",
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
    """Regenerate the curated CD015156 study-cluster match table."""

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
