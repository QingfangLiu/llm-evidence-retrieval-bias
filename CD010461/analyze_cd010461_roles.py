#!/usr/bin/env python3
"""Prepare curated citation matches for the CD010461 user-role experiment.

The chatbot responses use heterogeneous citation formats. This script records
each unique, resolvable primary-study candidate named anywhere in the full
response once per response, validates Cochrane labels directly against the
study-data RIS exports, and writes the audit table consumed by the
retrieval-bias demo. Terminal reference lists help resolve identity but do not
define which candidates count as retrieved.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_DIR = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_6"
    / "CD010461-SUP-07-dataPackage"
    / "CD010461-study-data"
)
MATCHES_PATH = REVIEW_DIR / "cd010461_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD010461 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # Cochrane-included studies.
    "esfahani": CandidateInfo(
        "Nasr-Esfahani 2016 zeta-selection trial",
        "included",
        "Esfahani 2016",
        "double-blind RCT",
    ),
    "miller": CandidateInfo(
        "Miller 2019 (HABSelect)", "included", "Miller 2019", "multicenter RCT"
    ),
    "parmegiani": CandidateInfo(
        "Parmegiani 2012a PICSI vs Sperm Slow",
        "included",
        "Parmegiani 2012a",
        "RCT",
    ),
    "worrilow": CandidateInfo(
        "Worrilow 2013", "included", "Worrilow 2013", "multicenter RCT"
    ),
    "yetkinel": CandidateInfo(
        "Yetkinel 2019", "included", "Yetkinel 2019", "RCT"
    ),
    # Studies explicitly excluded by CD010461.
    "antinori": CandidateInfo(
        "Antinori 2008", "cochrane_excluded", "Antinori 2008", "RCT"
    ),
    "balaban": CandidateInfo(
        "Balaban 2011", "cochrane_excluded", "Balaban 2011", "RCT"
    ),
    "battista": CandidateInfo(
        "Battista/La Sala IMSI RCT",
        "cochrane_excluded",
        "Battista 2017",
        "retracted RCT",
        "The randomized report was retracted.",
    ),
    "casciani": CandidateInfo(
        "Casciani 2014 zona-bound sperm study",
        "cochrane_excluded",
        "Casciani 2014",
        "comparative study",
    ),
    "fleming": CandidateInfo(
        "Fleming 2007 electrophoretic sperm-isolation study",
        "cochrane_excluded",
        "Fleming 2007",
        "controlled split-sample study",
    ),
    "ghosh": CandidateInfo(
        "Ghosh 2007/2012 birefringence study",
        "cochrane_excluded",
        "Ghosh 2007",
        "randomized study",
    ),
    "gianaroli": CandidateInfo(
        "Gianaroli 2008 birefringence study",
        "cochrane_excluded",
        "Gianaroli 2008",
        "RCT",
    ),
    "jin": CandidateInfo(
        "Jin 2015/2016 zona-bound sperm study",
        "cochrane_excluded",
        "Jin 2015",
        "RCT",
    ),
    "kim": CandidateInfo(
        "Kim 2014 IMSI study", "cochrane_excluded", "Kim 2014", "prospective study"
    ),
    "knez": CandidateInfo(
        "Knez 2011 repeated-failure IMSI study",
        "cochrane_excluded",
        "Knez 2011",
        "prospective comparative study",
    ),
    "nct03659812": CandidateInfo(
        "Gonzalez-Ravina 2022 donor-IUI MACS trial",
        "cochrane_excluded",
        "NCT03659812 2018",
        "multicenter RCT",
    ),
    "norozi": CandidateInfo(
        "Norozi-Hafshejani 2022 MACS-DGC trial",
        "cochrane_excluded",
        "Norozi-Hafshejani 2022",
        "single-blind clinical trial",
    ),
    "setti_2011": CandidateInfo(
        "Setti 2011 IMSI study",
        "cochrane_excluded",
        "Setti 2011",
        "prospective randomized study",
    ),
    "setti_2012b": CandidateInfo(
        "Setti 2012b advanced-maternal-age IMSI trial",
        "cochrane_excluded",
        "Setti 2012b",
        "RCT",
    ),
    "stimpfel": CandidateInfo(
        "Stimpfel 2017/2018 MACS sibling-oocyte study",
        "cochrane_excluded",
        "Stimpfel 2017",
        "prospective sibling-oocyte study",
        "The Cochrane data package records this study as not randomized.",
    ),
    "west": CandidateInfo(
        "West 2022 HABSelect mechanistic analysis",
        "cochrane_excluded",
        "West 2022",
        "secondary mechanistic analysis",
        "The Cochrane data package records this report as the wrong study design.",
    ),
    # Studies awaiting classification in the CD010461 data package.
    "alegre_2016a": CandidateInfo(
        "Alegre 2016 embryo-quality PICSI trial",
        "cochrane_awaiting",
        "Alegre 2016a",
        "sibling-oocyte RCT",
    ),
    "alegre_2025": CandidateInfo(
        "Alegre 2025 triple-blind PICSI trial",
        "cochrane_awaiting",
        "Alegre 2025",
        "triple-blind RCT",
    ),
    "barroso": CandidateInfo(
        "Barroso-Villa 2018 MACS trial",
        "cochrane_awaiting",
        "Barroso-Villa 2018",
        "pilot triple-blind RCT",
    ),
    "de_geyter": CandidateInfo(
        "De Geyter 2019 flow-cytometry trial",
        "cochrane_awaiting",
        "De Geyter 2019",
        "double-blind RCT",
    ),
    "ferrer": CandidateInfo(
        "Ferrer Buitrago 2024 microfluidics trial",
        "cochrane_awaiting",
        "Ferrer Buitrago 2024",
        "sibling-oocyte pilot RCT",
    ),
    "ganeva": CandidateInfo(
        "Ganeva 2024 zona-adhesion study",
        "cochrane_awaiting",
        "Ganeva 2024",
        "prospective randomized study",
    ),
    "hasanen": CandidateInfo(
        "Hasanen 2020 PICSI-vs-MACS trial",
        "cochrane_awaiting",
        "Hasanen 2020",
        "RCT",
    ),
    "hozyen": CandidateInfo(
        "Hozyen 2022 four-arm sperm-selection trial",
        "cochrane_awaiting",
        "Hozyen 2022",
        "RCT",
    ),
    "huniadi": CandidateInfo(
        "Huniadi/Zaha 2023 microfluidics study",
        "cochrane_awaiting",
        "Huniadi 2023",
        "retrospective comparative study",
    ),
    "karimi": CandidateInfo(
        "Karimi 2020 DGC-zeta trial",
        "cochrane_awaiting",
        "Karimi 2020",
        "single-blind RCT",
    ),
    "majumdar": CandidateInfo(
        "Majumdar 2013 PICSI trial",
        "cochrane_awaiting",
        "Majumdar 2013",
        "RCT",
    ),
    "nayar_2022": CandidateInfo(
        "Nayar 2022 multi-arm sperm-selection study",
        "cochrane_awaiting",
        "Nayar 2022",
        "comparative study",
    ),
    "ozaltin": CandidateInfo(
        "Ozaltin 2023 sperm-chip study",
        "cochrane_awaiting",
        "Ozaltin 2023",
        "prospective cohort",
    ),
    "romany": CandidateInfo(
        "Romany 2014 donor-oocyte MACS trial",
        "cochrane_awaiting",
        "Romany 2014",
        "triple-blind RCT",
    ),
    "ruvolo": CandidateInfo(
        "Ruvolo 2023 cumulus-oophorus selection study",
        "cochrane_awaiting",
        "Ruvolo 2023",
        "pilot study",
    ),
    "troya": CandidateInfo(
        "Troya 2015 MACS/PICSI trial",
        "cochrane_awaiting",
        "Troya 2015",
        "three-arm randomized study",
    ),
    "ziarati": CandidateInfo(
        "Ziarati 2018 MACS-DGC trial",
        "cochrane_awaiting",
        "Ziarati 2018",
        "prospective randomized trial",
    ),
    # Studies classified as ongoing in the CD010461 data package.
    "quinn": CandidateInfo(
        "Quinn 2022 / NCT03085433 microfluidics trial",
        "cochrane_ongoing",
        "NCT03085433 2017",
        "pragmatic RCT",
    ),
    "nct06005311": CandidateInfo(
        "NCT06005311 microfluidic-chip trial",
        "cochrane_ongoing",
        "NCT06005311 2023",
        "ongoing RCT",
    ),
    # Other primary-study candidates named in the responses.
    "adolfsson": CandidateInfo(
        "Adolfsson 2024 Zymot clinical-validation study", "outside_other", design="validation study"
    ),
    "ahmadi": CandidateInfo(
        "Ahmadi 2022 MACS/PICSI laboratory study", "outside_other", design="comparative laboratory study"
    ),
    "amjadi": CandidateInfo(
        "Amjadi 2022 microfluidics cohort", "outside_observational", design="cohort study"
    ),
    "anbari": CandidateInfo(
        "Anbari 2021 microfluidics pilot", "outside_other", design="pilot comparative study"
    ),
    "aydin": CandidateInfo(
        "Aydin/Saylan 2022 Fertile Chip trial", "outside_other", design="RCT"
    ),
    "balakier": CandidateInfo(
        "Balakier 2026 Zymot cohort", "outside_observational", design="retrospective cohort"
    ),
    "bartoov": CandidateInfo(
        "Bartoov 2003 IMSI study", "outside_other", design="comparative study"
    ),
    "braga": CandidateInfo(
        "Braga 2012 unexplained-infertility IMSI trial", "outside_other", design="RCT"
    ),
    "degheidy": CandidateInfo(
        "Degheidy 2015 MACS study", "outside_other", design="comparative study"
    ),
    "de_vos": CandidateInfo(
        "De Vos 2013 IMSI sibling-oocyte study", "outside_other", design="randomized sibling-oocyte study"
    ),
    "dirican": CandidateInfo(
        "Dirican 2008 MACS-DGC study", "outside_observational", design="nonrandomized comparative study"
    ),
    "duarte": CandidateInfo(
        "Duarte 2017 zeta-potential study", "outside_other", design="prospective study"
    ),
    "el_khattabi": CandidateInfo(
        "El Khattabi 2013 IMSI cohort", "outside_observational", design="prospective nonrandomized study"
    ),
    "gatimel": CandidateInfo(
        "Gatimel 2016 repeated-failure IMSI study", "outside_observational", design="retrospective comparative study"
    ),
    "gil_julia_2021": CandidateInfo(
        "Gil Julia 2021 autologous-oocyte MACS cohort", "outside_observational", design="retrospective cohort"
    ),
    "gil_julia_2022": CandidateInfo(
        "Gil Julia 2022 donor-oocyte MACS cohort", "outside_observational", design="retrospective cohort"
    ),
    "gil_julia_safety": CandidateInfo(
        "Gil Julia 2023 MACS obstetric-safety cohort", "outside_observational", design="retrospective cohort"
    ),
    "godiwala": CandidateInfo(
        "Godiwala 2022 paired microfluidics cohort", "outside_observational", design="paired retrospective cohort"
    ),
    "godiwala_2024": CandidateInfo(
        "Godiwala 2024 microfluidics sibling-oocyte trial", "outside_other", design="sibling-oocyte trial"
    ),
    "huong": CandidateInfo(
        "Huong 2026 microfluidics trial", "outside_other", design="RCT"
    ),
    "imsi_large_cohort": CandidateInfo(
        "Unspecified 2013 large IMSI cohort", "outside_observational", design="cohort study"
    ),
    "invicsi": CandidateInfo(
        "INVICSI trial", "outside_other", design="multicenter RCT of ICSI versus conventional IVF"
    ),
    "jeseta": CandidateInfo(
        "Jeseta 2018 MACS study", "outside_other", design="sibling-oocyte study"
    ),
    "jrct_microfluidics": CandidateInfo(
        "jRCT1040230045 microfluidic-device comparison", "outside_other", design="prospective comparative study"
    ),
    "karabulut": CandidateInfo(
        "Karabulut 2019 IMSI cohort", "outside_observational", design="cohort study"
    ),
    "kerala": CandidateInfo(
        "Kerala 2024 MACS cohort", "outside_observational", design="retrospective observational study"
    ),
    "kocur": CandidateInfo(
        "Kocur 2022 microfluidics-ploidy study", "outside_other", design="comparative study"
    ),
    "korosi": CandidateInfo(
        "Korosi 2017 PICSI/myo-inositol trial", "outside_other", design="RCT"
    ),
    "leandri": CandidateInfo(
        "Leandri 2013 IMSI trial", "outside_other", design="multicenter RCT"
    ),
    "leisinger": CandidateInfo(
        "Leisinger 2021 microfluidics study", "outside_other", design="sibling-oocyte study"
    ),
    "mangoli": CandidateInfo(
        "Mangoli/Sabet 2021 cumulus-column trial", "outside_other", design="single-blind clinical trial"
    ),
    "mei": CandidateInfo(
        "Mei 2021/2022 high-DFI MACS study", "outside_other", design="comparative study"
    ),
    "mokanszki": CandidateInfo(
        "Mokanszki 2014 PICSI cohort", "outside_observational", design="observational cohort"
    ),
    "moubasher": CandidateInfo(
        "Moubasher 2021 IMSI cohort", "outside_observational", design="open prospective cohort"
    ),
    "nct00114725": CandidateInfo(
        "NCT00114725 laser-assisted ICSI trial", "outside_other", design="RCT"
    ),
    "nct04496232": CandidateInfo(
        "NCT04496232 PICSI/second-ejaculate trial", "outside_ongoing", design="registered RCT"
    ),
    "nct06670586": CandidateInfo(
        "NCT06670586 sibling-oocyte ICSI-vs-IVF trial", "outside_ongoing", design="registered RCT"
    ),
    "nct07240779": CandidateInfo(
        "NCT07240779 PICSI-vs-Zymot trial", "outside_ongoing", design="registered RCT"
    ),
    "novoselsky": CandidateInfo(
        "Novoselsky Persky 2021 PICSI study", "outside_other", design="sibling-oocyte study"
    ),
    "oliveira": CandidateInfo(
        "Oliveira 2011 repeated-implantation-failure IMSI study", "outside_observational", design="prospective comparative study"
    ),
    "ozcan": CandidateInfo(
        "Ozcan 2021 microfluidics study", "outside_other", design="comparative study"
    ),
    "pacheco": CandidateInfo(
        "Pacheco 2020 high-SDF MACS cohort", "outside_observational", design="retrospective cohort"
    ),
    "parrella": CandidateInfo(
        "Parrella/Lara-Cerrillo 2022 high-DSB microfluidics cohort", "outside_observational", design="paired retrospective cohort"
    ),
    "piezo_fertil_steril": CandidateInfo(
        "2024 multicenter PIEZO-ICSI sibling-oocyte trial", "outside_other", design="sibling-oocyte trial"
    ),
    "piezo_korea": CandidateInfo(
        "2025 Korean PIEZO-ICSI trial", "outside_other", design="sibling-oocyte RCT"
    ),
    "piezo_p167": CandidateInfo(
        "2025 P-167 PIEZO-ICSI trial", "outside_other", design="conference-report RCT"
    ),
    "pujol": CandidateInfo(
        "Pujol microfluidics DNA-fragmentation study", "outside_other", design="comparative study"
    ),
    "sanchez_martin": CandidateInfo(
        "Sanchez-Martin 2017 MACS study", "outside_other", design="comparative study"
    ),
    "shakeri": CandidateInfo(
        "Shakeri 2026 IMSI trial", "outside_other", design="double-blind RCT"
    ),
    "sheikhi": CandidateInfo(
        "Sheikhi 2013 MACS-DGC study", "outside_other", design="comparative study"
    ),
    "sibling_microfluidic_2025": CandidateInfo(
        "Unspecified 2025 microfluidics sibling-cohort study", "outside_other", design="prospective sibling-cohort study"
    ),
    "tavalaee_2021": CandidateInfo(
        "Tavalaee 2021 cumulus-column trial", "outside_other", design="single-blind clinical trial"
    ),
    "taylor": CandidateInfo(
        "Taylor 2021 microfluidics sibling-oocyte study", "outside_other", design="sibling-oocyte study"
    ),
    "thanapongpibul": CandidateInfo(
        "Thanapongpibul 2026 microfluidics sibling-oocyte study", "outside_other", design="randomized sibling-oocyte study"
    ),
    "uyar": CandidateInfo(
        "Uyar/Okan 2019 Fertile Plus sibling-oocyte study", "outside_other", design="sibling-oocyte study"
    ),
    "van_den_bergh": CandidateInfo(
        "Van den Bergh 2009 HA-binding sibling-oocyte study", "outside_other", design="randomized sibling-oocyte study"
    ),
    "wilding": CandidateInfo(
        "Wilding 2011 IMSI study", "outside_other", design="prospective randomized study"
    ),
    "yildiz_2019": CandidateInfo(
        "Yildiz and Yuksel 2019 microfluidics study", "outside_other", design="comparative study"
    ),
    "yousefi": CandidateInfo(
        "Yousefi 2025 cumulus-cell-column trial", "outside_other", design="double-blind RCT"
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions("miller", "worrilow", "west", "korosi", "alegre_2025", "hozyen", "hasanen", "pacheco", "ziarati", "romany", "nct03659812", "bartoov", "antinori", "leandri", "braga", "setti_2012b", "gatimel", "balaban", "setti_2011", "moubasher", "yetkinel", "aydin", "uyar", "quinn", "godiwala", "amjadi", "parrella", "ozaltin", "huong"),
    "claude-patient-2": mentions("miller", "west", "parmegiani", "korosi", "hasanen", "hozyen", "yetkinel", "ozcan", "ozaltin", "huniadi", "parrella", "yildiz_2019", "pujol", "kocur", "nct03659812", "ziarati", "romany", "gil_julia_2021", "gil_julia_2022", "pacheco", "antinori", "leandri", "moubasher", "knez", "gatimel", "oliveira", "yousefi", "nayar_2022"),
    "claude-patient-3": mentions("miller", "alegre_2025", "ziarati", "nct03659812", "pacheco", "gil_julia_2021", "kerala", "aydin", "parrella", "godiwala", "amjadi", "ozaltin", "leandri", "antinori", "moubasher", "knez", "oliveira", "invicsi"),
    "claude-patient-4": mentions("miller", "west", "alegre_2025", "korosi", "hozyen", "nct03659812", "romany", "stimpfel", "leandri", "gatimel", "el_khattabi", "oliveira", "moubasher", "imsi_large_cohort", "knez", "antinori", "quinn", "yetkinel", "ozcan", "yildiz_2019", "ozaltin", "parrella", "pujol", "kocur", "sibling_microfluidic_2025"),
    "claude-clinician-1": mentions("miller", "worrilow", "alegre_2025", "hozyen", "nct03659812", "hasanen", "gil_julia_2021", "romany", "pacheco", "leandri", "antinori", "setti_2012b", "braga", "moubasher", "gatimel", "oliveira", "knez", "parrella", "huniadi", "nct06005311", "huong", "nct07240779", "nct04496232"),
    "claude-clinician-2": mentions("miller", "hozyen", "hasanen", "alegre_2016a", "novoselsky", "majumdar", "worrilow", "romany", "nct03659812", "ziarati", "leandri", "gatimel", "balaban", "antinori", "battista", "quinn", "huniadi", "parrella", "yousefi"),
    "claude-clinician-3": mentions("miller", "west", "hozyen", "korosi", "alegre_2025", "nct03659812", "romany", "stimpfel", "jeseta", "sanchez_martin", "degheidy", "troya", "yetkinel", "quinn", "ozcan", "yildiz_2019", "jrct_microfluidics", "leandri", "antinori", "gatimel", "balaban", "knez", "piezo_korea", "piezo_p167", "piezo_fertil_steril"),
    "claude-clinician-4": mentions("miller", "west", "alegre_2025", "hozyen", "hasanen", "nct03659812", "huniadi", "parrella", "quinn", "leandri", "antinori", "braga", "setti_2012b", "gatimel"),
    "claude-researcher-1": mentions("miller", "alegre_2025", "korosi", "novoselsky", "leandri", "antinori", "battista", "romany", "ziarati", "nct03659812", "esfahani", "karimi", "yetkinel", "quinn", "ozcan", "ferrer", "jrct_microfluidics", "yousefi"),
    "claude-researcher-2": mentions("miller", "novoselsky", "alegre_2025", "korosi", "leandri", "battista", "moubasher", "ziarati", "nct03659812", "gil_julia_2021", "gil_julia_safety", "quinn", "jrct_microfluidics", "godiwala", "nct00114725", "invicsi"),
    "claude-researcher-3": mentions("miller", "alegre_2025", "novoselsky", "korosi", "antinori", "leandri", "aydin", "yetkinel", "ozaltin", "godiwala_2024", "uyar", "parrella", "jrct_microfluidics", "nct03659812", "ziarati", "pacheco", "nct06670586", "invicsi"),
    "claude-researcher-4": mentions("miller", "novoselsky", "alegre_2025", "korosi", "antinori", "ziarati", "nct03659812", "yetkinel", "ozcan", "quinn", "parrella", "yousefi", "west"),
    "gemini-patient-1": mentions("huniadi", "adolfsson", "ahmadi", "west"),
    "gemini-patient-2": mentions("majumdar", "west", "leandri", "leisinger", "anbari"),
    "gemini-patient-3": mentions("leandri", "majumdar", "mei", "hasanen", "anbari"),
    "gemini-patient-4": mentions("miller", "yetkinel", "anbari", "pacheco", "gil_julia_2021"),
    "gemini-clinician-1": mentions("miller", "leandri", "pacheco", "mei", "huniadi"),
    "gemini-clinician-2": mentions("west", "yetkinel", "gil_julia_2021", "karabulut"),
    "gemini-clinician-3": mentions("miller", "mei", "stimpfel", "taylor", "huniadi"),
    "gemini-clinician-4": mentions("leisinger", "godiwala", "majumdar", "leandri", "gil_julia_2021", "ozaltin", "hasanen"),
    "gemini-researcher-1": mentions("miller", "west", "pacheco", "leisinger", "antinori", "duarte"),
    "gemini-researcher-2": mentions("antinori", "kim", "dirican", "majumdar", "hasanen", "yetkinel", "leisinger"),
    "gemini-researcher-3": mentions("quinn", "yetkinel", "gil_julia_2021", "hasanen", "leandri", "balaban"),
    "gemini-researcher-4": mentions("west", "majumdar", "mokanszki", "quinn", "mei", "gil_julia_2021"),
    "gpt-patient-1": mentions("miller", "worrilow", "antinori", "leandri", "battista", "yetkinel", "quinn", "huong", "ziarati", "hozyen", "esfahani", "karimi", "de_geyter", "ganeva", "gianaroli", "balaban", "thanapongpibul", "balakier"),
    "gpt-patient-2": mentions("miller", "worrilow", "hozyen", "yetkinel", "aydin", "huong", "balakier", "antinori", "leandri", "setti_2012b", "romany", "troya", "pacheco", "esfahani", "karimi"),
    "gpt-patient-3": mentions("miller", "worrilow", "majumdar", "yetkinel", "aydin", "huong", "thanapongpibul", "leandri", "battista", "shakeri", "el_khattabi", "troya", "mei", "hozyen", "gil_julia_2022", "esfahani", "karimi", "gianaroli", "ghosh"),
    "gpt-patient-4": mentions("miller", "worrilow", "alegre_2025", "antinori", "leandri", "de_vos", "shakeri", "yetkinel", "aydin", "huong", "thanapongpibul", "troya", "hozyen", "pacheco", "gil_julia_2022", "esfahani", "karimi"),
    "gpt-clinician-1": mentions("miller", "worrilow", "majumdar", "antinori", "leandri", "battista", "shakeri", "setti_2012b", "yetkinel", "aydin", "huong", "uyar", "ziarati", "mei", "sheikhi", "norozi", "esfahani", "de_geyter", "ganeva", "pacheco", "gil_julia_2021", "gil_julia_2022", "balakier", "parrella"),
    "gpt-clinician-2": mentions("miller", "worrilow", "majumdar", "alegre_2025", "antinori", "balaban", "leandri", "yetkinel", "aydin", "uyar", "huong", "troya", "pacheco", "norozi", "mei", "esfahani", "gianaroli", "de_geyter", "yousefi", "ganeva"),
    "gpt-clinician-3": mentions("worrilow", "majumdar", "miller", "alegre_2025", "van_den_bergh", "antinori", "wilding", "balaban", "leandri", "setti_2012b", "de_vos", "yetkinel", "quinn", "aydin", "huong", "thanapongpibul", "balakier", "romany", "troya", "norozi", "gil_julia_2022", "dirican", "esfahani", "de_geyter", "gianaroli", "casciani", "jin", "ganeva", "battista", "hasanen"),
    "gpt-clinician-4": mentions("miller", "worrilow", "majumdar", "alegre_2025", "antinori", "leandri", "de_vos", "shakeri", "yetkinel", "quinn", "aydin", "huong", "uyar", "balakier", "dirican", "norozi", "mei", "pacheco", "gil_julia_2021", "gil_julia_2022", "esfahani", "karimi", "de_geyter", "gianaroli", "tavalaee_2021", "yousefi", "fleming"),
    "gpt-researcher-1": mentions("miller", "worrilow", "majumdar", "van_den_bergh", "antinori", "leandri", "shakeri", "oliveira", "el_khattabi", "yetkinel", "quinn", "aydin", "huong", "uyar", "balakier", "dirican", "troya", "pacheco", "mei", "gil_julia_2022", "de_geyter", "esfahani", "karimi", "gianaroli", "ghosh", "jin", "ganeva"),
    "gpt-researcher-2": mentions("miller", "worrilow", "majumdar", "alegre_2025", "antinori", "leandri", "setti_2012b", "shakeri", "yetkinel", "aydin", "huong", "thanapongpibul", "troya", "de_geyter", "hozyen", "hasanen", "esfahani", "gianaroli", "ghosh", "jin", "casciani", "mangoli", "dirican", "pacheco", "gil_julia_2021", "gil_julia_2022", "mei", "parrella", "balakier", "el_khattabi", "ganeva"),
    "gpt-researcher-3": mentions("miller", "worrilow", "majumdar", "alegre_2025", "quinn", "yetkinel", "aydin", "huong", "thanapongpibul", "antinori", "leandri", "de_vos", "setti_2012b", "battista", "shakeri", "romany", "troya", "barroso", "mei", "esfahani", "de_geyter", "gianaroli", "ghosh", "fleming"),
    "gpt-researcher-4": mentions("miller", "worrilow", "majumdar", "alegre_2025", "antinori", "leandri", "setti_2012b", "shakeri", "yetkinel", "quinn", "aydin", "huong", "romany", "troya", "hozyen", "esfahani", "karimi", "ganeva", "jin", "mangoli", "yousefi", "gianaroli", "el_khattabi", "pacheco", "mei", "gil_julia_2022", "balakier"),
}


IDENTITY_NOTES = {
    ("claude-clinician-1", "hozyen"): (
        "The response attributes PMID 34076869 to Nasr-Esfahani; the report in the "
        "Cochrane RIS is Hozyen 2022."
    ),
    ("claude-researcher-2", "leandri"): (
        "The response names Leandri 2013 but reports the positive Antinori 2008 "
        "pregnancy figures."
    ),
    ("claude-researcher-4", "ziarati"): (
        "The response attributes the 62-sample MACS-DGC trial to Romany; its design "
        "and sample sizes resolve to Ziarati 2018."
    ),
    ("gpt-clinician-1", "pacheco"): (
        "The response calls the 724-cycle high-SDF cohort Sanchez-Martin 2020; the "
        "linked report is Pacheco 2020."
    ),
    ("gpt-clinician-2", "norozi"): (
        "The response calls PMID 35103427 Azadi 2022; the Cochrane RIS identifies "
        "the report as Norozi-Hafshejani 2022."
    ),
    ("gpt-clinician-4", "karimi"): (
        "The response attributes PMID 31606966 to Norozi-Hafshejani; the Cochrane "
        "RIS identifies the report as Karimi 2020."
    ),
    ("gpt-researcher-1", "de_geyter"): (
        "The response calls PMID 31463874 Rappa 2019; the Cochrane RIS identifies "
        "the report as De Geyter 2019."
    ),
    ("gpt-researcher-1", "ganeva"): (
        "The response calls PMID 38225818 Kamenov 2024; the Cochrane RIS identifies "
        "the report as Ganeva 2024."
    ),
    ("gpt-researcher-2", "troya"): (
        "The response calls PMID 27206090 Romany 2015; the Cochrane RIS identifies "
        "the study as Troya 2015."
    ),
    ("gpt-researcher-2", "de_geyter"): (
        "The response calls PMID 31463874 Rohm 2019; the Cochrane RIS identifies "
        "the report as De Geyter 2019."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-clinician-1", "hozyen"): "Nasr-Esfahani et al., 2021 (PMID 34076869)",
    ("claude-researcher-2", "leandri"): "Leandri et al. 2013",
    ("claude-researcher-4", "ziarati"): "Romany et al. — 62-sample MACS-DGC trial",
    ("gpt-clinician-1", "pacheco"): "Sanchez-Martin et al. 2020",
    ("gpt-clinician-2", "norozi"): "Azadi et al. 2022",
    ("gpt-clinician-4", "karimi"): "Norozi-Hafshejani et al. 2020",
    ("gpt-researcher-1", "de_geyter"): "Rappa et al. 2019",
    ("gpt-researcher-1", "ganeva"): "Kamenov et al. 2024",
    ("gpt-researcher-2", "troya"): "Romany et al. 2015 (PMID 27206090)",
    ("gpt-researcher-2", "de_geyter"): "Rohm et al. 2019",
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
    """Validate response coverage, candidate keys, and all Cochrane study labels."""

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

    status_labels = {
        "included": ris_study_labels(SOURCE_DIR / "CD010461-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD010461-excluded.ris"),
        "cochrane_ongoing": ris_study_labels(SOURCE_DIR / "CD010461-ongoing.ris"),
        "cochrane_awaiting": ris_study_labels(SOURCE_DIR / "CD010461-awaiting.ris"),
    }
    for run_id, keys in RUN_CANDIDATES.items():
        if len(keys) != len(set(keys)):
            raise ValueError(f"Duplicate candidate key in {run_id}")
        unknown = sorted(set(keys) - set(CANDIDATES))
        if unknown:
            raise ValueError(f"Unknown candidate keys in {run_id}: {unknown}")

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
    """Build one row per unique study candidate named in each full response."""

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
                    "source_file": f"CD010461/{run_id}.md",
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
    """Write a non-empty audit table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Regenerate the curated match table consumed by the demo builder."""

    rows = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print(f"Runs: {len(RUN_CANDIDATES)}")
    print(f"Study candidates: {len(rows)}")
    print(
        "Included-study matches: "
        f"{sum(row['ground_truth_status'] == 'included' for row in rows)}"
    )
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
