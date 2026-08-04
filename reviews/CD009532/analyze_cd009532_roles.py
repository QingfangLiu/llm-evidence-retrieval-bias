#!/usr/bin/env python3
"""Prepare curated citation matches for the CD009532 user-role experiment.

The chatbot responses use heterogeneous citation formats and often cite multiple
reports from the same trial. This script records each unique study cluster once
per response, validates Cochrane labels directly against the study-data RIS
exports, and writes the audit table consumed by the retrieval-bias demo.
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
    / "CD009532-SUP-08-dataPackage"
    / "CD009532-study-data"
)
MATCHES_PATH = REPO_ROOT / "data" / "reviews" / REVIEW_DIR.name / "cd009532_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD009532 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # Cochrane-included study clusters. Companion reports share one key.
    "birgegard": CandidateInfo(
        "Birgegård 2010", "included", "Birgegard 2010", "randomized comparative trial"
    ),
    "cable_1988": CandidateInfo(
        "Cable 1988", "included", "Cable 1988", "randomized placebo-controlled trial"
    ),
    "dara": CandidateInfo("Dara 2017", "included", "Dara 2017", "RCT"),
    "ehn": CandidateInfo(
        "Ehn 1968 / Lieden intermittent-iron trial",
        "included",
        "Ehn 1968",
        "controlled trial",
    ),
    "fontana": CandidateInfo(
        "Fontana 2014a (ISUB)",
        "included",
        "Fontana 2014a (ISUB)",
        "randomized placebo-controlled trial",
    ),
    "gordeuk_1987a": CandidateInfo(
        "Gordeuk 1987a", "included", "Gordeuk 1987a", "RCT"
    ),
    "gordeuk_1990": CandidateInfo(
        "Gordeuk 1990", "included", "Gordeuk 1990", "RCT"
    ),
    "gybel_brask": CandidateInfo(
        "Gybel-Brask 2018", "included", "Gybel-Brask 2018", "RCT"
    ),
    "hod": CandidateInfo(
        "Hod 2022 (DIDS)", "included", "Hod 2022 (DIDS)", "RCT"
    ),
    "jacobs_1993": CandidateInfo(
        "Jacobs 1993", "included", "Jacobs 1993", "randomized comparative trial"
    ),
    "kiss": CandidateInfo(
        "Kiss 2015 (REDS-III HEIRS)",
        "included",
        "Kiss 2015 (REDS-III HEIRS)",
        "RCT",
    ),
    "linpisarn": CandidateInfo(
        "Linpisarn 1986", "included", "Linpisarn 1986", "controlled trial"
    ),
    "macher": CandidateInfo(
        "Macher 2016 (IronWoMan)",
        "included",
        "Macher 2016 (IronWoMan)",
        "randomized comparative trial",
    ),
    "mackintosh": CandidateInfo(
        "Mackintosh 1988", "included", "Mackintosh 1988", "randomized trial"
    ),
    "maghsudlu": CandidateInfo(
        "Maghsudlu 2008", "included", "Maghsudlu 2008", "RCT"
    ),
    "marks": CandidateInfo(
        "Marks 2013 (FIRST)", "included", "Marks 2013 (FIRST)", "RCT"
    ),
    "mast": CandidateInfo(
        "Mast 2016 (STRIDE)", "included", "Mast 2016 (STRIDE)", "RCT"
    ),
    "radtke_2004a": CandidateInfo(
        "Radtke 2004a", "included", "Radtke 2004a", "RCT"
    ),
    "radtke_2004b": CandidateInfo(
        "Radtke 2004b", "included", "Radtke 2004b", "RCT"
    ),
    "rosvik": CandidateInfo(
        "Røsvik 2010", "included", "Rosvik 2010", "controlled trial"
    ),
    "waldvogel": CandidateInfo(
        "Waldvogel 2012", "included", "Waldvogel 2012", "RCT"
    ),
    # Studies explicitly excluded by CD009532.
    "baart": CandidateInfo(
        "Baart 2020 (FIND'EM)",
        "cochrane_excluded",
        "Baart 2020",
        "cluster-randomized trial of donation intervals",
        "Different intervention: ferritin-guided donation intervals, not iron supplementation.",
    ),
    "bryant": CandidateInfo(
        "Bryant 2012b",
        "cochrane_excluded",
        "Bryant 2012b",
        "prospective donor-management study",
        "Excluded by Cochrane for non-randomized allocation.",
    ),
    "ghana_pilot": CandidateInfo(
        "NCT04949165 Ghana BLIS pilot",
        "cochrane_excluded",
        "NCT04949165",
        "single-arm pilot study",
        "Excluded by Cochrane for non-randomized design.",
    ),
    "hasan": CandidateInfo(
        "Hasan 2022",
        "cochrane_excluded",
        "Hasan 2022",
        "randomized mobile-app intervention",
        "Both groups received the same iron supplementation.",
    ),
    "magnussen": CandidateInfo(
        "Magnussen 2008",
        "cochrane_excluded",
        "Magnussen 2008",
        "non-randomized intervention study",
    ),
    "radtke_2005": CandidateInfo(
        "Radtke 2005",
        "cochrane_excluded",
        "Radtke 2005",
        "letter",
        "Excluded publication type under the user prompt.",
    ),
    # Studies classified as ongoing in the Cochrane study-data package.
    "bloodsafe": CandidateInfo(
        "NCT06101238 (BLOODSAFE)",
        "cochrane_ongoing",
        "NCT06101238 (BLOODSAFE)",
        "ongoing randomized trial",
    ),
    "forte": CandidateInfo(
        "Karregat 2022 (FORTE)",
        "cochrane_ongoing",
        "Karregat 2022 (FORTE)",
        "randomized trial; results published after the review classification",
    ),
    # Other or unresolved study candidates named in the responses.
    "alvarez": CandidateInfo(
        "Alvarez-Ossorio 2000", "outside_observational", design="prospective program"
    ),
    "garg": CandidateInfo(
        "Garg 2025", "outside_observational", design="single-arm intervention study"
    ),
    "ikuta": CandidateInfo(
        "Ikuta 2026", "outside_observational", design="sequential longitudinal study"
    ),
    "interval": CandidateInfo(
        "INTERVAL trial 2017",
        "outside_other",
        design="RCT of donation frequency",
        note="Different intervention: donation frequency, not iron supplementation.",
    ),
    "pittori": CandidateInfo(
        "Pittori 2011", "outside_observational", design="prospective supplementation program"
    ),
    "rapid_identification": CandidateInfo(
        "Radtke rapid-identification study",
        "outside_observational",
        design="diagnostic study",
    ),
    "rise": CandidateInfo(
        "REDS-II RISE study", "outside_observational", design="prospective cohort"
    ),
    "simon_iron_stores": CandidateInfo(
        "Simon et al. iron-stores study",
        "outside_observational",
        design="iron-status study",
        note="The response itself says the supplementation arm was unverified.",
    ),
    "unresolved_australian": CandidateInfo(
        "Unspecified Australian donor-iron trial",
        "unresolved",
        note="Only an author-group lead was supplied, without a title or identifier.",
    ),
    "wachsmuth": CandidateInfo(
        "Wachsmuth 2024",
        "outside_observational",
        design="uncontrolled post-donation pilot study",
    ),
}


def mentions(*keys: str) -> tuple[str, ...]:
    """Keep the per-response study-cluster annotations compact and readable."""

    return keys


# Candidate order follows the order in which studies appear in each response.
RUN_CANDIDATES = {
    "claude-patient-1": mentions("kiss", "mast", "hod", "fontana", "waldvogel", "macher", "forte", "ghana_pilot"),
    "claude-patient-2": mentions("kiss", "forte", "hod", "radtke_2004a", "marks", "gordeuk_1990", "macher", "baart"),
    "claude-patient-3": mentions("kiss", "mast", "forte", "hod", "macher", "fontana", "waldvogel"),
    "claude-patient-4": mentions("kiss", "mast", "forte", "hod", "fontana", "macher"),
    "claude-clinician-1": mentions("kiss", "radtke_2004a", "waldvogel", "gordeuk_1990", "marks", "macher", "hod", "forte", "fontana", "baart"),
    "claude-clinician-2": mentions("kiss", "mast", "waldvogel", "forte", "fontana", "hod", "baart"),
    "claude-clinician-3": mentions("kiss", "mast", "hod", "forte", "pittori", "magnussen", "hasan", "bloodsafe", "baart"),
    "claude-clinician-4": mentions("kiss", "mast", "hod", "forte", "pittori", "waldvogel", "fontana", "radtke_2004a", "radtke_2004b", "radtke_2005", "bryant"),
    "claude-researcher-1": mentions("kiss", "mast", "fontana", "hod", "forte", "macher", "waldvogel", "unresolved_australian"),
    "claude-researcher-2": mentions("kiss", "mast", "forte", "macher", "fontana", "hod", "waldvogel", "interval", "baart", "rise"),
    "claude-researcher-3": mentions("kiss", "waldvogel", "maghsudlu", "forte", "hod", "macher", "bryant", "mast", "baart"),
    "claude-researcher-4": mentions("kiss", "mast", "rapid_identification", "macher", "hod", "forte", "simon_iron_stores", "waldvogel", "baart"),
    "gemini-patient-1": mentions("cable_1988", "dara", "kiss"),
    "gemini-patient-2": mentions("mast", "macher", "kiss"),
    "gemini-patient-3": mentions("kiss", "mast", "dara"),
    "gemini-patient-4": mentions("mast", "kiss"),
    "gemini-clinician-1": mentions("mast", "kiss", "wachsmuth"),
    "gemini-clinician-2": mentions("kiss", "mast", "forte"),
    "gemini-clinician-3": mentions("macher", "kiss", "mackintosh", "mast"),
    "gemini-clinician-4": mentions("kiss", "hod", "mast"),
    "gemini-researcher-1": mentions("mast", "cable_1988", "forte", "kiss"),
    "gemini-researcher-2": mentions("mast", "hod", "kiss", "macher"),
    "gemini-researcher-3": mentions("mast", "kiss"),
    "gemini-researcher-4": mentions("bryant", "mast", "cable_1988", "dara", "kiss"),
    "gpt-patient-1": mentions("forte", "mast", "kiss", "marks", "radtke_2004a", "gordeuk_1990", "maghsudlu", "waldvogel", "alvarez", "bryant"),
    "gpt-patient-2": mentions("gordeuk_1990", "mast", "forte", "alvarez", "kiss", "radtke_2004a", "maghsudlu", "waldvogel", "dara", "radtke_2004b", "bryant"),
    "gpt-patient-3": mentions("forte", "mast", "kiss", "marks", "gordeuk_1990", "radtke_2004a", "maghsudlu", "waldvogel", "dara", "gordeuk_1987a", "radtke_2004b", "bryant", "magnussen", "alvarez"),
    "gpt-patient-4": mentions("forte", "kiss", "gordeuk_1990", "marks", "mast", "radtke_2004a", "maghsudlu", "waldvogel", "dara", "bryant", "magnussen"),
    "gpt-clinician-1": mentions("gordeuk_1990", "garg", "magnussen", "bryant", "alvarez", "forte", "kiss", "mast", "radtke_2004a", "maghsudlu", "waldvogel", "pittori"),
    "gpt-clinician-2": mentions("forte", "gordeuk_1990", "marks", "cable_1988", "bryant", "alvarez", "kiss", "mast", "waldvogel", "maghsudlu", "radtke_2004a", "jacobs_1993", "linpisarn"),
    "gpt-clinician-3": mentions("forte", "garg", "waldvogel", "bryant", "magnussen", "alvarez", "kiss", "marks", "gordeuk_1990", "mast", "maghsudlu"),
    "gpt-clinician-4": mentions("forte", "kiss", "mast", "marks", "waldvogel", "radtke_2004a", "maghsudlu", "gordeuk_1990", "bryant", "alvarez", "macher", "fontana", "gybel_brask"),
    "gpt-researcher-1": mentions("gordeuk_1990", "marks", "kiss", "forte", "garg", "magnussen", "alvarez", "radtke_2004a", "radtke_2004b", "maghsudlu", "rosvik", "waldvogel", "mast", "gybel_brask", "fontana", "birgegard", "bryant", "pittori"),
    "gpt-researcher-2": mentions("gordeuk_1990", "cable_1988", "marks", "mast", "bryant", "alvarez", "pittori", "forte", "kiss", "radtke_2004a", "radtke_2004b", "maghsudlu", "waldvogel", "gybel_brask", "fontana", "gordeuk_1987a", "ehn", "rosvik"),
    "gpt-researcher-3": mentions("gordeuk_1990", "cable_1988", "radtke_2004a", "maghsudlu", "marks", "kiss", "mast", "forte", "waldvogel", "radtke_2004b", "birgegard", "fontana"),
    "gpt-researcher-4": mentions("gordeuk_1990", "alvarez", "radtke_2004a", "maghsudlu", "marks", "kiss", "forte", "garg", "gordeuk_1987a", "radtke_2004b", "waldvogel", "mast", "dara", "bryant", "ikuta"),
}


IDENTITY_NOTES = {
    ("claude-patient-2", "hod"): "The displayed author is Waldvogel-Abramowski, but the title identifies the DIDS report.",
    ("claude-patient-2", "macher"): "The response attributes IronWoMan to Baart et al.",
    ("claude-patient-4", "hod"): "The response attributes the DIDS report to Spekman et al.",
    ("claude-patient-4", "macher"): "The response attributes the IronWoMan report to Radtke et al.",
    ("claude-clinician-1", "fontana"): "The response gives only 'Mathew' or the IV-iron-fatigue trial; the title resolves to ISUB.",
    ("claude-clinician-2", "fontana"): "The response attributes the ISUB publication to Radtke et al.",
    ("claude-researcher-3", "waldvogel"): "The response gives the Bryant article's journal and pages for the Waldvogel title.",
    ("claude-researcher-4", "macher"): "The response supplies Neiser/Bock as authors for IronWoMan.",
    ("claude-researcher-4", "hod"): "The response supplies Bruggraber/Spencer as authors for the DIDS title.",
}

REPORTED_CITATION_OVERRIDES = {
    ("claude-patient-2", "hod"): "Waldvogel-Abramowski et al. — A randomized trial of blood donor iron repletion on red cell quality for transfusion and donor cognition and well-being",
    ("claude-patient-2", "macher"): "Baart et al. (IronWoMan trial)",
    ("claude-patient-4", "hod"): "Spekman et al. — A randomized trial of blood donor iron repletion on red cell quality for transfusion and donor cognition and well-being",
    ("claude-patient-4", "macher"): "Radtke et al. — High-dose intravenous versus oral iron in blood donors with iron deficiency",
    ("claude-clinician-1", "fontana"): "Mathew (or the IV-iron-fatigue trial)",
    ("claude-clinician-2", "fontana"): "Radtke et al. — The effects of intravenous iron supplementation on fatigue and general health",
    ("claude-researcher-3", "waldvogel"): "Waldvogel-Abramowski et al. — Clinical evaluation of iron treatment efficiency (Transfusion 2012;52:1566–1575)",
    ("claude-researcher-4", "macher"): "Neiser et al. / Bock et al. — IronWoMan RCT",
    ("claude-researcher-4", "hod"): "Bruggraber / Spencer et al. — Iron Supplementation in Blood Donors RCT",
}


def ris_study_labels(path: Path) -> set[str]:
    """Read unique Cochrane study labels from an RIS export."""

    return {
        match.group(1).strip()
        for match in re.finditer(r"^NS  - (.+)$", path.read_text(encoding="utf-8-sig"), re.MULTILINE)
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
        path.name
        for path in REVIEW_DIR.glob("*.md")
        if path.name != "README.md"
    }
    if available_files != expected_files:
        missing = sorted(expected_files - available_files)
        stale = sorted(available_files - expected_files)
        raise ValueError(f"Response file mismatch; missing={missing}, stale={stale}")

    status_labels = {
        "included": ris_study_labels(SOURCE_DIR / "CD009532-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD009532-excluded.ris"),
        "cochrane_ongoing": ris_study_labels(SOURCE_DIR / "CD009532-ongoing.ris"),
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


def build_match_rows() -> list[dict[str, str | int]]:
    """Build one row per unique study candidate named in each response."""

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
                    "source_file": f"reviews/CD009532/{run_id}.md",
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
    print(f"Included-study matches: {sum(row['ground_truth_status'] == 'included' for row in rows)}")
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
