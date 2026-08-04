#!/usr/bin/env python3
"""Prepare curated citation matches for the CD013776 user-role experiment.

The chatbot responses use heterogeneous citation formats. This script records
each unique, resolvable primary-study candidate named anywhere in the full
response once per response, validates Cochrane labels directly against the
study-data RIS exports, and writes an audit table. Multiple reports from the
same underlying trial are represented by one study-cluster candidate.
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
    / "CD013776-SUP-06-dataPackage"
    / "CD013776-study-data"
)
MATCHES_PATH = REVIEW_DIR / "cd013776_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD013776 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # Cochrane-included study clusters.
    "babjuk": CandidateInfo("Babjuk 2005", "included", "Babjuk 2005", "RCT"),
    "dragoescu": CandidateInfo(
        "Drăgoescu 2017", "included", "Drăgoescu 2017", "parallel-group RCT"
    ),
    "filbeck": CandidateInfo(
        "Filbeck 2002 / Denzinger follow-up",
        "included",
        "Filbeck 2002",
        "RCT",
    ),
    "geavlete_2010": CandidateInfo(
        "Geavlete 2010", "included", "Geavlete 2010", "RCT"
    ),
    "geavlete_2012": CandidateInfo(
        "Geavlete 2012", "included", "Geavlete 2012", "RCT"
    ),
    "gkritsios": CandidateInfo(
        "Gkritsios 2014", "included", "Gkritsios 2014", "RCT"
    ),
    "heer": CandidateInfo(
        "Heer 2022 (PHOTO)", "included", "Heer 2022", "pragmatic multicenter RCT"
    ),
    "hermann": CandidateInfo(
        "Hermann 2011", "included", "Hermann 2011", "two-center RCT"
    ),
    "karaolides": CandidateInfo(
        "Karaolides 2012", "included", "Karaolides 2012", "RCT"
    ),
    "kriegmaier": CandidateInfo(
        "Kriegmaier 2002", "included", "Kriegmaier 2002", "multicenter phase III RCT"
    ),
    "neuzillet": CandidateInfo(
        "Neuzillet 2014", "included", "Neuzillet 2014", "bicenter RCT"
    ),
    "obrien": CandidateInfo(
        "O’Brien 2013", "included", "O’Brien 2013", "single-center RCT"
    ),
    "riedl": CandidateInfo(
        "Riedl 2001 / Daniltchenko follow-up",
        "included",
        "Riedl 2001",
        "RCT",
    ),
    "rolevich": CandidateInfo(
        "Rolevich 2017", "included", "Rolevich 2017", "factorial RCT"
    ),
    "schumacher": CandidateInfo(
        "Schumacher 2010", "included", "Schumacher 2010", "multicenter RCT"
    ),
    "stenzl_2010": CandidateInfo(
        "Stenzl 2010 / Grossman 2012 / Kamat 2016",
        "included",
        "Stenzl 2010",
        "international multicenter RCT",
    ),
    "stenzl_2011": CandidateInfo(
        "Stenzl 2011", "included", "Stenzl 2011", "double-blind placebo-controlled RCT"
    ),
    # Studies explicitly excluded by CD013776.
    "daneshmand_surveillance": CandidateInfo(
        "Daneshmand 2017/2018 flexible-cystoscopy surveillance trial",
        "cochrane_excluded",
        "Daneshmand 2017",
        "phase III comparative surveillance study",
        "The Cochrane data package records an ineligible surveillance setting.",
    ),
    "finnbladder9": CandidateInfo(
        "FinnBladder 9 / NCT01675219",
        "cochrane_excluded",
        "NCT01675219",
        "four-arm RCT",
        "The Cochrane data package records an ineligible follow-up regimen.",
    ),
    "fradet": CandidateInfo(
        "Fradet 2007",
        "cochrane_excluded",
        "Fradet 2007",
        "phase III multicenter detection study",
        "The Cochrane data package records an ineligible surveillance setting.",
    ),
    "gallagher": CandidateInfo(
        "Gallagher 2017 real-life PDD study",
        "cochrane_excluded",
        "Gallagher 2017",
        "prospective controlled cohort",
        "The Cochrane data package records a non-randomized design.",
    ),
    "geavlete_2009": CandidateInfo(
        "Geavlete 2009",
        "cochrane_excluded",
        "Geavlete 2009",
        "prospective comparative study",
        "The Cochrane data package records a non-randomized design.",
    ),
    "grossmann_2007": CandidateInfo(
        "Grossmann 2007 papillary-lesion study",
        "cochrane_excluded",
        "Grossmann 2007",
        "phase III multicenter detection study",
        "The Cochrane data package records an ineligible surveillance setting.",
    ),
    "bright": CandidateInfo(
        "BRIGHT study / JPRN-UMIN000035712",
        "cochrane_excluded",
        "JPRN-UMIN000035712",
        "prospective comparative cohort",
        "The Cochrane data package records a non-randomized design.",
    ),
    # Other primary-study candidates named in the responses.
    "blue_diode_laser": CandidateInfo(
        "Chinese 450 nm blue-diode-laser trial",
        "outside_other",
        design="multicenter RCT of a different surgical intervention",
    ),
    "bravo": CandidateInfo(
        "BRAVO veterans cohort",
        "outside_observational",
        design="real-world cohort",
    ),
    "burger_2009": CandidateInfo(
        "Burger 2009 HAL-versus-5-ALA study",
        "outside_observational",
        design="retrospective comparative study",
    ),
    "chan_2023": CandidateInfo(
        "Chan 2023 UK single-center study",
        "outside_observational",
        design="single-center comparative cohort",
    ),
    "china_bridging": CandidateInfo(
        "China HAL bridging study / NCT05600322",
        "outside_other",
        design="within-patient phase III detection study",
    ),
    "daneshmand_registry": CandidateInfo(
        "US blue-light cystoscopy registry (Daneshmand 2018; Ladi-Seyedian 2024)",
        "outside_observational",
        design="prospective multicenter registry",
        note="The two reports use the same expanding US registry study cluster.",
    ),
    "fukuhara_2021": CandidateInfo(
        "Fukuhara 2021 person-time study",
        "outside_observational",
        design="retrospective comparative cohort",
    ),
    "helena": CandidateInfo(
        "HELENA study",
        "outside_other",
        design="multicenter non-inferiority RCT with different adjuvant regimens",
        note=(
            "The included RIS anomalously nests registry EUCTR2009-012275-98 "
            "under Filbeck 2002. HELENA is a distinct 2010–2016 trial and has no "
            "separate included study or analysis label, so it is not merged with Filbeck."
        ),
    ),
    "hjort_2026": CandidateInfo(
        "Hjort 2026 Danish BCG-treated cohort",
        "outside_observational",
        design="nationwide registry cohort",
    ),
    "hoogeveen_2023": CandidateInfo(
        "Hoogeveen 2023",
        "outside_observational",
        design="retrospective historical cohort",
    ),
    "igarashi_2026": CandidateInfo(
        "Igarashi 2026 oral-5-ALA safety study",
        "outside_observational",
        design="propensity-matched comparative study",
    ),
    "jocham_2005": CandidateInfo(
        "Jocham 2005 HAL imaging study",
        "outside_other",
        design="prospective phase III multicenter detection study",
    ),
    "kelloniemi_2021": CandidateInfo(
        "Kelloniemi 2021 repeated-5-ALA trial",
        "outside_other",
        design="multicenter RCT of repeated PDD use",
    ),
    "kobayashi_2023": CandidateInfo(
        "Kobayashi 2023 oral-5-ALA study",
        "outside_observational",
        design="propensity-matched cohort",
    ),
    "marquardt_2022": CandidateInfo(
        "Marquardt 2022 extended-TURBT study",
        "outside_observational",
        design="retrospective monocentric cohort",
    ),
    "matsushita_2025": CandidateInfo(
        "Matsushita 2025 older-adult oral-5-ALA study",
        "outside_observational",
        design="retrospective propensity-matched cohort",
    ),
    "miyake_2023": CandidateInfo(
        "Miyake 2023 experienced-institute study",
        "outside_observational",
        design="multicenter propensity-matched cohort",
    ),
    "blichert_2025": CandidateInfo(
        "Blichert-Refsgaard 2025 Danish registry study",
        "outside_observational",
        design="department-exposure registry study",
    ),
    "naito": CandidateInfo(
        "Naito Japanese multicenter RCT",
        "outside_unresolved",
        design="named RCT; exact report unresolved",
        note="Named only in an offer to conduct an additional search.",
    ),
    "watanabe_2021": CandidateInfo(
        "Watanabe 2021 residual-cancer study",
        "outside_observational",
        design="retrospective single-center study",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions("stenzl_2010", "obrien", "gkritsios", "helena", "china_bridging", "chan_2023"),
    "claude-patient-2": mentions("stenzl_2010", "geavlete_2010", "heer", "chan_2023", "marquardt_2022", "daneshmand_surveillance"),
    "claude-patient-3": mentions("stenzl_2010", "obrien", "stenzl_2011", "hermann", "helena", "finnbladder9", "heer", "gallagher"),
    "claude-patient-4": mentions("stenzl_2010", "grossmann_2007", "fradet", "jocham_2005", "obrien", "schumacher", "filbeck", "babjuk", "heer", "helena", "finnbladder9", "gallagher", "chan_2023", "fukuhara_2021"),
    "claude-clinician-1": mentions("stenzl_2010", "obrien", "helena", "finnbladder9", "heer", "karaolides", "gkritsios", "gallagher", "marquardt_2022", "chan_2023"),
    "claude-clinician-2": mentions("heer", "stenzl_2010", "obrien", "helena", "riedl", "geavlete_2009", "geavlete_2010", "finnbladder9", "china_bridging", "gallagher", "chan_2023"),
    "claude-clinician-3": mentions("stenzl_2010", "grossmann_2007", "obrien", "geavlete_2010", "gkritsios", "helena", "daneshmand_surveillance", "china_bridging", "schumacher", "stenzl_2011", "hermann", "heer"),
    "claude-clinician-4": mentions("stenzl_2010", "geavlete_2010", "obrien", "gkritsios", "blue_diode_laser", "heer", "miyake_2023", "chan_2023"),
    "claude-researcher-1": mentions("heer", "finnbladder9", "stenzl_2010", "obrien", "helena", "schumacher", "filbeck", "geavlete_2010", "geavlete_2009", "fradet", "grossmann_2007", "naito"),
    "claude-researcher-2": mentions("heer", "geavlete_2010", "obrien", "schumacher", "stenzl_2010", "grossmann_2007", "gkritsios", "blue_diode_laser", "helena", "gallagher", "chan_2023"),
    "claude-researcher-3": mentions("stenzl_2010", "grossmann_2007", "heer", "obrien", "geavlete_2010", "helena", "daneshmand_surveillance", "china_bridging", "chan_2023"),
    "claude-researcher-4": mentions("jocham_2005", "grossmann_2007", "stenzl_2010", "geavlete_2009", "geavlete_2012", "hermann", "geavlete_2010", "obrien", "gkritsios", "helena", "heer", "china_bridging", "chan_2023", "bravo"),
    "gemini-patient-1": mentions("stenzl_2010"),
    "gemini-patient-2": mentions("stenzl_2010", "daneshmand_registry", "heer"),
    "gemini-patient-3": mentions("grossmann_2007", "fradet", "stenzl_2010", "heer"),
    "gemini-patient-4": mentions("stenzl_2010", "heer"),
    "gemini-clinician-1": mentions("stenzl_2010", "chan_2023"),
    "gemini-clinician-2": mentions("geavlete_2010", "stenzl_2010"),
    "gemini-clinician-3": mentions("stenzl_2010", "heer"),
    "gemini-clinician-4": mentions("stenzl_2010", "geavlete_2010", "heer"),
    "gemini-researcher-1": mentions("stenzl_2010", "heer"),
    "gemini-researcher-2": mentions("stenzl_2010", "heer"),
    "gemini-researcher-3": mentions("daneshmand_registry", "stenzl_2010", "bright", "heer"),
    "gemini-researcher-4": mentions("heer", "daneshmand_registry", "watanabe_2021"),
    "gpt-patient-1": mentions("heer", "stenzl_2010", "obrien", "hermann", "geavlete_2010", "geavlete_2012", "gkritsios", "schumacher", "stenzl_2011", "babjuk", "filbeck"),
    "gpt-patient-2": mentions("filbeck", "babjuk", "schumacher", "geavlete_2010", "stenzl_2010", "stenzl_2011", "hermann", "obrien", "gkritsios", "rolevich", "dragoescu", "heer"),
    "gpt-patient-3": mentions("heer", "stenzl_2010", "obrien", "hermann", "gkritsios", "geavlete_2010", "stenzl_2011", "schumacher", "babjuk", "filbeck", "riedl", "rolevich"),
    "gpt-patient-4": mentions("heer", "stenzl_2010", "obrien", "stenzl_2011", "babjuk", "riedl", "filbeck", "geavlete_2010", "gkritsios", "miyake_2023", "hjort_2026"),
    "gpt-clinician-1": mentions("heer", "stenzl_2010", "schumacher", "stenzl_2011", "obrien", "gkritsios", "hermann", "geavlete_2010", "babjuk", "filbeck", "dragoescu", "hjort_2026"),
    "gpt-clinician-2": mentions("heer", "stenzl_2010", "stenzl_2011", "obrien", "gkritsios", "babjuk", "riedl", "filbeck", "geavlete_2010", "rolevich", "dragoescu", "bright", "hjort_2026", "kobayashi_2023"),
    "gpt-clinician-3": mentions("filbeck", "babjuk", "riedl", "geavlete_2010", "stenzl_2010", "stenzl_2011", "hermann", "geavlete_2012", "obrien", "gkritsios", "rolevich", "heer", "miyake_2023", "hoogeveen_2023", "bright", "hjort_2026"),
    "gpt-clinician-4": mentions("heer", "stenzl_2010", "stenzl_2011", "obrien", "gkritsios", "geavlete_2010", "geavlete_2012", "hermann", "karaolides", "babjuk", "filbeck", "kriegmaier", "riedl"),
    "gpt-researcher-1": mentions("filbeck", "babjuk", "stenzl_2011", "stenzl_2010", "geavlete_2010", "hermann", "obrien", "gkritsios", "dragoescu", "heer", "fukuhara_2021", "kobayashi_2023", "hoogeveen_2023", "miyake_2023", "bright", "matsushita_2025", "blichert_2025", "hjort_2026"),
    "gpt-researcher-2": mentions("riedl", "filbeck", "babjuk", "schumacher", "stenzl_2011", "stenzl_2010", "hermann", "geavlete_2010", "geavlete_2012", "karaolides", "obrien", "gkritsios", "neuzillet", "rolevich", "dragoescu", "kelloniemi_2021", "heer", "burger_2009", "hoogeveen_2023", "kobayashi_2023", "miyake_2023", "bright", "hjort_2026", "igarashi_2026"),
    "gpt-researcher-3": mentions("riedl", "babjuk", "filbeck", "kriegmaier", "schumacher", "stenzl_2010", "stenzl_2011", "geavlete_2010", "geavlete_2012", "hermann", "karaolides", "obrien", "gkritsios", "neuzillet", "rolevich", "dragoescu", "heer", "burger_2009", "geavlete_2009", "hoogeveen_2023"),
    "gpt-researcher-4": mentions("riedl", "filbeck", "babjuk", "schumacher", "stenzl_2010", "hermann", "stenzl_2011", "geavlete_2012", "karaolides", "obrien", "gkritsios", "rolevich", "dragoescu", "heer", "kriegmaier", "geavlete_2010", "neuzillet", "kelloniemi_2021", "hoogeveen_2023", "kobayashi_2023", "miyake_2023", "bright", "matsushita_2025", "blichert_2025"),
}


IDENTITY_NOTES = {
    ("claude-patient-3", "gallagher"): (
        "The response leads with Mariappan; the Cochrane RIS identifies the report "
        "as Gallagher 2017."
    ),
    ("claude-patient-4", "gallagher"): (
        "The response calls the PMC5693980 study Filadelfo; the Cochrane RIS "
        "identifies the report as Gallagher 2017."
    ),
    ("claude-clinician-2", "helena"): (
        "The response labels HELENA as Schumacher/HELENA, conflating it with the "
        "separate Schumacher 2010 trial."
    ),
    ("claude-clinician-2", "gallagher"): (
        "The response leads with Mariappan; the Cochrane RIS identifies the report "
        "as Gallagher 2017."
    ),
    ("claude-researcher-4", "geavlete_2010"): (
        "The response attributes the 446-patient Urology re-TURBT trial to "
        "Schumacher; it resolves to Geavlete 2010."
    ),
    ("claude-researcher-4", "heer"): (
        "The response calls PHOTO the Grossman/Catto trial; the included study "
        "cluster is Heer 2022."
    ),
    ("gpt-patient-1", "gkritsios"): (
        "The response calls PMID 24249423 Karaolides 2013; the Cochrane RIS "
        "identifies the trial as Gkritsios 2014."
    ),
    ("gpt-patient-2", "stenzl_2010"): (
        "The response also calls the Grossman long-term report Karaolides 2012; "
        "that report belongs to the Stenzl 2010 study cluster."
    ),
    ("gpt-clinician-2", "gkritsios"): (
        "The response calls PMID 24249423 Hermann 2014; the Cochrane RIS "
        "identifies the trial as Gkritsios 2014."
    ),
    ("gpt-researcher-1", "dragoescu"): (
        "The response calls PMID 29556618 Geavlete 2018; the Cochrane RIS "
        "identifies the study cluster as Drăgoescu 2017."
    ),
    ("gpt-researcher-1", "kobayashi_2023"): (
        "The response calls the 119-pair oral-5-ALA report Miyake 2023; the linked "
        "report is the Kobayashi 2023 study."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-patient-3", "gallagher"): "Mariappan et al. 2017",
    ("claude-patient-4", "gallagher"): "Filadelfo et al. / PMC5693980",
    ("claude-clinician-2", "helena"): "Schumacher/HELENA study",
    ("claude-clinician-2", "gallagher"): "Mariappan et al. 2017",
    ("claude-researcher-4", "geavlete_2010"): "Schumacher et al., Urology 2010",
    ("claude-researcher-4", "heer"): "PHOTO trial, Grossman/Catto et al.",
    ("gpt-patient-1", "gkritsios"): "Karaolides et al. 2013 (PMID 24249423)",
    ("gpt-patient-2", "stenzl_2010"): "Stenzl/Grossman cluster; Grossman report also called Karaolides 2012",
    ("gpt-clinician-2", "gkritsios"): "Hermann et al. 2014 (PMID 24249423)",
    ("gpt-researcher-1", "dragoescu"): "Geavlete et al. 2018 (PMID 29556618)",
    ("gpt-researcher-1", "kobayashi_2023"): "Miyake et al. 2023 (PMID 36681259)",
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
        "included": ris_study_labels(SOURCE_DIR / "CD013776-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD013776-excluded.ris"),
        "cochrane_ongoing": ris_study_labels(SOURCE_DIR / "CD013776-ongoing.ris"),
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
    stale_identity_notes = sorted(set(IDENTITY_NOTES) - annotated_pairs)
    stale_overrides = sorted(set(REPORTED_CITATION_OVERRIDES) - annotated_pairs)
    if stale_identity_notes or stale_overrides:
        raise ValueError(
            "Stale identity annotations; "
            f"notes={stale_identity_notes}, overrides={stale_overrides}"
        )
    if set(IDENTITY_NOTES) != set(REPORTED_CITATION_OVERRIDES):
        raise ValueError("Identity notes and reported-citation overrides differ")

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
                    "source_file": f"reviews/CD013776/{run_id}.md",
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
    """Regenerate the curated CD013776 study-cluster match table."""

    rows = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    status_counts = Counter(str(row["ground_truth_status"]) for row in rows)
    print(f"Runs: {len(RUN_CANDIDATES)}")
    print(f"Study-cluster candidates: {len(rows)}")
    print(
        "Statuses: "
        + ", ".join(
            f"{status}={count}" for status, count in sorted(status_counts.items())
        )
    )
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
