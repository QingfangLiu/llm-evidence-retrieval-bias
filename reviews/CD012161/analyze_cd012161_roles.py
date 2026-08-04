#!/usr/bin/env python3
"""Analyze CD012161 using only each response's terminal study list.

The extractor implements the review-specific boundary documented in README.md.
It preserves every terminal-list citation, resolves citations to study clusters,
deduplicates companion reports within a response, validates Cochrane labels
against the RIS exports, and writes the review's audit table.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_DIR = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_6"
    / "CD012161-SUP-06-dataPackage"
    / "CD012161-study-data"
)
MATCHES_PATH = REVIEW_DIR / "cd012161_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 184, "gemini": 48, "gpt": 213}
EXPECTED_RESPONSE_STUDY_ROWS = 388


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD012161 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_labels: tuple[str, ...] = ()
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 15 Cochrane-included study clusters.
    "dreyer_2005": CandidateInfo(
        "Dreyer 2005", "included", ("Dreyer 2005",), "randomized controlled trial"
    ),
    "ferguson_2001": CandidateInfo(
        "Ferguson 2001",
        "included",
        ("Ferguson 2001",),
        "randomized crossover trial",
    ),
    "home_2000": CandidateInfo(
        "Home 2000",
        "included",
        ("Home 2000",),
        "randomized controlled trial",
        "The 2006 pre-meal insulin-aspart publication is a companion extension report.",
    ),
    "iwamoto_2001": CandidateInfo(
        "Iwamoto 2001", "included", ("Iwamoto 2001",), "randomized controlled trial"
    ),
    "kawamori_2009": CandidateInfo(
        "Kawamori 2009", "included", ("Kawamori 2009",), "randomized controlled trial"
    ),
    "ma_2024": CandidateInfo(
        "Ma 2024", "included", ("Ma 2024",), "randomized controlled trial"
    ),
    "onset_1": CandidateInfo(
        "ONSET 1",
        "included",
        ("ONSET 1",),
        "randomized controlled trial",
        "The 26- and 52-week reports are grouped as one trial cluster.",
    ),
    "onset_8": CandidateInfo(
        "ONSET 8", "included", ("ONSET 8",), "randomized controlled trial"
    ),
    "pronto_t1dm": CandidateInfo(
        "PRONTO-T1DM",
        "included",
        ("PRONTO-T1DM",),
        "randomized controlled trial",
        "Primary, extension, CGM, and Japanese-subpopulation reports are one trial cluster.",
    ),
    "provenzano_2001": CandidateInfo(
        "Provenzano 2001",
        "included",
        ("Provenzano 2001",),
        "randomized crossover trial",
    ),
    "raskin_2000": CandidateInfo(
        "Raskin 2000", "included", ("Raskin 2000",), "randomized controlled trial"
    ),
    "recasens_2003": CandidateInfo(
        "Recasens 2003", "included", ("Recasens 2003",), "randomized controlled trial"
    ),
    "z011": CandidateInfo(
        "Z011",
        "included",
        ("Z011 2007",),
        "randomized controlled trial",
        "Some publications report Z011 together with other sponsor trials.",
    ),
    "z013": CandidateInfo(
        "Z013",
        "included",
        ("Z013 2007",),
        "randomized controlled trial",
        "Some publications report Z013 together with other sponsor trials.",
    ),
    "z015": CandidateInfo(
        "Z015",
        "included",
        ("Z015 2007",),
        "randomized controlled trial",
        "The Garg 1996 publication reports Z015 together with other sponsor trials.",
    ),
    # Candidate publications explicitly represented in the excluded RIS.
    "gemelli_1": CandidateInfo(
        "GEMELLI 1",
        "cochrane_excluded",
        ("Garg 2020b",),
        "randomized biosimilar trial",
        "The primary 26-week GEMELLI 1 report is excluded for the wrong comparison.",
    ),
    "heise_2016": CandidateInfo(
        "Heise faster-aspart pharmacology trial",
        "cochrane_excluded",
        ("Heise 2016",),
        "randomized crossover clamp trial",
        "The review excludes this short pharmacology study for duration.",
    ),
    "kazda_2022": CandidateInfo(
        "Kazda 2022 URLi meal-test trial",
        "cochrane_excluded",
        ("Kazda 2022",),
        "randomized crossover meal-test trial",
        "The review excludes this early-phase study for duration.",
    ),
    "lalli_1999": CandidateInfo(
        "Lalli 1999",
        "cochrane_excluded",
        ("Lalli 1999",),
        "randomized controlled trial",
        "The review excludes this study because the NPH regimens differed.",
    ),
    "lindholm_1999": CandidateInfo(
        "Lindholm 1999",
        "cochrane_excluded",
        ("Lindholm 1999",),
        "randomized crossover trial",
        "The review excludes this study for duration.",
    ),
    "vignati_1997": CandidateInfo(
        "Vignati 1997",
        "cochrane_excluded",
        ("Vignati 1997",),
        "randomized controlled trial",
        "The review excludes this twice-daily mixed-regimen study for duration.",
    ),
    # Other identifiable candidates outside the Cochrane included/excluded sets.
    "anderson_pooled": CandidateInfo(
        "Anderson 1997 pooled lispro-trial analysis",
        "outside_other",
        design="pooled analysis of randomized trials",
        note="The publication pools several sponsor trials without a separable Cochrane study label.",
    ),
    "uk_lispro_trial": CandidateInfo(
        "UK Trial Group lispro trial", "outside_other", design="randomized crossover trial"
    ),
    "garg_glulisine": CandidateInfo(
        "Garg 2005 glulisine trial", "outside_other", design="randomized controlled trial"
    ),
    "tamas_2001": CandidateInfo(
        "Tamás 2001", "outside_other", design="randomized controlled trial"
    ),
    "home_1998": CandidateInfo(
        "Home 1998 short aspart trial", "outside_other", design="randomized crossover trial"
    ),
    "heller_2004": CandidateInfo(
        "Heller 2004 aspart hypoglycaemia trial",
        "outside_other",
        design="randomized crossover trial",
    ),
    "heller_1999": CandidateInfo(
        "Heller 1999 nocturnal-hypoglycaemia trial",
        "outside_other",
        design="randomized crossover trial",
    ),
    "hypoana": CandidateInfo(
        "HypoAna trial",
        "outside_other",
        design="randomized crossover trial",
        note="The trial changes both basal and prandial insulin components.",
    ),
    "analogue_regimen": CandidateInfo(
        "Hermansen/Vague analogue-regimen trial",
        "outside_other",
        design="randomized controlled trial",
        note="The intervention changes both basal and prandial insulin components.",
    ),
    "devries_2003": CandidateInfo(
        "DeVries 2003 intensified-basal trial",
        "outside_other",
        design="randomized controlled trial",
        note="The intervention changes both basal-insulin intensity and prandial insulin.",
    ),
    "glargine_lispro": CandidateInfo(
        "Ashwell glargine-plus-lispro trial",
        "outside_other",
        design="randomized crossover trial",
        note="The intervention changes both basal and prandial insulin components.",
    ),
    "gobolus": CandidateInfo(
        "GoBolus study", "outside_observational", design="prospective real-world study"
    ),
    "lind_real_world": CandidateInfo(
        "Lind 2023 real-world faster-aspart study",
        "outside_observational",
        design="retrospective database study",
    ),
    "linnebjerg_pk": CandidateInfo(
        "Linnebjerg 2020 URLi pharmacology trial",
        "outside_other",
        design="randomized crossover pharmacology trial",
    ),
    "jablonska_meal": CandidateInfo(
        "Jabłońska 2018 high-fat meal trial",
        "outside_other",
        design="randomized crossover meal study",
    ),
    "heise_urli": CandidateInfo(
        "Heise 2020 URLi comparative meal-test trial",
        "outside_other",
        design="randomized crossover meal-test trial",
    ),
    "homko_2003": CandidateInfo(
        "Homko 2003 aspart-lispro study",
        "outside_other",
        design="randomized crossover pharmacology study",
    ),
    "plank_2002": CandidateInfo(
        "Plank 2002 aspart-lispro study",
        "outside_other",
        design="randomized crossover study",
    ),
    "rave_2006": CandidateInfo(
        "Rave 2006 glulisine meal study",
        "outside_other",
        design="randomized crossover meal study",
    ),
    "annuzzi_2001": CandidateInfo(
        "Annuzzi 2001 lispro-NPH trial",
        "outside_other",
        design="randomized crossover trial",
    ),
    "schernthaner_2004": CandidateInfo(
        "Schernthaner 2004 lispro-timing trial",
        "outside_other",
        design="randomized crossover trial",
        note="The comparison changes injection timing rather than the insulin analogue.",
    ),
    "pfutzner_1996": CandidateInfo(
        "Pfützner 1996 lispro study", "outside_other", design="comparative clinical trial"
    ),
    "kotsanos_qol": CandidateInfo(
        "Kotsanos 1997 quality-of-life analysis",
        "outside_other",
        design="pooled secondary analysis",
    ),
    "brunelle_pooled": CandidateInfo(
        "Brunelle 1998 hypoglycaemia analysis",
        "outside_other",
        design="pooled secondary analysis",
    ),
    "perriello_2002": CandidateInfo(
        "Perriello/Skrha 2002 lispro study", "outside_other", design="comparative trial"
    ),
    "holleman_severe": CandidateInfo(
        "Holleman 1997 severe-hypoglycaemia study",
        "outside_other",
        design="comparative clinical study",
    ),
    "glulisine_clamp": CandidateInfo(
        "Glulisine end-organ clamp study",
        "outside_other",
        design="randomized glucose-clamp study",
    ),
    "mixed_insulin": CandidateInfo(
        "Kolendorf biphasic-insulin study",
        "outside_other",
        design="mixed-insulin comparative study",
    ),
    "mathiesen_pregnancy": CandidateInfo(
        "Mathiesen 2007 pregnancy trial",
        "outside_other",
        design="randomized controlled trial in pregnancy",
    ),
    "copenfast": CandidateInfo(
        "CopenFast",
        "outside_other",
        design="randomized controlled trial in pregnancy",
    ),
    "closed_loop": CandidateInfo(
        "Lee 2021 hybrid-closed-loop trial",
        "outside_other",
        design="randomized crossover pump trial",
    ),
    "pronto_pump": CandidateInfo(
        "PRONTO-Pump", "outside_other", design="randomized pump-compatibility trial"
    ),
    "norgaard_pump": CandidateInfo(
        "Nørgaard/Ranjan non-automated-pump trial",
        "outside_other",
        design="randomized crossover pump trial",
    ),
    "van_bon_pump": CandidateInfo(
        "van Bon 2011 pump trial", "outside_other", design="randomized pump trial"
    ),
    "bode_lispro_pump": CandidateInfo(
        "Bode 2001 lispro-pump trial", "outside_other", design="randomized pump trial"
    ),
    "bode_aspart_pump": CandidateInfo(
        "Bode 2002 aspart-pump trial", "outside_other", design="randomized pump trial"
    ),
    "heise_fiasp_pump": CandidateInfo(
        "Heise 2017 faster-aspart pump pharmacology trial",
        "outside_other",
        design="randomized crossover pump trial",
    ),
    "weinzimer_pump": CandidateInfo(
        "Weinzimer 2008 pediatric pump trial",
        "outside_other",
        design="randomized pediatric pump trial",
    ),
    "ratner_lispro": CandidateInfo(
        "Ratner lispro hypoglycaemia study",
        "outside_unresolved",
        design="named multicenter trial; exact report unresolved",
    ),
    "early_lispro_unresolved": CandidateInfo(
        "Unspecified early lispro trials",
        "outside_unresolved",
        design="vaguely named trial group",
    ),
}


def normalize(text: str) -> str:
    """Normalize response text for stable review-specific matching."""

    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def resolve_candidate(entry: str) -> tuple[str, ...]:
    """Resolve one terminal-list entry to one or more study clusters."""

    text = normalize(entry)
    if "pronto pump" in text or "compatibility and safety of ultra rapid lispro" in text:
        return ("pronto_pump",)
    if any(value in text for value in ("hybrid closed loop", "closed loop system")):
        return ("closed_loop",)
    if (
        "continuous subcutaneous insulin infusion" in text
        or "insulin pump" in text
        or "csii" in text
    ):
        if "van bon" in text or "glulisine compared to insulin aspart" in text:
            return ("van_bon_pump",)
        if "weinzimer" in text:
            return ("weinzimer_pump",)
        if "non automated insulin pump" in text or "n rgaard" in text:
            return ("norgaard_pump",)
        if "comparison of insulin aspart with buffered" in text:
            return ("bode_aspart_pump",)
        if "comparison of insulin lispro and buffered" in text:
            return ("bode_lispro_pump",)
        if "pharmacological properties of faster acting insulin aspart" in text:
            return ("heise_fiasp_pump",)
        raise ValueError(f"Unresolved pump citation: {entry}")
    if "mathiesen" in text:
        return ("mathiesen_pregnancy",)
    if "copenfast" in text or "pregnancy and post delivery" in text:
        return ("copenfast",)
    if "gemelli 1" in text or "sar341402" in text:
        return ("gemelli_1",)
    if "pronto t1d" in text or "pronto type 1 diabetes" in text:
        return ("pronto_t1dm",)
    if "ultra rapid lispro" in text and any(
        value in text
        for value in (
            "long term efficacy and safety of ultra rapid lispro",
            "continuous glucose monitoring substudy",
            "cgm substudy",
            "japanese patients",
        )
    ):
        return ("pronto_t1dm",)
    if "nct03952130" in text or "predominantly chinese" in text or text.startswith("ma j"):
        return ("ma_2024",)
    if any(
        value in text
        for value in (
            "onset 8",
            "onset8",
            "insulin degludec treated",
            "combination with insulin degludec in japanese",
        )
    ):
        return ("onset_8",)
    if "onset 1" in text or "onset1" in text or (
        "russell jones" in text and "fast acting insulin aspart" in text
    ):
        return ("onset_1",)
    if "mathieu" in text and "fast acting insulin aspart" in text:
        return ("onset_1",)
    if (
        "efficacy and safety of insulin glulisine in patients with type 1 diabetes" in text
        and "japanese" not in text
    ):
        return ("dreyer_2005",)
    if "kawamori" in text or "glulisine in japanese patients" in text:
        return ("kawamori_2009",)
    if "severe hypoglycaemia" in text and "ferguson" in text:
        return ("ferguson_2001",)
    if "iwamoto" in text or "phase iii clinical trial in japan" in text:
        return ("iwamoto_2001",)
    if "provenzano" in text or "mediterranean or normal diet" in text:
        return ("provenzano_2001",)
    if (
        "recasens" in text
        or "preserving beta cell function" in text
        or ("insulin lispro is as effective" in text and "preserving" in text)
    ):
        return ("recasens_2003",)
    if "use of insulin aspart" in text and "mealtime insulin" in text:
        return ("raskin_2000",)
    if text.startswith("raskin") and "insulin aspart" in text:
        return ("raskin_2000",)
    if (
        ("insulin aspart vs human insulin" in text or "insulin aspart versus human insulin" in text)
        and "long term blood glucose control" in text
    ):
        return ("home_2000",)
    if "pre meal insulin aspart compared with pre meal soluble human insulin" in text:
        return ("home_2000",)
    if text.startswith("home et al") and "pre meal insulin aspart" in text:
        return ("home_2000",)
    if "30 month extension" in text and "insulin aspart" in text:
        return ("home_2000",)
    if "trial z011" in text:
        return ("z011",)
    if "trial z013" in text:
        return ("z013",)
    if "trial z015" in text:
        return ("z015",)
    if "improved mealtime treatment" in text:
        return ("z011", "z013")
    if "pre meal insulin analogue insulin lispro" in text:
        return ("z011", "z013", "z015")
    if "efficacy of insulin lispro in combination with nph human insulin" in text:
        return ("vignati_1997",)
    if "reduction of postprandial hyperglycemia" in text:
        return ("anderson_pooled",)
    if "uk trial group" in text or "gale eam" in text:
        return ("uk_lispro_trial",)
    if (
        ("garg" in text or "dailey" in text)
        and "glulisine" in text
        and "regular human insulin" in text
    ):
        return ("garg_glulisine",)
    if "tamas" in text or (
        "tam s" in text
        and (
            "optimised insulin aspart" in text
            or "optimized insulin aspart" in text
        )
    ):
        return ("tamas_2001",)
    if "tri continental insulin aspart" in text or text.startswith("devries"):
        return ("devries_2003",)
    if (
        "improved glycemic control with insulin aspart" in text
        or "improved glycaemic control with insulin aspart" in text
    ) and "1998" in text:
        return ("home_1998",)
    if "lindholm" in text and "improved postprandial" in text:
        return ("lindholm_1999",)
    if "hypoglycaemia with insulin aspart" in text:
        return ("heller_2004",)
    if "heller" in text and (
        "nocturnal hypoglycemia" in text or "nocturnal hypoglycaemia" in text
    ):
        return ("heller_1999",)
    if "hypoana" in text or "pedersen bjergaard" in text:
        return ("hypoana",)
    if "detemir" in text and ("nph" in text or "traditional human insulin" in text):
        return ("analogue_regimen",)
    if "12 month efficacy and safety of insulin detemir and insulin aspart" in text:
        return ("analogue_regimen",)
    if "glargine plus insulin lispro" in text or "glargine lispro trial" in text:
        return ("glargine_lispro",)
    if "gobolus" in text:
        return ("gobolus",)
    if "lind m" in text and "real world" in text:
        return ("lind_real_world",)
    if "kazda" in text and "meal test" in text:
        return ("kazda_2022",)
    if "linnebjerg" in text:
        return ("linnebjerg_pk",)
    if "jab o ska" in text or "high fat protein meal" in text:
        return ("jablonska_meal",)
    if "heise" in text and "faster acting insulin aspart" in text:
        return ("heise_2016",)
    if "heise" in text and "ultra rapid lispro" in text:
        return ("heise_urli",)
    if "homko" in text or "comparison of insulin aspart and lispro" in text:
        return ("homko_2003",)
    if "plank" in text and "direct comparison" in text:
        return ("plank_2002",)
    if "advantage of premeal injected insulin glulisine" in text:
        return ("rave_2006",)
    if "annuzzi" in text:
        return ("annuzzi_2001",)
    if "schernthaner" in text and "insulin lispro" in text:
        return ("schernthaner_2004",)
    if "p tzner" in text or "pf tzner" in text:
        return ("pfutzner_1996",)
    if "kotsanos" in text:
        return ("kotsanos_qol",)
    if "brunelle" in text and "meta analysis" in text:
        return ("brunelle_pooled",)
    if "perriello" in text or "12448933" in text:
        return ("perriello_2002",)
    if "ratner" in text:
        return ("ratner_lispro",)
    if "long term intensive treatment" in text and "lalli" in text:
        return ("lalli_1999",)
    if "reduced frequency of severe hypoglycemia" in text and "holleman" in text:
        return ("holleman_severe",)
    if "comparable end organ metabolic effects" in text:
        return ("glulisine_clamp",)
    if "rosskamp" in text:
        return ("early_lispro_unresolved",)
    if "kolendorf" in text or "biphasic" in text:
        return ("mixed_insulin",)
    raise ValueError(f"Unresolved terminal-list citation: {entry}")


def citation_identity_note(entry: str, key: str) -> str:
    """Return an audit note when a citation resolves despite conflicting details."""

    text = normalize(entry)
    if key == "raskin_2000" and text.startswith("home pd"):
        return "The title identifies Raskin 2000, but the response supplies Home as lead author."
    if key == "onset_8" and any(
        value in text for value in ("bowering", "diabetes ther 2023", "diabetes obes metab 2021")
    ):
        return "The ONSET 8 description is identifiable, but the response supplies conflicting authorship or publication details."
    if key == "pronto_t1dm" and any(
        value in text
        for value in (
            "32640842 adjacent",
            "malecki mt cao d liu r et al pronto t1d extension",
            "blevins t et al long term efficacy",
            "bergenstal rm et al ultra rapid lispro",
            "bode bw et al pronto t1d",
            "621 634",
            "3 14",
        )
    ):
        if "621 634" in text or "3 14" in text:
            return "The extension title identifies PRONTO-T1DM, but the response supplies conflicting page details."
        return "The PRONTO-T1DM report is identifiable, but the response supplies conflicting author or identifier details."
    if key == "dreyer_2005" and "diabetes care" in text:
        return "The title identifies Dreyer 2005, but the response supplies the wrong journal."
    if key == "home_2000" and "hylleberg" in text and "long term" in text:
        return "The title identifies Home 2000, but the author list is taken from a different aspart study."
    if key == "vignati_1997":
        return "The title identifies Vignati 1997, but the response supplies Anderson-paper authors and pages."
    if key == "closed_loop" and not text.startswith("lee mh"):
        return "The title identifies the Lee 2021 trial, but the response supplies a conflicting lead author."
    if key == "recasens_2003" and text.startswith("chatterjee"):
        return "The title identifies Recasens 2003, but the response supplies a conflicting lead author."
    if key == "rave_2006" and text.startswith("becker"):
        return "The title identifies Rave 2006, but the response supplies a conflicting lead author."
    if key == "garg_glulisine" and text.startswith("dailey"):
        return "The title identifies Garg 2005, but the response supplies a conflicting lead author."
    if key == "anderson_pooled" and "keohane" in text:
        return "The title identifies Anderson 1997, but the response supplies a conflicting author list."
    return ""


def ris_study_labels(path: Path) -> set[str]:
    """Read unique Cochrane study labels from an RIS export."""

    return {
        match.group(1).strip()
        for match in re.finditer(
            r"^NS  - (.+)$", path.read_text(encoding="utf-8-sig"), re.MULTILINE
        )
    }


def extract_terminal_list(path: Path) -> list[str]:
    """Extract only entries inside the response's dedicated terminal list."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if path.stem == "claude-researcher-2":
        entries = []
        in_list = False
        for line in lines:
            if "Here's an overview of primary studies" in line:
                in_list = True
            elif in_list and line == "A few notes for your screening process:":
                break
            elif in_list and line.startswith("- "):
                entries.append(line[2:].strip())
        if not entries:
            raise ValueError(f"No terminal study-list entries in {path.name}")
        return entries

    heading_indexes = []
    for index, line in enumerate(lines):
        if not (line.startswith("#") or line.startswith("**")):
            continue
        heading = normalize(line)
        if path.stem.startswith("gemini-"):
            if heading.startswith(("references", "primary studies")):
                heading_indexes.append(index)
        elif heading.startswith(
            (
                "primary studies",
                "individual primary studies",
                "list of primary studies",
                "full list of primary studies",
            )
        ):
            heading_indexes.append(index)
    if not heading_indexes:
        raise ValueError(f"No terminal study-list heading in {path.name}")

    block = lines[heading_indexes[-1] + 1 :]
    if path.stem == "gemini-researcher-1":
        entries = [
            block[index + 1].strip()
            for index, line in enumerate(block[:-1])
            if re.match(r"^\d+\.\s+", line)
        ]
        if entries:
            return entries

    numbered = [
        match.group(1).strip()
        for line in block
        if (match := re.match(r"^\d+\.\s+(.+)$", line))
    ]
    if numbered:
        return numbered
    if path.stem.startswith("gemini-"):
        references = [
            line.strip()
            for line in block
            if "doi.org/" in line.lower()
            and not line.lower().startswith("cited by:")
        ]
        if references:
            return references
    bullets = [
        match.group(1).strip()
        for line in block
        if (match := re.match(r"^[*-]\s+(.+)$", line))
    ]
    if bullets:
        return bullets
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
        "included": ris_study_labels(SOURCE_DIR / "CD012161-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD012161-excluded.ris"),
        "cochrane_awaiting": ris_study_labels(SOURCE_DIR / "CD012161-awaiting.ris"),
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
    used_candidates = set()
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
                used_candidates.add(key)
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
                    "source_file": f"reviews/CD012161/{path.name}",
                    "reported_citation": " || ".join(citations),
                    "canonical_candidate": candidate.label,
                    "ground_truth_status": candidate.status,
                    "cochrane_study_label": " || ".join(candidate.cochrane_labels),
                    "design": candidate.design,
                    "identity_issue": int(bool(identity_notes[key])),
                    "notes": "; ".join(notes),
                }
            )

    unused = set(CANDIDATES) - used_candidates
    if unused:
        raise ValueError(f"Candidate definitions are not used: {sorted(unused)}")
    observed_entries = Counter()
    for run_id, count in raw_counts.items():
        observed_entries[run_id.split("-")[0]] += count
    if dict(observed_entries) != EXPECTED_LIST_ENTRIES:
        raise ValueError(
            "Terminal-list entry count mismatch; "
            f"expected={EXPECTED_LIST_ENTRIES}, observed={dict(observed_entries)}"
        )
    if len(rows) != EXPECTED_RESPONSE_STUDY_ROWS:
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
    """Return the included Cochrane study labels credited by one audit row."""

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
    """Print compact extraction and included-study recall checks."""

    included_truth = ris_study_labels(SOURCE_DIR / "CD012161-included.ris")
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
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the terminal-list-only curated match table for CD012161."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
