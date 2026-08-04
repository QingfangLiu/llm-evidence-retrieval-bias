#!/usr/bin/env python3
"""Analyze CD001452 using only each response's terminal study list.

The extractor implements the review-specific boundary documented in README.md.
It reads the Cochrane data package directly from its ZIP archive, resolves every
listed citation to a study cluster, validates Cochrane labels against the RIS
exports, and writes the review's auditable role-study match table.
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
    / "source_reviews"
    / "2026_issue_7"
    / "CD001452-SUP-06-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd001452_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 75, "gemini": 37, "gpt": 102}
EXPECTED_RESPONSE_STUDY_ROWS = 214
RIS_MEMBERS = {
    "included": "CD001452-study-data/CD001452-included.ris",
    "cochrane_excluded": "CD001452-study-data/CD001452-excluded.ris",
    "cochrane_ongoing": "CD001452-study-data/CD001452-ongoing.ris",
}
CLAUDE_REVIEW_USE_RUNS = {
    "claude-clinician-2",
    "claude-clinician-4",
    "claude-patient-1",
    "claude-patient-3",
    "claude-researcher-1",
    "claude-researcher-2",
    "claude-researcher-3",
    "claude-researcher-4",
}
CSV_FIELDS = (
    "run_id",
    "model",
    "role_id",
    "replicate",
    "source_file",
    "reported_citation",
    "canonical_candidate",
    "ground_truth_status",
    "cochrane_study_label",
    "design",
    "identity_issue",
    "notes",
)


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD001452 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_labels: tuple[str, ...] = ()
    design: str = ""
    note: str = ""


CANDIDATES = {
    # All eight Cochrane-included study clusters.
    "alcaraz_1998": CandidateInfo(
        "Alcaraz Sanz 1998",
        "included",
        ("Alcaraz Sanz 1998",),
        "controlled comparative study",
    ),
    "eriksson_1999": CandidateInfo(
        "Eriksson 1999",
        "included",
        ("Eriksson 1999",),
        "randomized factorial trial",
    ),
    "kvist_2002": CandidateInfo(
        "Kvist 2002",
        "included",
        ("Kvist 2002",),
        "randomized controlled trial",
    ),
    "larsson_1998": CandidateInfo(
        "Larsson 1998",
        "included",
        ("Larsson 1998",),
        "randomized controlled trial",
        "The Pediatrics report and Rao commentary share one Cochrane study label.",
    ),
    "ogawa_2005": CandidateInfo(
        "Ogawa 2005",
        "included",
        ("Ogawa 2005",),
        "randomized factorial trial",
    ),
    "saththasivam_2009": CandidateInfo(
        "Saththasivam 2009",
        "included",
        ("Saththasivam 2009",),
        "controlled comparative study",
    ),
    "shah_1997": CandidateInfo(
        "Shah 1997",
        "included",
        ("Shah 1997",),
        "randomized controlled trial",
    ),
    "shrestha_2012": CandidateInfo(
        "Shrestha 2012",
        "included",
        ("Shrestha 2012",),
        "controlled comparative study",
    ),
    # All four Cochrane-excluded study labels.
    "bomben_2011": CandidateInfo(
        "Bomben 2011",
        "cochrane_excluded",
        ("Bomben 2011",),
        "conference abstract",
    ),
    "correcher_2012": CandidateInfo(
        "Correcher 2012",
        "cochrane_excluded",
        ("Correcher 2012",),
        "nonrandomized comparative study",
        "The source review excludes this study because it was not randomized.",
    ),
    "logan_1999": CandidateInfo(
        "Logan 1999",
        "cochrane_excluded",
        ("Logan 1999",),
        "nonrandomized comparative study",
        "The source review excludes this study because it was not randomized.",
    ),
    "shah_2006": CandidateInfo(
        "Shah 2006",
        "cochrane_excluded",
        ("Shah 2006",),
        "uncontrolled study",
    ),
    # The one ongoing study in the source package.
    "rbr_2wkqpw": CandidateInfo(
        "RBR-2wkqpw",
        "cochrane_ongoing",
        ("RBR-2wkqpw",),
        "ongoing randomized clinical trial",
    ),
    # Explicitly listed primary-study candidates outside the classified sets.
    "cavicchiolo_2022": CandidateInfo(
        "Cavicchiolo 2022",
        "invalid_comparison",
        design="randomized sucrose-dose trial",
        note="The study evaluates sucrose dosing during venepuncture and has no heel-lance comparator.",
    ),
    "larsson_emla_1998": CandidateInfo(
        "Larsson 1998 EMLA trial",
        "invalid_comparison",
        design="randomized placebo-controlled analgesia trial",
        note="The study compares EMLA with placebo before venepuncture and has no heel-lance arm.",
    ),
    "lorey_1994": CandidateInfo(
        "Lorey 1994",
        "outside_other",
        design="newborn-screening specimen-method study",
        note="The study is outside the Cochrane classified sets and focuses on screening-test measurements.",
    ),
    "taksande_2005": CandidateInfo(
        "Taksande 2005",
        "invalid_comparison",
        design="venepuncture pain-response study",
        note="The study evaluates pain during venepuncture and has no heel-lance comparator.",
    ),
}


def normalize(text: str) -> str:
    """Normalize response text for stable review-specific matching."""

    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def response_paths() -> list[Path]:
    """Return and validate the complete 3-by-3-by-4 response inventory."""

    paths = sorted(
        path
        for path in REVIEW_DIR.glob("*.md")
        if re.fullmatch(
            r"(?:claude|gemini|gpt)-(?:patient|clinician|researcher)-[1-4]",
            path.stem,
        )
    )
    expected = {
        f"{model}-{role}-{replicate}"
        for model in MODELS
        for role in ROLES
        for replicate in range(1, 5)
    }
    actual = {path.stem for path in paths}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"Response inventory mismatch; missing={missing}; extra={extra}")
    return paths


def last_heading_index(lines: list[str], prefixes: tuple[str, ...]) -> int:
    """Return the last heading-like line whose normalized text has a prefix."""

    indexes = [
        index
        for index, line in enumerate(lines)
        if (line.startswith("#") or line.startswith("**"))
        and normalize(line).startswith(prefixes)
    ]
    if not indexes:
        raise ValueError(f"No qualifying terminal-list heading: {prefixes}")
    return indexes[-1]


def extract_claude_list(path: Path, lines: list[str]) -> list[str]:
    """Extract Claude's final explicit study-list entries."""

    if path.stem == "claude-patient-2":
        start = last_heading_index(lines, ("reference list",))
    else:
        start = last_heading_index(lines, ("primary studies", "list of primary studies"))

    entries: list[str] = []
    stop_prefixes = (
        "a couple of notes",
        "a few additional notes",
        "a few notes",
        "a note on completeness",
        "a note on scope",
        "a note on sourcing",
        "if it would help",
        "if you want",
    )
    for line in lines[start + 1 :]:
        normalized = normalize(line)
        if entries and normalized.startswith(stop_prefixes):
            break
        if match := re.match(r"^(?:\*\*)?\d+\.\s+(.+)$", line):
            entries.append(match.group(1).strip())
        elif (
            path.stem == "claude-researcher-2"
            and re.match(r"^-\s+", line)
            and "taksande" in normalized
        ):
            entries.append(re.sub(r"^-\s+", "", line).strip())
    if not entries:
        raise ValueError(f"No Claude terminal-list entries in {path.name}")
    return entries


def extract_gemini_list(path: Path, lines: list[str]) -> list[str]:
    """Extract Gemini references while excluding its `Cited by` metadata."""

    entries: list[str] = []
    for index, line in enumerate(lines):
        if not line.startswith("Cited by:"):
            continue
        previous = index - 1
        while previous >= 0 and not lines[previous].strip():
            previous -= 1
        if previous < 0:
            raise ValueError(f"Missing citation before `Cited by` in {path.name}")
        entries.append(lines[previous].strip())
    if entries:
        return entries

    if path.stem != "gemini-clinician-3":
        raise ValueError(f"No Gemini terminal references in {path.name}")
    start = last_heading_index(lines, ("requested primary studies",))
    entries = [
        match.group(1).strip()
        for line in lines[start + 1 :]
        if (match := re.match(r"^\*\s+(.+)$", line))
    ]
    if not entries:
        raise ValueError(f"No Gemini bullet-list entries in {path.name}")
    return entries


def extract_gpt_list(path: Path, lines: list[str]) -> list[str]:
    """Extract GPT's final numbered primary-study list."""

    start = last_heading_index(lines, ("primary studies", "individual primary studies"))
    entries = [
        match.group(1).strip()
        for line in lines[start + 1 :]
        if (match := re.match(r"^\d+\.\s+(.+)$", line))
    ]
    if not entries:
        raise ValueError(f"No GPT terminal-list entries in {path.name}")
    return entries


def extract_terminal_list(path: Path) -> list[str]:
    """Extract only entries inside one response's terminal study list."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if path.stem.startswith("claude-"):
        return extract_claude_list(path, lines)
    if path.stem.startswith("gemini-"):
        return extract_gemini_list(path, lines)
    return extract_gpt_list(path, lines)


def resolve_candidate(entry: str) -> str:
    """Resolve one terminal-list entry to its canonical candidate."""

    text = normalize(entry)
    if "pain associated with neonatal test" in text or "alcaraz sanz" in text:
        return "alcaraz_1998"
    if "oral glucose and venepuncture reduce blood sampling pain" in text:
        return "eriksson_1999"
    if "can venepuncture reduce the pain of neonatal pku" in text:
        return "kvist_2002"
    if "alleviation of the pain of venepuncture" in text:
        return "larsson_emla_1998"
    if "venipuncture is more effective and less painful than heel lancing" in text:
        return "larsson_1998"
    if "venepuncture is preferable to heel lance" in text:
        return "ogawa_2005"
    if "venipuncture versus heel prick for blood glucose monitoring" in text:
        return "saththasivam_2009"
    if "comparison of pain response to venepuncture versus heel lance" in text:
        return "shrestha_2012"
    if "neonatal pain response to heel" in text and "venepuncture" in text:
        if "2006" in text or "shah v a" in text or "wang f" in text:
            return "shah_2006"
        return "shah_1997"
    if "venepunture is less painful more effective and less expensive" in text:
        return "bomben_2011"
    if (
        "back of the hand venepuncture" in text
        or "venopunci n en el dorso de la mano" in text
        or "venopuncion en el dorso de la mano" in text
    ):
        return "correcher_2012"
    if "venepuncture versus heel prick for the collection of the newborn screening test" in text:
        return "logan_1999"
    if "hand puncture in relieving pain" in text or "rbr 2wkqpw" in text:
        return "rbr_2wkqpw"
    if "a single dose of oral sucrose is enough to control pain" in text:
        return "cavicchiolo_2022"
    if "effect of specimen collection method on newborn screening for pku" in text:
        return "lorey_1994"
    if "pain response of neonates to venipuncture" in text:
        return "taksande_2005"
    raise ValueError(f"Unresolved terminal-list citation: {entry}")


def citation_identity_note(entry: str, key: str) -> str:
    """Return an audit note when citation details conflict with the source."""

    text = normalize(entry)
    if key == "kvist_2002" and (
        "22 1 27 29" in text or "22 3 27 30" in text or "22 1 27 30" in text
    ):
        return (
            "The title identifies Kvist 2002, but the response supplies a "
            "conflicting issue number or page range."
        )
    if key == "logan_1999" and "17 2 30" in text:
        return (
            "The title identifies Logan 1999, but the response supplies issue "
            "2 rather than issue 1."
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


def validate_candidate_labels() -> None:
    """Require candidate Cochrane labels to equal the current RIS truth sets."""

    for status, member in RIS_MEMBERS.items():
        expected = ris_study_labels(member)
        configured = {
            label
            for candidate in CANDIDATES.values()
            if candidate.status == status
            for label in candidate.cochrane_labels
        }
        if configured != expected:
            raise ValueError(
                f"{status} labels mismatch; "
                f"missing={sorted(expected - configured)}; "
                f"extra={sorted(configured - expected)}"
            )


def parse_run_id(path: Path) -> tuple[str, str, int]:
    """Return model, role, and replicate from a validated response filename."""

    model, role, replicate_text = path.stem.split("-")
    return model, role, int(replicate_text)


def build_match_rows() -> tuple[list[dict[str, str | int]], dict[str, int]]:
    """Resolve terminal entries and deduplicate study clusters within runs."""

    validate_candidate_labels()
    rows: list[dict[str, str | int]] = []
    raw_counts: dict[str, int] = {}
    model_counts: Counter[str] = Counter()

    for path in response_paths():
        model, role, replicate = parse_run_id(path)
        entries = extract_terminal_list(path)
        raw_counts[path.stem] = len(entries)
        model_counts[model] += len(entries)
        grouped: dict[str, list[str]] = defaultdict(list)
        for entry in entries:
            grouped[resolve_candidate(entry)].append(entry)

        for key, citations in grouped.items():
            info = CANDIDATES[key]
            identity_notes = {
                note
                for citation in citations
                if (note := citation_identity_note(citation, key))
            }
            notes = [info.note] if info.note else []
            notes.extend(sorted(identity_notes))
            if len(citations) > 1:
                notes.append(
                    f"Grouped {len(citations)} terminal-list citations to one study cluster."
                )
            rows.append(
                {
                    "run_id": path.stem,
                    "model": model,
                    "role_id": role,
                    "replicate": replicate,
                    "source_file": str(path.relative_to(REPO_ROOT)),
                    "reported_citation": " || ".join(dict.fromkeys(citations)),
                    "canonical_candidate": info.label,
                    "ground_truth_status": info.status,
                    "cochrane_study_label": " || ".join(info.cochrane_labels),
                    "design": info.design,
                    "identity_issue": int(bool(identity_notes)),
                    "notes": "; ".join(notes),
                }
            )

    if dict(model_counts) != EXPECTED_LIST_ENTRIES:
        raise ValueError(
            f"Terminal-list entry counts changed: {dict(model_counts)} "
            f"!= {EXPECTED_LIST_ENTRIES}"
        )
    if len(rows) != EXPECTED_RESPONSE_STUDY_ROWS:
        raise ValueError(
            f"Response-study row count changed: {len(rows)} "
            f"!= {EXPECTED_RESPONSE_STUDY_ROWS}"
        )
    return rows, raw_counts


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write the standard retrieval-bias audit-table schema."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def included_labels(row: dict[str, str | int]) -> set[str]:
    """Return included Cochrane labels represented by one audit row."""

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

    print(f"Runs: {len(response_paths())}")
    print(f"Terminal-list entries: {sum(raw_counts.values())}")
    print(f"Response-study rows: {len(rows)}")
    print(
        f"Source truth: {len(included_truth)} included labels; "
        f"{len(included_pmid_truth)} explicit PubMed IDs"
    )
    for model in MODELS:
        run_ids = [run_id for run_id in raw_counts if run_id.startswith(f"{model}-")]
        print(
            f"{model}: {sum(raw_counts[run_id] for run_id in run_ids)} entries; "
            f"{sum(len(by_run[run_id]) for run_id in run_ids)} response-study rows"
        )

    print("Model-role summary:")
    for model in MODELS:
        for role in ROLES:
            run_ids = [
                f"{model}-{role}-{replicate}" for replicate in range(1, 5)
            ]
            retrieved_by_run = [
                set().union(*(included_labels(row) for row in by_run[run_id]))
                for run_id in run_ids
            ]
            included_matches = sum(len(labels) for labels in retrieved_by_run)
            pooled = set().union(*retrieved_by_run)
            pooled_pmids = {
                pmid for label in pooled for pmid in included_pmids.get(label, set())
            }
            print(
                f"  {model}-{role}: "
                f"entries={sum(raw_counts[run_id] for run_id in run_ids)}; "
                f"rows={sum(len(by_run[run_id]) for run_id in run_ids)}; "
                f"included={included_matches}; "
                f"mean_recall={included_matches / (4 * len(included_truth)):.1%}; "
                f"pooled={len(pooled)}/{len(included_truth)}; "
                f"pooled_cluster_pmids={len(pooled_pmids)}/{len(included_pmid_truth)}"
            )

    pooled_all = set().union(
        *(
            included_labels(row)
            for run_rows in by_run.values()
            for row in run_rows
        )
    )
    missed_all = sorted(included_truth - pooled_all)
    pooled_all_pmids = {
        pmid for label in pooled_all for pmid in included_pmids.get(label, set())
    }
    missed_pmids = sorted(included_pmid_truth - pooled_all_pmids)
    print(
        f"Pooled all runs: {len(pooled_all)}/{len(included_truth)} labels; "
        f"missed labels={','.join(missed_all) or 'none'}"
    )
    print(
        f"Pooled cluster-associated PMIDs: "
        f"{len(pooled_all_pmids)}/{len(included_pmid_truth)}; "
        f"missed PMIDs={','.join(missed_pmids) or 'none'}"
    )

    status_counts = Counter(str(row["ground_truth_status"]) for row in rows)
    print(
        "Audit statuses: "
        + "; ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
    )
    frequencies = Counter(
        label
        for row in rows
        for label in included_labels(row)
    )
    print(
        "Included-study frequency: "
        + "; ".join(
            f"{label}={frequencies.get(label, 0)}" for label in sorted(included_truth)
        )
    )

    deviating_included = sum(
        len(
            set().union(
                *(included_labels(row) for row in by_run[run_id])
            )
        )
        for run_id in CLAUDE_REVIEW_USE_RUNS
    )
    other_claude_runs = [
        run_id
        for run_id in by_run
        if run_id.startswith("claude-") and run_id not in CLAUDE_REVIEW_USE_RUNS
    ]
    other_included = sum(
        len(
            set().union(
                *(included_labels(row) for row in by_run[run_id])
            )
        )
        for run_id in other_claude_runs
    )
    print(
        f"Claude disclosed-review-use runs: "
        f"{deviating_included}/{len(CLAUDE_REVIEW_USE_RUNS) * len(included_truth)} "
        f"included matches; other Claude runs: "
        f"{other_included}/{len(other_claude_runs) * len(included_truth)}"
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
        run_missed_pmids = sorted(included_pmid_truth - retrieved_pmids)
        print(
            f"  {run_id}: {len(retrieved)}/{len(included_truth)}; "
            f"cluster-associated PMIDs={len(retrieved_pmids)}/{len(included_pmid_truth)}; "
            f"missed labels={','.join(missing) or 'none'}; "
            f"missed PMIDs={','.join(run_missed_pmids) or 'none'}"
        )
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the terminal-list-only curated match table for CD001452."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
