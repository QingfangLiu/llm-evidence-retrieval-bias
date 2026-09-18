"""Audit review-source evidence visible in the saved chatbot answers.

This screen finds passages for human review; it cannot reconstruct browser
search results or prove that an unmentioned source was not consulted.

Run ``python3 scripts/audit_review_use.py`` to write a compact passage screen.
After manually coding every flagged response in the decisions CSV, run with
``--finalize`` to validate the decisions and write the full audit and summary.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEWS_DIR = ROOT / "reviews"
SCREEN_PATH = ROOT / "data/analysis/review_use_screen.csv"
DECISIONS_PATH = ROOT / "data/curation/review_use_decisions.csv"
AUDIT_PATH = ROOT / "data/analysis/review_use_audit.csv"
SUMMARY_PATH = ROOT / "data/analysis/review_use_by_system.csv"

RESPONSE_NAME = re.compile(
    r"^(claude|gemini|gpt)-(patient|clinician|researcher)-([1-4])\.md$"
)
COCHRANE = re.compile(r"cochrane|cochranelibrary|10\.1002/14651858", re.I)
REVIEW_SOURCE_PHRASES = re.compile(
    r"(?:\b(?:used?|using|consulted|sourced|pulled|derived|based on|cited in|"
    r"found in|identified from)\b.{0,70}\b(?:reviews?|meta.analysis|narrative synthesis)\b|"
    r"\b(?:reviews?|meta.analysis|narrative synthesis)\b.{0,70}\b(?:used?|"
    r"consulted|sourced|reference lists?|citation lists?|included.studies lists?|"
    r"found in search|came up in search)\b|"
    r"\breviews?'?s? (?:reference|citation|included.studies) lists?\b)",
    re.I,
)
DETAILED_IDENTITIES = (
    "confirmed_target_2026",
    "probable_target_2026",
    "named_prior",
    "unspecified_cochrane",
    "not_applicable",
)
DETAILED_EVIDENCE_LEVELS = (
    "used_study_identification",
    "used_review_information",
    "reported_hit",
    "mention_only",
    "no_detected",
)
IDENTITY_GROUP = {
    "confirmed_target_2026": "matching_2026_cochrane",
    "probable_target_2026": "matching_2026_cochrane",
    "named_prior": "older_or_unspecified_cochrane",
    "unspecified_cochrane": "older_or_unspecified_cochrane",
    "not_applicable": "not_applicable",
}
EVIDENCE_GROUP = {
    "used_study_identification": "used_study_identification",
    "used_review_information": "review_mentioned",
    "reported_hit": "review_mentioned",
    "mention_only": "review_mentioned",
    "no_detected": "no_detected",
}
IDENTITIES = (
    "matching_2026_cochrane",
    "older_or_unspecified_cochrane",
    "not_applicable",
)
EVIDENCE_LEVELS = ("used_study_identification", "review_mentioned", "no_detected")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def inventory() -> list[dict[str, object]]:
    review_dirs = sorted(path for path in REVIEWS_DIR.iterdir() if path.is_dir())
    if len(review_dirs) != 20:
        raise ValueError(f"Expected 20 review folders, found {len(review_dirs)}")
    rows = []
    for review_dir in review_dirs:
        if not re.fullmatch(r"CD\d{6}", review_dir.name):
            raise ValueError(f"Unexpected review folder: {review_dir.name}")
        response_paths = sorted(
            path for path in review_dir.glob("*.md") if path.name != "README.md"
        )
        if len(response_paths) != 36:
            raise ValueError(f"{review_dir.name}: expected 36 answers, found {len(response_paths)}")
        seen = set()
        for path in response_paths:
            match = RESPONSE_NAME.fullmatch(path.name)
            if not match:
                raise ValueError(f"Unexpected response filename: {path}")
            model, role, replicate = match.groups()
            cell = (model, role, replicate)
            if cell in seen:
                raise ValueError(f"Duplicate response cell: {path}")
            seen.add(cell)
            rows.append(
                {
                    "review_id": review_dir.name,
                    "model": model,
                    "role": role,
                    "replicate": replicate,
                    "source_file": str(path.relative_to(ROOT)),
                    "path": path,
                }
            )
    if len(rows) != 720:
        raise ValueError(f"Expected 720 answers, found {len(rows)}")
    return rows


def screen_line(line: str, review_id: str) -> str | None:
    if COCHRANE.search(line) or re.search(rf"\b{review_id}\b", line, re.I):
        return "cochrane_or_target_id"
    if REVIEW_SOURCE_PHRASES.search(line):
        return "review_source_phrase"
    return None


def screen(rows: list[dict[str, object]]) -> tuple[list[dict[str, str]], set[str]]:
    passages = []
    flagged = set()
    for row in rows:
        path = row["path"]
        assert isinstance(path, Path)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            cue = screen_line(line, str(row["review_id"]))
            if cue is None:
                continue
            source_file = str(row["source_file"])
            flagged.add(source_file)
            passages.append(
                {
                    "review_id": str(row["review_id"]),
                    "model": str(row["model"]),
                    "role": str(row["role"]),
                    "replicate": str(row["replicate"]),
                    "source_file": source_file,
                    "line": str(line_number),
                    "cue": cue,
                    "excerpt": line.strip(),
                }
            )
    return passages, flagged


def finalize(
    rows: list[dict[str, object]],
    passages: list[dict[str, str]],
    flagged: set[str],
) -> None:
    if not DECISIONS_PATH.exists():
        raise FileNotFoundError(f"Missing manual decisions: {DECISIONS_PATH}")
    screened_lines = {(passage["source_file"], passage["line"]) for passage in passages}
    with DECISIONS_PATH.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "source_file", "identity_detail", "evidence_detail", "evidence_line", "note"
        }
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Decision CSV must contain {sorted(required)}")
        decisions = {}
        for decision in reader:
            source_file = decision["source_file"]
            if source_file in decisions:
                raise ValueError(f"Duplicate decision: {source_file}")
            if source_file not in flagged:
                raise ValueError(f"Decision for unflagged response: {source_file}")
            if decision["identity_detail"] not in DETAILED_IDENTITIES:
                raise ValueError(f"Invalid detailed identity for {source_file}")
            if decision["evidence_detail"] not in DETAILED_EVIDENCE_LEVELS:
                raise ValueError(f"Invalid detailed evidence level for {source_file}")
            if (decision["identity_detail"] == "not_applicable") != (
                decision["evidence_detail"] == "no_detected"
            ):
                raise ValueError(f"Incompatible identity/evidence for {source_file}")
            decision_line = decision["evidence_line"].strip()
            if decision_line:
                lines = (ROOT / source_file).read_text(encoding="utf-8").splitlines()
                if not decision_line.isdigit() or not 1 <= int(decision_line) <= len(lines):
                    raise ValueError(f"Invalid evidence line for {source_file}")
                if (source_file, decision_line) not in screened_lines:
                    raise ValueError(f"Evidence line was not screened: {source_file}:{decision_line}")
            elif decision["evidence_detail"] != "no_detected":
                raise ValueError(f"Missing evidence line for {source_file}")
            decisions[source_file] = decision
    missing = sorted(flagged - decisions.keys())
    if missing:
        raise ValueError(f"Missing {len(missing)} manual decisions; first: {missing[0]}")

    audit_rows = []
    for row in rows:
        source_file = str(row["source_file"])
        decision = decisions.get(source_file)
        if decision is None:
            identity = "not_applicable"
            evidence_level = "no_detected"
            evidence_line = ""
            note = "No screening cue detected; this does not establish non-use."
            coding = "screen_default"
        else:
            identity = IDENTITY_GROUP[decision["identity_detail"]]
            evidence_level = EVIDENCE_GROUP[decision["evidence_detail"]]
            evidence_line = decision["evidence_line"].strip()
            note = decision["note"]
            coding = "manual"
        path = row["path"]
        assert isinstance(path, Path)
        evidence_excerpt = (
            path.read_text(encoding="utf-8").splitlines()[int(evidence_line) - 1].strip()
            if evidence_line else ""
        )
        audit_rows.append(
            {
                "review_id": str(row["review_id"]),
                "model": str(row["model"]),
                "role": str(row["role"]),
                "replicate": str(row["replicate"]),
                "source_file": source_file,
                "identity": identity,
                "evidence_level": evidence_level,
                "evidence_line": evidence_line,
                "evidence_excerpt": evidence_excerpt,
                "coding": coding,
                "note": note,
            }
        )
    audit_fields = list(audit_rows[0])
    write_csv(AUDIT_PATH, audit_fields, audit_rows)

    counts = Counter(
        (row["model"], row["identity"], row["evidence_level"])
        for row in audit_rows
    )
    summary_rows = []
    for model in ("claude", "gemini", "gpt"):
        for identity in IDENTITIES:
            levels = ("no_detected",) if identity == "not_applicable" else EVIDENCE_LEVELS[:-1]
            for evidence_level in levels:
                count = counts[(model, identity, evidence_level)]
                summary_rows.append(
                    {
                        "model": model,
                        "identity": identity,
                        "evidence_level": evidence_level,
                        "responses": str(count),
                        "denominator": "240",
                    }
                )
    write_csv(SUMMARY_PATH, list(summary_rows[0]), summary_rows)
    print(f"Wrote {AUDIT_PATH.relative_to(ROOT)} ({len(audit_rows)} rows)")
    print(f"Wrote {SUMMARY_PATH.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize", action="store_true", help="Validate decisions and summarize")
    args = parser.parse_args()
    rows = inventory()
    passages, flagged = screen(rows)
    screen_fields = list(passages[0]) if passages else [
        "review_id", "model", "role", "replicate", "source_file", "line", "cue", "excerpt"
    ]
    write_csv(SCREEN_PATH, screen_fields, passages)
    print(f"Screened {len(rows)} responses; {len(flagged)} flagged, {len(passages)} passages")
    print(f"Wrote {SCREEN_PATH.relative_to(ROOT)}")
    if args.finalize:
        finalize(rows, passages, flagged)


if __name__ == "__main__":
    main()
