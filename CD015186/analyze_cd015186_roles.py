#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD015186 role experiment.

Each complete chatbot response is curated once at the study-cluster level.
Cochrane labels are validated against the included, excluded, ongoing, and
awaiting-classification RIS exports supplied with the review data package.
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
    / "CD015186-SUP-08-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd015186_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
RIS_MEMBERS = {
    "included": "CD015186-study-data/CD015186-included.ris",
    "cochrane_excluded": "CD015186-study-data/CD015186-excluded.ris",
    "cochrane_ongoing": "CD015186-study-data/CD015186-ongoing.ris",
    "cochrane_awaiting": "CD015186-study-data/CD015186-awaiting.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD015186 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 10 Cochrane-included study clusters.
    "arimura": CandidateInfo(
        "Arimura 2023 KDB-versus-microhook trial",
        "included",
        "Arimura 2023",
        "randomized clinical trial",
    ),
    "babighian": CandidateInfo(
        "Babighian 2010 excimer-laser trabeculotomy trial",
        "included",
        "Babighian 2010",
        "RCT",
    ),
    "falkenberry": CandidateInfo(
        "Falkenberry 2020 excisional-goniotomy trial",
        "included",
        "Falkenberry 2020",
        "RCT",
    ),
    "goldberg": CandidateInfo(
        "Goldberg 2024 STREAMLINE-versus-iStent trial",
        "included",
        "Goldberg 2024",
        "RCT",
    ),
    "kicinska": CandidateInfo(
        "Kicinska 2023 three-variant canaloplasty trial",
        "included",
        "Kicinska 2023",
        "randomized trial",
        "The 12-month and three-year reports are grouped under one Cochrane label.",
    ),
    "maheshwari": CandidateInfo(
        "Maheshwari 2023 Tanito-microhook trial",
        "included",
        "Maheshwari 2023",
        "RCT",
        "The early and two-year reports are grouped under one Cochrane label.",
    ),
    "quaranta": CandidateInfo(
        "Quaranta 1999 goniotrabeculotomy trial",
        "included",
        "Quaranta 1999",
        "RCT",
    ),
    "sato_phaco": CandidateInfo(
        "Sato 2018 suture-trabeculotomy-plus-phaco trial",
        "included",
        "Sato 2018",
        "pilot RCT",
    ),
    "ting": CandidateInfo(
        "Ting 2018 phaco-Trabectome trial",
        "included",
        "Ting 2018",
        "RCT",
    ),
    "yin": CandidateInfo(
        "Yin 2024 ABiC-versus-GATT trial",
        "included",
        "Yin 2024",
        "RCT",
    ),

    # Identifiable source-package studies classified outside the included set.
    "ayub": CandidateInfo(
        "Ayub 2025 bent-needle-goniotomy trial",
        "cochrane_excluded",
        "Ayub 2025",
        "RCT",
        "Protocol and results reports are grouped as one study cluster.",
    ),
    "gemini": CandidateInfo(
        "GEMINI OMNI study",
        "cochrane_excluded",
        "Greenwood 2023",
        "prospective single-arm study",
        "The 12- and 36-month GEMINI reports are grouped together.",
    ),
    "golaszewska": CandidateInfo(
        "Golaszewska 2023 canaloplasty-versus-iStent study",
        "cochrane_excluded",
        "Golaszewska 2023",
        "comparative study",
    ),
    "kvt": CandidateInfo(
        "KDB-versus-Trabectome fellow-eye trial",
        "cochrane_excluded",
        "NCT03894631",
        "randomized intra-subject trial",
    ),
    "sato_standalone": CandidateInfo(
        "Sato 2018 standalone 360-degree suture trabeculotomy study",
        "cochrane_excluded",
        "Sato 2018b",
        "prospective study",
    ),
    "sato_extent": CandidateInfo(
        "Sato incision-extent trial",
        "cochrane_excluded",
        "Sato 2021",
        "RCT",
        "The 12-month and five-year reports are grouped as one trial cluster.",
    ),
    "tvc": CandidateInfo(
        "TVC trabeculectomy-versus-canaloplasty trial",
        "cochrane_excluded",
        "Matlach 2015",
        "RCT",
        "The original and 11-year follow-up reports are grouped together.",
    ),
    "vcst_vt": CandidateInfo(
        "VCST-versus-VT trial",
        "cochrane_excluded",
        "NCT05666440",
        "RCT",
    ),
    "ventura": CandidateInfo(
        "Ventura-Abreu 2021 KDB-plus-phaco trial",
        "cochrane_excluded",
        "Ventura-Abreu 2021",
        "RCT",
    ),
    "swedish_migs": CandidateInfo(
        "Swedish Microinvasive Glaucoma Surgery Study",
        "cochrane_ongoing",
        "NCT05035394",
        "RCT",
        "The source package classifies this study as ongoing although responses "
        "cite a 2026 publication.",
    ),
    "evolve": CandidateInfo(
        "EVOLVE OMNI trial",
        "cochrane_awaiting",
        "NCT06407973",
        "RCT",
    ),
    "magic": CandidateInfo(
        "MAGIC iTrack-versus-OMNI trial",
        "cochrane_awaiting",
        "NCT04769453",
        "RCT",
    ),
    "trident": CandidateInfo(
        "TRIDENT OMNI-versus-iStent trial",
        "cochrane_awaiting",
        "NCT04658095",
        "RCT",
    ),

    # Other identifiable primary-study candidates named in the responses.
    "fea_istent": CandidateInfo("Fea 2010 first-generation iStent trial", "outside_other", design="RCT"),
    "us_istent": CandidateInfo("US iStent pivotal trial", "outside_other", design="RCT"),
    "istent_inject_meds": CandidateInfo("iStent inject-versus-medication trial", "outside_other", design="RCT"),
    "synergy": CandidateInfo("Synergy iStent inject study", "outside_observational", design="prospective study"),
    "istent_inject_pivotal": CandidateInfo("iStent inject pivotal trial", "outside_other", design="RCT"),
    "fan_gaskin": CandidateInfo("Fan Gaskin 2024 iStent inject trial", "outside_other", design="RCT"),
    "two_stents_prostaglandin": CandidateInfo("Two-iStent-versus-prostaglandin trial", "outside_other", design="RCT"),
    "istent_initial_iop": CandidateInfo("Ustaoglu/Kanclerz iStent cohort", "outside_observational", design="prospective cohort"),
    "istent_standalone_alt": CandidateInfo("Two-or-three-iStent standalone study", "outside_observational", design="prospective study"),
    "istent_multi_dose": CandidateInfo("Katz one-, two-, or three-iStent study", "outside_other", design="randomized trial"),
    "istent_seven_year": CandidateInfo("Seven-year iStent follow-up study", "outside_observational", design="long-term cohort"),
    "nct01444105": CandidateInfo("Two-iStent-versus-SLT trial", "outside_other", design="RCT"),
    "istent_infinite": CandidateInfo("iStent infinite pivotal study", "outside_observational", design="prospective study"),
    "lass_endothelial": CandidateInfo("LASS endothelial-cell post hoc study", "outside_other", design="post hoc primary-data analysis"),
    "morita_istent": CandidateInfo("Morita iStent study", "outside_observational", design="observational study"),
    "guedes_istent": CandidateInfo("Guedes iStent study", "outside_observational", design="observational study"),
    "hooshmand_istent": CandidateInfo("Hooshmand iStent study", "outside_observational", design="observational study"),
    "hydrus_ii": CandidateInfo("HYDRUS II", "outside_other", design="RCT"),
    "horizon": CandidateInfo("HORIZON", "outside_other", design="RCT"),
    "compare": CandidateInfo("COMPARE Hydrus-versus-two-iStent trial", "outside_other", design="RCT"),
    "integrity": CandidateInfo("INTEGRITY iStent-infinite-versus-Hydrus trial", "outside_other", design="RCT"),
    "holmes": CandidateInfo("Holmes Hydrus study", "outside_observational", design="observational study"),
    "chee": CandidateInfo("Chee Hydrus study", "outside_observational", design="observational study"),
    "jablonska": CandidateInfo("Jablonska Hydrus study", "outside_observational", design="observational study"),
    "komzak": CandidateInfo("Komzak Hydrus study", "outside_observational", design="observational study"),
    "weisch": CandidateInfo("Weisch Hydrus study", "outside_observational", design="observational study"),
    "fgb_registry": CandidateInfo("FGB Hydrus registry study", "outside_observational", design="registry study"),
    "hydrus_triple": CandidateInfo("Hydrus triple-procedure study", "outside_observational", design="observational study"),
    "hydrus_realworld": CandidateInfo("Salimi/Otarola Hydrus real-world cohort", "outside_observational", design="retrospective cohort"),
    "hydrus_laroche": CandidateInfo("Laroche Hydrus study", "outside_observational", design="observational study"),
    "hydrus_explant": CandidateInfo("Hydrus explant study", "outside_observational", design="case series"),
    "lee_kdb_istent": CandidateInfo("Lee 2019 KDB-versus-iStent study", "outside_observational", design="retrospective comparison"),
    "arnljots_kdb_istent": CandidateInfo("Arnljots 2021 KDB-versus-iStent inject study", "outside_observational", design="retrospective comparison"),
    "dorairaj_endothelial": CandidateInfo("Dorairaj KDB-versus-iStent endothelial study", "outside_observational", design="fellow-eye comparison"),
    "dorairaj_kdb": CandidateInfo("Dorairaj KDB multicenter study", "outside_observational", design="retrospective study"),
    "sieck_kdb": CandidateInfo("Sieck/Wakil KDB study", "outside_observational", design="retrospective cohort"),
    "salinas_kdb": CandidateInfo("Salinas KDB study", "outside_observational", design="retrospective cohort"),
    "kdb_high_myopia": CandidateInfo("KDB high-myopia study", "outside_observational", design="matched cohort"),
    "kdb_black": CandidateInfo("Laroche/Adebayo KDB Black-patient cohort", "outside_observational", design="retrospective cohort"),
    "kdb_midterm": CandidateInfo("KDB mid-term outcomes study", "outside_observational", design="observational study"),
    "kdb_japanese": CandidateInfo("Japanese KDB study", "outside_observational", design="observational study"),
    "kdb_predictors": CandidateInfo("KDB outcome-predictor study", "outside_observational", design="retrospective cohort"),
    "kdb_indian": CandidateInfo("Indian KDB study", "outside_observational", design="observational study"),
    "kdb_dominican": CandidateInfo("Dominican KDB study", "outside_observational", design="observational study"),
    "kdb_uveitis": CandidateInfo("Miller KDB uveitic-glaucoma study", "outside_observational", design="case series"),
    "vasu_kdb_6year": CandidateInfo("Vasu six-year KDB study", "outside_observational", design="long-term cohort"),
    "chen_abinterno": CandidateInfo("Chen ab-interno trabeculotomy study", "outside_observational", design="comparative cohort"),
    "qiao_gatt_kdb": CandidateInfo("Qiao GATT-versus-KDB study", "outside_observational", design="comparative cohort"),
    "jea_exfoliation": CandidateInfo("Jea exfoliation-versus-POAG Trabectome study", "outside_observational", design="prospective cohort"),
    "jea_trabeculectomy": CandidateInfo("Jea Trabectome-versus-trabeculectomy study", "outside_observational", design="retrospective comparison"),
    "minckler": CandidateInfo("Minckler Trabectome study", "outside_observational", design="case series"),
    "jordan_trabectome": CandidateInfo("Jordan Trabectome study", "outside_observational", design="case series"),
    "mayo_trabectome": CandidateInfo("Mayo Clinic Trabectome study", "outside_observational", design="case series"),
    "trabectome_high_iop": CandidateInfo("High-IOP Trabectome study", "outside_observational", design="prospective cohort"),
    "trabectome_chinese": CandidateInfo("Chinese Trabectome study", "outside_observational", design="observational study"),
    "trabectome_failed": CandidateInfo("Trabectome after failed surgery study", "outside_observational", design="retrospective cohort"),
    "trabectome_race": CandidateInfo("Trabectome race-outcomes study", "outside_observational", design="retrospective cohort"),
    "trabectome_steroid": CandidateInfo("Trabectome steroid-response study", "outside_observational", design="retrospective cohort"),
    "trabectome_iop_tertiles": CandidateInfo("Trabectome IOP-tertile study", "outside_observational", design="retrospective cohort"),
    "trabectome_juvenile": CandidateInfo("Juvenile-onset Trabectome study", "outside_observational", design="retrospective cohort"),
    "trabectome_longterm": CandidateInfo("Long-term Trabectome study", "outside_observational", design="long-term cohort"),
    "trabectome_berlin": CandidateInfo("Berlin Trabectome study", "outside_observational", design="observational study"),
    "trabectome_francis": CandidateInfo("Francis Trabectome study", "outside_observational", design="observational study"),
    "trabectome_kondo": CandidateInfo("Kondo Trabectome comparison", "outside_observational", design="comparative cohort"),
    "yalinbas": CandidateInfo("Yalinbas suture-trabeculotomy comparison", "outside_observational", design="retrospective comparison"),
    "trabectome_angle_closure": CandidateInfo("Trabectome angle-closure study", "outside_observational", design="observational study"),
    "trab360": CandidateInfo("TRAB360 study", "outside_observational", design="retrospective cohort"),
    "grover_gatt": CandidateInfo("Grover foundational GATT study", "outside_observational", design="retrospective cohort"),
    "aktas_2019": CandidateInfo("Aktas 2019 Prolene GATT study", "outside_observational", design="retrospective cohort"),
    "aktas_2022": CandidateInfo("Aktas 2022 GATT study", "outside_observational", design="retrospective cohort"),
    "gatt_four_year": CandidateInfo("Four-year GATT outcomes study", "outside_observational", design="case series"),
    "gatt_severity": CandidateInfo("GATT severity-comparison study", "outside_observational", design="comparative cohort"),
    "gatt_ben_haim": CandidateInfo("Ben Haim GATT study", "outside_observational", design="retrospective cohort"),
    "gatt_failed": CandidateInfo("GATT after prior glaucoma surgery study", "outside_observational", design="retrospective cohort"),
    "gatt_secondary_vitreoretinal": CandidateInfo("GATT after vitreoretinal surgery study", "outside_observational", design="retrospective cohort"),
    "gatt_juvenile_wang": CandidateInfo("Wang juvenile-onset GATT study", "outside_observational", design="retrospective cohort"),
    "gatt_juvenile_sharma": CandidateInfo("Sharma juvenile-onset GATT study", "outside_observational", design="retrospective cohort"),
    "gatt_resistant": CandidateInfo("GATT resistant-glaucoma study", "outside_observational", design="retrospective cohort"),
    "gatt_advanced": CandidateInfo("GATT advanced-glaucoma study", "outside_observational", design="retrospective cohort"),
    "gatt_phaco_wan": CandidateInfo("Wan phaco-GATT study", "outside_observational", design="retrospective cohort"),
    "gatt_congenital": CandidateInfo("GATT congenital-glaucoma study", "outside_observational", design="retrospective cohort"),
    "gatt_trabeculectomy": CandidateInfo("GATT-versus-trabeculectomy study", "outside_observational", design="comparative cohort"),
    "gatt_faria": CandidateInfo("Faria GATT study", "outside_observational", design="observational study"),
    "gatt_steroid_uveitic": CandidateInfo("GATT steroid-induced/uveitic study", "outside_observational", design="retrospective cohort"),
    "gatt_prior_failed_2024": CandidateInfo("2024 GATT prior-failed-surgery study", "outside_observational", design="retrospective cohort"),
    "gatt_phaco_optimization": CandidateInfo("Phaco-GATT optimization study", "outside_observational", design="comparative cohort"),
    "gatt_maheshwari_2026": CandidateInfo("Maheshwari 2026 GATT-versus-microhook study", "outside_observational", design="comparative cohort"),
    "nishida_2026": CandidateInfo("Nishida 2026 trabeculotomy study", "outside_observational", design="observational study"),
    "romeo": CandidateInfo("ROMEO OMNI study", "outside_observational", design="retrospective multicenter study"),
    "omni_midterm": CandidateInfo("Toneatto OMNI mid-term study", "outside_observational", design="observational study"),
    "omni_superior_inferior": CandidateInfo("OMNI superior-versus-inferior study", "outside_observational", design="comparative cohort"),
    "omni_iris": CandidateInfo("IRIS Registry OMNI study", "outside_observational", design="registry study"),
    "abic_grover": CandidateInfo("Grover ab-interno canaloplasty study", "outside_observational", design="prospective study"),
    "abic_gallardo": CandidateInfo("Gallardo ab-interno canaloplasty study", "outside_observational", design="observational study"),
    "itrack_registry": CandidateInfo("iTrack canaloplasty registry study", "outside_observational", design="registry study"),
    "abic_injection": CandidateInfo("ABiC injection-comparison study", "outside_observational", design="comparative cohort"),
    "abic_angle_closure": CandidateInfo("ABiC angle-closure study", "outside_observational", design="observational study"),
    "abic_khaimi": CandidateInfo("Khaimi ab-interno canaloplasty study", "outside_observational", design="case series"),
    "abic_koerber": CandidateInfo("Koerber/Ondrejka ab-interno canaloplasty study", "outside_observational", design="case series"),
    "omni_trainee": CandidateInfo("OMNI trainee-surgeon study", "outside_observational", design="retrospective cohort"),
    "omni_grabska": CandidateInfo("Grabska-Liberek OMNI study", "outside_observational", design="observational study"),
    "omni_martinez": CandidateInfo("Martinez-de-la-Casa OMNI study", "outside_observational", design="observational study"),
    "hydrus_omni": CandidateInfo("Hydrus-versus-OMNI study", "outside_observational", design="comparative cohort"),
    "polish_canaloplasty": CandidateInfo("Polish canaloplasty cohort", "outside_observational", design="observational study"),
    "color_doppler": CandidateInfo("Canaloplasty color-Doppler study", "outside_observational", design="prospective study"),
    "omni_istent_case_series": CandidateInfo("OMNI-after-iStent study", "outside_observational", design="case series"),
    "klabe_omni": CandidateInfo("Klabe standalone OMNI study", "outside_observational", design="prospective study"),
    "itrack_vs_istent": CandidateInfo("iTrack-versus-iStent study", "outside_observational", design="comparative cohort"),
    "streamline_cohort": CandidateInfo("STREAMLINE canaloplasty cohort", "outside_observational", design="prospective study"),
    "streamline_postop": CandidateInfo("STREAMLINE postoperative-outcomes study", "outside_observational", design="post hoc primary-data analysis"),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions(
        "us_istent", "istent_inject_pivotal", "istent_seven_year",
        "istent_standalone_alt", "istent_multi_dose", "two_stents_prostaglandin",
        "horizon", "compare", "jea_exfoliation", "trabectome_chinese",
        "mayo_trabectome", "jea_trabeculectomy", "trabectome_juvenile",
        "sieck_kdb", "dorairaj_kdb", "salinas_kdb", "arimura", "grover_gatt",
        "aktas_2019", "gatt_four_year", "gatt_severity", "gatt_ben_haim",
        "gatt_prior_failed_2024", "romeo", "gemini", "omni_iris",
        "omni_superior_inferior",
    ),
    "claude-patient-2": mentions(
        "istent_inject_pivotal", "two_stents_prostaglandin", "istent_initial_iop",
        "horizon", "compare", "chee", "holmes", "integrity", "komzak",
        "gatt_ben_haim", "gatt_juvenile_sharma", "gatt_phaco_optimization",
        "gatt_severity", "gatt_four_year", "gatt_congenital",
        "trabectome_high_iop", "mayo_trabectome", "trabectome_longterm",
        "kdb_high_myopia", "abic_grover", "abic_gallardo", "itrack_registry",
        "abic_angle_closure", "abic_injection", "polish_canaloplasty", "tvc",
        "omni_iris", "omni_istent_case_series", "evolve", "trident",
    ),
    "claude-patient-3": mentions(
        "hydrus_ii", "horizon", "hydrus_realworld", "istent_inject_pivotal",
        "compare", "integrity", "abic_grover", "polish_canaloplasty",
        "itrack_registry", "abic_angle_closure", "color_doppler",
        "golaszewska", "gatt_ben_haim", "gatt_resistant", "gatt_advanced",
        "gatt_four_year", "gatt_severity",
    ),
    "claude-patient-4": mentions(
        "us_istent", "istent_inject_pivotal", "fan_gaskin", "hydrus_ii",
        "horizon", "compare", "holmes", "integrity", "trabectome_berlin",
        "trabectome_longterm", "mayo_trabectome", "jea_exfoliation",
        "trabectome_high_iop", "gatt_ben_haim", "gatt_juvenile_sharma",
        "gatt_resistant", "gatt_trabeculectomy", "gatt_advanced",
        "gatt_four_year", "gatt_severity", "romeo", "omni_iris",
        "omni_superior_inferior",
    ),
    "claude-clinician-1": mentions(
        "istent_inject_pivotal", "hydrus_ii", "horizon", "compare",
        "falkenberry", "lee_kdb_istent", "dorairaj_endothelial",
        "dorairaj_kdb", "salinas_kdb", "jea_trabeculectomy",
        "trabectome_high_iop", "mayo_trabectome", "trabectome_chinese", "ayub",
        "gatt_four_year", "gatt_secondary_vitreoretinal", "romeo",
        "omni_superior_inferior", "goldberg",
    ),
    "claude-clinician-2": mentions(
        "us_istent", "istent_inject_pivotal", "fan_gaskin", "hydrus_ii",
        "horizon", "compare", "minckler", "jea_exfoliation", "mayo_trabectome",
        "trabectome_juvenile", "trabectome_kondo", "trabectome_high_iop",
        "grover_gatt", "aktas_2019", "gatt_four_year", "gatt_severity",
        "gatt_juvenile_sharma", "kdb_high_myopia",
    ),
    "claude-clinician-3": mentions(
        "istent_inject_pivotal", "two_stents_prostaglandin",
        "istent_initial_iop", "horizon", "trabectome_francis",
        "jea_exfoliation", "trabectome_chinese", "trabectome_high_iop",
        "trabectome_steroid", "gatt_congenital", "gatt_juvenile_wang",
        "gatt_phaco_wan", "gatt_severity", "gatt_ben_haim", "ayub",
        "falkenberry", "ventura", "arimura", "salinas_kdb", "lee_kdb_istent",
        "dorairaj_kdb", "omni_midterm", "omni_superior_inferior", "abic_grover",
        "gemini", "sato_extent", "compare", "integrity", "holmes", "komzak",
    ),
    "claude-clinician-4": mentions(
        "istent_inject_pivotal", "two_stents_prostaglandin", "horizon",
        "grover_gatt", "gatt_four_year", "gatt_severity", "gatt_advanced",
        "gatt_resistant", "gatt_phaco_wan", "trabectome_berlin",
        "jea_exfoliation", "trabectome_failed", "trabectome_longterm", "romeo",
        "tvc", "trabectome_angle_closure", "kdb_high_myopia", "ventura", "ayub",
    ),
    "claude-researcher-1": mentions(
        "hydrus_ii", "horizon", "fea_istent", "us_istent",
        "istent_inject_pivotal", "istent_inject_meds", "compare", "integrity",
        "komzak", "holmes", "fgb_registry", "hydrus_triple", "grover_gatt",
        "aktas_2019", "gatt_ben_haim", "gatt_resistant", "gatt_severity",
        "gatt_prior_failed_2024", "gatt_faria", "gatt_four_year",
        "gatt_steroid_uveitic", "ayub", "vcst_vt", "ting",
        "trabectome_chinese", "minckler", "dorairaj_kdb", "salinas_kdb",
        "kdb_black", "kdb_midterm", "kdb_japanese", "kdb_predictors",
        "kdb_indian", "romeo", "omni_martinez", "omni_grabska", "omni_trainee",
        "hydrus_omni", "polish_canaloplasty",
    ),
    "claude-researcher-2": mentions(
        "istent_inject_pivotal", "nct01444105", "two_stents_prostaglandin",
        "falkenberry", "arnljots_kdb_istent", "sieck_kdb", "horizon", "compare",
        "minckler", "jordan_trabectome", "trabectome_high_iop", "salinas_kdb",
        "kdb_predictors", "kdb_black", "gatt_severity", "qiao_gatt_kdb",
        "ayub", "gatt_secondary_vitreoretinal", "gatt_four_year", "yin", "romeo",
        "evolve", "itrack_vs_istent", "magic", "goldberg", "streamline_cohort",
        "streamline_postop",
    ),
    "claude-researcher-3": mentions(
        "istent_inject_pivotal", "two_stents_prostaglandin",
        "istent_initial_iop", "horizon", "trabectome_failed",
        "trabectome_high_iop", "trabectome_race", "trabectome_steroid",
        "jea_exfoliation", "trabectome_iop_tertiles", "salinas_kdb",
        "kdb_indian", "kdb_predictors", "qiao_gatt_kdb", "kdb_black",
        "dorairaj_kdb", "kdb_midterm", "falkenberry", "arimura",
        "dorairaj_endothelial", "gatt_ben_haim", "gatt_resistant",
        "gatt_advanced", "gatt_four_year", "gatt_severity", "gatt_phaco_wan",
        "ayub", "gemini", "omni_superior_inferior", "romeo",
    ),
    "claude-researcher-4": mentions(
        "istent_inject_pivotal", "two_stents_prostaglandin",
        "istent_initial_iop", "horizon", "gatt_severity", "gatt_failed",
        "gatt_juvenile_wang", "gatt_juvenile_sharma", "gatt_resistant",
        "gatt_advanced", "ayub", "vcst_vt", "romeo", "tvc",
        "trabectome_chinese", "jea_trabeculectomy", "mayo_trabectome",
        "trabectome_high_iop", "dorairaj_kdb", "kdb_black", "kdb_predictors",
        "salinas_kdb", "kdb_midterm", "kdb_japanese", "kdb_dominican",
        "kdb_high_myopia", "itrack_registry", "abic_grover", "abic_gallardo",
    ),
    "gemini-patient-1": mentions(
        "chee", "istent_inject_meds", "holmes", "jablonska",
        "hydrus_laroche", "istent_inject_pivotal",
    ),
    "gemini-patient-2": mentions(
        "horizon", "hydrus_realworld", "omni_midterm", "gatt_juvenile_wang",
    ),
    "gemini-patient-3": mentions(
        "aktas_2022", "istent_inject_meds", "horizon", "weisch",
    ),
    "gemini-patient-4": mentions(
        "gemini", "guedes_istent", "hooshmand_istent", "horizon",
    ),
    "gemini-clinician-1": mentions(
        "chen_abinterno", "falkenberry", "kvt", "istent_inject_pivotal",
        "ventura",
    ),
    "gemini-clinician-2": mentions(
        "horizon", "compare", "abic_koerber", "vasu_kdb_6year",
    ),
    "gemini-clinician-3": mentions(
        "horizon", "gatt_failed", "klabe_omni", "gemini",
        "istent_inject_pivotal",
    ),
    "gemini-clinician-4": mentions(
        "horizon", "kdb_uveitis", "istent_inject_pivotal",
    ),
    "gemini-researcher-1": mentions(
        "morita_istent", "hydrus_ii", "horizon", "vasu_kdb_6year",
    ),
    "gemini-researcher-2": mentions(
        "gatt_faria", "istent_inject_meds", "hydrus_explant",
    ),
    "gemini-researcher-3": mentions(
        "horizon", "compare", "istent_inject_pivotal", "grover_gatt",
    ),
    "gemini-researcher-4": mentions(
        "compare", "romeo", "horizon", "istent_inject_pivotal",
    ),
    "gpt-patient-1": mentions(
        "fea_istent", "us_istent", "istent_inject_meds", "hydrus_ii", "horizon",
        "istent_inject_pivotal", "compare", "ventura", "yin", "ayub",
        "lass_endothelial", "synergy", "grover_gatt", "jordan_trabectome",
        "dorairaj_kdb", "abic_gallardo", "gemini", "gatt_four_year", "romeo",
    ),
    "gpt-patient-2": mentions(
        "hydrus_ii", "horizon", "compare", "us_istent",
        "istent_inject_pivotal", "fan_gaskin", "swedish_migs", "dorairaj_kdb",
        "ventura", "grover_gatt", "trab360", "yin", "romeo", "gemini", "ting",
        "babighian",
    ),
    "gpt-patient-3": mentions(
        "quaranta", "fea_istent", "us_istent", "hydrus_ii", "ting", "horizon",
        "istent_inject_pivotal", "compare", "ventura", "gemini",
        "lass_endothelial", "integrity", "ayub", "maheshwari", "yin",
    ),
    "gpt-patient-4": mentions(
        "fea_istent", "us_istent", "istent_inject_pivotal",
        "two_stents_prostaglandin", "hydrus_ii", "horizon", "compare", "ventura",
        "sieck_kdb", "maheshwari", "sato_phaco", "grover_gatt", "yin", "gemini",
        "romeo", "abic_gallardo",
    ),
    "gpt-clinician-1": mentions(
        "fea_istent", "us_istent", "hydrus_ii", "horizon",
        "istent_inject_pivotal", "fan_gaskin", "compare", "integrity", "ventura",
        "ting", "yin", "sato_extent", "grover_gatt", "dorairaj_kdb",
        "sieck_kdb", "gemini", "romeo", "lass_endothelial", "istent_infinite",
    ),
    "gpt-clinician-2": mentions(
        "fea_istent", "us_istent", "istent_inject_pivotal", "fan_gaskin",
        "swedish_migs", "two_stents_prostaglandin", "hydrus_ii", "horizon",
        "compare", "integrity", "ventura", "yin", "sieck_kdb", "gemini", "romeo",
    ),
    "gpt-clinician-3": mentions(
        "quaranta", "babighian", "sato_phaco", "ting", "sato_extent", "ventura",
        "kicinska", "arimura", "yin", "maheshwari", "ayub", "sieck_kdb",
        "yalinbas", "abic_koerber", "abic_khaimi",
    ),
    "gpt-clinician-4": mentions(
        "babighian", "ting", "sato_phaco", "sato_extent", "ventura",
        "maheshwari", "yin", "ayub", "swedish_migs", "jea_trabeculectomy",
        "sieck_kdb", "minckler",
    ),
    "gpt-researcher-1": mentions(
        "quaranta", "fea_istent", "babighian", "us_istent", "hydrus_ii", "ting",
        "sato_phaco", "horizon", "istent_inject_pivotal", "compare", "ventura",
        "sato_extent", "kicinska", "arimura", "yin", "maheshwari",
        "fan_gaskin", "integrity",
    ),
    "gpt-researcher-2": mentions(
        "arimura", "babighian", "falkenberry", "goldberg", "kicinska",
        "maheshwari", "quaranta", "sato_phaco", "ting", "yin", "ventura",
        "sato_extent", "ayub", "gatt_maheshwari_2026",
    ),
    "gpt-researcher-3": mentions(
        "quaranta", "babighian", "jea_trabeculectomy", "ting", "sato_phaco",
        "sato_standalone", "falkenberry", "ventura", "sato_extent", "kicinska",
        "arimura", "yin", "maheshwari", "ayub", "swedish_migs",
        "nishida_2026",
    ),
    "gpt-researcher-4": mentions(
        "hydrus_ii", "horizon", "compare", "integrity", "fea_istent", "us_istent",
        "istent_inject_meds", "synergy", "istent_inject_pivotal",
        "istent_infinite", "ventura", "dorairaj_kdb", "maheshwari", "yin",
        "grover_gatt", "ting", "babighian", "kicinska", "gemini", "romeo",
        "abic_koerber",
    ),
}


IDENTITY_NOTES = {
    ("gemini-researcher-3", "horizon"): (
        "The response calls the HORIZON trial COMPASS while linking a HORIZON "
        "publication."
    ),
    ("gpt-clinician-2", "fan_gaskin"): (
        "The response attributes the 2024 randomized iStent inject trial to "
        "Ahmed; its primary report is led by Fan Gaskin."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("gemini-researcher-3", "horizon"): "COMPASS study linked to a HORIZON report",
    ("gpt-clinician-2", "fan_gaskin"): "Ahmed et al. 2024 iStent inject trial",
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
    used_candidates = {key for keys in RUN_CANDIDATES.values() for key in keys}
    unused_candidates = sorted(set(CANDIDATES) - used_candidates)
    if unused_candidates:
        raise ValueError(f"Unused candidate keys: {unused_candidates}")

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
                    f"{candidate.status} label not in RIS: "
                    f"{candidate.cochrane_label}"
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
                    "source_file": f"CD015186/{run_id}.md",
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
    """Regenerate the curated CD015186 study-cluster match table."""

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
