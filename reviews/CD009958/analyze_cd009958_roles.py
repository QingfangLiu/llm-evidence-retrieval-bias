#!/usr/bin/env python3
"""Prepare curated citation matches for the CD009958 user-role experiment.

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


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_DIR = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_6"
    / "CD009958-SUP-07-dataPackage"
    / "CD009958-study-data"
)
MATCHES_PATH = REPO_ROOT / "data" / "reviews" / REVIEW_DIR.name / "cd009958_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD009958 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # Cochrane-included clinical studies and economic substudies.
    "bergstrom": CandidateInfo(
        "Bergstrom 2013 (TURN)", "included", "Bergstrom 2013", "RCT"
    ),
    "defloor": CandidateInfo(
        "Defloor 2005", "included", "Defloor 2005", "cluster-randomized trial"
    ),
    "ghezeljeh": CandidateInfo(
        "Ghezeljeh 2017", "included", "Ghezeljeh 2017", "RCT"
    ),
    "jin": CandidateInfo("Jin 2024", "included", "Jin 2024", "RCT"),
    "manzano": CandidateInfo(
        "Manzano 2014", "included", "Manzano 2014", "RCT"
    ),
    "moore": CandidateInfo(
        "Moore 2011", "included", "Moore 2011", "cluster-randomized trial"
    ),
    "moore_economic": CandidateInfo(
        "Moore 2013 economic analysis",
        "included",
        "Moore 2013",
        "economic substudy",
    ),
    "paulden": CandidateInfo(
        "Paulden 2014 TURN economic analysis",
        "included",
        "Paulden 2014",
        "economic substudy",
    ),
    "pickham": CandidateInfo(
        "Pickham 2018 (LS-HAPI)", "included", "Pickham 2018", "RCT"
    ),
    "tarigan": CandidateInfo(
        "Tarigan 2021", "included", "Tarigan 2021", "pilot RCT"
    ),
    "young": CandidateInfo("Young 2004", "included", "Young 2004", "RCT"),
    "zhang": CandidateInfo("Zhang 2024", "included", "Zhang 2024", "RCT"),
    "zhou": CandidateInfo("Zhou 2014", "included", "Zhou 2014", "RCT"),
    # Studies explicitly excluded by CD009958.
    "de_meyer": CandidateInfo(
        "De Meyer 2019 (PROTECT)",
        "cochrane_excluded",
        "De Meyer 2019",
        "cluster-randomized trial",
        "Participants with stage 1 pressure injury were eligible.",
    ),
    "girard": CandidateInfo(
        "Girard 2014 prone-positioning analysis",
        "cochrane_excluded",
        "Girard 2014",
        "RCT analysis",
        "Results were not separable for participants without pressure injury at baseline.",
    ),
    "jiang": CandidateInfo(
        "Jiang 2020",
        "cochrane_excluded",
        "Jiang 2020",
        "comparative study",
        "Repositioning regimen and support surface differed together.",
    ),
    "kapp_2023": CandidateInfo(
        "Kapp 2023 turning-and-positioning system trial",
        "cochrane_excluded",
        "Kapp 2023",
        "RCT",
        "The intervention was a turning and positioning medical device.",
    ),
    "malekara": CandidateInfo(
        "Malekara 2025",
        "cochrane_excluded",
        "Malekara 2025",
        "RCT",
        "Some participants had pressure injury at baseline.",
    ),
    "vanderwee": CandidateInfo(
        "Vanderwee 2007",
        "cochrane_excluded",
        "Vanderwee 2007",
        "RCT",
        "Participants had pre-existing stage 1 pressure injury.",
    ),
    "yap": CandidateInfo(
        "Yap 2022 (TEAM-UP)",
        "cochrane_excluded",
        "Yap 2022",
        "cluster-randomized trial",
        "Six participants had pressure injury at baseline.",
    ),
    # Study classified as ongoing in the CD009958 data package.
    "penfup": CandidateInfo(
        "NCT04604665 (PENFUP)",
        "cochrane_ongoing",
        "NCT04604665",
        "ongoing cluster-randomized trial",
    ),
    # Other or unresolved study candidates named in the responses.
    "bai": CandidateInfo(
        "Bai 2020 foam-mattress cohort",
        "outside_observational",
        design="prospective cohort",
    ),
    "colin": CandidateInfo(
        "Colin 1996 lateral-position physiology study",
        "outside_physiological",
        design="healthy-volunteer physiological study",
    ),
    "curvilinear_2018": CandidateInfo(
        "Curvilinear supine-position trial 2018",
        "outside_other",
        design="clinical trial",
    ),
    "darvall": CandidateInfo(
        "Darvall 2018",
        "outside_observational",
        design="pre-post intervention study",
    ),
    "gattinoni": CandidateInfo(
        "Gattinoni 2001 prone-positioning trial", "outside_other", design="RCT"
    ),
    "gay": CandidateInfo(
        "Gay 2025 ESCARD prone-position bundle trial",
        "outside_other",
        design="stepped-wedge randomized trial",
        note="Published after the review search date.",
    ),
    "kallman": CandidateInfo(
        "Källman 2015 lying-position physiology study",
        "outside_physiological",
        design="physiological study",
    ),
    "kapp_2019": CandidateInfo(
        "Kapp 2019 tilt-maintenance study",
        "outside_observational",
        design="observational study",
    ),
    "kim_shin": CandidateInfo(
        "Kim and Shin 2021 interface-pressure study",
        "outside_physiological",
        design="healthy-volunteer physiological study",
    ),
    "peterson_2008": CandidateInfo(
        "Peterson 2008 head-of-bed physiology study",
        "outside_physiological",
        design="healthy-volunteer physiological study",
    ),
    "peterson_2010": CandidateInfo(
        "Peterson 2010 turning-pressure study",
        "outside_physiological",
        design="healthy-volunteer physiological study",
    ),
    "rich": CandidateInfo(
        "Rich 2011",
        "outside_observational",
        design="observational cohort",
    ),
    "still": CandidateInfo(
        "Still 2013 Turn Team study",
        "outside_observational",
        design="before-after intervention study",
    ),
    "unresolved_stroke": CandidateInfo(
        "Unspecified 30° versus 90° stroke-position trial",
        "unresolved",
        note="No authors, year, journal, or identifier were supplied.",
    ),
    "vanderwee_2005": CandidateInfo(
        "Vanderwee 2005 support-surface trial",
        "outside_other",
        design="RCT of alternating-pressure mattresses",
    ),
    "winkelman": CandidateInfo(
        "Winkelman and Chiang 2010",
        "outside_observational",
        design="manual-turning study",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response full-text annotations compact and readable."""

    return keys


# Candidate order follows first appearance anywhere in each complete response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions("bergstrom", "defloor", "manzano", "vanderwee", "moore", "young", "penfup", "yap"),
    "claude-patient-2": mentions("bergstrom", "yap", "defloor", "vanderwee", "moore", "young", "winkelman"),
    "claude-patient-3": mentions("bergstrom", "yap", "defloor", "vanderwee", "manzano", "moore", "young"),
    "claude-patient-4": mentions("bergstrom", "yap", "defloor", "vanderwee", "manzano", "moore", "young", "zhou"),
    "claude-clinician-1": mentions("bergstrom", "yap", "defloor", "vanderwee", "manzano", "moore", "young"),
    "claude-clinician-2": mentions("bergstrom", "yap", "defloor", "vanderwee", "penfup", "moore", "young"),
    "claude-clinician-3": mentions("bergstrom", "yap", "vanderwee", "defloor", "moore", "young", "unresolved_stroke", "penfup"),
    "claude-clinician-4": mentions("bergstrom", "yap", "defloor", "vanderwee", "manzano", "young", "moore", "penfup"),
    "claude-researcher-1": mentions("bergstrom", "yap", "defloor", "manzano", "penfup", "moore", "young", "ghezeljeh", "vanderwee", "pickham"),
    "claude-researcher-2": mentions("bergstrom", "defloor", "vanderwee", "manzano", "darvall", "yap", "moore", "young", "vanderwee_2005"),
    "claude-researcher-3": mentions("defloor", "vanderwee", "bergstrom", "manzano", "yap", "young", "moore", "penfup"),
    "claude-researcher-4": mentions("bergstrom", "paulden", "yap", "defloor", "vanderwee", "manzano", "pickham", "zhou", "moore", "young", "ghezeljeh", "penfup"),
    "gemini-patient-1": mentions("still", "bergstrom", "bai"),
    "gemini-patient-2": mentions("defloor", "manzano", "moore"),
    "gemini-patient-3": mentions("defloor", "yap", "manzano", "moore", "kapp_2019", "young"),
    "gemini-patient-4": mentions("yap", "moore", "young"),
    "gemini-clinician-1": mentions("still", "yap", "moore"),
    "gemini-clinician-2": mentions("defloor", "yap", "moore", "young", "kapp_2019"),
    "gemini-clinician-3": mentions("bergstrom", "defloor", "moore"),
    "gemini-clinician-4": mentions("defloor", "vanderwee", "moore", "young"),
    "gemini-researcher-1": mentions("bergstrom", "defloor", "moore", "kapp_2019"),
    "gemini-researcher-2": mentions("bergstrom", "defloor", "still", "moore", "young"),
    "gemini-researcher-3": mentions("defloor", "bergstrom", "moore", "young"),
    "gemini-researcher-4": mentions("defloor", "bergstrom", "yap", "moore"),
    "gpt-patient-1": mentions("bergstrom", "moore", "defloor", "vanderwee", "manzano", "pickham", "jiang", "yap", "young", "de_meyer", "zhang"),
    "gpt-patient-2": mentions("bergstrom", "moore", "defloor", "manzano", "vanderwee", "pickham", "yap", "young", "ghezeljeh", "jin", "zhang"),
    "gpt-patient-3": mentions("defloor", "vanderwee", "bergstrom", "manzano", "jiang", "yap", "pickham", "young", "moore", "de_meyer", "jin", "zhang"),
    "gpt-patient-4": mentions("defloor", "vanderwee", "bergstrom", "manzano", "pickham", "yap", "rich", "moore", "young", "ghezeljeh", "kapp_2023", "colin", "kallman", "peterson_2008", "peterson_2010", "kim_shin"),
    "gpt-clinician-1": mentions("defloor", "vanderwee", "bergstrom", "manzano", "pickham", "yap", "young", "moore", "ghezeljeh", "gattinoni", "jin", "zhang", "malekara", "gay", "peterson_2008"),
    "gpt-clinician-2": mentions("defloor", "vanderwee", "bergstrom", "manzano", "pickham", "yap", "young", "moore", "ghezeljeh", "girard", "gay", "jin", "zhang", "malekara"),
    "gpt-clinician-3": mentions("defloor", "vanderwee", "bergstrom", "manzano", "yap", "young", "moore", "kallman", "curvilinear_2018", "malekara"),
    "gpt-clinician-4": mentions("bergstrom", "defloor", "moore", "girard", "vanderwee", "manzano", "pickham", "yap", "young", "ghezeljeh", "gay"),
    "gpt-researcher-1": mentions("defloor", "bergstrom", "manzano", "yap", "young", "moore", "ghezeljeh", "curvilinear_2018", "jin", "zhang", "malekara", "gay", "pickham", "de_meyer", "vanderwee"),
    "gpt-researcher-2": mentions("defloor", "bergstrom", "manzano", "yap", "vanderwee", "young", "moore", "ghezeljeh", "girard", "gay", "jin", "zhang", "malekara", "pickham", "de_meyer", "kapp_2023"),
    "gpt-researcher-3": mentions("defloor", "vanderwee", "manzano", "bergstrom", "pickham", "yap", "young", "moore", "girard", "ghezeljeh", "jin", "zhang", "gay", "peterson_2008"),
    "gpt-researcher-4": mentions("defloor", "bergstrom", "manzano", "yap", "pickham", "young", "moore", "girard", "ghezeljeh", "curvilinear_2018", "jin", "zhang", "malekara", "colin", "peterson_2008", "kim_shin"),
}


IDENTITY_NOTES = {
    ("claude-clinician-2", "penfup"): (
        "The response attributes the Colombian ICU cluster-RCT protocol to Manzano; "
        "its setting and protocol description resolve to PENFUP/NCT04604665."
    ),
    ("claude-researcher-1", "defloor"): (
        "The citation names Defloor 2005, but its two-arm 16-home description belongs "
        "to Vanderwee 2007."
    ),
    ("claude-researcher-4", "zhou"): (
        "The response gives the lead author as Zhou Q rather than Zhou X."
    ),
    ("gemini-clinician-4", "vanderwee"): (
        "The response gives 2006, while the Cochrane study label and issue year are 2007."
    ),
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-clinician-2", "penfup"): "Manzano F et al. — Colombian ICU cluster-RCT protocol",
    ("claude-researcher-4", "zhou"): "Zhou Q et al. (2014 trial, China)",
    ("gemini-clinician-4", "vanderwee"): "Vanderwee et al. (2006)",
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
        "included": ris_study_labels(SOURCE_DIR / "CD009958-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD009958-excluded.ris"),
        "cochrane_ongoing": ris_study_labels(SOURCE_DIR / "CD009958-ongoing.ris"),
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
                    "source_file": f"reviews/CD009958/{run_id}.md",
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
