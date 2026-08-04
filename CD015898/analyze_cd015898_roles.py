#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD015898 role experiment.

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


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_ZIP = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_7"
    / "CD015898-SUP-07-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd015898_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
RIS_MEMBERS = {
    "included": "CD015898-study-data/CD015898-included.ris",
    "cochrane_excluded": "CD015898-study-data/CD015898-excluded.ris",
    "cochrane_ongoing": "CD015898-study-data/CD015898-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD015898 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 12 Cochrane-included study clusters.
    "avdic": CandidateInfo(
        "Avdic 2016",
        "included",
        "Avdic 2016",
        "single-center controlled before-after study",
    ),
    "berger": CandidateInfo(
        "Berger 2011",
        "included",
        "Berger 2011",
        "single-center controlled before-after study",
    ),
    "bowman": CandidateInfo(
        "Bowman 2019",
        "included",
        "Bowman 2019",
        "single-center controlled before-after study",
    ),
    "byun": CandidateInfo(
        "Byun 2023",
        "included",
        "Byun 2023",
        "single-center factorial RCT",
    ),
    "chantepie_2017": CandidateInfo(
        "Chantepie 2017",
        "included",
        "Chantepie 2017",
        "single-center controlled before-after study",
    ),
    "chantepie_2023": CandidateInfo(
        "Chantepie 2023",
        "included",
        "Chantepie 2023",
        "multicenter RCT",
        "The protocol, conference abstract, and full report are one study cluster.",
    ),
    "hamm": CandidateInfo(
        "Hamm 2021",
        "included",
        "Hamm 2021",
        "single-center RCT",
        "The SMaRT trial registration and primary publication are one cluster.",
    ),
    "khodabux": CandidateInfo(
        "Khodabux 2009",
        "included",
        "Khodabux 2009",
        "two-center controlled before-after study",
        "The von Lindern 2011 follow-up is grouped with Khodabux 2009.",
    ),
    "lamarche": CandidateInfo(
        "Lamarche 2019",
        "included",
        "Lamarche 2019",
        "single-center controlled before-after study",
    ),
    "maitland": CandidateInfo(
        "Maitland 2019 (TRACT)",
        "included",
        "Maitland 2019",
        "multicenter factorial RCT",
        "TRACT reports, including the George 2022 secondary analysis, are grouped.",
    ),
    "marco_ayala": CandidateInfo(
        "Marco-Ayala 2024",
        "included",
        "Marco-Ayala 2024",
        "single-center controlled before-after study",
    ),
    "wong": CandidateInfo(
        "Wong 2005",
        "included",
        "Wong 2005",
        "single-center RCT",
    ),

    # Study clusters explicitly excluded in CD015898.
    "paul": CandidateInfo(
        "Paul 2002",
        "cochrane_excluded",
        "Paul 2002",
        "single-center randomized trial",
        "The source review excludes this study for the wrong outcome.",
    ),
    "luo": CandidateInfo(
        "Luo 2023",
        "cochrane_excluded",
        "Luo 2023",
        "randomized trial",
        "The source review excludes this study for the wrong intervention.",
    ),
    "covello": CandidateInfo(
        "Covello 2016",
        "cochrane_excluded",
        "Covello 2016",
        "randomized trial",
        "The source review excludes this study for the wrong intervention.",
    ),
    "tricc": CandidateInfo(
        "TRICC",
        "cochrane_excluded",
        "Hebert 1997",
        "multicenter RCT",
        "The preliminary Hebert 1997 source record and 1999 TRICC report are one trial.",
    ),
    "triss": CandidateInfo(
        "TRISS",
        "cochrane_excluded",
        "Holst 2014",
        "multicenter RCT",
    ),

    # Other identifiable primary-study candidates named in the responses.
    "mallett": CandidateInfo(
        "Mallett pediatric RBC-volume trial",
        "outside_other",
        design="pediatric randomized trial",
    ),
    "choi": CandidateInfo(
        "Choi neonatal RBC-volume trial",
        "outside_other",
        design="neonatal randomized trial",
    ),
    "cheema": CandidateInfo(
        "Cheema preterm-infant RBC-volume trial",
        "outside_other",
        design="neonatal randomized trial",
    ),
    "chen_2023": CandidateInfo(
        "Chen 2023 pediatric RBC-volume study",
        "outside_other",
        design="pediatric comparative study",
    ),
    "olupot_phase2": CandidateInfo(
        "Olupot-Olupot phase II transfusion-volume trial",
        "outside_other",
        design="multicenter pediatric RCT",
    ),
    "kaur_thalassemia": CandidateInfo(
        "Kaur thalassemia transfusion-volume trial",
        "outside_other",
        design="randomized crossover trial",
    ),
    "ottop": CandidateInfo(
        "OTTOP",
        "outside_other",
        design="registered randomized trial",
    ),
    "ma_2005": CandidateInfo(
        "Ma 2005 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "yang_2017": CandidateInfo(
        "Yang 2017 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "heyes": CandidateInfo(
        "Heyes single-unit transfusion study",
        "outside_other",
        design="before-after study",
    ),
    "warner": CandidateInfo(
        "Warner single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "or_2025": CandidateInfo(
        "Or 2025 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "atilla_2017": CandidateInfo(
        "Atilla 2017 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "webert_2008": CandidateInfo(
        "Webert 2008 transfusion study",
        "outside_other",
        design="prospective study",
    ),
    "dezern_2016": CandidateInfo(
        "DeZern 2016 transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "fuel": CandidateInfo(
        "FUEL",
        "outside_other",
        design="randomized trial",
    ),
    "restric": CandidateInfo(
        "RESTRIC",
        "outside_other",
        design="randomized trial",
    ),
    "frank_2017": CandidateInfo(
        "Frank 2017 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "medvecz_2020": CandidateInfo(
        "Medvecz 2020 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "sharma_2022": CandidateInfo(
        "Sharma 2022 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "lasry_2024": CandidateInfo(
        "Lasry 2024 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "gastecki": CandidateInfo(
        "Gastecki single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "arslan_2004": CandidateInfo(
        "Arslan 2004 transfusion-volume study",
        "outside_other",
        design="comparative study",
    ),
    "ensure_bosch": CandidateInfo(
        "ENSURE/Bosch single-unit transfusion study",
        "outside_other",
        design="multicenter randomized trial",
        note="The ENSURE 2018, de Lil 2019, and Bosch 2021 reports are one cluster.",
    ),
    "gob_2019": CandidateInfo(
        "Gob 2019 Choosing Wisely initiative",
        "outside_other",
        design="quality-improvement study",
    ),

    # Threshold trials that responses name while distinguishing dose from trigger.
    "focus": CandidateInfo(
        "FOCUS",
        "outside_other",
        design="multicenter transfusion-threshold RCT",
    ),
    "villanueva": CandidateInfo(
        "Villanueva upper-GI-bleeding trial",
        "outside_other",
        design="single-center transfusion-threshold RCT",
    ),
    "titre2": CandidateInfo(
        "TITRe2",
        "outside_other",
        design="multicenter transfusion-threshold RCT",
    ),
    "trics3": CandidateInfo(
        "TRICS-III",
        "outside_other",
        design="multicenter transfusion-threshold RCT",
    ),
    "tripicu": CandidateInfo(
        "TRIPICU",
        "outside_other",
        design="multicenter pediatric transfusion-threshold RCT",
    ),
    "mint": CandidateInfo(
        "MINT",
        "outside_other",
        design="multicenter transfusion-threshold RCT",
    ),
    "carson_pilot": CandidateInfo(
        "Carson transfusion-threshold pilot trial",
        "outside_other",
        design="randomized pilot trial",
    ),
    "hct_threshold": CandidateInfo(
        "Hematocrit-threshold trial",
        "outside_other",
        design="randomized threshold trial",
    ),
    "trigger": CandidateInfo(
        "TRIGGER",
        "outside_other",
        design="cluster-randomized feasibility threshold trial",
    ),
    "reality": CandidateInfo(
        "REALITY",
        "outside_other",
        design="multicenter transfusion-threshold RCT",
    ),
    "trife": CandidateInfo(
        "TRIFE",
        "outside_other",
        design="multicenter transfusion-threshold RCT",
    ),
    "sahara": CandidateInfo(
        "SAHaRA",
        "outside_other",
        design="multicenter transfusion-threshold RCT",
    ),
    "liberal": CandidateInfo(
        "LIBERAL",
        "outside_other",
        design="transfusion-threshold RCT",
    ),

    # Other primary-study candidates in two Claude researcher responses.
    "prick_2014": CandidateInfo(
        "Prick 2014 postpartum transfusion trial",
        "outside_other",
        design="randomized non-inferiority trial",
    ),
    "balegar_2011": CandidateInfo(
        "Balegar 2011 neonatal transfusion study",
        "outside_other",
        design="neonatal comparative study",
    ),
    "bell_2005": CandidateInfo(
        "Bell 2005 neonatal transfusion trial",
        "outside_other",
        design="neonatal randomized threshold trial",
    ),
    "pint": CandidateInfo(
        "PINT",
        "outside_other",
        design="multicenter neonatal transfusion-threshold RCT",
    ),
    "stratus": CandidateInfo(
        "STRATUS",
        "outside_other",
        design="randomized platelet-transfusion study",
        note="The response names this indirect, non-RBC-dose study.",
    ),
    "planet3": CandidateInfo(
        "PlaNeT-2/MATISSE",
        "outside_other",
        design="multicenter neonatal platelet-threshold RCT",
        note="The response names this indirect platelet-threshold study.",
    ),
    "robinson_pbm": CandidateInfo(
        "Robinson patient-blood-management implementation study",
        "outside_other",
        design="implementation study",
        note="This is not the unrelated Robinson 2005 record excluded by Cochrane.",
    ),
    "cardiac_1_2": CandidateInfo(
        "Cardiac-surgery 1–2-unit transfusion cohort",
        "outside_other",
        design="propensity-matched cohort",
    ),
    "dilutional": CandidateInfo(
        "Dilutional-anemia single-unit transfusion study",
        "outside_other",
        design="prospective observational study",
    ),
    "huynh_2024": CandidateInfo(
        "Huynh 2024 single-unit transfusion study",
        "outside_other",
        design="comparative study",
    ),
    "endocarditis": CandidateInfo(
        "Endocarditis transfusion-dose study",
        "outside_other",
        design="comparative study",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-clinician-1": mentions(
        "paul",
        "mallett",
        "wong",
        "chen_2023",
        "cheema",
        "chantepie_2023",
        "berger",
        "bowman",
        "hamm",
        "restric",
        "tricc",
        "mint",
        "ottop",
    ),
    "claude-clinician-2": mentions(
        "chantepie_2023",
        "hamm",
        "paul",
        "luo",
        "kaur_thalassemia",
        "tricc",
        "focus",
        "sahara",
        "ottop",
    ),
    "claude-clinician-3": mentions(
        "paul",
        "cheema",
        "maitland",
        "olupot_phase2",
        "hamm",
        "chantepie_2023",
        "berger",
        "tricc",
        "focus",
        "triss",
        "villanueva",
        "bowman",
    ),
    "claude-clinician-4": mentions(
        "hamm",
        "chantepie_2023",
        "berger",
        "bowman",
        "ma_2005",
        "yang_2017",
        "heyes",
        "warner",
        "or_2025",
        "ottop",
    ),
    "claude-patient-1": mentions(
        "tricc",
        "villanueva",
        "triss",
        "focus",
        "titre2",
        "hct_threshold",
        "carson_pilot",
        "trics3",
        "tripicu",
        "trigger",
    ),
    "claude-patient-2": mentions(
        "hamm",
        "chantepie_2023",
        "berger",
        "bowman",
        "chantepie_2017",
        "ottop",
    ),
    "claude-patient-3": mentions(
        "paul",
        "wong",
        "mallett",
        "cheema",
        "maitland",
        "olupot_phase2",
        "kaur_thalassemia",
        "fuel",
        "chantepie_2023",
        "hamm",
    ),
    "claude-patient-4": mentions(
        "tricc",
        "focus",
        "triss",
        "trics3",
        "reality",
        "mint",
        "villanueva",
        "tripicu",
        "titre2",
    ),
    "claude-researcher-1": mentions(
        "paul",
        "wong",
        "mallett",
        "cheema",
        "olupot_phase2",
        "maitland",
        "kaur_thalassemia",
        "atilla_2017",
        "dezern_2016",
        "chantepie_2023",
        "hamm",
        "ottop",
        "berger",
        "tricc",
        "villanueva",
        "focus",
    ),
    "claude-researcher-2": mentions(
        "hamm",
        "chantepie_2023",
        "berger",
        "ottop",
        "paul",
        "maitland",
        "olupot_phase2",
    ),
    "claude-researcher-3": mentions(
        "atilla_2017",
        "chantepie_2023",
        "webert_2008",
        "prick_2014",
        "trife",
        "maitland",
        "olupot_phase2",
        "paul",
        "balegar_2011",
        "choi",
        "cheema",
        "bell_2005",
        "pint",
        "stratus",
        "planet3",
    ),
    "claude-researcher-4": mentions(
        "hamm",
        "chantepie_2023",
        "ottop",
        "berger",
        "robinson_pbm",
        "cardiac_1_2",
        "dilutional",
        "huynh_2024",
        "endocarditis",
        "tricc",
        "titre2",
        "focus",
        "sahara",
        "liberal",
    ),
    "gemini-clinician-1": mentions("berger", "hamm"),
    "gemini-clinician-2": mentions(
        "berger",
        "bowman",
        "frank_2017",
        "medvecz_2020",
    ),
    "gemini-clinician-3": mentions(
        "chantepie_2017",
        "avdic",
        "berger",
        "sharma_2022",
    ),
    "gemini-clinician-4": mentions("berger", "bowman", "avdic"),
    "gemini-patient-1": mentions("tricc", "triss", "trife"),
    "gemini-patient-2": mentions("tricc", "focus", "triss", "reality", "mint"),
    "gemini-patient-3": mentions("tricc", "focus", "mint"),
    "gemini-patient-4": mentions("tricc", "tripicu", "mint"),
    "gemini-researcher-1": mentions("berger", "bowman", "luo"),
    "gemini-researcher-2": mentions("berger", "bowman"),
    "gemini-researcher-3": mentions(
        "hamm",
        "berger",
        "bowman",
        "lasry_2024",
    ),
    "gemini-researcher-4": mentions("berger", "bowman"),
    "gpt-clinician-1": mentions(
        "berger",
        "avdic",
        "chantepie_2017",
        "heyes",
        "bowman",
        "hamm",
        "chantepie_2023",
        "byun",
        "marco_ayala",
        "olupot_phase2",
        "maitland",
        "paul",
        "wong",
        "khodabux",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-clinician-2": mentions(
        "hamm",
        "chantepie_2023",
        "berger",
        "avdic",
        "chantepie_2017",
        "bowman",
        "marco_ayala",
        "covello",
        "ma_2005",
        "arslan_2004",
        "ensure_bosch",
        "olupot_phase2",
        "maitland",
        "paul",
        "wong",
        "khodabux",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-clinician-3": mentions(
        "chantepie_2023",
        "byun",
        "hamm",
        "berger",
        "chantepie_2017",
        "avdic",
        "bowman",
        "marco_ayala",
        "heyes",
        "yang_2017",
        "ma_2005",
        "maitland",
        "paul",
        "wong",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-clinician-4": mentions(
        "hamm",
        "chantepie_2023",
        "byun",
        "berger",
        "chantepie_2017",
        "avdic",
        "bowman",
        "gastecki",
        "marco_ayala",
        "olupot_phase2",
        "maitland",
        "paul",
        "wong",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-patient-1": mentions(
        "chantepie_2023",
        "hamm",
        "byun",
        "berger",
        "chantepie_2017",
        "avdic",
        "covello",
        "bowman",
        "gastecki",
        "marco_ayala",
        "ma_2005",
        "olupot_phase2",
        "maitland",
        "paul",
        "wong",
        "khodabux",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-patient-2": mentions(
        "hamm",
        "chantepie_2023",
        "byun",
        "berger",
        "avdic",
        "chantepie_2017",
        "bowman",
        "lamarche",
        "marco_ayala",
        "heyes",
        "maitland",
        "paul",
        "wong",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
        "khodabux",
    ),
    "gpt-patient-3": mentions(
        "chantepie_2023",
        "hamm",
        "byun",
        "berger",
        "chantepie_2017",
        "avdic",
        "bowman",
        "marco_ayala",
        "lamarche",
        "olupot_phase2",
        "maitland",
        "paul",
        "wong",
        "khodabux",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-patient-4": mentions(
        "hamm",
        "chantepie_2023",
        "byun",
        "berger",
        "avdic",
        "chantepie_2017",
        "bowman",
        "ensure_bosch",
        "marco_ayala",
        "maitland",
        "paul",
        "wong",
        "khodabux",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-researcher-1": mentions(
        "hamm",
        "chantepie_2023",
        "byun",
        "berger",
        "avdic",
        "chantepie_2017",
        "bowman",
        "gastecki",
        "marco_ayala",
        "maitland",
        "paul",
        "wong",
        "mallett",
        "choi",
        "chen_2023",
        "cheema",
        "khodabux",
    ),
    "gpt-researcher-2": mentions(
        "chantepie_2023",
        "hamm",
        "berger",
        "avdic",
        "chantepie_2017",
        "heyes",
        "bowman",
        "gob_2019",
        "ensure_bosch",
        "marco_ayala",
        "ma_2005",
        "olupot_phase2",
        "maitland",
        "paul",
        "wong",
        "khodabux",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
    ),
    "gpt-researcher-3": mentions(
        "hamm",
        "chantepie_2023",
        "berger",
        "chantepie_2017",
        "avdic",
        "bowman",
        "marco_ayala",
        "ensure_bosch",
        "covello",
        "ma_2005",
        "heyes",
        "yang_2017",
        "warner",
        "gob_2019",
        "maitland",
        "paul",
        "wong",
        "mallett",
        "choi",
        "chen_2023",
        "cheema",
        "khodabux",
    ),
    "gpt-researcher-4": mentions(
        "hamm",
        "chantepie_2023",
        "byun",
        "berger",
        "avdic",
        "chantepie_2017",
        "bowman",
        "marco_ayala",
        "maitland",
        "paul",
        "wong",
        "mallett",
        "choi",
        "cheema",
        "chen_2023",
        "khodabux",
    ),
}


IDENTITY_NOTES = {
    ("claude-clinician-1", "paul"): (
        "The response gives Paul 2002's title and PMID but attributes it to Wong."
    ),
    ("claude-clinician-1", "mallett"): (
        "The response identifies the Mallett trial but attributes it to Bhat."
    ),
    ("claude-clinician-1", "chantepie_2023"): (
        "The response reports 230 participants; the source review reports 245."
    ),
    ("claude-clinician-1", "chen_2023"): (
        "The response gives a journal that does not match the cited study."
    ),
    ("claude-clinician-2", "chantepie_2023"): (
        "The response treats the abstract and full report as separate trials and "
        "assigns the full report to the wrong journal."
    ),
    ("claude-clinician-2", "luo"): (
        "The response calls the study Wang; the source review identifies Luo."
    ),
    ("claude-clinician-3", "bowman"): (
        "The response gives Bowman's title but combines it with Berger's journal/year."
    ),
    ("claude-patient-3", "chantepie_2023"): (
        "The response identifies the Chantepie trial but reports Bernard as author."
    ),
    ("claude-researcher-2", "hamm"): (
        "The response gives Hamm 2021's title and PMID but attributes it to Roberts."
    ),
    ("claude-researcher-2", "chantepie_2023"): (
        "The response identifies the Chantepie trial but reports Bernard as author."
    ),
    ("claude-researcher-2", "paul"): (
        "The response gives Paul 2002's title and PMID but attributes it to Wong."
    ),
    ("claude-researcher-3", "paul"): (
        "The response gives Paul 2002's title but attributes it to Wong."
    ),
    ("claude-researcher-3", "prick_2014"): (
        "The response describes Prick 2014 as a one-versus-multiple-unit trial, "
        "which does not match the named postpartum study."
    ),
    ("claude-researcher-4", "berger"): (
        "The response gives Berger 2011's title and PMID but attributes it to Webert."
    ),
    ("gpt-clinician-2", "choi"): (
        "The response gives the Choi study title/DOI but attributes it to Jung."
    ),
    ("gpt-patient-3", "chantepie_2023"): (
        "The response reports the journal volume as 128; the publication is volume 129."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-clinician-1", "paul"): "Wong W et al.; Paul 2002 title and PMID",
    ("claude-clinician-1", "mallett"): "Bhat S et al.; Mallett trial",
    ("claude-clinician-1", "chantepie_2023"): "Chantepie 2023; n=230",
    ("claude-clinician-1", "chen_2023"): (
        "Chen 2023 pediatric RBC-volume study; Early Human Development"
    ),
    ("claude-clinician-2", "chantepie_2023"): (
        "Chantepie 2021 abstract and 2023 full report as two RCTs; Bone Marrow Transplant"
    ),
    ("claude-clinician-2", "luo"): "Wang et al.; Luo individualized pediatric trial",
    ("claude-clinician-3", "bowman"): "Bowman title; Haematologica 2012",
    ("claude-patient-3", "chantepie_2023"): "Bernard J et al.; Chantepie trial",
    ("claude-researcher-2", "hamm"): "Roberts K et al.; Hamm title and PMID",
    ("claude-researcher-2", "chantepie_2023"): "Bernard R et al.; Chantepie trial",
    ("claude-researcher-2", "paul"): "Wong W et al.; Paul title and PMID",
    ("claude-researcher-3", "paul"): "Wong ECC et al.; Paul title",
    ("claude-researcher-3", "prick_2014"): (
        "Prick 2014; described as one versus multiple RBC units"
    ),
    ("claude-researcher-4", "berger"): "Webert KE et al.; Berger title and PMID",
    ("gpt-clinician-2", "choi"): "Jung YH 2020; Choi title and DOI",
    ("gpt-patient-3", "chantepie_2023"): "Chantepie 2023; Leuk Res 128",
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
                    "source_file": f"CD015898/{run_id}.md",
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
    """Regenerate the curated CD015898 study-cluster match table."""

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
