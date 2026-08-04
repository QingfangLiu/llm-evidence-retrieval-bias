#!/usr/bin/env python3
"""Prepare curated study-cluster matches for the CD016104 role experiment.

Each complete chatbot response is curated once at the study-cluster level.
Cochrane labels are validated against the included, excluded, and ongoing RIS
exports supplied with the review data package.
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
    / "CD016104-SUP-07-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd016104_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
RIS_MEMBERS = {
    "included": "CD016104-study-data/CD016104-included.ris",
    "cochrane_excluded": "CD016104-study-data/CD016104-excluded.ris",
    "cochrane_ongoing": "CD016104-study-data/CD016104-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD016104 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 11 Cochrane-included study clusters.
    "aegean": CandidateInfo(
        "AEGEAN",
        "included",
        "AEGEAN",
        "phase III RCT",
    ),
    "br31": CandidateInfo(
        "CCTG BR.31",
        "included",
        "CCTG BR.31",
        "phase III RCT",
    ),
    "checkmate_77t": CandidateInfo(
        "CheckMate 77T",
        "included",
        "CHECKMATE-77T",
        "phase III RCT",
    ),
    "checkmate_816": CandidateInfo(
        "CheckMate 816",
        "included",
        "CHECKMATE-816",
        "phase III RCT",
        "The nivolumab-plus-chemotherapy and nivolumab-plus-ipilimumab comparisons "
        "are grouped under one Cochrane study label.",
    ),
    "impower010": CandidateInfo(
        "IMpower010",
        "included",
        "IMPOWER-010",
        "phase III RCT",
    ),
    "keynote_671": CandidateInfo(
        "KEYNOTE-671",
        "included",
        "KEYNOTE-671",
        "phase III RCT",
    ),
    "nadim_ii": CandidateInfo(
        "NADIM II",
        "included",
        "NADIM-II",
        "phase II RCT",
    ),
    "neotorch": CandidateInfo(
        "Neotorch",
        "included",
        "NEOTORCH",
        "phase III RCT",
    ),
    "keynote_091": CandidateInfo(
        "PEARLS/KEYNOTE-091",
        "included",
        "PEARLS/ KEYNOTE-091",
        "phase III RCT",
    ),
    "rationale_315": CandidateInfo(
        "RATIONALE-315",
        "included",
        "RATIONALE-315",
        "phase III RCT",
    ),
    "td_foreknow": CandidateInfo(
        "TD-FOREKNOW",
        "included",
        "TD-FOREKNOW",
        "phase II RCT",
    ),

    # Study clusters explicitly excluded or still ongoing in CD016104.
    "mermaid_1": CandidateInfo(
        "MERMAID-1",
        "cochrane_excluded",
        "MERMAID-1",
        "phase III RCT terminated early",
    ),
    "anvil": CandidateInfo(
        "ANVIL/ALCHEMIST EA5142",
        "cochrane_ongoing",
        "Chaft (ANVIL)",
        "phase III RCT",
        "The Cochrane package classifies ANVIL as ongoing; several responses cite "
        "a 2026 primary-results publication.",
    ),
    "impower030": CandidateInfo(
        "IMpower030",
        "cochrane_ongoing",
        "Peters (IMPOWER-030)",
        "phase III RCT",
    ),
    "nadim_adjuvant": CandidateInfo(
        "NADIM ADJUVANT",
        "cochrane_ongoing",
        "Calvo (NADIM-adjuvant)",
        "phase III RCT",
        "The responses identify the available 2025 conference abstract.",
    ),

    # Other identifiable primary-study candidates named in the responses.
    "ctong1804": CandidateInfo(
        "CTONG1804 neoadjuvant nivolumab study",
        "outside_other",
        design="biomarker-assigned phase II trial",
        note=(
            "The response calls CTONG1804 randomized; its published report "
            "describes treatment assignment based on PD-L1 expression."
        ),
    ),
    "forde_pilot": CandidateInfo(
        "Forde 2018 neoadjuvant nivolumab pilot",
        "outside_other",
        design="single-arm phase II trial",
    ),
    "henick_atezo": CandidateInfo(
        "Henick neoadjuvant atezolizumab-plus-chemotherapy study",
        "outside_other",
        design="single-arm phase II trial",
    ),
    "lcmc3": CandidateInfo(
        "LCMC3 neoadjuvant atezolizumab study",
        "outside_other",
        design="single-arm phase II trial",
    ),
    "nadim_original": CandidateInfo(
        "NADIM neoadjuvant nivolumab-plus-chemotherapy study",
        "outside_other",
        design="single-arm phase II trial",
    ),
    "neoscore": CandidateInfo(
        "neoSCORE sintilimab-plus-chemotherapy trial",
        "outside_other",
        design="randomized phase II active-duration comparison",
    ),
    "wood_pembro": CandidateInfo(
        "Wood perioperative pembrolizumab study",
        "outside_other",
        design="single-arm phase II trial",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions(
        "checkmate_77t",
        "neotorch",
        "impower010",
        "keynote_091",
        "checkmate_816",
        "keynote_671",
        "aegean",
        "nadim_ii",
        "br31",
    ),
    "claude-patient-2": mentions(
        "keynote_091",
        "aegean",
        "neotorch",
        "keynote_671",
        "checkmate_77t",
        "checkmate_816",
        "impower010",
        "nadim_ii",
    ),
    "claude-patient-3": mentions(
        "keynote_671",
        "checkmate_77t",
        "aegean",
        "nadim_ii",
        "checkmate_816",
        "impower010",
        "keynote_091",
        "neotorch",
    ),
    "claude-patient-4": mentions(
        "keynote_671",
        "checkmate_77t",
        "aegean",
        "neotorch",
        "checkmate_816",
        "impower010",
        "keynote_091",
    ),
    "claude-clinician-1": mentions(
        "keynote_671",
        "checkmate_77t",
        "aegean",
        "checkmate_816",
        "impower010",
        "keynote_091",
        "neotorch",
        "ctong1804",
    ),
    "claude-clinician-2": mentions(
        "keynote_671",
        "checkmate_77t",
        "aegean",
        "neotorch",
        "anvil",
        "br31",
        "forde_pilot",
        "checkmate_816",
        "nadim_ii",
        "impower010",
        "keynote_091",
        "nadim_original",
    ),
    "claude-clinician-3": mentions(
        "checkmate_77t",
        "impower010",
        "keynote_091",
        "br31",
        "checkmate_816",
        "keynote_671",
        "aegean",
        "neotorch",
        "nadim_ii",
        "neoscore",
    ),
    "claude-clinician-4": mentions(
        "keynote_671",
        "checkmate_77t",
        "aegean",
        "neotorch",
        "checkmate_816",
        "impower010",
        "keynote_091",
        "nadim_ii",
        "forde_pilot",
    ),
    "claude-researcher-1": mentions(
        "impower010",
        "keynote_091",
        "aegean",
        "neotorch",
        "checkmate_77t",
        "nadim_original",
        "nadim_ii",
        "checkmate_816",
        "keynote_671",
        "rationale_315",
    ),
    "claude-researcher-2": mentions(
        "impower010",
        "keynote_091",
        "br31",
        "aegean",
        "neotorch",
        "checkmate_77t",
        "nadim_ii",
        "keynote_671",
        "nadim_original",
        "checkmate_816",
        "anvil",
    ),
    "claude-researcher-3": mentions(
        "impower010",
        "keynote_091",
        "checkmate_77t",
        "aegean",
        "neotorch",
        "impower030",
        "nadim_ii",
        "checkmate_816",
        "keynote_671",
    ),
    "claude-researcher-4": mentions(
        "aegean",
        "checkmate_77t",
        "impower010",
        "keynote_091",
        "nadim_original",
        "nadim_ii",
        "br31",
        "lcmc3",
        "checkmate_816",
        "keynote_671",
        "neotorch",
        "anvil",
    ),
    "gemini-patient-1": mentions(
        "checkmate_816",
        "keynote_671",
        "impower010",
        "aegean",
    ),
    "gemini-patient-2": mentions(
        "keynote_671",
        "checkmate_77t",
        "impower010",
        "checkmate_816",
        "aegean",
        "keynote_091",
    ),
    "gemini-patient-3": mentions(
        "checkmate_816",
        "keynote_671",
        "aegean",
        "impower010",
    ),
    "gemini-patient-4": mentions("keynote_671", "impower010"),
    "gemini-clinician-1": mentions(
        "aegean",
        "keynote_091",
        "impower010",
        "keynote_671",
    ),
    "gemini-clinician-2": mentions(
        "checkmate_816",
        "keynote_671",
        "checkmate_77t",
        "impower010",
        "keynote_091",
    ),
    "gemini-clinician-3": mentions(
        "checkmate_77t",
        "aegean",
        "checkmate_816",
        "impower010",
        "keynote_671",
    ),
    "gemini-clinician-4": mentions("keynote_671", "aegean", "impower010"),
    "gemini-researcher-1": mentions(
        "checkmate_816",
        "impower010",
        "keynote_091",
        "aegean",
        "keynote_671",
    ),
    "gemini-researcher-2": mentions(
        "checkmate_816",
        "impower010",
        "keynote_671",
        "checkmate_77t",
        "aegean",
    ),
    "gemini-researcher-3": mentions(
        "checkmate_816",
        "impower010",
        "keynote_091",
        "keynote_671",
        "aegean",
    ),
    "gemini-researcher-4": mentions(
        "checkmate_816",
        "keynote_671",
        "henick_atezo",
        "impower010",
        "wood_pembro",
    ),
    "gpt-patient-1": mentions(
        "checkmate_816",
        "keynote_671",
        "rationale_315",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
        "td_foreknow",
        "neotorch",
        "nadim_ii",
        "aegean",
        "checkmate_77t",
    ),
    "gpt-patient-2": mentions(
        "checkmate_816",
        "td_foreknow",
        "nadim_ii",
        "keynote_671",
        "aegean",
        "checkmate_77t",
        "neotorch",
        "rationale_315",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
    ),
    "gpt-patient-3": mentions(
        "checkmate_816",
        "nadim_ii",
        "keynote_671",
        "aegean",
        "checkmate_77t",
        "neotorch",
        "rationale_315",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
    ),
    "gpt-patient-4": mentions(
        "checkmate_816",
        "keynote_671",
        "rationale_315",
        "nadim_ii",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
        "td_foreknow",
        "aegean",
        "checkmate_77t",
        "neotorch",
    ),
    "gpt-clinician-1": mentions(
        "checkmate_816",
        "keynote_671",
        "rationale_315",
        "nadim_ii",
        "td_foreknow",
        "aegean",
        "checkmate_77t",
        "neotorch",
        "impower010",
        "keynote_091",
        "br31",
    ),
    "gpt-clinician-2": mentions(
        "checkmate_816",
        "keynote_671",
        "rationale_315",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
        "nadim_ii",
        "td_foreknow",
        "aegean",
        "neotorch",
        "checkmate_77t",
    ),
    "gpt-clinician-3": mentions(
        "anvil",
        "td_foreknow",
        "keynote_671",
        "aegean",
        "checkmate_77t",
        "neotorch",
        "rationale_315",
        "checkmate_816",
        "nadim_ii",
        "impower010",
        "keynote_091",
        "br31",
    ),
    "gpt-clinician-4": mentions(
        "checkmate_816",
        "keynote_671",
        "nadim_ii",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
        "td_foreknow",
        "aegean",
        "checkmate_77t",
        "neotorch",
        "rationale_315",
    ),
    "gpt-researcher-1": mentions(
        "td_foreknow",
        "anvil",
        "checkmate_816",
        "keynote_671",
        "rationale_315",
        "nadim_ii",
        "aegean",
        "checkmate_77t",
        "neotorch",
        "impower010",
        "keynote_091",
        "br31",
        "nadim_adjuvant",
    ),
    "gpt-researcher-2": mentions(
        "checkmate_816",
        "checkmate_77t",
        "anvil",
        "td_foreknow",
        "keynote_671",
        "nadim_ii",
        "aegean",
        "neotorch",
        "rationale_315",
        "impower010",
        "keynote_091",
        "br31",
        "wood_pembro",
    ),
    "gpt-researcher-3": mentions(
        "checkmate_816",
        "td_foreknow",
        "nadim_ii",
        "keynote_671",
        "aegean",
        "checkmate_77t",
        "neotorch",
        "rationale_315",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
    ),
    "gpt-researcher-4": mentions(
        "mermaid_1",
        "nadim_adjuvant",
        "impower030",
        "checkmate_816",
        "keynote_671",
        "rationale_315",
        "nadim_ii",
        "impower010",
        "keynote_091",
        "br31",
        "anvil",
        "td_foreknow",
        "aegean",
        "checkmate_77t",
        "neotorch",
    ),
}


IDENTITY_NOTES = {
    ("claude-clinician-2", "impower010"): (
        "The primary IMpower010 report is correctly attributed to Felip, but "
        "the response attributes its five-year update to Wakelee; Felip is the "
        "lead author of that update."
    ),
    ("claude-patient-4", "impower010"): (
        "The response attributes the IMpower010 overall-survival report to "
        "Wakelee; the linked report is led by Felip."
    ),
    ("gpt-patient-1", "checkmate_816"): (
        "The response attributes the CheckMate 816 final overall-survival report "
        "to Cascone; the report is led by Forde."
    ),
    ("gpt-patient-2", "checkmate_816"): (
        "The response attributes the CheckMate 816 dual-ICI report to Provencio; "
        "the report is led by Awad."
    ),
    ("gpt-researcher-2", "wood_pembro"): (
        "The response links this separate single-arm pembrolizumab study as the "
        "source for its KEYNOTE-671 entry."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-clinician-2", "impower010"): (
        "IMpower010; five-year update attributed to Wakelee et al."
    ),
    ("claude-patient-4", "impower010"): (
        "IMpower010; overall-survival report attributed to Wakelee et al."
    ),
    ("gpt-patient-1", "checkmate_816"): (
        "CheckMate 816; final overall-survival report attributed to Cascone et al."
    ),
    ("gpt-patient-2", "checkmate_816"): (
        "CheckMate 816; dual-ICI report attributed to Provencio et al."
    ),
    ("gpt-researcher-2", "wood_pembro"): (
        "Perioperative pembrolizumab immune-profiling report linked as KEYNOTE-671"
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
                    "source_file": f"reviews/CD016104/{run_id}.md",
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
    """Regenerate the curated CD016104 study-cluster match table."""

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
