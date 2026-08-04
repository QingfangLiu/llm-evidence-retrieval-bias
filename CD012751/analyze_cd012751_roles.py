#!/usr/bin/env python3
"""Analyze CD012751 using only each response's terminal study list.

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


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_DIR = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_6"
    / "CD012751-SUP-07-dataPackage"
    / "CD012751-study-data"
)
MATCHES_PATH = REVIEW_DIR / "cd012751_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 207, "gemini": 59, "gpt": 310}
EXPECTED_RESPONSE_STUDY_ROWS = 753


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD012751 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_labels: tuple[str, ...] = ()
    design: str = ""
    note: str = ""


CANDIDATES = {
    # Cochrane-included anti-TNF study clusters.
    "targan_1997": CandidateInfo(
        "Targan 1997", "included", ("Targan 1997",), "randomized controlled trial"
    ),
    "rutgeerts_1999": CandidateInfo(
        "Rutgeerts 1999",
        "included",
        ("Rutgeerts 1999",),
        "randomized controlled trial",
    ),
    "present_1999": CandidateInfo(
        "Present 1999",
        "included",
        ("Present 1999",),
        "randomized controlled trial",
    ),
    "accent_1": CandidateInfo(
        "ACCENT I",
        "included",
        (
            "Hanauer 2002 (ACCENT I) - Induction (non-response)",
            "Hanauer 2002 (ACCENT I) - Maintenence (Responders)",
        ),
        "randomized controlled trial",
    ),
    "accent_2": CandidateInfo(
        "ACCENT II",
        "included",
        (
            "Sands 2004 (ACCENT II) Induction (Non-responders)",
            "Sands 2004 (ACCENT II) Maintenance (Responders)",
        ),
        "randomized controlled trial",
    ),
    "sonic": CandidateInfo(
        "SONIC",
        "included",
        ("Colombel 2010 (SONIC)",),
        "randomized controlled trial",
    ),
    "stop_it": CandidateInfo(
        "STOP-IT",
        "included",
        ("Buhl 2022 (STOP-IT)",),
        "randomized withdrawal trial",
    ),
    "classic_1": CandidateInfo(
        "CLASSIC I",
        "included",
        ("Hanauer 2006 (CLASSIC I)",),
        "randomized controlled trial",
    ),
    "classic_2": CandidateInfo(
        "CLASSIC II",
        "included",
        ("Sandborn 2007b (CLASSIC II)",),
        "randomized controlled trial",
    ),
    "charm": CandidateInfo(
        "CHARM",
        "included",
        (
            "Colombel 2007 (CHARM) - Induction (non-responders)",
            "Colombel 2007 (CHARM) - Maintenance (responders)",
        ),
        "randomized controlled trial",
    ),
    "gain": CandidateInfo(
        "GAIN",
        "included",
        ("Sandborn 2007a",),
        "randomized controlled trial",
    ),
    "extend": CandidateInfo(
        "EXTEND",
        "included",
        ("Rutgeerts 2012 (EXTEND)",),
        "randomized controlled trial",
    ),
    "precise_1": CandidateInfo(
        "PRECiSE 1",
        "included",
        ("Sandborn 2007c (PRECISE 1)",),
        "randomized controlled trial",
    ),
    "precise_2": CandidateInfo(
        "PRECiSE 2",
        "included",
        ("Schreiber 2007 (PRECISE 2)",),
        "randomized controlled trial",
        "PRECiSE 3 is a companion extension report in this study cluster.",
    ),
    # Natalizumab and vedolizumab study clusters.
    "ghosh_2003": CandidateInfo(
        "Ghosh 2003",
        "included",
        ("Ghosh 2003",),
        "randomized controlled trial",
    ),
    "enact_1": CandidateInfo(
        "ENACT-1",
        "included",
        ("Sandborn 2005a (ENACT 1)",),
        "randomized controlled trial",
    ),
    "enact_2": CandidateInfo(
        "ENACT-2",
        "included",
        ("Sandborn 2005a (ENACT 2)",),
        "randomized controlled trial",
    ),
    "encore": CandidateInfo(
        "ENCORE",
        "included",
        ("Targan 2007 (ENCORE)",),
        "randomized controlled trial",
    ),
    "gemini_2": CandidateInfo(
        "GEMINI 2",
        "included",
        (
            "Sandborn 2013 (GEMINI II) - Induction",
            "Sandborn 2013 (GEMINI II) - Maintenance",
        ),
        "randomized controlled trial",
    ),
    "gemini_3": CandidateInfo(
        "GEMINI 3",
        "included",
        ("Sands 2014 (GEMINI III)",),
        "randomized controlled trial",
    ),
    "visible_2": CandidateInfo(
        "VISIBLE 2",
        "included",
        ("Vermeire 2021 (VISIBLE 2)",),
        "randomized controlled trial",
    ),
    "watanabe_2020": CandidateInfo(
        "Watanabe 2020 vedolizumab trial",
        "included",
        ("Watanabe 2020 - Induction", "Watanabe 2020 - Maintenance"),
        "randomized controlled trial",
    ),
    # Ustekinumab and selective IL-23 study clusters.
    "certifi": CandidateInfo(
        "CERTIFI",
        "included",
        (
            "Sandborn 2012 (CERTIFI) - Induction",
            "Sandborn 2012 (CERTIFI) - Induction (non-response)",
            "Sandborn 2012 (CERTIFI) - Maintenance",
        ),
        "randomized controlled trial",
    ),
    "uniti_1": CandidateInfo(
        "UNITI-1",
        "included",
        ("Feagan 2015a (UNITI-1)",),
        "randomized controlled trial",
    ),
    "uniti_2": CandidateInfo(
        "UNITI-2",
        "included",
        ("Feagan 2015b(UNITI-2)",),
        "randomized controlled trial",
    ),
    "im_uniti": CandidateInfo(
        "IM-UNITI",
        "included",
        ("Feagan 2015c (IM-UNITI)",),
        "randomized controlled trial",
    ),
    "seavue": CandidateInfo(
        "SEAVUE",
        "included",
        ("Sands 2022 (SEAVUE)",),
        "randomized active-comparator trial",
    ),
    "risankizumab_phase_2": CandidateInfo(
        "Risankizumab phase 2",
        "included",
        ("Feagan 2017",),
        "randomized controlled trial",
    ),
    "advance": CandidateInfo(
        "ADVANCE",
        "included",
        ("D'Haens 2022 (ADVANCE)",),
        "randomized controlled trial",
    ),
    "motivate": CandidateInfo(
        "MOTIVATE",
        "included",
        ("Panaccione 2022 (MOTIVATE)",),
        "randomized controlled trial",
    ),
    "fortify": CandidateInfo(
        "FORTIFY",
        "included",
        ("Ferrante 2022 - FORTIFY",),
        "randomized controlled trial",
    ),
    "sequence": CandidateInfo(
        "SEQUENCE",
        "included",
        ("Peyrin-Biroulet 2024 - SEQUENCE",),
        "randomized active-comparator trial",
    ),
    "galaxi_1": CandidateInfo(
        "GALAXI-1",
        "included",
        ("Sandborn 2022 - GALAXI 1",),
        "randomized controlled trial",
    ),
    "galaxi_2": CandidateInfo(
        "GALAXI-2",
        "included",
        ("Panaccione 2024 (GALAXI-2)",),
        "randomized controlled trial",
    ),
    "galaxi_3": CandidateInfo(
        "GALAXI-3",
        "included",
        ("Panaccione 2024 (GALAXI-3)",),
        "randomized controlled trial",
    ),
    "graviti": CandidateInfo(
        "GRAVITI",
        "included",
        ("Hart 2025 (GRAVITI)",),
        "randomized controlled trial",
    ),
    "serenity": CandidateInfo(
        "SERENITY",
        "included",
        ("Sands 2022 (SERENITY)",),
        "randomized controlled trial",
    ),
    "vivid_1": CandidateInfo(
        "VIVID-1",
        "included",
        ("Ferrante 2024 (VIVID-1)",),
        "randomized controlled trial",
    ),
    # JAK-inhibitor and other targeted-therapy study clusters.
    "celest": CandidateInfo(
        "CELEST",
        "included",
        ("Sandborn 2020d (CELEST) - Induction",),
        "randomized controlled trial",
        "The Cochrane package excludes the CELEST maintenance population.",
    ),
    "u_excel": CandidateInfo(
        "U-EXCEL",
        "included",
        ("Loftus 2023 (U-EXCEL)",),
        "randomized controlled trial",
    ),
    "u_exceed": CandidateInfo(
        "U-EXCEED",
        "included",
        ("Loftus 2023 (U-EXCEED)",),
        "randomized controlled trial",
    ),
    "u_endure": CandidateInfo(
        "U-ENDURE",
        "included",
        ("Loftus 2023 (U-ENDURE)",),
        "randomized controlled trial",
    ),
    "fitzroy": CandidateInfo(
        "FITZROY",
        "included",
        (
            "Vermeire 2017 FITZROY  - induction",
            "Vermeire 2017 FITZROY - induction non-responders",
            "Vermeire 2017 FITZROY - maintenance responders",
        ),
        "randomized controlled trial",
    ),
    "diversity_a": CandidateInfo(
        "DIVERSITY A",
        "included",
        ("Vermeire 2025 - DIVERSITY A",),
        "randomized controlled trial",
    ),
    "diversity_b": CandidateInfo(
        "DIVERSITY B",
        "included",
        ("Vermeire 2025 - DIVERSITY B",),
        "randomized controlled trial",
    ),
    "diversity_maintenance": CandidateInfo(
        "DIVERSITY maintenance",
        "included",
        ("Vermeire 2025 - DIVERSITY (maintenance)",),
        "randomized controlled trial",
    ),
    "tofacitinib": CandidateInfo(
        "Tofacitinib phase IIb program",
        "included",
        ("Panes 2017 Induction", "Panes 2017 Maintenance"),
        "randomized controlled trial",
    ),
    "bergamot": CandidateInfo(
        "BERGAMOT",
        "included",
        (
            "Sandborn 2023 - BERGAMOT (cohort 1)",
            "Sandborn 2023 - BERGAMOT (cohort 3)",
            "Sandborn 2023 - BERGAMOT Maintenance",
        ),
        "randomized controlled trial",
        "The Cochrane package excludes BERGAMOT cohort 2.",
    ),
    # Cochrane-excluded study clusters.
    "welcome": CandidateInfo(
        "WELCOME",
        "cochrane_excluded",
        ("Sandborn 2010b (WELCOME)",),
        "randomized controlled trial",
    ),
    # Other identifiable studies and out-of-scope publications.
    "varsity": CandidateInfo(
        "VARSITY",
        "outside_wrong_population",
        design="randomized controlled trial in ulcerative colitis",
    ),
    "ustekinumab_uc": CandidateInfo(
        "Ustekinumab ulcerative-colitis program",
        "outside_wrong_population",
        design="randomized controlled trial in ulcerative colitis",
    ),
    "fmt": CandidateInfo(
        "Sokol fecal-microbiota-transplantation trial",
        "outside_other",
        design="randomized controlled trial",
        note="The intervention is not a biologic or targeted small-molecule therapy.",
    ),
    "profile": CandidateInfo(
        "PROFILE",
        "outside_other",
        design="randomized treatment-strategy trial",
    ),
    "brodalumab": CandidateInfo(
        "Brodalumab phase 2 trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "treat_registry": CandidateInfo(
        "TREAT registry",
        "outside_observational",
        design="prospective registry",
    ),
    "pyramid_registry": CandidateInfo(
        "PYRAMID registry",
        "outside_observational",
        design="prospective registry",
    ),
    "gemini_lts": CandidateInfo(
        "GEMINI long-term safety study",
        "outside_other",
        design="open-label extension study",
    ),
    "lemaitre_2017": CandidateInfo(
        "Lemaitre 2017",
        "outside_observational",
        design="nationwide cohort study",
    ),
    "natalizumab_pml": CandidateInfo(
        "Van Assche natalizumab PML report",
        "outside_other",
        design="case report",
    ),
    "upadacitinib_real_world": CandidateInfo(
        "Elford upadacitinib cohort",
        "outside_observational",
        design="retrospective cohort study",
    ),
}


def normalize(text: str) -> str:
    """Normalize punctuation and Markdown enough for ordered identity rules."""

    return (
        text.lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace("‑", "-")
        .replace("\u00a0", " ")
    )


def resolve_candidate(entry: str) -> tuple[str, ...]:
    """Resolve one extracted citation with ordered review-specific rules."""

    text = normalize(entry)

    if "vedolizumab versus adalimumab" in text and "ulcerative colitis" in text:
        return ("varsity",)
    if "ustekinumab as induction and maintenance therapy for ulcerative colitis" in text:
        return ("ustekinumab_uc",)
    if "progressive multifocal leukoencephalopathy" in text:
        return ("natalizumab_pml",)
    if "treat registry" in text:
        return ("treat_registry",)
    if "pyramid registry" in text:
        return ("pyramid_registry",)
    if "gemini long-term safety" in text or "long-term safety of vedolizumab" in text:
        return ("gemini_lts",)
    if "association between use of thiopurines" in text and "risk of lymphoma" in text:
        return ("lemaitre_2017",)
    if "real-world effectiveness of upadacitinib" in text:
        return ("upadacitinib_real_world",)
    if "fecal microbiota transplantation" in text:
        return ("fmt",)
    if "top-down versus accelerated step-up" in text or "profile" in text:
        return ("profile",)
    if "brodalumab" in text:
        return ("brodalumab",)

    if "risankizumab" in text and "ustekinumab" in text:
        return ("sequence",)
    if "ustekinumab versus adalimumab" in text:
        return ("seavue",)

    if (
        "final randomized u-endure" in text
        or "final u-endure" in text
        or "final results from the randomized u-endure" in text
        or "final phase 3 u-endure" in text
    ):
        return ("u_endure",)
    if "upadacitinib maintenance therapy" in text and "u-endure" in text:
        return ("u_endure",)
    if "u-excel" in text or "u-exceed" in text:
        keys = []
        if "u-excel" in text:
            keys.append("u_excel")
        if "u-exceed" in text:
            keys.append("u_exceed")
        if "u-endure" in text:
            keys.append("u_endure")
        return tuple(keys)
    if "upadacitinib induction and maintenance therapy" in text:
        return ("u_excel", "u_exceed", "u_endure")
    if "celest" in text or "efficacy and safety of upadacitinib in a randomized trial" in text:
        return ("celest",)

    if "vivid-1" in text or "mirikizumab" in text and "phase 3" in text:
        return ("vivid_1",)
    if "serenity" in text or "mirikizumab in a randomized phase 2" in text:
        return ("serenity",)

    if (
        "galaxi-2" in text
        or "galaxi-3" in text
        or "galaxi 2" in text
        or "galaxi 3" in text
    ):
        keys = []
        if "galaxi-2" in text or "galaxi 2" in text:
            keys.append("galaxi_2")
        if "galaxi-3" in text or "galaxi 3" in text:
            keys.append("galaxi_3")
        return tuple(keys)
    if "graviti" in text or "subcutaneous induction and maintenance" in text and "guselkumab" in text:
        return ("graviti",)
    if "galaxi-1" in text or "guselkumab for the treatment of crohn" in text:
        return ("galaxi_1",)

    if "advance" in text or "motivate" in text:
        keys = []
        if "advance" in text:
            keys.append("advance")
        if "motivate" in text:
            keys.append("motivate")
        if "fortify" in text:
            keys.append("fortify")
        return tuple(keys)
    if "fortify" in text:
        return ("fortify",)
    if "risankizumab" in text and "phase 2" in text:
        return ("risankizumab_phase_2",)

    if "five-year efficacy and safety of ustekinumab" in text or "im-uniti long-term" in text:
        return ("im_uniti",)
    if "uniti-1" in text or "uniti-2" in text or "im-uniti" in text:
        keys = []
        if "uniti-1" in text:
            keys.append("uniti_1")
        if "uniti-2" in text:
            keys.append("uniti_2")
        if "im-uniti" in text:
            keys.append("im_uniti")
        return tuple(keys)
    if "ustekinumab as induction and maintenance therapy for crohn" in text:
        return ("uniti_1", "uniti_2", "im_uniti")
    if "ustekinumab induction and maintenance therapy in refractory" in text:
        return ("certifi",)
    if "randomized trial of ustekinumab" in text:
        return ("certifi",)

    if "bergamot" in text or "etrolizumab as induction and maintenance" in text:
        return ("bergamot",)
    if "tofacitinib for induction and maintenance" in text:
        return ("tofacitinib",)
    if "diversity" in text and "filgotinib" in text:
        return ("diversity_a", "diversity_b", "diversity_maintenance")
    if "fitzroy" in text or "clinical remission" in text and "filgotinib" in text:
        return ("fitzroy",)

    if "visible 2" in text or "subcutaneous vedolizumab" in text:
        return ("visible_2",)
    if "effects of vedolizumab in japanese patients" in text:
        return ("watanabe_2020",)
    if "gemini 3" in text or "effects of vedolizumab induction therapy" in text:
        return ("gemini_3",)
    if "gemini 2" in text or "vedolizumab as induction and maintenance" in text:
        return ("gemini_2",)
    if "vedolizumab in crohn's disease in patients from asian countries" in text:
        return ("gemini_2",)

    if "encore" in text or "natalizumab for the treatment of active crohn" in text:
        return ("encore",)
    if "enact-1" in text or "enact-2" in text or "enact 1" in text or "enact 2" in text:
        keys = []
        if "enact-1" in text or "enact 1" in text:
            keys.append("enact_1")
        if "enact-2" in text or "enact 2" in text:
            keys.append("enact_2")
        return tuple(keys)
    if "natalizumab induction and maintenance therapy" in text:
        return ("enact_1", "enact_2")
    if "natalizumab for active crohn" in text:
        return ("ghosh_2003",)

    if "welcome" in text or "secondary failure to infliximab" in text and "certolizumab" in text:
        return ("welcome",)
    if "precise 3" in text or "continuous therapy with certolizumab" in text:
        return ("precise_2",)
    if "precise 2" in text or "maintenance therapy with certolizumab" in text:
        return ("precise_2",)
    if "precise 1" in text or "certolizumab pegol for the treatment" in text:
        return ("precise_1",)

    if "extend" in text or "adalimumab induces and maintains mucosal healing" in text:
        return ("extend",)
    if "gain" in text or "adalimumab induction therapy" in text and "previously treated" in text:
        return ("gain",)
    if "classic ii" in text or "classic-ii" in text or "adalimumab for maintenance treatment" in text:
        return ("classic_2",)
    if "charm" in text or "adalimumab for maintenance of clinical response" in text:
        return ("charm",)
    if "classic i" in text or "classic-i" in text or "human anti-tumor necrosis factor" in text:
        return ("classic_1",)

    if "stop-it" in text or "discontinuation of infliximab therapy" in text:
        return ("stop_it",)
    if "sonic" in text or "infliximab, azathioprine, or combination therapy" in text:
        return ("sonic",)
    if "accent ii" in text or "fistulizing crohn" in text and "maintenance" in text:
        return ("accent_2",)
    if "accent i" in text or "maintenance infliximab for crohn" in text:
        return ("accent_1",)
    if "infliximab for the treatment of fistulas" in text:
        return ("present_1999",)
    if "retreatment with anti-tumor necrosis factor antibody" in text:
        return ("rutgeerts_1999",)
    if "short-term study of chimeric monoclonal antibody" in text:
        return ("targan_1997",)

    raise ValueError(f"Unresolved terminal-list entry: {entry}")


def citation_identity_note(entry: str, key: str, run_id: str) -> str:
    """Return an audit note when a citation resolves despite conflicting details."""

    text = normalize(entry)
    stripped = text.lstrip("*")
    if key == "visible_2" and stripped.startswith(("sands ", "sandborn ", "löwenberg ")):
        return (
            "The title identifies VISIBLE 2, but the response supplies a "
            "conflicting lead author and, in some cases, conflicting pages or year."
        )
    if key == "seavue" and "lancet gastroenterol hepatol" in text:
        return (
            "The title identifies SEAVUE, but the response supplies conflicting "
            "journal and page details."
        )
    if key == "sequence" and "am j gastroenterol" in text:
        return (
            "The title identifies the SEQUENCE primary report, but the response "
            "supplies conflicting journal and page details."
        )
    if key == "vivid_1" and stripped.startswith(("d'haens ", "sandborn ")):
        return (
            "The title identifies VIVID-1, but the response supplies a conflicting "
            "lead author."
        )
    if key == "gain" and run_id in {"gpt-clinician-2", "gpt-patient-3"}:
        return (
            "The listed GAIN citation is identifiable, but its supporting PubMed "
            "link points to a different publication."
        )
    if key == "extend" and run_id == "gpt-researcher-4":
        return (
            "The listed EXTEND citation is identifiable, but its supporting PubMed "
            "link points to an adalimumab prescribing-practices survey."
        )
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
    if path.stem == "claude-researcher-1":
        entries = []
        in_list = False
        for line in lines:
            if line == "## Anti-TNF agents":
                in_list = True
            elif in_list and line == "---":
                break
            elif in_list and line.startswith("- "):
                entries.append(line[2:].strip())
        if not entries:
            raise ValueError(f"No terminal study-list entries in {path.name}")
        return entries

    heading_indexes = []
    for index, line in enumerate(lines):
        lowered = normalize(line)
        heading_like = line.startswith("#") or line.startswith("**")
        if not heading_like:
            continue
        if path.stem.startswith("gemini-"):
            if "references" in lowered or "primary study references" in lowered:
                heading_indexes.append(index)
        elif "primary studies" in lowered:
            heading_indexes.append(index)
    if not heading_indexes:
        raise ValueError(f"No terminal study-list heading in {path.name}")

    block = lines[heading_indexes[-1] + 1 :]
    numbered = [
        match.group(1).strip()
        for line in block
        if (match := re.match(r"^\d+\.\s+(.+)$", line))
    ]
    if numbered:
        return numbered

    bullets = [
        match.group(1).strip()
        for line in block
        if (match := re.match(r"^[*-]\s+(.+)$", line))
    ]
    if bullets and not path.stem.startswith("gemini-"):
        return bullets

    if path.stem.startswith("gemini-"):
        references = [
            line.strip()
            for line in block
            if "doi.org/" in line.lower() and not line.lower().startswith("cited by:")
        ]
        if references:
            return references
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
        "included": ris_study_labels(SOURCE_DIR / "CD012751-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD012751-excluded.ris"),
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
                if note := citation_identity_note(entry, key, run_id):
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
                    "source_file": f"CD012751/{path.name}",
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
    if len(rows) != EXPECTED_RESPONSE_STUDY_ROWS:
        raise ValueError(
            "Response-study row count mismatch; "
            f"expected={EXPECTED_RESPONSE_STUDY_ROWS}, observed={len(rows)}"
        )
    labels_by_run: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["ground_truth_status"] == "included":
            labels_by_run[str(row["run_id"])].extend(
                label.strip()
                for label in str(row["cochrane_study_label"]).split(" || ")
                if label.strip()
            )
    for run_id, labels in labels_by_run.items():
        duplicates = [label for label, count in Counter(labels).items() if count > 1]
        if duplicates:
            raise ValueError(f"Duplicate included labels in {run_id}: {duplicates}")
    return rows, raw_counts


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write a non-empty audit table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def included_labels(row: dict[str, str | int]) -> set[str]:
    """Return the included Cochrane study rows credited by one audit row."""

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
    """Print compact extraction and included-study-row recall checks."""

    included_truth = ris_study_labels(SOURCE_DIR / "CD012751-included.ris")
    by_run: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for row in rows:
        by_run[str(row["run_id"])].append(row)

    assignment_count = sum(
        len(resolve_candidate(entry))
        for path in response_paths()
        for entry in extract_terminal_list(path)
    )
    print(f"Runs: {len(by_run)}")
    print(f"Terminal-list entries: {sum(raw_counts.values())}")
    print(f"Candidate-study assignments before deduplication: {assignment_count}")
    print(f"Response-study rows after within-response deduplication: {len(rows)}")
    for model in MODELS:
        run_ids = [run_id for run_id in by_run if run_id.startswith(f"{model}-")]
        print(
            f"{model}: {sum(raw_counts[run_id] for run_id in run_ids)} entries; "
            f"{sum(len(by_run[run_id]) for run_id in run_ids)} response-study rows"
        )
    print("Included-study-row recall by run:")
    for run_id in sorted(by_run):
        retrieved = set().union(*(included_labels(row) for row in by_run[run_id]))
        print(f"  {run_id}: {len(retrieved)}/{len(included_truth)}")
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the terminal-list-only curated match table for CD012751."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
