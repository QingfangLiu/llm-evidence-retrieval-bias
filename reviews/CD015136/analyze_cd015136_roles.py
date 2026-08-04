#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD015136 role experiment.

Each complete chatbot response is curated once at the underlying-study level.
Cochrane labels are validated against the included, excluded, ongoing, and
awaiting-classification RIS exports supplied with the review data package.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_DIR = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_6"
    / "CD015136-SUP-08-dataPackage"
    / "CD015136-study-data"
)
MATCHES_PATH = REPO_ROOT / "data" / "reviews" / REVIEW_DIR.name / "cd015136_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD015136 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All Cochrane-included study clusters, including clusters never retrieved.
    "alsabbagh": CandidateInfo("Alsabbagh 2012", "included", "Alsabbagh 2012", "RCT"),
    "bosworth": CandidateInfo("Bosworth 2018 (CITIES)", "included", "Bosworth 2018", "RCT"),
    "bynum": CandidateInfo("Bynum 2001", "included", "Bynum 2001", "RCT"),
    "gautier": CandidateInfo("Gautier 2021", "included", "Gautier 2021", "randomized comparative study"),
    "gonzales": CandidateInfo("Gonzales 2021 (TRANSAFE Rx)", "included", "Gonzales 2021", "RCT"),
    "hoda": CandidateInfo("Hoda 2023", "included", "Hoda 2023", "RCT"),
    "hussain": CandidateInfo("Hussain 2024", "included", "Hussain 2024", "RCT"),
    "ibrahim": CandidateInfo("Ibrahim 2022", "included", "Ibrahim 2022", "RCT"),
    "ihekoronye": CandidateInfo("Ihekoronye 2024", "included", "Ihekoronye 2024", "RCT"),
    "kosse": CandidateInfo("Kosse 2019 (ADAPT)", "included", "Kosse 2019", "cluster RCT"),
    "lauffenburger": CandidateInfo("Lauffenburger 2019 (ENGAGE-DM)", "included", "Lauffenburger 2019", "pragmatic RCT"),
    "margolis": CandidateInfo("Margolis 2013 (HyperLink)", "included", "Margolis 2013", "cluster RCT", "Long-term and process reports are grouped with the original HyperLink trial."),
    "mozu": CandidateInfo("Mozu 2023", "included", "Mozu 2023", "RCT"),
    "odegard_map": CandidateInfo("Odegard 2012 (MAP)", "included", "Odegard 2012", "RCT"),
    "powers": CandidateInfo("Powers 1983", "included", "Powers 1983", "RCT"),
    "salmany": CandidateInfo("Salmany 2018", "included", "Salmany 2018", "RCT"),
    "sarayani": CandidateInfo("Sarayani 2018", "included", "Sarayani 2018", "RCT"),
    "scala": CandidateInfo("Scala 2018", "included", "Scala 2018", "RCT"),
    "shdaifat": CandidateInfo("Shdaifat 2022", "included", "Shdaifat 2022", "RCT"),
    "sudas": CandidateInfo("Sudas Na Ayutthaya 2018", "included", "Sudas Na Ayutthaya 2018", "RCT"),
    "young": CandidateInfo("Young 2012 (PARTE)", "included", "Young 2012", "pilot RCT"),

    # Studies explicitly excluded by CD015136.
    "de_vera": CandidateInfo("De Vera 2014 (EmPhAsIS)", "cochrane_excluded", "De Vera 2014", "cluster-RCT protocol"),
    "green": CandidateInfo("Green 2008 (e-BP)", "cochrane_excluded", "Green 2008", "three-arm RCT"),
    "jiang": CandidateInfo("Jiang 2021 (Yixing)", "cochrane_excluded", "Jiang 2021", "non-randomized comparative study"),
    "lyons": CandidateInfo("Lyons 2016 (MASE)", "cochrane_excluded", "Lyons 2016", "RCT"),
    "mikuls": CandidateInfo("Mikuls 2019 (RAmP-UP)", "cochrane_excluded", "Mikuls 2019", "site-randomized trial"),
    "pham": CandidateInfo("Pham 2023", "cochrane_excluded", "Pham 2023", "RCT"),
    "polgreen": CandidateInfo("Polgreen 2020 (PharmText BP)", "cochrane_excluded", "Polgreen 2020", "cluster-RCT protocol"),

    # Studies awaiting classification in the review update.
    "gamal": CandidateInfo("Gamal 2025 (Kidney Health app)", "cochrane_awaiting", "Gamal 2025", "RCT"),
    "gossenheimer": CandidateInfo("Gossenheimer 2023 (TPCDT; NCT05380596)", "cochrane_awaiting", "Gossenheimer 2023", "RCT protocol"),
    "qian": CandidateInfo("Qian 2025 (Alfalfa app)", "cochrane_awaiting", "Qian 2025", "RCT"),

    # Other identifiable primary-study candidates named in the responses.
    "aco_diabetes": CandidateInfo("Nuttall 2024 remote-pharmacist ACO cohort", "outside_observational", design="retrospective comparative cohort"),
    "aguiar": CandidateInfo("Aguiar 2018 diabetes trial", "outside_other", design="hybrid-care RCT"),
    "al_ammari": CandidateInfo("Al Ammari 2021 telepharmacy anticoagulation clinic", "outside_observational", design="uncontrolled service evaluation"),
    "alanazi": CandidateInfo("Alanazi 2022 virtual anticoagulation study", "outside_other", design="crossover comparative study"),
    "barbanel": CandidateInfo("Barbanel 2003 asthma trial", "outside_other", design="small hybrid-care RCT"),
    "better_outcomes": CandidateInfo("Better Outcomes for Everybody respiratory trial", "outside_other", design="community-pharmacy RCT/protocol"),
    "australian_hospital": CandidateInfo("Australian rural-hospital virtual-pharmacy stepped-wedge trial", "outside_unresolved", design="hospital-based stepped-wedge trial"),
    "bandiera": CandidateInfo("Bandiera 2024 (OpTAT)", "outside_other", design="hybrid-care RCT"),
    "brasen": CandidateInfo("Brasen 2019 home-warfarin trial", "outside_other", design="RCT"),
    "butt": CandidateInfo("Butt 2016 diabetes intervention", "outside_other", design="predominantly face-to-face RCT"),
    "carter_2018": CandidateInfo("Carter 2018 (ICARE)", "outside_other", design="cluster RCT"),
    "celeste": CandidateInfo("CELESTE (NCT06108674)", "outside_other", design="ongoing RCT"),
    "chaemkiri": CandidateInfo("Chaemkiri 2026 post-stroke trial", "outside_other", design="RCT published after the review search"),
    "chiang_mai": CandidateInfo("Chiang Mai postal-warfarin study", "outside_observational", design="retrospective cohort"),
    "choe": CandidateInfo("Choe 2005 diabetes study", "outside_other", design="hybrid-care RCT"),
    "cohen": CandidateInfo("Cohen 2019/2020 diabetes-depression telehealth trial", "outside_other", design="RCT with nurse-led telehealth comparator"),
    "cooney": CandidateInfo("Cooney/Drawz 2015 CKD trial", "outside_other", design="pragmatic RCT"),
    "diabetes_nurse": CandidateInfo("Three-arm diabetes specialist nurse telecare trial", "outside_unresolved", design="named only by intervention and design"),
    "dpath": CandidateInfo("D-PATH pharmacist diabetes pathway", "outside_other", design="ongoing community-pharmacy trial"),
    "fox": CandidateInfo("Fox 2025 heart-failure telehealth study", "outside_observational", design="nonrandomized controlled study"),
    "friend": CandidateInfo("FRIEND diabetes trial", "outside_other", design="RCT without a clear pharmacist-led remote intervention"),
    "gammaitoni": CandidateInfo("Gammaitoni 2000 palliative pharmaceutical-care trial", "outside_other", design="RCT"),
    "gay": CandidateInfo("Gay 2006 pediatric diabetes telecare trial", "outside_other", design="RCT"),
    "gerber": CandidateInfo("Gerber 2023 diabetes mHealth trial", "outside_other", design="multicomponent RCT"),
    "greenwood": CandidateInfo("Greenwood 2015 diabetes telehealth trial", "outside_other", design="RCT without a clear pharmacist-led remote intervention"),
    "hale": CandidateInfo("Hale 2016 MedSentry heart-failure trial", "outside_other", design="pilot RCT without pharmacist-led care"),
    "hedegaard": CandidateInfo("Hedegaard 2015 hypertension adherence trial", "outside_other", design="hybrid-care RCT"),
    "home_televisit": CandidateInfo("Older-adult pharmacist home-televisit trial", "outside_unresolved", design="two-site cluster RCT"),
    "hyperlink3": CandidateInfo("Margolis 2022 (HyperLink 3)", "outside_other", design="pragmatic cluster RCT", note="HyperLink 3 is distinct from the included 2013 HyperLink trial cluster."),
    "india_depression": CandidateInfo("India pharmacist-psychiatrist depression trial", "outside_other", design="in-person collaborative-care RCT"),
    "ishani": CandidateInfo("Ishani interprofessional CKD telehealth trial", "outside_other", design="multidisciplinary RCT"),
    "jarab": CandidateInfo("Jarab 2012 diabetes trial", "outside_other", design="hybrid-care RCT"),
    "karaoui": CandidateInfo("Karaoui 2021 anticoagulation transitions trial", "outside_other", design="post-discharge RCT"),
    "kennelty": CandidateInfo("Kennelty 2021 remote clinical-pharmacy trial", "outside_other", design="cluster RCT"),
    "kooij": CandidateInfo("Kooij 2016 (TelCIP)", "outside_other", design="cluster RCT"),
    "kwon": CandidateInfo("Kwon and Denomme 2024 heart-failure study", "outside_observational", design="retrospective single-arm study"),
    "li": CandidateInfo("Li 2022 hypertension telemedicine pilot", "outside_observational", design="prospective nonrandomized cohort"),
    "looney": CandidateInfo("Looney 2026 oral-anticancer monitoring trial", "outside_other", design="randomized study published after the review search"),
    "magid": CandidateInfo("Magid 2013 Heart360 hypertension trial", "outside_other", design="RCT"),
    "maxwell": CandidateInfo("Maxwell 2016 veteran diabetes telehealth study", "outside_observational", design="comparative service evaluation"),
    "mehos": CandidateInfo("Mehos 2000 hypertension trial", "outside_other", design="small RCT"),
    "missouri_asthma": CandidateInfo("Missouri telephonic asthma medication-review pilot", "outside_unresolved", design="pilot comparative study"),
    "murray": CandidateInfo("Murray 2007 heart-failure adherence trial", "outside_other", design="hybrid-care RCT"),
    "nct00869076": CandidateInfo("NCT00869076 pharmacist diabetes-management trial", "outside_other", design="RCT with unclear remote delivery"),
    "nct01270594": CandidateInfo("NCT01270594 COPD telepharmacy pilot", "outside_other", design="pilot RCT"),
    "nct01534559": CandidateInfo("NCT01534559 post-discharge medicines-management trial", "outside_other", design="RCT"),
    "norouzi": CandidateInfo("Norouzi 2023 tele-visit study", "outside_observational", design="before-after study without pharmacist-specific delivery"),
    "norway": CandidateInfo("Norway chronic-condition telemedicine trial", "outside_other", design="pragmatic RCT without pharmacist-specific delivery"),
    "nps_hf": CandidateInfo("NPS MedicineWise heart-failure app pilot", "outside_other", design="pilot RCT"),
    "oconnor": CandidateInfo("O'Connor 2014 diabetes telephone-outreach trial", "outside_other", design="pragmatic RCT with mixed professional delivery"),
    "odegard_2005": CandidateInfo("Odegard 2005 poorly controlled diabetes trial", "outside_other", design="hybrid-care RCT"),
    "online_anticoag": CandidateInfo("Hospital versus online anticoagulation-clinic cohort", "outside_observational", design="comparative cohort"),
    "poonprapai": CandidateInfo("Poonprapai 2022 diabetes app trial", "outside_other", design="RCT"),
    "rural_pilot": CandidateInfo("Rural centralized pharmacist-telehealth pilot", "outside_observational", design="uncontrolled pilot"),
    "rural_quality": CandidateInfo("Rural telepharmacy medication-use quality study, 2013-2019", "outside_observational", design="comparative observational study"),
    "rural_rxaction": CandidateInfo("Charrois Rural RxACTION trial", "outside_other", design="community-pharmacist RCT with in-person care"),
    "salvo": CandidateInfo("Salvo and Brooks 2012 diabetes study", "outside_observational", design="retrospective comparative cohort"),
    "saudi_warfarin": CandidateInfo("Saudi warfarin telepharmacy cohort", "outside_observational", design="retrospective cohort"),
    "seamon": CandidateInfo("Seamon 2021 rural diabetes telemedicine program", "outside_observational", design="program evaluation"),
    "smart_warfarin": CandidateInfo("SMART app-assisted warfarin home-management trial", "outside_other", design="RCT protocol"),
    "spain_hiv": CandidateInfo("Spanish HIV teleconsultation and home-delivery cohort", "outside_observational", design="cohort study"),
    "stic2it": CandidateInfo("Choudhry 2018 (STIC2IT)", "outside_other", design="cluster RCT"),
    "swiss_tbc": CandidateInfo("Swiss TBC-HTA trial", "outside_unresolved", design="named hybrid telehealth trial"),
    "taiwan_hbpm": CandidateInfo("Taiwan digital HBPM case-management study", "outside_observational", design="nationwide observational study"),
    "technomed": CandidateInfo("Lau 2022 (TECHNOMED)", "outside_other", design="RCT"),
    "telnet": CandidateInfo("TELnet@NRW", "outside_other", design="stepped-wedge cluster RCT without pharmacist-specific delivery"),
    "tsuyuki": CandidateInfo("Tsuyuki 2015 RxACTION trial", "outside_other", design="face-to-face pharmacist RCT"),
    "uae_192": CandidateInfo("UAE multifactorial pharmacist intervention, n=192", "outside_other", design="hybrid-care RCT"),
    "university_pilot": CandidateInfo("University telepharmacist chronic-care pilot", "outside_observational", design="uncontrolled pilot"),
    "virtual_hospital": CandidateInfo("Spanish HIV Virtual Hospital trial", "outside_other", design="RCT"),
    "video_anticoag": CandidateInfo("Video versus face-to-face anticoagulation counseling trial", "outside_other", design="RCT"),
    "wang_2022": CandidateInfo("Wang 2022 diabetes and hypertension trial", "outside_other", design="post-discharge RCT"),
    "wang_2024": CandidateInfo("Wang 2024 heart-failure management trial", "outside_other", design="multicenter RCT"),
    "wang_2026": CandidateInfo("Wang 2026 remote-warfarin trial", "outside_other", design="RCT published after the review search"),
    "wu": CandidateInfo("Wu 2025 breast-cancer remote follow-up trial", "outside_other", design="RCT published after the review search"),
    "wolverton": CandidateInfo("Wolverton 2026 hypertension telehealth cohort", "outside_observational", design="retrospective comparative cohort"),
    "zhang": CandidateInfo("Zhang 2021 ambulatory cancer-pain trial", "outside_other", design="RCT"),
    "zhu": CandidateInfo("Zhu 2021 internet-based warfarin trial", "outside_other", design="multicenter RCT"),
    "zillich": CandidateInfo("Zillich 2014 home-health MTM trial", "outside_other", design="pragmatic RCT"),
    "atrium_hiv": CandidateInfo("Atrium Health HIV specialty-pharmacy cohort", "outside_observational", design="retrospective cohort"),
    "rickles": CandidateInfo("Rickles 2005 antidepressant telemonitoring trial", "outside_other", design="RCT"),
    "zhai": CandidateInfo("Zhai 2020 hypertension text-messaging trial", "outside_other", design="RCT led by pharmacy students"),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions("ibrahim", "mozu", "green", "magid", "maxwell", "uae_192", "zillich", "wu"),
    "claude-patient-2": mentions("margolis", "polgreen", "rural_rxaction", "sarayani", "karaoui", "nct01270594", "hale", "kwon", "tsuyuki"),
    "claude-patient-3": mentions("sarayani", "ihekoronye", "odegard_map", "lyons", "diabetes_nurse", "margolis", "mozu", "qian", "smart_warfarin", "jiang", "nct01270594", "better_outcomes", "stic2it", "university_pilot", "nct01534559"),
    "claude-patient-4": mentions("stic2it", "wang_2022", "gerber", "wu", "qian", "zhu", "australian_hospital", "rural_pilot", "swiss_tbc"),
    "claude-clinician-1": mentions("margolis", "li", "gerber", "butt", "seamon", "aco_diabetes", "saudi_warfarin", "zhu", "qian"),
    "claude-clinician-2": mentions("margolis", "hyperlink3", "nct00869076", "technomed", "sudas", "al_ammari", "qian", "zhu", "video_anticoag", "online_anticoag", "murray", "hale", "norway"),
    "claude-clinician-3": mentions("margolis", "ibrahim", "mozu", "celeste", "gossenheimer", "jiang", "qian", "wang_2024", "chiang_mai"),
    "claude-clinician-4": mentions("margolis", "hyperlink3", "li", "cohen", "karaoui", "ishani", "better_outcomes", "celeste"),
    "claude-researcher-1": mentions("margolis", "hyperlink3", "cooney", "ihekoronye", "brasen", "zhu", "qian", "murray", "kwon", "smart_warfarin"),
    "claude-researcher-2": mentions("stic2it", "uae_192", "rural_pilot", "gamal", "wang_2024", "home_televisit", "wu", "qian", "brasen", "zhu", "chiang_mai", "spain_hiv", "virtual_hospital", "telnet"),
    "claude-researcher-3": mentions("karaoui", "taiwan_hbpm", "hyperlink3", "wang_2022", "gerber", "ihekoronye", "gay", "alanazi", "al_ammari", "fox", "de_vera", "bynum", "india_depression", "dpath"),
    "claude-researcher-4": mentions("al_ammari", "greenwood", "ihekoronye", "sarayani", "friend", "aco_diabetes", "hyperlink3", "ibrahim", "li", "stic2it", "rural_quality", "spain_hiv", "atrium_hiv", "young", "missouri_asthma", "bynum", "fox", "nps_hf"),
    "gemini-patient-1": mentions("ibrahim", "carter_2018", "norouzi"),
    "gemini-patient-2": mentions("carter_2018", "kennelty"),
    "gemini-patient-3": mentions("margolis", "kennelty", "norouzi"),
    "gemini-patient-4": mentions("margolis", "stic2it", "ibrahim"),
    "gemini-clinician-1": mentions("jarab", "margolis", "li", "carter_2018"),
    "gemini-clinician-2": mentions("stic2it", "kennelty", "ibrahim"),
    "gemini-clinician-3": mentions("mozu", "hyperlink3", "cohen"),
    "gemini-clinician-4": mentions("ibrahim", "carter_2018", "norouzi"),
    "gemini-researcher-1": mentions("ibrahim", "zhai", "young", "norouzi"),
    "gemini-researcher-2": mentions("ibrahim", "norouzi", "odegard_map"),
    "gemini-researcher-3": mentions("hyperlink3", "carter_2018", "stic2it", "young"),
    "gemini-researcher-4": mentions("margolis", "jarab", "stic2it"),
    "gpt-patient-1": mentions("green", "margolis", "mozu", "lyons", "sarayani", "wang_2022", "gerber", "chaemkiri", "oconnor"),
    "gpt-patient-2": mentions("green", "margolis", "ibrahim", "mozu", "sarayani", "gerber", "oconnor", "barbanel", "young", "cooney", "pham", "fox"),
    "gpt-patient-3": mentions("green", "margolis", "mozu", "sarayani", "oconnor", "cooney", "pham", "zillich", "gerber", "aguiar", "hedegaard", "odegard_2005"),
    "gpt-patient-4": mentions("green", "margolis", "technomed", "ibrahim", "mozu", "sarayani", "lyons", "lauffenburger", "stic2it", "ihekoronye", "shdaifat", "sudas", "pham", "wolverton"),
    "gpt-clinician-1": mentions("green", "margolis", "ibrahim", "mozu", "sarayani", "lauffenburger", "gautier", "gerber", "kosse", "shdaifat", "cooney", "sudas", "gonzales", "zhang", "fox"),
    "gpt-clinician-2": mentions("green", "margolis", "technomed", "stic2it", "lyons", "sarayani", "cooney", "li", "odegard_2005", "barbanel", "hedegaard"),
    "gpt-clinician-3": mentions("green", "margolis", "stic2it", "lyons", "sarayani", "gerber", "cooney", "looney", "odegard_2005", "bandiera", "li", "fox"),
    "gpt-clinician-4": mentions("mehos", "green", "margolis", "technomed", "mozu", "lyons", "odegard_map", "sarayani", "ihekoronye", "oconnor", "young", "sudas", "odegard_2005", "aguiar", "barbanel"),
    "gpt-researcher-1": mentions("mehos", "green", "margolis", "mozu", "lyons", "sarayani", "lauffenburger", "kooij", "young", "cooney", "salvo", "barbanel", "odegard_2005", "choe", "hedegaard", "aguiar", "wang_2022", "wang_2024"),
    "gpt-researcher-2": mentions("green", "margolis", "mozu", "lauffenburger", "sarayani", "lyons", "young", "rickles", "sudas", "zhang", "fox", "wang_2026", "gerber", "barbanel", "odegard_2005", "wang_2024"),
    "gpt-researcher-3": mentions("mehos", "green", "margolis", "bosworth", "stic2it", "ibrahim", "mozu", "li", "lauffenburger", "sarayani", "gautier", "hoda", "ihekoronye", "hussain", "gay", "kosse", "shdaifat", "gammaitoni", "sudas", "gonzales", "chaemkiri", "fox"),
    "gpt-researcher-4": mentions("mehos", "green", "margolis", "bosworth", "ibrahim", "mozu", "lyons", "sarayani", "lauffenburger", "gautier", "poonprapai", "hoda", "ihekoronye", "young", "kosse", "shdaifat", "sudas", "mikuls", "gonzales", "odegard_2005", "stic2it", "gerber", "wang_2022", "cooney", "li"),
}


IDENTITY_NOTES = {
    ("claude-patient-1", "ibrahim"): "The response attributes the UAE trial to Al Hail; the included RIS identifies Ibrahim 2022.",
    ("claude-researcher-2", "gamal"): "The response calls the Kidney Health app study a hypertension pilot; the Cochrane awaiting record identifies a CKD trial by Gamal 2025.",
    ("gpt-patient-1", "oconnor"): "The response calls PMID 25315207 Fischer et al.; the primary report is O'Connor et al. 2014.",
    ("gpt-patient-3", "sarayani"): "The response leads with Jahangard-Rafsanjani; the included RIS labels this study cluster Sarayani 2018.",
    ("gpt-patient-4", "sarayani"): "The response leads with Jahangard-Rafsanjani; the included RIS labels this study cluster Sarayani 2018.",
    ("gpt-clinician-2", "sarayani"): "The response leads with Jahangard-Rafsanjani; the included RIS labels this study cluster Sarayani 2018.",
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-patient-1", "ibrahim"): "Al Hail et al. (UAE trial)",
    ("claude-researcher-2", "gamal"): "Kidney Health app hypertension pilot",
    ("gpt-patient-1", "oconnor"): "Fischer et al. 2014 (PMID 25315207)",
    ("gpt-patient-3", "sarayani"): "Jahangard-Rafsanjani et al. 2018",
    ("gpt-patient-4", "sarayani"): "Jahangard-Rafsanjani et al. 2018",
    ("gpt-clinician-2", "sarayani"): "Jahangard-Rafsanjani et al. 2018",
}


def ris_study_labels(path: Path) -> set[str]:
    """Read unique Cochrane study labels from an RIS export."""

    return {
        match.group(1).strip()
        for match in re.finditer(
            r"^NS  - (.+)$", path.read_text(encoding="utf-8-sig"), re.MULTILINE
        )
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
        "included": ris_study_labels(SOURCE_DIR / "CD015136-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD015136-excluded.ris"),
        "cochrane_ongoing": ris_study_labels(SOURCE_DIR / "CD015136-ongoing.ris"),
        "cochrane_awaiting": ris_study_labels(SOURCE_DIR / "CD015136-awaiting.ris"),
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
            notes = "; ".join(value for value in (identity_note, candidate.note) if value)
            rows.append(
                {
                    "run_id": run_id,
                    "model": model,
                    "role_id": role_id,
                    "replicate": int(replicate_text),
                    "source_file": f"reviews/CD015136/{run_id}.md",
                    "reported_citation": REPORTED_CITATION_OVERRIDES.get((run_id, key), candidate.label),
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
    """Regenerate the curated CD015136 study-cluster match table."""

    rows = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    status_counts = Counter(str(row["ground_truth_status"]) for row in rows)
    retrieved_included = {
        str(row["cochrane_study_label"])
        for row in rows
        if row["ground_truth_status"] == "included"
    }
    all_included = ris_study_labels(SOURCE_DIR / "CD015136-included.ris")
    print(f"Runs: {len(RUN_CANDIDATES)}")
    print(f"Study-cluster candidates: {len(rows)}")
    print(
        "Statuses: "
        + ", ".join(
            f"{status}={count}" for status, count in sorted(status_counts.items())
        )
    )
    print(
        f"Included study clusters retrieved: {len(retrieved_included)}/{len(all_included)}"
    )
    print("Missed included clusters: " + ", ".join(sorted(all_included - retrieved_included)))
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
