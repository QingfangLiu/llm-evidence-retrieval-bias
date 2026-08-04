#!/usr/bin/env python3
"""Curate terminal study lists from the CD005354 user-role experiment."""

from __future__ import annotations

import csv
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_ZIP = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_7"
    / "CD005354-SUP-07-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd005354_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 207, "gemini": 49, "gpt": 251}
EXPECTED_RESPONSE_STUDY_ROWS = 488
EXPECTED_COHCRANE_LABELS = {
    "included": 59,
    "cochrane_excluded": 63,
    "cochrane_awaiting": 30,
    "cochrane_ongoing": 7,
}
RIS_MEMBERS = {
    "included": "CD005354-study-data/CD005354-included.ris",
    "cochrane_excluded": "CD005354-study-data/CD005354-excluded.ris",
    "cochrane_awaiting": "CD005354-study-data/CD005354-awaiting.ris",
    "cochrane_ongoing": "CD005354-study-data/CD005354-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical information for one response-level study candidate."""

    label: str
    status: str
    cochrane_labels: tuple[str, ...] = ()
    design: str = ""
    note: str = ""


OUTSIDE_CANDIDATES: dict[str, CandidateInfo] = {
    "integrated_hphmg": CandidateInfo(
        "Platteau 2008 integrated HP-hMG analysis",
        "invalid_publication_type",
        design="pooled individual-participant-data analysis",
        note="The publication pools raw data from two trials rather than reporting one primary study.",
    ),
    "engage_cluster": CandidateInfo(
        "ENGAGE trial and companion analyses",
        "cochrane_excluded",
        ("Boostanfar 2010",),
        "randomized controlled trial",
        "Main and companion ENGAGE reports are grouped with the source-package study label.",
    ),
    "vuong_corifollitropin": CandidateInfo(
        "Vuong corifollitropin-alfa trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "polyzos_corifollitropin": CandidateInfo(
        "Drakopoulos 2017 corifollitropin poor-responder trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "kolibianakis_corifollitropin": CandidateInfo(
        "Kolibianakis corifollitropin poor-responder trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "sorouri_corifollitropin": CandidateInfo(
        "Sorouri 2019 corifollitropin trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "fusi_corifollitropin": CandidateInfo(
        "Fusi 2020 corifollitropin poor-responder trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "souza_corifollitropin": CandidateInfo(
        "Souza 2017 corifollitropin comparative study",
        "outside_other",
        design="comparative primary study",
    ),
    "china_corifollitropin": CandidateInfo(
        "Chinese corifollitropin N02 phase 3 trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "corifollitropin_economic": CandidateInfo(
        "Corifollitropin economic analysis",
        "outside_other",
        design="economic study alongside a randomized trial",
    ),
    "beyond_trial": CandidateInfo(
        "BEYOND follitropin-delta trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "de_placido_2005": CandidateInfo(
        "De Placido 2005 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "marrs_2004": CandidateInfo(
        "Marrs 2004 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "barrenetxea_2008": CandidateInfo(
        "Barrenetxea 2008 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "matorras_2009": CandidateInfo(
        "Matorras 2009 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "konig_2013": CandidateInfo(
        "König 2013 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "vuong_lh_2015": CandidateInfo(
        "Vuong 2015 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "musters_2012": CandidateInfo(
        "Musters 2012 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "espart_2017": CandidateInfo(
        "Humaidan 2017 ESPART trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "lh_timing_trial": CandidateInfo(
        "Early- versus mid-follicular recombinant-LH exposure trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "younis_2016": CandidateInfo(
        "Younis 2016 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "bosch_lh_2011": CandidateInfo(
        "Bosch recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "gizzo_2015": CandidateInfo(
        "Gizzo 2015 recombinant-LH pilot study",
        "outside_other",
        design="prospective comparative pilot study",
    ),
    "bielfeld_2024": CandidateInfo(
        "Bielfeld 2024 recombinant-LH comparative study",
        "outside_other",
        design="comparative primary study",
    ),
    "balasch_lh_2001": CandidateInfo(
        "Balasch recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "pacchiarotti_2010": CandidateInfo(
        "Pacchiarotti 2010 hMG versus rFSH-plus-rLH trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "tehraninejad_2017": CandidateInfo(
        "Tehraninejad 2017 gonadotropin-combination trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "levi_setti_2015": CandidateInfo(
        "Levi-Setti 2015 gonadotropin-combination cohort",
        "outside_observational",
        design="observational cohort",
    ),
    "buhler_case_control": CandidateInfo(
        "Bühler recombinant-LH matched case-control study",
        "outside_observational",
        design="matched case-control study",
    ),
    "requena_endocrine": CandidateInfo(
        "Requena gonadotropin endocrine-profile study",
        "outside_other",
        design="comparative primary study",
    ),
    "shu_2019": CandidateInfo(
        "Shu 2019 HP-hMG-plus-rFSH trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "yahyaei_2023": CandidateInfo(
        "Yahyaei 2023 PCOS stimulation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "patki_2018": CandidateInfo(
        "Patki 2018 urinary-versus-recombinant gonadotropin study",
        "outside_observational",
        design="retrospective cohort",
    ),
    "yang_2022": CandidateInfo(
        "Yang 2022 urinary-versus-recombinant FSH cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "dalal_2012": CandidateInfo(
        "Dalal 2012 HP-hMG versus rFSH study",
        "outside_other",
        design="comparative primary study",
    ),
    "bjercke_2010": CandidateInfo(
        "Bjercke 2010 HP-hMG versus rFSH study",
        "outside_other",
        design="comparative primary study",
    ),
    "carone_2012": CandidateInfo(
        "Carone 2012 WHO type I anovulation study",
        "outside_other",
        design="comparative primary study outside IVF scope",
    ),
    "iui_cost_trial": CandidateInfo(
        "Urinary-versus-recombinant FSH ovulation-induction study",
        "outside_other",
        design="randomized study outside IVF scope",
    ),
    "bagcilar_pcos": CandidateInfo(
        "Bagcilar PCOS rFSH-versus-urinary-FSH study",
        "outside_unresolved",
        design="reported prospective randomized study",
        note="The response does not provide enough bibliographic detail to resolve a source report.",
    ),
    "megaset_hr_secondary": CandidateInfo(
        "MEGASET-HR secondary analyses",
        "cochrane_excluded",
        ("Khair 2020",),
        "secondary biomarker and economic analyses",
        "Later MEGASET-HR analyses are grouped with the source-package Khair 2020 label.",
    ),
    "source_lh_review": CandidateInfo(
        "Source-of-LH-preparation review",
        "invalid_publication_type",
        design="review publication",
    ),
    "pain_perception_trial": CandidateInfo(
        "Unspecified FSH-versus-FSH/LH pain-perception trial",
        "outside_unresolved",
        design="reported randomized trial",
        note="The citation is insufficient to resolve to a specific publication.",
    ),
    "balasch_2000": CandidateInfo(
        "Balasch 2000 sequential FSH comparison",
        "outside_observational",
        design="sequential within-patient comparison",
    ),
    "antagonist_cycle_cohort": CandidateInfo(
        "Large antagonist-cycle recombinant-versus-urinary FSH cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "duarte_2023": CandidateInfo(
        "Duarte 2023 follitropin-delta plus menotropin study",
        "outside_other",
        design="prospective controlled clinical study",
    ),
    "follitropin_alpha_beta_cohort": CandidateInfo(
        "Follitropin-alfa versus follitropin-beta cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "gazzo_2024": CandidateInfo(
        "Gazzo 2024 individualized follitropin cohort",
        "outside_observational",
        design="retrospective cohort",
    ),
    "hphmg_rlh_iui": CandidateInfo(
        "HP-hMG versus rFSH-plus-rLH IUI trial",
        "outside_other",
        design="randomized study outside IVF scope",
    ),
    "humaidan_2004": CandidateInfo(
        "Humaidan 2004 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "israeli_2024": CandidateInfo(
        "Israeli 2024 fertility-preservation cohort",
        "outside_observational",
        design="retrospective cohort outside IVF-treatment scope",
    ),
    "lahoud_2017": CandidateInfo(
        "Lahoud 2017 recombinant-LH supplementation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "lockwood_2017": CandidateInfo(
        "Lockwood 2017 HMG-preparation trial",
        "outside_other",
        design="randomized trial without an rFSH arm",
    ),
    "mohamed_2003": CandidateInfo(
        "Mohamed 2003 poor-responder gonadotropin trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "sohrabvand_2010": CandidateInfo(
        "Sohrabvand 2010 FSH-versus-hMG trial",
        "outside_unresolved",
        design="reported comparative primary study",
        note="The incomplete citation does not resolve to the source-package Sohrabvand 2012 study.",
    ),
    "balasch_combo_unresolved": CandidateInfo(
        "Unspecified Balasch gonadotropin-combination trial",
        "outside_unresolved",
        design="reported randomized trial",
        note="The incomplete and possibly conflated citation cannot be resolved to a specific report.",
    ),
}


def normalize(text: str) -> str:
    """Normalize citation text for stable review-specific matching."""

    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def zip_text(member: str) -> str:
    """Read one UTF-8 text member directly from the Cochrane ZIP package."""

    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(member).decode("utf-8-sig")


def ris_records(member: str) -> list[str]:
    """Split one RIS member into records carrying Cochrane study labels."""

    return [
        record
        for record in re.split(r"^ER  -\s*$", zip_text(member), flags=re.MULTILINE)
        if re.search(r"^NS  - .+$", record, re.MULTILINE)
    ]


def ris_study_labels(member: str) -> set[str]:
    """Read unique Cochrane study labels from one RIS member in the ZIP."""

    return {
        match.group(1).strip()
        for match in re.finditer(r"^NS  - (.+)$", zip_text(member), re.MULTILINE)
    }


def ris_pubmed_ids(member: str) -> dict[str, set[str]]:
    """Return explicit PubMed IDs grouped by Cochrane study label."""

    identifiers: dict[str, set[str]] = defaultdict(set)
    for record in ris_records(member):
        label_match = re.search(r"^NS  - (.+)$", record, re.MULTILINE)
        if not label_match:
            continue
        label = label_match.group(1).strip()
        identifiers[label].update(
            match.group(1)
            for match in re.finditer(
                r"^C3  - PubMed\s+(\d+)\s*$", record, re.MULTILINE
            )
        )
    return identifiers


def load_source_candidates() -> tuple[
    dict[str, CandidateInfo], list[tuple[str, str]], list[tuple[str, str]]
]:
    """Build source candidates plus exact report-title and DOI lookup rows."""

    candidates: dict[str, CandidateInfo] = {}
    title_rows: list[tuple[str, str]] = []
    doi_rows: list[tuple[str, str]] = []
    design_by_status = {
        "included": "Cochrane-included study cluster",
        "cochrane_excluded": "Cochrane-excluded study",
        "cochrane_awaiting": "study awaiting classification",
        "cochrane_ongoing": "ongoing study",
    }
    for status, member in RIS_MEMBERS.items():
        for label in sorted(ris_study_labels(member)):
            key = f"source:{status}:{label}"
            candidates[key] = CandidateInfo(
                label,
                status,
                (label,),
                design_by_status[status],
            )
        for record in ris_records(member):
            label = re.search(r"^NS  - (.+)$", record, re.MULTILINE).group(1).strip()
            key = f"source:{status}:{label}"
            for title in re.findall(r"^(?:TI|TT)  - (.+)$", record, re.MULTILINE):
                title_text = normalize(title)
                if len(title_text) >= 30:
                    title_rows.append((title_text, key))
            for doi in re.findall(r"^DO  - (.+)$", record, re.MULTILINE):
                doi_text = normalize(doi)
                if doi_text:
                    doi_rows.append((doi_text, key))
    return candidates, title_rows, doi_rows


SOURCE_CANDIDATES, SOURCE_TITLE_ROWS, SOURCE_DOI_ROWS = load_source_candidates()
CANDIDATES = {**SOURCE_CANDIDATES, **OUTSIDE_CANDIDATES}


def source_key(status: str, label: str) -> str:
    """Return a validated source candidate key."""

    key = f"source:{status}:{label}"
    if key not in SOURCE_CANDIDATES:
        raise ValueError(f"Unknown source candidate: {status} {label}")
    return key


def exact_source_keys(text: str) -> tuple[str, ...]:
    """Resolve copied source report titles and identifiers without fuzzy matching."""

    matches = {
        key
        for title, key in SOURCE_TITLE_ROWS
        if title in text or (len(text) >= 50 and text in title)
    }
    matches.update(key for doi, key in SOURCE_DOI_ROWS if doi in text)
    return tuple(sorted(matches))


def label_source_keys(text: str) -> tuple[str, ...]:
    """Resolve unambiguous source labels from an author or registry identifier."""

    tokens = set(text.split())
    matches = set()
    for key, candidate in SOURCE_CANDIDATES.items():
        label = normalize(candidate.label)
        if label in text:
            matches.add(key)
            continue
        label_match = re.fullmatch(r"(.+?)\s+(\d{4})[a-z]?", label)
        if not label_match:
            continue
        author_text, year = label_match.groups()
        author_tokens = author_text.split()
        if year not in tokens:
            continue
        if len(author_tokens) == 1 and author_tokens[0] in tokens:
            matches.add(key)
        elif len(author_tokens) > 1 and all(token in tokens for token in author_tokens):
            matches.add(key)
    return tuple(sorted(matches))


def resolve_candidate(entry: str) -> tuple[str, ...]:
    """Resolve one terminal-list entry to one or more study clusters."""

    text = normalize(entry)
    if (
        "integrated analysis" in text
        and "hmg" in text
        and ("rfsh" in text or "recombinant fsh" in text)
    ):
        return ("integrated_hphmg",)
    if "gonadotropin specific follicular steroidogenesis" in text:
        return ("megaset_hr_secondary",)
    if "megaset hr" in text or "pmid 32416978" in text:
        return (source_key("included", "Witz 2020"),)
    if text.startswith("hedon") or "pmid 8822422" in text:
        return (source_key("included", "Hedon 1995"),)
    if text.startswith("schats") or "pmid 10920087" in text:
        return (source_key("included", "Schats 2000"),)

    exact = exact_source_keys(text)
    if len(exact) == 1:
        return exact
    labels = label_source_keys(text)
    if len(labels) == 1:
        return labels

    phrase_rules = (
        (("pmid 8567765",), source_key("included", "Out 1995")),
        (("pmid 10783345",), source_key("included", "Lenton 2000")),
        (("pmid 18367182",), source_key("included", "Baker 2009")),
        (("pmid 19572228",), source_key("included", "Abate 2009")),
        (("pmid 25242998",), source_key("included", "Sohrabvand 2012")),
        (("pmid 12215327",), source_key("included", "European and Israeli Study Group 2002")),
        (("pmid 12773445",), source_key("included", "Kilani 2003")),
        (("pmid 22244781",), source_key("included", "Devroey 2012")),
        (("pmid 11172835",), source_key("included", "Strehler 2001")),
        (("pmid 16600226",), source_key("included", "Mohamed 2006")),
        (("pmid 25735918",), source_key("included", "Rettenbacher 2015")),
        (("pmid 26733057",), source_key("included", "Strowitzki 2016")),
        (("pmid 27912901",), source_key("included", "Nyboe Andersen 2017")),
        (("pmid 34179971",), source_key("included", "Qiao 2021")),
        (("pmid 40633120",), source_key("included", "EUCTR2021-001785-38-ES")),
        (("pmid 34977459",), source_key("cochrane_awaiting", "Hossein Rashidi 2021")),
        (("pmid 31157267",), "shu_2019"),
        (("pmid 37340371",), "yahyaei_2023"),
        (("pmid 15169576",), "humaidan_2004"),
        (("pmid 28107729",), "lahoud_2017"),
        (("pmid 14704644",), "mohamed_2003"),
        (("clinical outcome following stimulation", "andersen"), source_key("included", "Andersen 2006")),
        (("clinical outcome after hp hmg",), source_key("included", "Andersen 2006")),
        (("highly purified hmg versus recombinant fsh in ovarian hyperstimulation",), source_key("included", "Bosch 2008")),
        (("hmg vs rfsh in gnrh antagonist cycles", "nct00669786"), source_key("included", "Bosch 2008")),
        (("follicular steroidogenesis in gnrh antagonist",), source_key("included", "Bosch 2008")),
        (("efficacy of recombinant versus human derived",), source_key("included", "Abate 2009")),
        (("adapt 1",), source_key("included", "EUCTR2021-001785-38-ES")),
        (("follitropin delta in repeated ovarian stimulation",), source_key("included", "Nyboe Andersen 2017")),
        (("repeated cycle safety trial",), source_key("included", "Nyboe Andersen 2017")),
        (("individualized versus conventional ovarian stimulation",), source_key("included", "Nyboe Andersen 2017")),
        (("clinically validate follitropin delta",), source_key("included", "Qiao 2021")),
        (("ishihara", "amh stratified", "follitropin delta"), source_key("included", "Ishihara 2021b")),
        (("ovaleap", "gonal f"), source_key("included", "Strowitzki 2016")),
        (("bemfola", "gonal f"), source_key("included", "Rettenbacher 2015")),
        (("primapur", "gonal f"), source_key("included", "Barakhoeva 2019")),
        (("follitrope", "gonal f"), source_key("included", "Hu 2020")),
        (("ql1012", "gonal f"), source_key("included", "Hu 2023")),
        (("da 3801",), source_key("included", "Moon 2007")),
        (("follitropin epsilon",), source_key("included", "Griesinger 2020")),
        (("folitime", "gonal f"), source_key("included", "Pasqualini 2021")),
        (("pmc3850313",), source_key("cochrane_awaiting", "Turkcapar 2013")),
        (("human menopausal gonadotropin versus recombinant fsh in polycystic",), source_key("cochrane_awaiting", "Turkcapar 2013")),
        (("recombinant versus highly purified fsh in polycystic",), source_key("cochrane_awaiting", "NCT01337531")),
        (("pcos undergoing icsi", "bagcilar"), "bagcilar_pcos"),
        (("polycystic ovary syndrome undergoing icsi cycles", "bagcilar"), "bagcilar_pcos"),
        (("a randomized dose response trial of a single injection",), source_key("cochrane_excluded", "Abyholm 2008")),
        (("dose finding study group", "corifollitropin"), source_key("cochrane_excluded", "Abyholm 2008")),
        (("ensure study group",), source_key("cochrane_excluded", "Hillensjo 2009")),
        (("lower body weight women", "corifollitropin"), source_key("cochrane_excluded", "Hillensjo 2009")),
        (("pursue",), source_key("cochrane_excluded", "Boostanfar 2015")),
        (("pmid 26003273",), source_key("cochrane_excluded", "Boostanfar 2015")),
        (("engage", "retrospective analysis"), "engage_cluster"),
        (("short follicular phase",), "engage_cluster"),
        (("pharmacokinetics and follicular dynamics",), "engage_cluster"),
        (("pharmacokinetic pharmacodynamic sub study",), "engage_cluster"),
        (("engage",), "engage_cluster"),
        (("double blind non inferiority rct comparing corifollitropin",), "engage_cluster"),
        (("corifollitropin alfa vs recombinant fsh", "35 42"), "vuong_corifollitropin"),
        (("hox023",), "vuong_corifollitropin"),
        (("pmid 30895237",), "vuong_corifollitropin"),
        (("corifollitropin alfa followed by highly purified hmg",), "polyzos_corifollitropin"),
        (("corifollitropin alfa compared with follitropin beta in poor responders",), "kolibianakis_corifollitropin"),
        (("pmid 25492411",), "kolibianakis_corifollitropin"),
        (("sorouri", "corifollitropin"), "sorouri_corifollitropin"),
        (("fusi", "corifollitropin"), "fusi_corifollitropin"),
        (("souza", "corifollitropin"), "souza_corifollitropin"),
        (("corifollitropin alfa n02",), "china_corifollitropin"),
        (("pmid 42462332",), "china_corifollitropin"),
        (("economic analysis", "corifollitropin"), "corifollitropin_economic"),
        (("cost comparison analysis", "khair"), "megaset_hr_secondary"),
        (("pharmacoeconomics open", "khair"), "megaset_hr_secondary"),
        (("beyond",), "beyond_trial"),
        (("pmid 15576390",), "de_placido_2005"),
        (("de placido", "recombinant human lh supplementation"), "de_placido_2005"),
        (("initial inadequate ovarian response", "step up"), "de_placido_2005"),
        (("pmid 14989794",), "marrs_2004"),
        (("randomized trial to compare", "with or without recombinant human lh"), "marrs_2004"),
        (("baruffi", "recombinant human lh"), "marrs_2004"),
        (("pmid 17531989",), "barrenetxea_2008"),
        (("barrenetxea",), "barrenetxea_2008"),
        (("pmid 20031032",), "matorras_2009"),
        (("matorras",), "matorras_2009"),
        (("konig", "lh supplementation"), "konig_2013"),
        (("pmid 25740882",), "vuong_lh_2015"),
        (("vuong", "recombinant lh", "rfsh alone"), "vuong_lh_2015"),
        (("pmid 22095792",), "musters_2012"),
        (("musters",), "musters_2012"),
        (("espart",), "espart_2017"),
        (("efficacy and safety of follitropin alfa lutropin alfa",), "espart_2017"),
        (("early vs mid follicular lh exposure",), "lh_timing_trial"),
        (("early versus mid follicular lh exposure",), "lh_timing_trial"),
        (("younis", "lh supplementation"), "younis_2016"),
        (("bosch", "rlh supplementation"), "bosch_lh_2011"),
        (("gizzo", "recombinant lh"), "gizzo_2015"),
        (("bielfeld",), "bielfeld_2024"),
        (("pmid 11464575",), "balasch_lh_2001"),
        (("balasch", "rfsh alone", "recombinant lh"), "balasch_lh_2001"),
        (("pmid 20537626",), "pacchiarotti_2010"),
        (("urinary hmg", "pergoveris"), "pacchiarotti_2010"),
        (("pmid 29177245",), "tehraninejad_2017"),
        (("controlled ovarian stimulation with rfsh plus rlh", "hmg plus rfsh"), "tehraninejad_2017"),
        (("routine clinical practice in a real life population",), "levi_setti_2015"),
        (("buhler", "matched case control"), "buhler_case_control"),
        (("fischer", "matched case control"), "buhler_case_control"),
        (("endocrine profile following stimulation", "luteinizing hormone"), "requena_endocrine"),
        (("clinical outcomes following long gnrh",), "shu_2019"),
        (("hp hmg plus rfsh", "rfsh alone"), "shu_2019"),
        (("introduce an optimal method", "polycystic"), "yahyaei_2023"),
        (("introduce an optimal method",), "yahyaei_2023"),
        (("jhrs 79 17",), "patki_2018"),
        (("patki", "urinary versus recombinant"), "patki_2018"),
        (("cumulative live birth rate", "yang"), "yang_2022"),
        (("dalal",), "dalal_2012"),
        (("bjercke",), "bjercke_2010"),
        (("who type i anovulation",), "carone_2012"),
        (("ovulation induction", "cost minimization"), "iui_cost_trial"),
        (("pmc1550405",), "iui_cost_trial"),
        (("gonadotropin specific follicular steroidogenesis",), "megaset_hr_secondary"),
        (("does the source of lh preparation matter",), "source_lh_review"),
        (("pain perception",), "pain_perception_trial"),
        (("baker", "clinical efficacy of highly purified urinary fsh"), source_key("included", "Baker 2009")),
        (("kelly", "clinical efficacy of highly purified urinary fsh"), source_key("included", "Baker 2009")),
        (("balasch", "follicular development and hormonal levels"), "balasch_2000"),
        (("over 2000 gnrh antagonist cycles",), "antagonist_cycle_cohort"),
        (("duarte filho", "follitropin delta combined with menotropin"), "duarte_2023"),
        (("follitropin alpha versus follitropin beta", "retrospective"), "follitropin_alpha_beta_cohort"),
        (("algorithm vs clinical experience",), "gazzo_2024"),
        (("nct01604044",), "hphmg_rlh_iui"),
        (("humaidan", "gnrh agonist down regulation"), "humaidan_2004"),
        (("highly purified hmg versus rfsh", "fertility preservation"), "israeli_2024"),
        (("lahoud",), "lahoud_2017"),
        (("lockwood", "two hmg preparations"), "lockwood_2017"),
        (("s1472 6483 10 60513 5",), "marrs_2004"),
        (("pmc5601935",), "tehraninejad_2017"),
        (("tehraninejad",), "tehraninejad_2017"),
        (("vuong", "antagonist ovarian stimulation", "rfsh alone"), "vuong_lh_2015"),
        (("vuong", "antagonist ovarian stimulation", "recombinant follicle"), "vuong_lh_2015"),
        (("dev038",), "vuong_lh_2015"),
        (("konig", "lh supplementation"), "konig_2013"),
        (("nig", "lh supplementation"), "konig_2013"),
        (("det266",), "konig_2013"),
        (("ovulation induction", "cost effectiveness"), "iui_cost_trial"),
        (("prospective and randomized study of ovarian stimulation for icsi",), source_key("included", "Franco 2000")),
        (("prospective randomized study comparing highly purified urinary fsh", "polycystic"), source_key("cochrane_awaiting", "NCT01337531")),
        (("human menopausal gonadotropin versus recombinant fsh in pcos",), source_key("cochrane_awaiting", "Turkcapar 2013")),
        (("comparison of highly purified urinary versus recombinant fsh effect on art outcomes",), source_key("included", "Sohrabvand 2012")),
        (("comparison of fsh and hmg on ovarian stimulation outcome",), "sohrabvand_2010"),
        (("ziebe", "embryo quality", "merit"), source_key("included", "Andersen 2006")),
        (("nct00669786",), source_key("included", "Bosch 2008")),
        (("balasch", "highly purified hmg", "verify full citation"), "balasch_combo_unresolved"),
        (("westergaard", "1996"), source_key("cochrane_excluded", "Westerguard 1996")),
        (("effect of human menopausal gonadotrophin and highly purified",), source_key("cochrane_excluded", "Westerguard 1996")),
        (("comparison of two recombinant follicle stimulating hormone preparations",), source_key("cochrane_excluded", "Tulppala 1999")),
        (("pmid 10548606",), source_key("cochrane_excluded", "Tulppala 1999")),
        (("requena", "single blastocyst transfer"), source_key("cochrane_excluded", "Requena 2010")),
    )
    for phrases, key in phrase_rules:
        if all(phrase in text for phrase in phrases):
            return (key,)

    if exact:
        return exact
    if labels:
        return labels
    raise ValueError(f"Unresolved terminal-list entry: {entry}")


def citation_identity_note(entry: str, key: str) -> str:
    """Return an audit note when a citation resolves despite conflicting details."""

    text = normalize(entry)
    label = CANDIDATES[key].label
    if label == "Kilani 2003" and ("out hj" in text or "ferraretti" in text):
        return "Author attribution conflicts with the Kilani 2003 report identified by PMID/title."
    if label == "Baker 2009" and "kelly aj" in text:
        return "Author attribution conflicts with the Baker 2009 report title."
    if label == "European and Israeli Study Group 2002" and "westergaard" in text:
        return "Author attribution conflicts with the study-group-authored source report."
    if label == "Hompes 2008" and text.startswith("bosch"):
        return "Author attribution conflicts with the Hompes 2008 report title."
    if label == "Andersen 2006" and text.startswith("devroey"):
        return "Lead-author attribution conflicts with the Andersen 2006 source report."
    if label == "Drakakis 2002" and (
        "author s unspecified" in text or "el toukhy" in text
    ):
        return "The response did not identify the Drakakis authorship and suggested an unrelated author."
    if label == "Turkcapar 2013" and any(
        author in text for author in ("bahceci", "kilic", "selman")
    ):
        return "Author attribution conflicts with the Turkcapar 2013 source report."
    if label == "Sohrabvand 2012" and "mohammadi yeganeh" in text:
        return "Author attribution conflicts with the Sohrabvand 2012 source report."
    if label == "Sohrabvand 2012" and re.search(r"\b2014\b", text):
        return "Publication year conflicts with the 2012 source report."
    if label == "Hedon 1995" and re.search(r"\b1996\b", text):
        return "Publication year conflicts with the 1995 source report."
    if label == "Shu 2019 HP-hMG-plus-rFSH trial" and (
        text.startswith("ye h") or "journal of thoracic disease" in text
    ):
        return "Author and journal attribution conflict with the Shu 2019 report identified by PMID."
    if label == "Platteau 2008 integrated HP-hMG analysis" and text.startswith(
        "andersen"
    ):
        return "Lead-author attribution conflicts with the Platteau 2008 pooled analysis."
    return ""


def extract_terminal_list(path: Path) -> list[str]:
    """Extract only entries inside the response's dedicated final study list."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if path.stem == "claude-clinician-4":
        start = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("## Primary studies:")
        )
        end = next(
            index
            for index, line in enumerate(lines[start + 1 :], start + 1)
            if line.startswith("A few notes for your review:")
        )
        entries = [
            match.group(1).strip()
            for line in lines[start + 1 : end]
            if (match := re.match(r"^-\s+(.+)$", line))
        ]
        if entries:
            return entries
        raise ValueError(f"No cohesive study-list entries in {path.name}")
    if path.stem == "claude-patient-3":
        entries = [
            line.strip()
            for line in lines
            if re.match(r"^\*\*.+?\*\*\s+[—-]", line)
        ]
        if entries:
            return entries
        raise ValueError(f"No cohesive study-list entries in {path.name}")

    heading_indexes = []
    for index, line in enumerate(lines):
        heading = normalize(line)
        if path.stem.startswith("gemini-"):
            if (line.startswith("#") or line.startswith("**")) and (
                "references" in heading
            ):
                heading_indexes.append(index)
        elif (
            (line.startswith("#") or line.startswith("**"))
            and "primary studies" in heading
        ):
            heading_indexes.append(index)
    if not heading_indexes:
        raise ValueError(f"No terminal study-list heading in {path.name}")

    block = lines[heading_indexes[-1] + 1 :]
    if path.stem.startswith("gemini-"):
        entries = []
        for index, line in enumerate(block):
            if "Cited by:" not in line:
                continue
            previous = index - 1
            while previous >= 0 and not block[previous].strip():
                previous -= 1
            if previous >= 0:
                entries.append(block[previous].strip())
        if entries:
            return entries
    numbered = [
        match.group(1).strip()
        for line in block
        if (match := re.match(r"^\s*\d+[.)]\s+(.+)$", line))
    ]
    if numbered:
        return numbered
    raise ValueError(f"No terminal study-list entries in {path.name}")


def response_paths() -> list[Path]:
    """Return the complete expected 3-model, 3-role, 4-replicate file set."""

    expected = {
        f"{model}-{role}-{replicate}.md"
        for model in MODELS
        for role in ROLES
        for replicate in range(1, 5)
    }
    available = {
        path.name for path in REVIEW_DIR.glob("*.md") if path.name != "README.md"
    }
    if available != expected:
        missing = sorted(expected - available)
        stale = sorted(available - expected)
        raise ValueError(f"Response file mismatch; missing={missing}, stale={stale}")
    empty = sorted(
        name
        for name in expected
        if not (REVIEW_DIR / name).read_text(encoding="utf-8").strip()
    )
    if empty:
        raise ValueError(f"Empty response files: {empty}")
    return [REVIEW_DIR / name for name in sorted(expected)]


def validate_cochrane_labels() -> None:
    """Require every Cochrane-classified candidate label to occur in its RIS."""

    labels_by_status = {
        status: ris_study_labels(member) for status, member in RIS_MEMBERS.items()
    }
    observed_counts = {
        status: len(labels) for status, labels in labels_by_status.items()
    }
    if observed_counts != EXPECTED_COHCRANE_LABELS:
        raise ValueError(
            "Cochrane source-label count mismatch; "
            f"expected={EXPECTED_COHCRANE_LABELS}, observed={observed_counts}"
        )
    for candidate in CANDIDATES.values():
        if candidate.status not in labels_by_status:
            continue
        for label in candidate.cochrane_labels:
            if label not in labels_by_status[candidate.status]:
                raise ValueError(f"{candidate.status} label not in RIS: {label}")


def build_match_rows() -> tuple[list[dict[str, str | int]], dict[str, int]]:
    """Build one row per deduplicated study cluster in each terminal list."""

    validate_cochrane_labels()
    rows: list[dict[str, str | int]] = []
    raw_counts: dict[str, int] = {}
    for path in response_paths():
        run_id = path.stem
        model, role_id, replicate_text = run_id.split("-")
        entries = extract_terminal_list(path)
        raw_counts[run_id] = len(entries)
        grouped: dict[str, list[str]] = defaultdict(list)
        identity_notes: dict[str, list[str]] = defaultdict(list)
        for entry in entries:
            for key in resolve_candidate(entry):
                grouped[key].append(entry)
                if note := citation_identity_note(entry, key):
                    identity_notes[key].append(note)

        for key, citations in grouped.items():
            candidate = CANDIDATES[key]
            notes = list(dict.fromkeys(identity_notes[key]))
            if len(citations) > 1:
                notes.append(
                    f"Grouped {len(citations)} terminal-list citations to one study cluster."
                )
            if candidate.note:
                notes.append(candidate.note)
            rows.append(
                {
                    "run_id": run_id,
                    "model": model,
                    "role_id": role_id,
                    "replicate": int(replicate_text),
                    "source_file": f"reviews/CD005354/{path.name}",
                    "reported_citation": " || ".join(citations),
                    "canonical_candidate": candidate.label,
                    "ground_truth_status": candidate.status,
                    "cochrane_study_label": " || ".join(candidate.cochrane_labels),
                    "design": candidate.design,
                    "identity_issue": int(bool(identity_notes[key])),
                    "notes": "; ".join(notes),
                }
            )

    observed_entries = Counter()
    for run_id, count in raw_counts.items():
        observed_entries[run_id.split("-")[0]] += count
    if dict(observed_entries) != EXPECTED_LIST_ENTRIES:
        raise ValueError(
            "Terminal-list entry count mismatch; "
            f"expected={EXPECTED_LIST_ENTRIES}, observed={dict(observed_entries)}"
        )
    if EXPECTED_RESPONSE_STUDY_ROWS and len(rows) != EXPECTED_RESPONSE_STUDY_ROWS:
        raise ValueError(
            "Response-study row count mismatch; "
            f"expected={EXPECTED_RESPONSE_STUDY_ROWS}, observed={len(rows)}"
        )

    labels_by_run_status: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        labels_by_run_status[(str(row["run_id"]), str(row["ground_truth_status"]))].extend(
            label.strip()
            for label in str(row["cochrane_study_label"]).split(" || ")
            if label.strip()
        )
    for run_status, labels in labels_by_run_status.items():
        duplicates = [label for label, count in Counter(labels).items() if count > 1]
        if duplicates:
            raise ValueError(f"Duplicate Cochrane labels in {run_status}: {duplicates}")
    return rows, raw_counts


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write a non-empty audit table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def included_labels(row: dict[str, str | int]) -> set[str]:
    """Return included Cochrane study labels credited by one audit row."""

    if row["ground_truth_status"] != "included":
        return set()
    return {
        label.strip()
        for label in str(row["cochrane_study_label"]).split(" || ")
        if label.strip()
    }


def print_summary(
    rows: list[dict[str, str | int]], raw_counts: dict[str, int]
) -> None:
    """Print compact extraction, classification, and recall checks."""

    included_truth = ris_study_labels(RIS_MEMBERS["included"])
    included_pmids = ris_pubmed_ids(RIS_MEMBERS["included"])
    by_run: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for row in rows:
        by_run[str(row["run_id"])].append(row)
    print(f"Runs: {len(response_paths())}")
    print(f"Terminal-list entries: {sum(raw_counts.values())}")
    print(f"Response-study rows after within-response deduplication: {len(rows)}")
    print(
        "Statuses: "
        + ", ".join(
            f"{status}={count}"
            for status, count in sorted(
                Counter(str(row["ground_truth_status"]) for row in rows).items()
            )
        )
    )
    for model in MODELS:
        run_ids = [run_id for run_id in raw_counts if run_id.startswith(f"{model}-")]
        print(
            f"{model}: {sum(raw_counts[run_id] for run_id in run_ids)} entries; "
            f"{sum(len(by_run.get(run_id, [])) for run_id in run_ids)} response-study rows"
        )
    print("Included-study recall by run:")
    for path in response_paths():
        run_id = path.stem
        retrieved = set().union(
            *(included_labels(row) for row in by_run.get(run_id, []))
        )
        print(f"  {run_id}: {len(retrieved)}/{len(included_truth)}")
    retrieved_all = set().union(*(included_labels(row) for row in rows))
    print(
        f"Pooled included coverage: {len(retrieved_all)}/{len(included_truth)}; "
        f"missed labels={','.join(sorted(included_truth - retrieved_all)) or 'none'}"
    )
    if not set().union(*included_pmids.values()):
        print("Included-study PMID coverage: unavailable (no explicit PubMed IDs in RIS)")
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the terminal-list-only curated match table for CD005354."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
