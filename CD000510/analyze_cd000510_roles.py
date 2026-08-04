#!/usr/bin/env python3
"""Analyze CD000510 using only each response's terminal study list.

The extractor implements the review-specific boundary documented in README.md.
It reads the Cochrane data package directly from its ZIP archive, resolves every
listed citation to a study cluster, deduplicates companion reports within a
response, validates Cochrane labels against the RIS exports, and writes the
review's audit table.
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
    / "CD000510-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd000510_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 143, "gemini": 42, "gpt": 200}
EXPECTED_RESPONSE_STUDY_ROWS = 351
RIS_MEMBERS = {
    "included": "CD000510-study-data/CD000510-included.ris",
    "cochrane_excluded": "CD000510-study-data/CD000510-excluded.ris",
    "cochrane_awaiting": "CD000510-study-data/CD000510-awaiting.ris",
    "cochrane_ongoing": "CD000510-study-data/CD000510-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD000510 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_labels: tuple[str, ...] = ()
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All 10 Cochrane-included study clusters.
    "bevilacqua_1996": CandidateInfo(
        "Bevilacqua 1996",
        "included",
        ("Bevilacqua 1996",),
        "randomized controlled trial",
    ),
    "bevilacqua_1997": CandidateInfo(
        "Bevilacqua 1997",
        "included",
        ("Bevilacqua 1997",),
        "randomized controlled trial",
    ),
    "dunn_1991": CandidateInfo(
        "Dunn 1991", "included", ("Dunn 1991",), "randomized controlled trial"
    ),
    "dunn_2011": CandidateInfo(
        "Dunn 2011",
        "included",
        ("Dunn 2011",),
        "randomized controlled trial",
        "The trial registration, meeting abstract, and journal article are one study cluster.",
    ),
    "egberts_1993": CandidateInfo(
        "Egberts 1993",
        "included",
        ("Egberts 1993",),
        "randomized controlled trial",
    ),
    "kattwinkel_1993": CandidateInfo(
        "Kattwinkel 1993",
        "included",
        ("Kattwinkel 1993",),
        "randomized controlled trial",
    ),
    "kendig_1991": CandidateInfo(
        "Kendig 1991",
        "included",
        ("Kendig 1991",),
        "randomized controlled trial",
        "The 1998 Sinkin school-age follow-up is grouped with the original trial.",
    ),
    "merritt_1991": CandidateInfo(
        "Merritt 1991",
        "included",
        ("Merritt 1991",),
        "randomized controlled trial",
        "The 1993 Vaucher follow-up is grouped with the original trial.",
    ),
    "support_2010": CandidateInfo(
        "SUPPORT 2010",
        "included",
        ("SUPPORT 2010",),
        "randomized controlled trial",
        "The 2012 neurodevelopmental and 2014 respiratory follow-ups are grouped with SUPPORT.",
    ),
    "walti_1995": CandidateInfo(
        "Walti 1995", "included", ("Walti 1995",), "randomized controlled trial"
    ),
    # Candidate publications represented in the Cochrane excluded RIS.
    "iarukova_1999": CandidateInfo(
        "Iarŭkova 1999",
        "cochrane_excluded",
        ("Iarŭkova 1999",),
        "retrospective comparative study",
    ),
    "morley_2008": CandidateInfo(
        "Morley 2008 (COIN)",
        "cochrane_excluded",
        ("Morley 2008",),
        "randomized controlled trial",
    ),
    "rojas_2009": CandidateInfo(
        "Rojas 2009",
        "cochrane_excluded",
        ("Rojas 2009",),
        "randomized controlled trial",
    ),
    "sandri_2010": CandidateInfo(
        "Sandri 2010 (CURPAP)",
        "cochrane_excluded",
        ("Sandri 2010",),
        "randomized controlled trial",
    ),
    # Awaiting-classification and ongoing studies represented in the RIS exports.
    "murphy_2024": CandidateInfo(
        "Murphy 2024 (POPART)",
        "cochrane_awaiting",
        ("Murphy 2024",),
        "randomized controlled trial",
        "The protocol and results publication are one study cluster.",
    ),
    "prolisa": CandidateInfo(
        "pro.LISA",
        "cochrane_ongoing",
        ("DRKS00028086",),
        "ongoing randomized controlled trial",
        "The response commonly cites the published protocol rather than results.",
    ),
    # Identifiable candidates outside the Cochrane classified sets.
    "merritt_1986": CandidateInfo(
        "Merritt 1986",
        "outside_other",
        design="randomized controlled trial",
    ),
    "egberts_1997_pooled": CandidateInfo(
        "Egberts 1997 pooled Curosurf analysis",
        "outside_other",
        design="pooled analysis of randomized trials",
    ),
    "bevilacqua_moderate_rds": CandidateInfo(
        "Bevilacqua moderately severe RDS trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "bevilacqua_observes": CandidateInfo(
        "Bevilacqua 2003 OBSERVES",
        "outside_observational",
        design="observational comparative study",
    ),
    "kendig_1998": CandidateInfo(
        "Kendig 1998 two-prophylaxis-strategy trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "osiris_1992": CandidateInfo(
        "OSIRIS 1992",
        "outside_other",
        design="randomized controlled trial",
    ),
    "dambeanu_1997": CandidateInfo(
        "Dambeanu 1997",
        "outside_other",
        design="randomized pilot trial",
    ),
    "gortner_1998": CandidateInfo(
        "Gortner 1998",
        "outside_other",
        design="controlled clinical trial",
    ),
    "chu_2006": CandidateInfo(
        "Chu 2006 Tianjin trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "kandraju_2013": CandidateInfo(
        "Kandraju 2013",
        "outside_other",
        design="randomized controlled trial",
    ),
    "kim_2014": CandidateInfo(
        "Kim 2014 Korean multicenter cohort",
        "outside_observational",
        design="retrospective multicenter cohort study",
    ),
    "chun_2017": CandidateInfo(
        "Chun 2017",
        "outside_observational",
        design="comparative cohort study",
    ),
    "koch_2010": CandidateInfo(
        "Koch 2010",
        "outside_observational",
        design="retrospective comparative study",
    ),
    "kong_2016": CandidateInfo(
        "Kong 2016 Chinese pilot study",
        "outside_observational",
        design="prospective nonrandomized controlled trial",
    ),
    "sunset_2023": CandidateInfo(
        "SUNSET 2023",
        "outside_other",
        design="randomized controlled trial",
    ),
    "amv_2011": CandidateInfo(
        "Göpel 2011 AMV trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "verder_1994": CandidateInfo(
        "Verder 1994",
        "outside_other",
        design="randomized controlled trial",
    ),
    "rong_2019": CandidateInfo(
        "Rong 2019",
        "outside_other",
        design="randomized controlled trial",
    ),
    "katheria_cali": CandidateInfo(
        "Katheria CaLI trial",
        "outside_other",
        design="randomized controlled trial",
        note="The 2026 Dorner two-year report is grouped with the original CaLI trial.",
    ),
    "kakkilaya_2026": CandidateInfo(
        "Kakkilaya 2026 delivery-room LISA trial",
        "outside_other",
        design="randomized pilot trial",
    ),
    "pelkonen_1998": CandidateInfo(
        "Pelkonen 1998 school-age lung-function follow-up",
        "outside_other",
        design="follow-up study",
    ),
    "osborn_click_test": CandidateInfo(
        "Osborn click-test surfactant study",
        "outside_unresolved",
        design="vaguely specified primary study",
    ),
}


def normalize(text: str) -> str:
    """Normalize response text for stable review-specific matching."""

    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def resolve_candidate(entry: str) -> tuple[str, ...]:
    """Resolve one terminal-list entry to one or more study clusters."""

    text = normalize(entry)
    if "use of surfactant for prophylaxis versus rescue treatment" in text:
        keys = ["bevilacqua_1997"]
        if "prophylaxis of respiratory distress syndrome by treatment" in text:
            keys.append("bevilacqua_1996")
        return tuple(keys)
    if "prophylaxis of respiratory distress syndrome by treatment" in text:
        return ("bevilacqua_1996",)
    if "observational study of surfactant treatment" in text or "observes group" in text:
        return ("bevilacqua_observes",)
    if "moderately severe neonatal respiratory distress syndrome" in text:
        return ("bevilacqua_moderate_rds",)
    if "bovine surfactant replacement therapy in neonates of less than 30 weeks" in text:
        return ("dunn_1991",)
    if (
        "randomized trial comparing 3 approaches" in text
        or "randomized trial comparing three approaches" in text
    ) or (
        "delivery room management" in text and "vermont oxford" in text
    ):
        return ("dunn_2011",)
    if "comparison of prophylaxis and rescue treatment with curosurf" in text or (
        text.startswith("egberts") and "cochrane included" in text
    ):
        return ("egberts_1993",)
    if "mortality severe respiratory distress syndrome" in text and "curosurf" in text:
        return ("egberts_1997_pooled",)
    if "prophylactic administration of calf lung surfactant extract" in text:
        return ("kattwinkel_1993",)
    if "comparison of surfactant as immediate prophylaxis and as rescue therapy" in text:
        return ("kendig_1991",)
    if "school age follow up of prophylactic versus rescue surfactant" in text:
        return ("kendig_1991",)
    if "comparison of two strategies for surfactant prophylaxis" in text:
        return ("kendig_1998",)
    if "randomized placebo controlled trial of human surfactant" in text or (
        text.startswith("merritt ta") and "1991 prophylactic vs rescue trial" in text
    ):
        return ("merritt_1991",)
    if "outcome at twelve months" in text or "one year follow up" in text:
        return ("merritt_1991",)
    if "prophylactic treatment of very premature infants with human surfactant" in text:
        return ("merritt_1986",)
    if "early cpap versus surfactant" in text:
        return ("support_2010",)
    if "neurodevelopmental outcomes in the early cpap" in text:
        return ("support_2010",)
    if "respiratory outcomes of the surfactant positive pressure" in text:
        return ("support_2010",)
    if "prophylactic vs selective use of surfactant" in text and "walti" in text:
        return ("walti_1995",)
    if "porcine surfactant replacement therapy in newborns of 25" in text:
        return ("walti_1995",)
    if (
        "administration of exogenous surfactant in very low birth weight" in text
        or ("bulgarian trial" in text and "1999" in text)
    ):
        return ("iarukova_1999",)
    if "nasal cpap or intubation at birth" in text or "coin trial" in text:
        return ("morley_2008",)
    if "very early surfactant without mandatory ventilation" in text:
        return ("rojas_2009",)
    if (
        "prophylactic or early selective surfactant combined with ncpap" in text
        or "prophylactic or early selective surfactant combined with nasal continuous" in text
    ):
        return ("sandri_2010",)
    if "prophylactic oropharyngeal surfactant" in text or "popart" in text:
        return ("murphy_2024",)
    if "pro lisa" in text:
        return ("prolisa",)
    if "early versus delayed neonatal administration" in text and "osiris" in text:
        return ("osiris_1992",)
    if "spontaneous breathing" in text and "dambeanu" in text:
        return ("dambeanu_1997",)
    if "early versus late surfactant treatment" in text and "gortner" in text:
        return ("gortner_1998",)
    if "protective and curative effects" in text or "tianjin study investigators" in text:
        return ("chu_2006",)
    if "early routine versus late selective surfactant" in text:
        return ("kandraju_2013",)
    if (
        "53 multi" in text
        or "53 neonatal intensive care units" in text
        or (text.startswith("kim") and "early prophylactic versus late selective" in text)
    ):
        return ("kim_2014",)
    if (
        "prophylactic versus early rescue surfactant treatment" in text
        or text.startswith("chun")
    ):
        return ("chun_2017",)
    if "prophylactic administration of surfactant in extremely premature infants" in text:
        return ("koch_2010",)
    if "bovine surfactant replacement therapy in neonates of less than 32 weeks" in text:
        return ("kong_2016",)
    if (
        "sunset trial" in text
        or "surfactant nebulisation for early aeration" in text
        or "surfactant nebulisation for the early aeration" in text
    ):
        return ("sunset_2023",)
    if "avoidance of mechanical ventilation by surfactant treatment" in text:
        return ("amv_2011",)
    if "surfactant therapy and nasal continuous positive airway pressure" in text:
        return ("verder_1994",)
    if "multicentered randomized study on early versus rescue calsurf" in text:
        return ("rong_2019",)
    if "caffeine and less invasive surfactant administration" in text:
        return ("katheria_cali",)
    if "two year outcomes after caffeine and less invasive surfactant" in text:
        return ("katheria_cali",)
    if "less invasive surfactant administration in the delivery room" in text:
        return ("kakkilaya_2026",)
    if "effect of neonatal surfactant therapy on lung function at school age" in text:
        return ("pelkonen_1998",)
    if "click test" in text and "osborn" in text:
        return ("osborn_click_test",)
    raise ValueError(f"Unresolved terminal-list citation: {entry}")


def citation_identity_note(entry: str, key: str) -> str:
    """Return an audit note when a citation resolves despite conflicting details."""

    text = normalize(entry)
    if key == "bevilacqua_1997" and (
        "j perinat med" in text or "1996 24 1 12" in text
    ) and "prophylaxis of respiratory distress syndrome by treatment" not in text:
        return (
            "The title identifies Bevilacqua 1997, but the response supplies "
            "publication details from another report."
        )
    if key == "bevilacqua_1996" and "24 1 12" in text:
        return "The title identifies Bevilacqua 1996, but the response supplies conflicting pages."
    if key == "bevilacqua_moderate_rds" and "1997" in text:
        return (
            "The title identifies the moderately severe RDS trial, but the "
            "response supplies the wrong publication year."
        )
    if key == "kattwinkel_1993" and "less than 29 weeks" in text:
        return (
            "The title identifies Kattwinkel 1993, but the response supplies "
            "the wrong gestational-age range."
        )
    if key == "kattwinkel_1993" and "delayed treatment in neonates 29 weeks" in text:
        return (
            "The title identifies Kattwinkel 1993, but the response changes "
            "both the comparator wording and gestational-age range."
        )
    if key == "kendig_1991" and text.startswith("vaucher"):
        return (
            "The follow-up title identifies Kendig 1991, but the response "
            "supplies authors and publication details from the Merritt follow-up."
        )
    if key == "merritt_1991" and text.startswith("merritt") and "outcome at twelve months" in text:
        return (
            "The follow-up title identifies Merritt 1991, but the response "
            "supplies the original trial's lead author."
        )
    if key == "kim_2014" and text.startswith("konkel"):
        return (
            "The title identifies Kim 2014, but the response supplies a "
            "conflicting lead author."
        )
    if key == "kong_2016" and text.startswith("feng"):
        return (
            "The title identifies Kong 2016, but the response supplies a "
            "conflicting lead author."
        )
    if key == "walti_1995" and ("biol neonate" in text or "franco belgian" in text):
        return (
            "The author and comparison identify Walti 1995, but the response "
            "supplies conflicting publication details."
        )
    return ""


def zip_text(member: str) -> str:
    """Read one UTF-8 text member directly from the Cochrane ZIP package."""

    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(member).decode("utf-8-sig")


def ris_study_labels(member: str) -> set[str]:
    """Read unique Cochrane study labels from one RIS member in the ZIP."""

    return {
        match.group(1).strip()
        for match in re.finditer(r"^NS  - (.+)$", zip_text(member), re.MULTILINE)
    }


def ris_pubmed_ids(member: str) -> dict[str, set[str]]:
    """Return explicit PubMed IDs grouped by Cochrane study label."""

    identifiers: dict[str, set[str]] = defaultdict(set)
    for record in re.split(r"^ER  -\s*$", zip_text(member), flags=re.MULTILINE):
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


def extract_terminal_list(path: Path) -> list[str]:
    """Extract only entries inside the response's dedicated terminal list."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if path.stem == "claude-researcher-4":
        start = next(
            index
            for index, line in enumerate(lines)
            if normalize(line).startswith("core trials directly comparing")
        )
        entries = [
            match.group(1).strip()
            for line in lines[start + 1 :]
            if (match := re.match(r"^\d+\.\s+(.+)$", line))
        ]
        entries.extend(
            match.group(1).strip()
            for line in lines[start + 1 :]
            if (match := re.match(r"^-\s+(.+)$", line))
            and "early prophylactic versus late selective use" in normalize(line)
        )
        if entries:
            return entries
        raise ValueError(f"No cohesive study-list entries in {path.name}")

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
                "final list of primary studies",
            )
        ):
            heading_indexes.append(index)
    if not heading_indexes:
        raise ValueError(f"No terminal study-list heading in {path.name}")

    block = lines[heading_indexes[-1] + 1 :]
    if path.stem.startswith("gemini-"):
        entries = [
            block[index - 1].strip()
            for index, line in enumerate(block)
            if line.startswith("Cited by:") and index > 0 and block[index - 1].strip()
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
                    "source_file": f"retrieval_bias/CD000510/{path.name}",
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
        missing = sorted(included_truth - retrieved)
        retrieved_pmids = {
            pmid for label in retrieved for pmid in included_pmids.get(label, set())
        }
        missed_pmids = sorted(
            pmid for label in missing for pmid in included_pmids.get(label, set())
        )
        print(
            f"  {run_id}: {len(retrieved)}/{len(included_truth)}; "
            f"cluster-associated PMIDs={len(retrieved_pmids)}/{len(included_pmid_truth)}; "
            f"missed labels={','.join(missing) or 'none'}; "
            f"missed PMIDs={','.join(missed_pmids) or 'none'}"
        )
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the terminal-list-only curated match table for CD000510."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
