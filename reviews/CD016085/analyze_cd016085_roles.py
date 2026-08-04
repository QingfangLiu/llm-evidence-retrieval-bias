#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD016085 role experiment.

Each complete chatbot response is curated once at the study-cluster level.
Cochrane labels are validated against the included, excluded, awaiting, and
ongoing RIS exports supplied with the review data package.
"""

from __future__ import annotations

import csv
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_ZIP = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_7"
    / "CD016085-SUP-08-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd016085_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
RIS_MEMBERS = {
    "included": "CD016085-study-data/CD016085-included.ris",
    "cochrane_excluded": "CD016085-study-data/CD016085-excluded.ris",
    "cochrane_awaiting": "CD016085-study-data/CD016085-awaiting.ris",
    "cochrane_ongoing": "CD016085-study-data/CD016085-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD016085 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All nine Cochrane-included study clusters.
    "avidzba": CandidateInfo(
        "Avidzba 2024",
        "included",
        "Avidzba 2024",
        "single-center randomized trial",
    ),
    "bp_target": CandidateInfo(
        "BP-TARGET",
        "included",
        "BP-TARGET",
        "multicenter RCT",
    ),
    "clever": CandidateInfo(
        "CLEVER",
        "included",
        "CLEVER",
        "single-center RCT",
    ),
    "detect": CandidateInfo(
        "DETECT",
        "included",
        "DETECT",
        "single-center feasibility RCT",
        "The cited publication also contains a meta-analysis; only its original "
        "randomized DETECT component is treated as the primary study.",
    ),
    "enchanted": CandidateInfo(
        "ENCHANTED",
        "included",
        "ENCHANTED",
        "multicenter phase III RCT",
    ),
    "enchanted2_mt": CandidateInfo(
        "ENCHANTED2/MT",
        "included",
        "ENCHANTED2/MT",
        "multicenter phase III RCT",
    ),
    "identify": CandidateInfo(
        "IDENTIFY",
        "included",
        "IDENTIFY",
        "multicenter RCT",
    ),
    "optimal_bp": CandidateInfo(
        "OPTIMAL-BP",
        "included",
        "OPTIMAL-BP",
        "multicenter RCT",
        "The 2026 one-year report is grouped with the original OPTIMAL-BP trial.",
    ),
    "best_ii": CandidateInfo(
        "BEST-II",
        "included",
        "The BEST-II",
        "multicenter phase II RCT",
    ),

    # Study clusters explicitly excluded or awaiting classification in CD016085.
    "determine": CandidateInfo(
        "DETERMINE",
        "cochrane_excluded",
        "DETERMINE",
        "randomized-trial protocol",
    ),
    "individuate": CandidateInfo(
        "INDIVIDUATE",
        "cochrane_excluded",
        "INDIVIDUATE",
        "exploratory RCT",
    ),
    "the_best": CandidateInfo(
        "BEST observational cohort",
        "cochrane_excluded",
        "THE BEST",
        "prospective multicenter cohort",
    ),
    "chase_mt": CandidateInfo(
        "CHASE-MT",
        "cochrane_awaiting",
        "CHASE-MT",
        "registered trial",
    ),
    "crisis_i": CandidateInfo(
        "CRISIS I",
        "cochrane_awaiting",
        "CRISIS I",
        "registered trial",
    ),
    "sharma_2018": CandidateInfo(
        "Sharma 2018",
        "cochrane_awaiting",
        "Sharma 2018",
        "single-center randomized trial",
    ),

    # Trials still ongoing in the source review package.
    "enchanted3_mt": CandidateInfo(
        "ENCHANTED3/MT",
        "cochrane_ongoing",
        "ENCHANTED3/MT",
        "adaptive-platform randomized trial",
    ),
    "hope": CandidateInfo(
        "HOPE",
        "cochrane_ongoing",
        "HOPE STUDY",
        "multicenter RCT",
        "The Cochrane package classifies HOPE as ongoing; several responses cite "
        "its June 2026 primary-results publication.",
    ),

    # Other identifiable primary-study candidates named in the responses.
    "intense": CandidateInfo(
        "INTENSE",
        "outside_other",
        design="registered ongoing multicenter RCT",
    ),
    "interact4": CandidateInfo(
        "INTERACT4",
        "outside_other",
        design="prehospital randomized trial",
        note=(
            "The response explicitly excludes this pre-reperfusion trial from "
            "its final list but still identifies it by name."
        ),
    ),
    "matusevicius_2020": CandidateInfo(
        "Matusevicius 2020 BP-after-EVT study",
        "outside_other",
        design="multicenter registry cohort",
    ),
    "mistry_2017": CandidateInfo(
        "Mistry 2017 post-thrombectomy BP study",
        "outside_other",
        design="retrospective multicenter cohort",
    ),
    "stepanchenko_2026": CandidateInfo(
        "Stepanchenko 2026 thrombolysis BP trial",
        "outside_other",
        design="single-center randomized conference report",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions(
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "identify",
    ),
    "claude-patient-2": mentions(
        "chase_mt",
        "detect",
        "bp_target",
        "optimal_bp",
        "enchanted2_mt",
        "best_ii",
        "identify",
        "individuate",
        "determine",
        "enchanted",
    ),
    "claude-patient-3": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "bp_target",
        "identify",
        "best_ii",
        "enchanted3_mt",
        "enchanted",
    ),
    "claude-patient-4": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "identify",
    ),
    "claude-clinician-1": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "detect",
        "crisis_i",
        "intense",
        "enchanted3_mt",
    ),
    "claude-clinician-2": mentions(
        "hope",
        "bp_target",
        "optimal_bp",
        "enchanted2_mt",
        "best_ii",
        "detect",
        "intense",
    ),
    "claude-clinician-3": mentions(
        "bp_target",
        "optimal_bp",
        "best_ii",
        "enchanted2_mt",
        "detect",
        "intense",
    ),
    "claude-clinician-4": mentions(
        "bp_target",
        "best_ii",
        "enchanted2_mt",
        "optimal_bp",
        "clever",
        "detect",
        "crisis_i",
        "hope",
    ),
    "claude-researcher-1": mentions(
        "enchanted",
        "bp_target",
        "optimal_bp",
        "enchanted2_mt",
        "best_ii",
    ),
    "claude-researcher-2": mentions(
        "bp_target",
        "optimal_bp",
        "enchanted2_mt",
        "best_ii",
        "enchanted",
    ),
    "claude-researcher-3": mentions(
        "enchanted",
        "bp_target",
        "optimal_bp",
        "enchanted2_mt",
        "sharma_2018",
        "mistry_2017",
        "interact4",
        "the_best",
        "matusevicius_2020",
    ),
    "claude-researcher-4": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "identify",
        "detect",
        "crisis_i",
        "clever",
        "hope",
    ),
    "gemini-patient-1": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "bp_target",
    ),
    "gemini-patient-2": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
    ),
    "gemini-patient-3": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
    ),
    "gemini-patient-4": mentions(
        "enchanted",
        "enchanted2_mt",
        "optimal_bp",
        "bp_target",
        "best_ii",
    ),
    "gemini-clinician-1": mentions(
        "bp_target",
        "best_ii",
        "optimal_bp",
        "enchanted2_mt",
    ),
    "gemini-clinician-2": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "bp_target",
        "best_ii",
    ),
    "gemini-clinician-3": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "bp_target",
    ),
    "gemini-clinician-4": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "bp_target",
    ),
    "gemini-researcher-1": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "bp_target",
    ),
    "gemini-researcher-2": mentions(
        "optimal_bp",
        "enchanted2_mt",
        "best_ii",
    ),
    "gemini-researcher-3": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
    ),
    "gemini-researcher-4": mentions(
        "enchanted",
        "optimal_bp",
        "enchanted2_mt",
        "best_ii",
    ),
    "gpt-patient-1": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "hope",
        "enchanted",
        "bp_target",
        "best_ii",
        "detect",
        "identify",
    ),
    "gpt-patient-2": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "best_ii",
        "optimal_bp",
        "detect",
        "identify",
        "hope",
    ),
    "gpt-patient-3": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "detect",
        "identify",
        "hope",
    ),
    "gpt-patient-4": mentions(
        "bp_target",
        "enchanted2_mt",
        "best_ii",
        "optimal_bp",
        "detect",
        "identify",
        "clever",
        "hope",
        "enchanted",
    ),
    "gpt-clinician-1": mentions(
        "enchanted",
        "hope",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "detect",
        "identify",
    ),
    "gpt-clinician-2": mentions(
        "detect",
        "enchanted",
        "enchanted2_mt",
        "hope",
        "bp_target",
        "optimal_bp",
        "best_ii",
        "identify",
    ),
    "gpt-clinician-3": mentions(
        "enchanted2_mt",
        "optimal_bp",
        "bp_target",
        "best_ii",
        "detect",
        "identify",
        "hope",
        "enchanted",
    ),
    "gpt-clinician-4": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "detect",
        "identify",
        "hope",
    ),
    "gpt-researcher-1": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "best_ii",
        "optimal_bp",
        "detect",
        "identify",
        "hope",
    ),
    "gpt-researcher-2": mentions(
        "enchanted",
        "stepanchenko_2026",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "detect",
        "identify",
        "hope",
    ),
    "gpt-researcher-3": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "best_ii",
        "optimal_bp",
        "detect",
        "identify",
        "hope",
    ),
    "gpt-researcher-4": mentions(
        "enchanted",
        "bp_target",
        "enchanted2_mt",
        "optimal_bp",
        "best_ii",
        "detect",
        "identify",
        "hope",
    ),
}


IDENTITY_NOTES = {
    ("claude-patient-2", "chase_mt"): (
        "The response names only 'CHASE' in its search preamble; it is mapped to "
        "the Cochrane awaiting-classification CHASE-MT registry by context."
    ),
    ("claude-clinician-4", "detect"): (
        "The response describes DETECT's randomized design and mixed "
        "trial/meta-analysis publication as a 'BEST' feasibility precursor, then "
        "later calls DETECT unpublished."
    ),
    ("claude-researcher-3", "sharma_2018"): (
        "The response attributes NCT03443596 and its trial report to Mistry; the "
        "Cochrane records identify Sharma as the lead author."
    ),
    ("claude-researcher-3", "mistry_2017"): (
        "The response identifies the Mistry 2017 multicenter cohort but reports "
        "11,019 participants; the publication enrolled 228."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-patient-2", "chase_mt"): "CHASE (possible trial)",
    ("claude-clinician-4", "detect"): (
        "'BEST' feasibility precursor with a trial/meta-analysis publication; "
        "DETECT NCT04484350"
    ),
    ("claude-researcher-3", "sharma_2018"): (
        "Mistry et al.; randomized trial of early intensive BP lowering on "
        "cerebral perfusion; NCT03443596"
    ),
    ("claude-researcher-3", "mistry_2017"): (
        "Mistry et al. Systolic blood pressure within 24 hours after "
        "thrombectomy and functional outcomes; reported as n=11,019"
    ),
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
                    "source_file": f"reviews/CD016085/{run_id}.md",
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
    """Regenerate the curated CD016085 study-cluster match table."""

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
