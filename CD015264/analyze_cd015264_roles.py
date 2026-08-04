#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD015264 role experiment.

Each complete chatbot response is curated once at the study-cluster level.
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
    / "Cochrane_reviews"
    / "source_reviews"
    / "2026_issue_6"
    / "CD015264-SUP-08-dataPackage"
    / "CD015264-study-data"
)
MATCHES_PATH = REVIEW_DIR / "cd015264_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD015264 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 16 Cochrane-included study clusters, including clusters never retrieved.
    "areekul": CandidateInfo("Areekul 1979", "included", "Areekul 1979", "RCT"),
    "benjamin": CandidateInfo("Benjamin 1952", "included", "Benjamin 1952", "RCT"),
    "chinnock": CandidateInfo(
        "Chinnock 1952", "included", "Chinnock 1952", "quasi-randomized trial"
    ),
    "craigmile": CandidateInfo(
        "Craigmile 1956", "included", "Craigmile 1956", "quasi-randomized trial"
    ),
    "deshmukh": CandidateInfo(
        "Deshmukh 2010", "included", "Deshmukh 2010", "cluster RCT"
    ),
    "fukui": CandidateInfo(
        "Fukui 1959", "included", "Fukui 1959", "quasi-randomized trial"
    ),
    "gutierrez_diaz": CandidateInfo(
        "Gutiérrez-Diaz 1959",
        "included",
        "Gutiérrez-Diaz 1959",
        "quasi-randomized trial",
    ),
    "kudo": CandidateInfo("Kudo 1962", "included", "Kudo 1962", "RCT"),
    "murakami": CandidateInfo("Murakami 1962", "included", "Murakami 1962", "RCT"),
    "scaglione": CandidateInfo(
        "Scaglione 1955", "included", "Scaglione 1955", "quasi-randomized trial"
    ),
    "scrimshaw_1953": CandidateInfo(
        "Scrimshaw 1953 / Aguirre 1955",
        "included",
        "Scrimshaw 1953",
        "controlled school supplementation study",
        "The growth and hematology reports are grouped under one Cochrane study label.",
    ),
    "scrimshaw_1959": CandidateInfo(
        "Scrimshaw 1959", "included", "Scrimshaw 1959", "controlled trial"
    ),
    "shimazono": CandidateInfo(
        "Shimazono 1963", "included", "Shimazono 1963", "controlled trial"
    ),
    "strand": CandidateInfo(
        "Strand 2020 (BeLive; NCT02272842)",
        "included",
        "Strand 2020",
        "RCT",
        "The protocol, primary report, and later outcome reports are one trial cluster.",
    ),
    "taneja": CandidateInfo(
        "Taneja 2013 (North India; NCT00717730)",
        "included",
        "Taneja 2013",
        "factorial RCT",
        "All short- and long-term outcome reports are one trial cluster.",
    ),
    "yajnik": CandidateInfo(
        "Yajnik 2021 nutrient-bar trial",
        "included",
        "Yajnik 2021",
        "RCT",
    ),

    # Study clusters explicitly excluded by CD015264.
    "bjorke_monsen": CandidateInfo(
        "Bjørke-Monsen/Torsvik infant B12 studies",
        "cochrane_excluded",
        "Bjørke-Monsen 2011",
        "intramuscular randomized trials",
        "The excluded RIS groups the 2008 and 2011 reports and related registry records under this label; responses also cite the later Torsvik report.",
    ),
    "finberg": CandidateInfo(
        "Finberg 1952", "cochrane_excluded", "Finberg 1952", "quasi-randomized trial"
    ),
    "haiden": CandidateInfo(
        "Haiden 2006 anemia-of-prematurity trial",
        "cochrane_excluded",
        "Haiden 2006",
        "RCT",
    ),
    "hess": CandidateInfo(
        "Hess 2019 Lao micronutrient-powder trial",
        "cochrane_excluded",
        "Hess 2019",
        "RCT",
        "Responses cite Hinnouho 2022, a later report from this trial program.",
    ),
    "larcomb": CandidateInfo(
        "Larcomb 1954", "cochrane_excluded", "Larcomb 1954", "RCT"
    ),
    "torsvik_2015": CandidateInfo(
        "Torsvik 2015 low-birth-weight infant trial",
        "cochrane_excluded",
        "Torsvik 2015",
        "RCT",
    ),
    "worthington_white": CandidateInfo(
        "Worthington-White 1994 preterm-infant trial",
        "cochrane_excluded",
        "Worthington-White 1994",
        "factorial RCT",
    ),

    # Study clusters awaiting classification in CD015264.
    "chandelia": CandidateInfo(
        "Chandelia 2012 anemia trial",
        "cochrane_awaiting",
        "Chandelia 2012",
        "RCT",
    ),
    "mackay": CandidateInfo(
        "Mackay 1956 protein-deficient-child trial",
        "cochrane_awaiting",
        "Mackay 1956",
        "quasi-randomized trial",
    ),

    # Other identifiable primary-study candidates named in the responses.
    "bacopa": CandidateInfo(
        "Indian Bacopa-plus-micronutrient schoolchild trial",
        "outside_other",
        design="multi-ingredient RCT",
    ),
    "crump": CandidateInfo(
        "Crump and Tully 1955 growth-failure study",
        "outside_other",
        design="controlled study",
    ),
    "downing": CandidateInfo(
        "Downing 1950 premature-infant study",
        "outside_other",
        design="controlled study",
    ),
    "guatemala": CandidateInfo(
        "Allen 2007 Guatemalan infant fortification trial",
        "outside_other",
        design="randomized feeding trial reported as a conference abstract",
    ),
    "hendren": CandidateInfo(
        "Hendren 2016 methyl-B12 autism trial",
        "outside_other",
        design="subcutaneous-injection RCT",
    ),
    "india_anemia_routes": CandidateInfo(
        "Indian Pediatrics parenteral-versus-oral B12 anemia trial",
        "outside_other",
        design="active-comparator RCT",
    ),
    "kenya_feeding": CandidateInfo(
        "Kenya Child Nutrition Project feeding trial",
        "outside_other",
        design="cluster-randomized feeding trial",
        note="Siekmann, Neumann, and Hulett reports are grouped as one trial program.",
    ),
    "kvestad_observational": CandidateInfo(
        "Kvestad 2017 Nepalese B12-status cohort",
        "outside_observational",
        design="longitudinal cohort",
    ),
    "louwman": CandidateInfo(
        "Louwman/van Dusseldorp preschool B-vitamin trial",
        "outside_other",
        design="multi-vitamin RCT",
    ),
    "maternal_india": CandidateInfo(
        "Srinivasan 2016 maternal B12 trial",
        "outside_other",
        design="maternal-supplementation RCT",
    ),
    "maternal_nepal": CandidateInfo(
        "Chandyo maternal B12 supplementation trial",
        "outside_other",
        design="maternal-supplementation RCT",
    ),
    "matcobind": CandidateInfo(
        "MATCOBIND maternal B12 trial",
        "outside_other",
        design="maternal-supplementation RCT protocol",
    ),
    "montoye": CandidateInfo(
        "Montoye 1955 young-boy growth and fitness study",
        "outside_other",
        design="controlled study",
    ),
    "nct06100146": CandidateInfo(
        "NCT06100146 adolescent fortified-flour trial",
        "outside_other",
        design="ongoing RCT",
    ),
    "nigeria_nephrotic": CandidateInfo(
        "Nigerian nephrotic-syndrome B-vitamin trial",
        "outside_other",
        design="combination-supplement RCT",
    ),
    "rascoff": CandidateInfo(
        "Rascoff 1951 premature-infant study",
        "outside_other",
        design="comparative study",
    ),
    "sezer": CandidateInfo(
        "Sezer 2018 oral-versus-parenteral B12 trial",
        "outside_other",
        design="active-comparator trial",
    ),
    "sheng": CandidateInfo(
        "Sheng 2019 complementary-feeding trial",
        "outside_other",
        design="cluster-randomized feeding trial",
    ),
    "spies": CandidateInfo(
        "Spies 1952 nutritive-failure study",
        "outside_other",
        design="controlled study",
    ),
    "sublingual_im": CandidateInfo(
        "Sublingual-versus-intramuscular pediatric B12 trial",
        "outside_other",
        design="active-comparator trial",
    ),
    "uganda_hiv": CandidateInfo(
        "Ndeezi 2011 Ugandan HIV micronutrient trial",
        "outside_other",
        design="multi-micronutrient RCT",
    ),
    "wetzel": CandidateInfo(
        "Wetzel 1949/1952 growth-failure studies",
        "outside_other",
        design="controlled supplementation studies",
    ),
    "wilde": CandidateInfo(
        "Wilde 1952 Aleut schoolchild growth study",
        "outside_other",
        design="controlled study",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions("taneja", "strand", "nigeria_nephrotic", "india_anemia_routes", "haiden"),
    "claude-patient-2": mentions("strand", "taneja", "louwman", "nigeria_nephrotic", "sheng", "bacopa", "nct06100146"),
    "claude-patient-3": mentions("taneja", "strand", "bjorke_monsen", "torsvik_2015", "nigeria_nephrotic", "sublingual_im"),
    "claude-patient-4": mentions("strand", "taneja", "nigeria_nephrotic"),
    "claude-clinician-1": mentions("taneja", "strand", "bjorke_monsen", "torsvik_2015", "hess", "uganda_hiv", "sheng"),
    "claude-clinician-2": mentions("strand", "taneja", "bjorke_monsen", "torsvik_2015", "nigeria_nephrotic", "kenya_feeding"),
    "claude-clinician-3": mentions("strand", "taneja", "torsvik_2015", "nigeria_nephrotic"),
    "claude-clinician-4": mentions("taneja", "strand", "bjorke_monsen", "torsvik_2015", "nigeria_nephrotic", "sheng"),
    "claude-researcher-1": mentions("taneja", "strand", "bjorke_monsen", "torsvik_2015", "nigeria_nephrotic"),
    "claude-researcher-2": mentions("strand", "maternal_nepal", "bjorke_monsen", "taneja", "sezer", "chandelia", "sublingual_im", "nigeria_nephrotic", "kenya_feeding", "matcobind"),
    "claude-researcher-3": mentions("taneja", "strand", "maternal_nepal", "maternal_india", "yajnik", "nigeria_nephrotic", "nct06100146"),
    "claude-researcher-4": mentions("strand", "taneja", "bjorke_monsen", "torsvik_2015", "nigeria_nephrotic", "uganda_hiv"),
    "gemini-patient-1": mentions("taneja", "strand", "hendren"),
    "gemini-patient-2": mentions("taneja", "sezer", "hendren", "strand"),
    "gemini-patient-3": mentions("taneja", "strand"),
    "gemini-patient-4": mentions("strand", "taneja", "hendren"),
    "gemini-clinician-1": mentions("taneja", "strand"),
    "gemini-clinician-2": mentions("taneja", "strand", "hendren"),
    "gemini-clinician-3": mentions("strand", "taneja", "torsvik_2015", "maternal_india"),
    "gemini-clinician-4": mentions("taneja", "strand", "kvestad_observational"),
    "gemini-researcher-1": mentions("taneja", "strand"),
    "gemini-researcher-2": mentions("strand", "taneja", "sezer"),
    "gemini-researcher-3": mentions("taneja", "strand"),
    "gemini-researcher-4": mentions("taneja", "strand", "hendren"),
    "gpt-patient-1": mentions("strand", "taneja", "rascoff", "chinnock", "wetzel", "larcomb", "montoye"),
    "gpt-patient-2": mentions("taneja", "strand", "guatemala", "hess", "uganda_hiv", "bjorke_monsen", "worthington_white"),
    "gpt-patient-3": mentions("taneja", "strand", "larcomb", "mackay", "scrimshaw_1953"),
    "gpt-patient-4": mentions("strand", "taneja"),
    "gpt-clinician-1": mentions("taneja", "strand", "bjorke_monsen", "torsvik_2015"),
    "gpt-clinician-2": mentions("taneja", "strand", "bjorke_monsen", "worthington_white"),
    "gpt-clinician-3": mentions("strand", "taneja", "guatemala", "bjorke_monsen"),
    "gpt-clinician-4": mentions("taneja", "strand", "guatemala"),
    "gpt-researcher-1": mentions("taneja", "strand", "larcomb", "rascoff", "chinnock", "wetzel", "spies", "montoye", "crump", "mackay", "scrimshaw_1953", "worthington_white", "bjorke_monsen"),
    "gpt-researcher-2": mentions("taneja", "strand", "guatemala", "bjorke_monsen", "worthington_white"),
    "gpt-researcher-3": mentions("taneja", "strand", "guatemala", "scrimshaw_1953", "larcomb", "chinnock", "mackay", "rascoff", "wetzel", "spies", "montoye"),
    "gpt-researcher-4": mentions("taneja", "strand", "guatemala", "wetzel", "downing", "rascoff", "chinnock", "finberg", "spies", "wilde", "larcomb", "crump", "montoye", "scrimshaw_1953", "mackay", "shimazono", "bjorke_monsen", "worthington_white"),
}


IDENTITY_NOTES = {
    ("claude-patient-4", "strand"): (
        "The response attributes the 2020 PLOS Medicine primary report to Kvestad; "
        "the included RIS identifies Strand as first author"
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-patient-4", "strand"): "Kvestad et al. 2020 PLOS Medicine",
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
        "included": ris_study_labels(SOURCE_DIR / "CD015264-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD015264-excluded.ris"),
        "cochrane_ongoing": ris_study_labels(SOURCE_DIR / "CD015264-ongoing.ris"),
        "cochrane_awaiting": ris_study_labels(SOURCE_DIR / "CD015264-awaiting.ris"),
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
                    "source_file": f"retrieval_bias/CD015264/{run_id}.md",
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
    """Regenerate the curated CD015264 study-cluster match table."""

    rows = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    status_counts = Counter(str(row["ground_truth_status"]) for row in rows)
    retrieved_included = {
        str(row["cochrane_study_label"])
        for row in rows
        if row["ground_truth_status"] == "included"
    }
    all_included = ris_study_labels(SOURCE_DIR / "CD015264-included.ris")
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
