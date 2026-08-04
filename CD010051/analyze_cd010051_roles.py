#!/usr/bin/env python3
"""Analyze CD010051 using only each response's dedicated final study list.

The review-specific resolver reads the Cochrane RIS exports directly from the
source ZIP, collapses companion reports to Cochrane study clusters, preserves
classifications for excluded/awaiting/ongoing records, and explicitly retains
identifiable records outside the source package. Raw response files are never
modified.
"""

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
    / "Cochrane_reviews"
    / "source_reviews"
    / "2026_issue_7"
    / "CD010051-SUP-07-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd010051_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 226, "gemini": 50, "gpt": 286}
EXPECTED_RESPONSE_STUDY_ROWS = 484
RIS_MEMBERS = {
    "included": "CD010051-study-data/CD010051-included.ris",
    "cochrane_excluded": "CD010051-study-data/CD010051-excluded.ris",
    "cochrane_awaiting": "CD010051-study-data/CD010051-awaiting.ris",
    "cochrane_ongoing": "CD010051-study-data/CD010051-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD010051 source-package status of one candidate."""

    label: str
    status: str
    cochrane_labels: tuple[str, ...] = ()
    design: str = ""
    note: str = ""


OUTSIDE_CANDIDATES = {
    "park_retracted": CandidateInfo(
        "Park 2019 retracted BMC Ophthalmology report",
        "outside_retracted",
        design="retracted randomized trial report",
        note=(
            "This is distinct from the Cochrane-included Park 2019 Korean Journal "
            "of Ophthalmology study cluster."
        ),
    ),
    "malhotra_pooled": CandidateInfo(
        "Malhotra 2019 pooled OTX-101 analysis",
        "outside_secondary",
        design="pooled secondary analysis of randomized trials",
    ),
    "rolando_posthoc": CandidateInfo(
        "Rolando 2025 OTX-101 post-hoc analysis",
        "outside_secondary",
        design="post-hoc analysis of randomized trials",
    ),
    "otx_head_to_head_unconfirmed": CandidateInfo(
        "Unconfirmed cyclosporine 0.05% versus 0.09% head-to-head trial",
        "outside_unresolved",
        design="reported randomized trial",
        note="The response does not provide a confirmable primary report or registration.",
    ),
    "gannan_postcataract": CandidateInfo(
        "Gannan post-cataract dry-eye trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "salam_2025": CandidateInfo(
        "Salam 2025 aqueous versus oil-emulsion trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "mu_2026": CandidateInfo(
        "Mu 2026 short-FBUT dry-eye trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "dong_2026": CandidateInfo(
        "Dong 2026 cyclosporine plus punctal-plug trial",
        "outside_other",
        design="paired-eye clinical trial",
    ),
    "perry_2006": CandidateInfo(
        "Perry 2006 meibomian-gland dysfunction trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "perry_2008": CandidateInfo(
        "Perry 2008 topical cyclosporine study",
        "outside_observational",
        design="primary clinical study",
    ),
    "byun_2011": CandidateInfo(
        "Byun 2011 Korean surveillance study",
        "outside_observational",
        design="prospective open-label surveillance study",
    ),
    "wilson_2007": CandidateInfo(
        "Wilson 2007 long-term resolution case series",
        "outside_observational",
        design="retrospective case series",
    ),
    "straub_2016": CandidateInfo(
        "Straub 2016 ten-year follow-up",
        "outside_observational",
        design="retrospective long-term cohort",
    ),
    "pisella_2018": CandidateInfo(
        "Pisella 2018 French early-access cohort",
        "outside_observational",
        design="prospective real-world cohort",
    ),
    "geerling_2022": CandidateInfo(
        "Geerling 2022 PERSPECTIVE study",
        "outside_observational",
        design="prospective multicenter observational study",
    ),
    "johnston_2026": CandidateInfo(
        "Johnston 2026 cyclosporine-switch study",
        "outside_observational",
        design="single-arm phase IV study",
    ),
    "long_term_cationic_2026": CandidateInfo(
        "Leonardi 2026 long-term cationic-emulsion study",
        "outside_other",
        design="open-label induction and randomized maintenance study",
    ),
    "advanced_cationic_24_month": CandidateInfo(
        "Twenty-four-month retrospective cationic-emulsion study",
        "outside_observational",
        design="retrospective study",
    ),
    "akpek_cataract_2024": CandidateInfo(
        "Akpek 2024 pre-cataract ocular-surface trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "preservative_free": CandidateInfo(
        "Preservative-free cyclosporine interventional study",
        "outside_observational",
        design="prospective interventional study",
    ),
    "locatelli": CandidateInfo(
        "Locatelli cyclosporine-versus-lifitegrast comparison",
        "outside_observational",
        design="comparative patient-preference study",
    ),
    "kolluru": CandidateInfo(
        "Kolluru cyclosporine/lifitegrast comparison abstract",
        "outside_other",
        design="conference abstract",
    ),
    "impact": CandidateInfo(
        "Stonecipher 2016 IMPACT study",
        "outside_observational",
        design="open-label interventional study",
    ),
    "persist": CandidateInfo(
        "Mah 2012 PERSIST study",
        "outside_observational",
        design="retrospective review",
    ),
    "yoon_switch": CandidateInfo(
        "Yoon 2025 cyclosporine-switch study",
        "outside_observational",
        design="prospective open-label multicenter study",
    ),
    "ayres_sahara": CandidateInfo(
        "Ayres 2023 SAHARA report",
        "cochrane_excluded",
        ("Ayres 2024",),
        "randomized active-controlled trial",
        "The source package files the SAHARA report under Ayres 2024.",
    ),
    "lee_2016_duplicate": CandidateInfo(
        "Lee 2016 post-cataract comparator study",
        "cochrane_excluded",
        ("Lee 2016", "Lee 2016a"),
        "comparative clinical study",
        "The excluded RIS duplicates the same report under Lee 2016 and Lee 2016a.",
    ),
    "vkc_nct00426023": CandidateInfo(
        "NCT00426023 vernal-keratoconjunctivitis trial",
        "outside_other",
        design="randomized controlled trial outside the review condition",
    ),
    "audrey": CandidateInfo(
        "NCT04147650 AUDREY voclosporin trial",
        "outside_other",
        design="randomized controlled trial of a different intervention",
    ),
    "nct03865888": CandidateInfo(
        "NCT03865888 tacrolimus-versus-cyclosporine trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "nct06981104": CandidateInfo(
        "NCT06981104 mild-to-moderate dry-eye trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "nct00520260": CandidateInfo(
        "NCT00520260 NSAID induction trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "nct01198782": CandidateInfo(
        "NCT01198782 post-Restasis discontinuation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "nct00553735": CandidateInfo(
        "NCT00553735 GVHD dry-eye prevention trial",
        "outside_other",
        design="terminated clinical trial",
    ),
    "nct00405457": CandidateInfo(
        "NCT00405457 lubricant-plus-Restasis trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "nct04144413": CandidateInfo(
        "NCT04144413 long-term cationic-emulsion study",
        "outside_other",
        design="long-term interventional study",
    ),
    "deveney_2009": CandidateInfo(
        "Deveney 2009 postoperative glaucoma-surgery study",
        "outside_observational",
        design="postoperative clinical study",
    ),
    "colligris_vkc": CandidateInfo(
        "Colligris pediatric vernal-keratoconjunctivitis trial",
        "outside_other",
        design="randomized controlled trial outside the review condition",
    ),
    "retrospective_dose_comparison": CandidateInfo(
        "Cyclosporine 0.05% versus 0.1% Sjögren dry-eye comparison",
        "outside_observational",
        design="retrospective comparative study",
    ),
    "ipl_three_arm_2025": CandidateInfo(
        "2025 IPL/cyclosporine/diquafosol comparison",
        "outside_other",
        design="prospective comparative study",
    ),
    "unresolved_report": CandidateInfo(
        "Identifiable but source-unresolved primary report",
        "outside_unresolved",
        design="reported primary study",
        note="The terminal-list citation is insufficient to link the report to the source package.",
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
    """Split one RIS member into records that have Cochrane study labels."""

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


def load_source_candidates() -> tuple[dict[str, CandidateInfo], list[tuple[str, str]]]:
    """Build source candidate definitions and exact report-title lookup rows."""

    candidates: dict[str, CandidateInfo] = {}
    title_rows: list[tuple[str, str]] = []
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
            for title in re.findall(r"^TI  - (.+)$", record, re.MULTILINE):
                title_text = normalize(title)
                if len(title_text) >= 35:
                    title_rows.append((title_text, key))
    return candidates, title_rows


SOURCE_CANDIDATES, SOURCE_TITLE_ROWS = load_source_candidates()
CANDIDATES = {**SOURCE_CANDIDATES, **OUTSIDE_CANDIDATES}


def source_key(status: str, label: str) -> str:
    """Return a validated source candidate key."""

    key = f"source:{status}:{label}"
    if key not in SOURCE_CANDIDATES:
        raise ValueError(f"Unknown source candidate: {status} {label}")
    return key


def exact_source_title_keys(text: str) -> tuple[str, ...]:
    """Resolve copied source report titles without broad fuzzy matching."""

    matches = {
        key
        for title, key in SOURCE_TITLE_ROWS
        if title in text or (len(text) >= 50 and text in title)
    }
    return tuple(sorted(matches))


def resolve_candidate(entry: str) -> tuple[str, ...]:
    """Resolve one terminal-list entry to one or more study clusters."""

    text = normalize(entry)

    # Entries that explicitly combine distinct primary trials are split first.
    if "essence 1 essence 2" in text:
        return (
            source_key("included", "Sheppard 2021"),
            source_key("included", "Akpek 2023"),
        )

    # Stable identifiers and highly specific report/program names.
    identifier_rules = (
        (("10768324",), source_key("included", "Sall 2000")),
        (("10811092",), source_key("included", "Stevenson 2000")),
        (("20698799",), source_key("included", "Chen 2010")),
        (("31374063", "pmc6709181"), source_key("included", "Chen 2019")),
        (("20679084",), source_key("included", "Baiza-Durán 2010")),
        (("30323548",), source_key("included", "Tauber 2018")),
        (("30965064", "nct02688556"), source_key("included", "Goldberg 2019")),
        (("30703441",), source_key("included", "Wirta 2019")),
        (("34481407",), source_key("included", "Sheppard 2021")),
        (("37022717",), source_key("included", "Akpek 2023")),
        (("38451509",), source_key("included", "Peng 2024")),
        (("38771801",), source_key("included", "Akpek 2023")),
        (("27055414",), source_key("included", "Leonardi 2016")),
        (("28362054",), source_key("included", "Baudouin 2017")),
        (("28708219", "30389343"), source_key("included", "Leonardi 2016")),
        (("33546885",), source_key("included", "Peng 2021")),
        (("36164414",), source_key("included", "Peng 2022")),
        (("36973703", "pmc10041473"), source_key("included", "Rao 2023")),
        (("28759302",), source_key("included", "Kim 2017")),
        (("35914303",), source_key("included", "Gao 2023")),
        (("23135530",), source_key("included", "Prabhasawat 2012")),
        (("35233694",), source_key("included", "Jo 2022")),
        (("27929721",), source_key("included", "Park 2017")),
        (("17914201",), source_key("included", "Jain 2007")),
        (("18848318",), source_key("included", "Kim 2009")),
        (("18180683",), source_key("included", "Willen 2008")),
        (("17982500",), source_key("cochrane_excluded", "Wang 2008")),
        (("39373208",), source_key("cochrane_excluded", "Feng 2024")),
        (("39604906",), source_key("cochrane_excluded", "Gao 2024")),
        (("38143559",), "ayres_sahara"),
        (("40146145",), "salam_2025"),
        (("41628505",), "mu_2026"),
        (("40678997",), "gannan_postcataract"),
        (("31361655",), "malhotra_pooled"),
        (("41420783",), "rolando_posthoc"),
        (("29440872",), "pisella_2018"),
        (("35298789",), "geerling_2022"),
        (("41809208",), "johnston_2026"),
        (("42283972", "nct04144413"), "long_term_cationic_2026"),
        (("27257373",), "impact"),
        (("16371776",), "perry_2006"),
        (("18695097",), "perry_2008"),
        (("40597071",), "retrospective_dose_comparison"),
        (("41366894",), "ipl_three_arm_2025"),
        (("41567664",), "dong_2026"),
        (("21999340",), source_key("included", "Rao 2010")),
        (("21407074",), source_key("cochrane_excluded", "Su 2011")),
        (("nct05245604",), source_key("included", "Eom 2023")),
        (("nct04127851",), source_key("included", "Lee 2022")),
        (("nct02917512",), source_key("included", "Shin 2021")),
        (("nct00739349",), source_key("cochrane_ongoing", "NCT00739349")),
        (("nct03461575",), source_key("cochrane_ongoing", "NCT03461575")),
        (("nct06043908", "40178682", "41212221"), source_key("cochrane_ongoing", "NCT06043908")),
        (("nct06766357",), source_key("cochrane_ongoing", "NCT06766357")),
        (("nct06392438",), source_key("cochrane_excluded", "NCT06392438")),
        (("nct00426023",), "vkc_nct00426023"),
        (("nct04147650",), "audrey"),
        (("nct03865888",), "nct03865888"),
        (("nct06981104",), "nct06981104"),
        (("nct00520260",), "nct00520260"),
        (("nct01198782",), "nct01198782"),
        (("nct00553735",), "nct00553735"),
        (("nct00405457",), "nct00405457"),
    )
    for identifiers, key in identifier_rules:
        if any(identifier in text for identifier in identifiers):
            return (key,)

    if "effectiveness and optical quality of topical 3 0 diquafosol" in text:
        return ("lee_2016_duplicate",)

    # Exact copied source titles are accepted only by normalized containment.
    if title_keys := exact_source_title_keys(text):
        return title_keys

    # Companion publications and common paraphrases.
    phrase_rules: tuple[tuple[tuple[str, ...], str], ...] = (
        (("two multicenter randomized studies",), source_key("included", "Sall 2000")),
        (("phase iii safety evaluation", "up to 3 years"), source_key("included", "Sall 2000")),
        (("phase iii safety evaluation", "up to three years"), source_key("included", "Sall 2000")),
        (("blood concentrations of cyclosporin",), source_key("included", "Sall 2000")),
        (("blood csa levels",), source_key("included", "Sall 2000")),
        (("interleukin 6 levels",), source_key("included", "Sall 2000")),
        (("goblet cell numbers and epithelial proliferation",), source_key("included", "Sall 2000")),
        (("a comparison of cyclosporine 0 05 ophthalmic emulsion versus vehicle",), source_key("included", "Chen 2010")),
        (("eight week multicenter randomized double blind",), source_key("included", "Chen 2010")),
        (("12 week multicenter randomized double masked placebo controlled",), source_key("included", "Chen 2019")),
        (("12 week randomized phase iii", "medicine"), source_key("included", "Chen 2019")),
        (("phase iii randomized trial", "medicine"), source_key("included", "Chen 2019")),
        (("medicine", "2019", "0 05 cyclosporine ophthalmic emulsion", "moderate to severe dry eye"), source_key("included", "Chen 2019")),
        (("efficacy and safety of cyclosporin a ophthalmic emulsion in the treatment of moderate to severe",), source_key("included", "Stevenson 2000")),
        (("dose ranging clinical trial", "keratoconjunctivitis sicca"), source_key("included", "Stevenson 2000")),
        (("dose ranging randomized trial", "moderate to severe dry eye"), source_key("included", "Stevenson 2000")),
        (("siccanove",), source_key("included", "Baudouin 2017")),
        (("sansika",), source_key("included", "Leonardi 2016")),
        (("one year efficacy and safety", "cationic emulsion"), source_key("included", "Leonardi 2016")),
        (("pooled analysis of two double masked",), source_key("included", "Leonardi 2016")),
        (("otx 101", "pooled analysis"), "malhotra_pooled"),
        (("otx 101", "post hoc"), "rolando_posthoc"),
        (("day 14", "otx 101"), source_key("included", "Tauber 2018")),
        (("phase ii iii", "otx 101"), source_key("included", "Tauber 2018")),
        (("phase 2b 3", "otx 101"), source_key("included", "Tauber 2018")),
        (("phase 3", "otx 101"), source_key("included", "Goldberg 2019")),
        (("worse eye analysis", "otx 101"), source_key("included", "Goldberg 2019")),
        (("clinical phase ii", "water free"), source_key("included", "Wirta 2019")),
        (("essence 2 open label extension",), source_key("included", "Akpek 2023")),
        (("essence 2 ole",), source_key("included", "Akpek 2023")),
        (("essence 2",), source_key("included", "Akpek 2023")),
        (("essence 1",), source_key("included", "Sheppard 2021")),
        (("water free 0 1 cyclosporine a solution", "randomized essence study"), source_key("included", "Sheppard 2021")),
        (("randomized phase 2b 3 essence",), source_key("included", "Sheppard 2021")),
        (("china phase 3", "water free"), source_key("included", "Peng 2024")),
        (("shr8028",), source_key("included", "Peng 2024")),
        (("water free cyclosporine ophthalmic solution versus vehicle",), source_key("included", "Peng 2024")),
        (("water free cyclosporine ophthalmic solution vs vehicle",), source_key("included", "Peng 2024")),
        (("cyclagel", "phase ii"), source_key("included", "Peng 2021")),
        (("phase ii randomized study", "cyclosporine ophthalmic gel"), source_key("included", "Peng 2021")),
        (("cosmo",), source_key("included", "Peng 2022")),
        (("micellar nano particulate",), source_key("included", "Rao 2023")),
        (("mnp cyclosporine",), source_key("included", "Rao 2023")),
        (("novel 0 05 cyclosporine nanoemulsion", "conventional"), source_key("included", "Kim 2017")),
        (("randomized comparison of csa 0 05 nanoemulsion and conventional emulsion",), source_key("included", "Kim 2017")),
        (("primary sj gren", "topical 0 05"), source_key("included", "Gao 2023")),
        (("cyclosporine artificial tears or their combination",), source_key("included", "Gao 2023")),
        (("vitamin a and cyclosporine",), source_key("included", "Kim 2009")),
        (("contact lens wearers with dry eyes",), source_key("included", "Willen 2008")),
        (("pilot trial of cyclosporine 1 ophthalmic ointment",), source_key("included", "Laibovitz 1993")),
        (("flow cytometric analysis of inflammatory markers",), source_key("included", "Brignole 2001")),
        (("galatoire",), source_key("included", "Brignole 2001")),
        (("safety and efficacy of cyclosporine 0 05 drops versus unpreserved artificial tears",), source_key("included", "Salib 2006")),
        (("topical cyclosporine nanoemulsion 0 05", "diquafosol 3"), source_key("included", "Park 2019")),
        (("randomized multicenter study comparing 0 1 0 15 and 0 3 sodium hyaluronate",), source_key("included", "Park 2017")),
        (("comparison of topical cyclosporine and diquafosol",), source_key("included", "Ma 2015")),
        (("withdrawal", "cyclosporine ophthalmic emulsion"), source_key("included", "Rao 2010")),
        (("rao sn", "dry eye progression"), source_key("included", "Rao 2010")),
        (("reversibility of dry eye deceleration",), source_key("included", "Rao 2010")),
        (("comparative clinical trial of two aqueous cyclosporine",), source_key("included", "Baiza-Durán 2010")),
        (("randomized comparison of csa 0 05 csa 0 1 and vehicle",), source_key("included", "Baiza-Durán 2010")),
        (("micellar nanoparticulate csa investigators",), source_key("included", "Rao 2023")),
        (("tjo 018",), source_key("included", "Lee 2022")),
        (("paired eye", "absorbable punctal plugs"), "dong_2026"),
        (("combined with absorbable punctal plugs",), "dong_2026"),
        (("tearcare",), "ayres_sahara"),
        (("sahara",), "ayres_sahara"),
        (("fluorometholone",), source_key("cochrane_excluded", "Gao 2024")),
        (("punctal occlusion",), source_key("cochrane_excluded", "Roberts 2007a")),
        (("punctal plugs", "feng"), source_key("cochrane_excluded", "Feng 2024")),
        (("once daily versus twice daily",), source_key("cochrane_excluded", "Su 2011")),
        (("decreasing cyclosporine",), source_key("cochrane_excluded", "Su 2011")),
        (("contact lens intolerant",), source_key("cochrane_excluded", "Hom 2006")),
        (("chronic graft versus host disease",), source_key("cochrane_excluded", "Wang 2008")),
        (("retracted", "park"), "park_retracted"),
        (("comparison of 0 05 cyclosporine and 3 diquafosol",), "park_retracted"),
        (("post cataract",), "gannan_postcataract"),
        (("post cataract surgery",), "gannan_postcataract"),
        (("aqueous solution and oil emulsion",), "salam_2025"),
        (("aqueous versus oil",), "salam_2025"),
        (("short fbut",), "mu_2026"),
        (("short fluorescein tear",), "mu_2026"),
        (("short tear break up time",), "mu_2026"),
        (("evaluation of topical cyclosporine for the treatment",), "perry_2008"),
        (("prospective multicenter open label surveillance",), "byun_2011"),
        (("cyclosporine 0 05 ophthalmic emulsion for dry eye in korea",), "byun_2011"),
        (("long term resolution of chronic dry eye",), "wilson_2007"),
        (("10 year follow up",), "straub_2016"),
        (("ten year follow up",), "straub_2016"),
        (("french early access",), "pisella_2018"),
        (("perspective",), "geerling_2022"),
        (("switching prospective open label multicenter",), "yoon_switch"),
        (("inadequately controlled", "single arm open label phase 4"), "johnston_2026"),
        (("long term evolution of treatment outcomes",), "long_term_cationic_2026"),
        (("long term evolution", "once daily csa 0 1 cationic emulsion"), "long_term_cationic_2026"),
        (("long term efficacy and safety", "36 month phase 3b"), "long_term_cationic_2026"),
        (("24 month retrospective", "cationic emulsion"), "advanced_cationic_24_month"),
        (("optimizing the ocular surface", "cataract"), "akpek_cataract_2024"),
        (("preservative free cyclosporine",), "preservative_free"),
        (("cyclisis pf",), "preservative_free"),
        (("locatelli",), "locatelli"),
        (("kolluru",), "kolluru"),
        (("impact study",), "impact"),
        (("persist", "restasis satisfaction"), "persist"),
        (("effects of postoperative cyclosporine",), "deveney_2009"),
        (("pediatric vernal keratoconjunctivitis",), "colligris_vkc"),
        (("voclosporin",), "audrey"),
        (("head to head", "0 09"), "otx_head_to_head_unconfirmed"),
    )
    for phrases, key in phrase_rules:
        if all(phrase in text for phrase in phrases):
            return (key,)

    return ("unresolved_report",)


def citation_identity_note(entry: str, key: str) -> str:
    """Return an audit note when a citation resolves despite conflicting details."""

    text = normalize(entry)
    if key == source_key("included", "Wirta 2019") and text.startswith("sall"):
        return "The title and PMID identify Wirta 2019, but the response gives Sall as lead author."
    if key == source_key("included", "Akpek 2023") and (
        text.startswith("wirta") or text.startswith("sheppard")
    ):
        return "The ESSENCE-2 report identifies Akpek 2023, but the response gives another lead author."
    if key == source_key("included", "Chen 2010") and text.startswith("leonardi"):
        return "The title identifies Chen 2010, but the response gives Leonardi as lead author."
    if key == source_key("included", "Chen 2019") and text.startswith("wang"):
        return "The title identifies Chen 2019, but the response gives Wang as lead author."
    if key == source_key("included", "Peng 2024") and text.startswith("sheppard"):
        return "The China phase III report identifies Peng 2024, but the response gives Sheppard as lead author."
    if key == source_key("included", "Leonardi 2016") and "ophthalmic res" in text:
        return "The SANSIKA title identifies Leonardi 2016, but the response gives conflicting journal details."
    return ""


def extract_terminal_list(path: Path) -> list[str]:
    """Extract only entries inside the response's dedicated final study list."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if path.stem == "claude-researcher-1":
        start = next(
            index
            for index, line in enumerate(lines)
            if "Landmark/pivotal trials" in line
        )
        entries = [line[2:].strip() for line in lines[start:] if line.startswith("- ")]
        if entries:
            return entries
        raise ValueError(f"No cohesive study-list entries in {path.name}")

    heading_indexes = []
    for index, line in enumerate(lines):
        heading = normalize(line)
        if path.stem.startswith("gemini-"):
            if (line.startswith("#") or line.startswith("**")) and heading.startswith(
                "references"
            ):
                heading_indexes.append(index)
        elif (
            line.startswith("#")
            and heading.startswith(
                ("primary studies", "individual primary studies", "list of primary studies")
            )
        ) or re.match(
            r"^\*\*(?:primary studies|individual primary studies|list of primary studies)[^*]*\*\*:?\s*$",
            line.strip(),
            re.IGNORECASE,
        ):
            heading_indexes.append(index)
    if not heading_indexes:
        raise ValueError(f"No terminal study-list heading in {path.name}")

    block = lines[heading_indexes[-1] + 1 :]
    if path.stem.startswith("gemini-"):
        entries = []
        for index, line in enumerate(block):
            if not line.startswith("Cited by:"):
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
    return [REVIEW_DIR / name for name in sorted(expected)]


def validate_cochrane_labels() -> None:
    """Require every Cochrane-classified candidate label to occur in its RIS."""

    labels_by_status = {
        status: ris_study_labels(member) for status, member in RIS_MEMBERS.items()
    }
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
                    "source_file": f"retrieval_bias/CD010051/{path.name}",
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
    if any(
        row["canonical_candidate"] == CANDIDATES["unresolved_report"].label
        for row in rows
    ):
        raise ValueError("A generic unresolved citation remains in the curated match rows")

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
    """Print compact extraction, recall, and missed-study checks."""

    included_truth = ris_study_labels(RIS_MEMBERS["included"])
    included_pmids = ris_pubmed_ids(RIS_MEMBERS["included"])
    included_pmid_truth = set().union(*included_pmids.values())
    by_run: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for row in rows:
        by_run[str(row["run_id"])].append(row)
    assignment_count = sum(
        len(resolve_candidate(entry))
        for path in response_paths()
        for entry in extract_terminal_list(path)
    )
    print(f"Runs: {len(response_paths())}")
    print(f"Terminal-list entries: {sum(raw_counts.values())}")
    print(f"Candidate-study assignments before deduplication: {assignment_count}")
    print(f"Response-study rows after within-response deduplication: {len(rows)}")
    print(
        "Source-package classified labels: "
        + ", ".join(
            f"{status}={len(ris_study_labels(member))}"
            for status, member in RIS_MEMBERS.items()
        )
    )
    print(
        "Included PMID coverage in source RIS: "
        f"{len(included_pmid_truth)} explicit PubMed IDs"
    )
    for model in MODELS:
        run_ids = [run_id for run_id in raw_counts if run_id.startswith(f"{model}-")]
        print(
            f"{model}: {sum(raw_counts[run_id] for run_id in run_ids)} entries; "
            f"{sum(len(by_run.get(run_id, [])) for run_id in run_ids)} response-study rows"
        )
    print("Included-study recall by run:")
    pooled_retrieved: set[str] = set()
    for path in response_paths():
        run_id = path.stem
        retrieved = set().union(
            *(included_labels(row) for row in by_run.get(run_id, []))
        )
        pooled_retrieved.update(retrieved)
        print(
            f"  {run_id}: clusters={len(retrieved)}/{len(included_truth)}; "
            f"study rows={len(retrieved)}/{len(included_truth)}"
        )
    pooled_missing = sorted(included_truth - pooled_retrieved)
    print(
        f"Pooled included recall: clusters={len(pooled_retrieved)}/{len(included_truth)}; "
        f"study rows={len(pooled_retrieved)}/{len(included_truth)}"
    )
    print(f"Pooled missed included labels: {','.join(pooled_missing) or 'none'}")
    if included_pmid_truth:
        pooled_pmids = {
            pmid
            for label in pooled_retrieved
            for pmid in included_pmids.get(label, set())
        }
        missed_pmids = sorted(included_pmid_truth - pooled_pmids)
        print(
            f"Pooled source-PMID recall: {len(pooled_pmids)}/{len(included_pmid_truth)}; "
            f"missed PMIDs={','.join(missed_pmids) or 'none'}"
        )
    else:
        print("Pooled source-PMID recall: unavailable; source RIS has no PubMed IDs")
    unresolved = [
        row for row in rows if row["ground_truth_status"] == "outside_unresolved"
    ]
    print(f"Outside-unresolved response-study rows: {len(unresolved)}")
    for row in unresolved:
        print(
            f"  {row['run_id']}: {str(row['reported_citation'])[:180]}"
        )
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the terminal-list-only curated match table for CD010051."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
