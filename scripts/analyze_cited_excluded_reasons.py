#!/usr/bin/env python3
"""Classify and count Cochrane-excluded studies cited by chatbot responses.

The 20 review-specific match tables identify chatbot-cited study clusters and
their Cochrane status. This analysis keeps only ``cochrane_excluded`` rows,
deduplicates them by (review, Cochrane study label), joins each cluster to the
exclusion reason in the review's excluded RIS export, and applies the explicit
decisions in ``cited_excluded_reason_curation.csv``.

The curation is intentionally separate from both the Cochrane source data and
the generated summaries. A new cited excluded study therefore causes a hard
failure until its reason has been reviewed and classified. Categories are
multi-label: a study excluded for both population and intervention contributes
to both category counts. The category-combination output provides mutually
exclusive counts that sum to the number of unique cited excluded studies.
"""

from __future__ import annotations

import csv
import html
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from llm_evidence_retrieval_bias.review_registry import review_sources  # noqa: E402

RETRIEVAL_BIAS_DIR = REPO_ROOT
TAXONOMY_PATH = RETRIEVAL_BIAS_DIR / "cited_excluded_reason_taxonomy.csv"
CURATION_PATH = RETRIEVAL_BIAS_DIR / "cited_excluded_reason_curation.csv"
STUDY_AUDIT_PATH = RETRIEVAL_BIAS_DIR / "cited_excluded_study_reason_audit.csv"
CATEGORY_COUNTS_PATH = RETRIEVAL_BIAS_DIR / "cited_excluded_reason_counts.csv"
COMBINATION_COUNTS_PATH = (
    RETRIEVAL_BIAS_DIR / "cited_excluded_reason_combination_counts.csv"
)


def normalize_label(value: str) -> str:
    """Normalize a study label only for joining curated labels to RIS labels."""

    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def clean_ris_text(value: str) -> str:
    """Remove Cochrane HTML markup while preserving the source reason wording."""

    without_tags = re.sub(r"<[^>]+>", " ", html.unescape(value))
    return re.sub(r"\s+", " ", without_tags).strip()


def load_exclusion_reasons_by_label(text: str) -> dict[str, str]:
    """Map normalized Cochrane study labels to their distinct RIS N1 reason."""

    reasons_by_label: dict[str, set[str]] = defaultdict(set)
    for record in text.split("ER  -"):
        labels = [
            match.group(1).strip()
            for match in re.finditer(r"^NS  - (.+)$", record, re.MULTILINE)
        ]
        reason_lines = [
            match.group(1).strip()
            for match in re.finditer(r"^N1  - (.+)$", record, re.MULTILINE)
        ]
        reason = clean_ris_text(" ".join(reason_lines))
        for label in labels:
            if reason:
                reasons_by_label[normalize_label(label)].add(reason)

    conflicting = {
        label: sorted(reasons)
        for label, reasons in reasons_by_label.items()
        if len(reasons) != 1
    }
    if conflicting:
        raise ValueError(
            "Excluded RIS labels must have exactly one distinct N1 reason: "
            f"{conflicting}"
        )
    return {label: next(iter(reasons)) for label, reasons in reasons_by_label.items()}


def load_taxonomy() -> list[str]:
    """Load the ordered set of allowed high-level reason categories."""

    with TAXONOMY_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    categories = [row["reason_category"].strip() for row in rows]
    if not categories or any(not category for category in categories):
        raise ValueError(f"{TAXONOMY_PATH.name}: empty reason category")
    if len(categories) != len(set(categories)):
        raise ValueError(f"{TAXONOMY_PATH.name}: duplicate reason category")
    return categories


def load_curation(allowed_categories: set[str]) -> dict[tuple[str, str], tuple[str, ...]]:
    """Load one explicit multi-label classification per cited excluded study."""

    decisions: dict[tuple[str, str], tuple[str, ...]] = {}
    with CURATION_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["review"].strip(), row["study_label"].strip())
            categories = tuple(
                category.strip()
                for category in row["reason_categories"].split(";")
                if category.strip()
            )
            if key in decisions:
                raise ValueError(f"{CURATION_PATH.name}: duplicate decision for {key}")
            if not categories:
                raise ValueError(f"{CURATION_PATH.name}: no categories for {key}")
            if len(categories) != len(set(categories)):
                raise ValueError(
                    f"{CURATION_PATH.name}: duplicate category within {key}"
                )
            unknown = set(categories) - allowed_categories
            if unknown:
                raise ValueError(
                    f"{CURATION_PATH.name}: unknown categories for {key}: "
                    f"{sorted(unknown)}"
                )
            decisions[key] = categories
    return decisions


def build_study_audit_rows() -> tuple[list[dict[str, object]], list[str]]:
    """Join cited-excluded matches, Cochrane reasons, and curation decisions."""

    category_order = load_taxonomy()
    category_rank = {
        category: position for position, category in enumerate(category_order)
    }
    decisions = load_curation(set(category_order))
    cited_studies: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    reason_by_key: dict[tuple[str, str], str] = {}

    for source in review_sources():
        with source.matches_path.open(newline="", encoding="utf-8") as handle:
            matches = list(csv.DictReader(handle))
        for row in matches:
            if row["ground_truth_status"] != "cochrane_excluded":
                continue
            label = row["cochrane_study_label"].strip()
            if not label:
                raise ValueError(
                    f"{source.review_id}: excluded match lacks Cochrane study label"
                )
            cited_studies[(source.review_id, label)].append(row)

        ris_reasons = load_exclusion_reasons_by_label(
            source.read_source_text("excluded_ris")
        )
        for review, label in cited_studies:
            if review != source.review_id:
                continue
            component_labels = [
                part.strip() for part in label.split("||") if part.strip()
            ]
            reasons = {
                ris_reasons.get(normalize_label(component_label), "")
                for component_label in component_labels
            }
            reasons.discard("")
            if len(reasons) != 1:
                raise ValueError(
                    f"{review}/{label}: expected one distinct matched exclusion "
                    f"reason, found {sorted(reasons)}"
                )
            reason_by_key[(review, label)] = next(iter(reasons))

    cited_keys = set(cited_studies)
    decision_keys = set(decisions)
    if cited_keys != decision_keys:
        missing = sorted(cited_keys - decision_keys)
        stale = sorted(decision_keys - cited_keys)
        raise ValueError(
            "Curation must cover the current cited-excluded study set exactly; "
            f"missing={missing}, stale={stale}"
        )

    rows: list[dict[str, object]] = []
    for key in sorted(cited_keys):
        matches = cited_studies[key]
        categories = tuple(
            sorted(decisions[key], key=lambda category: category_rank[category])
        )
        rows.append(
            {
                "review": key[0],
                "study_label": key[1],
                "cochrane_exclusion_reason": reason_by_key[key],
                "reason_categories": ";".join(categories),
                "response_study_mentions": len(matches),
            }
        )
    return rows, category_order


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a non-empty audit or summary table with stable column order."""

    if not rows:
        raise ValueError(f"Refusing to write empty artifact: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def build_category_count_rows(
    study_rows: list[dict[str, object]], category_order: list[str]
) -> list[dict[str, object]]:
    """Count unique studies and response-study mentions for each category."""

    study_counts: Counter[str] = Counter()
    mention_counts: Counter[str] = Counter()
    for row in study_rows:
        categories = str(row["reason_categories"]).split(";")
        for category in categories:
            study_counts[category] += 1
            mention_counts[category] += int(row["response_study_mentions"])

    total_studies = len(study_rows)
    total_mentions = sum(int(row["response_study_mentions"]) for row in study_rows)
    return [
        {
            "reason_category": category,
            "unique_excluded_studies": study_counts[category],
            "percent_of_unique_excluded_studies": round(
                100 * study_counts[category] / total_studies, 1
            ),
            "response_study_mentions": mention_counts[category],
            "percent_of_response_study_mentions": round(
                100 * mention_counts[category] / total_mentions, 1
            ),
        }
        for category in category_order
    ]


def build_combination_count_rows(
    study_rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    """Count mutually exclusive category combinations across unique studies."""

    study_counts: Counter[str] = Counter()
    mention_counts: Counter[str] = Counter()
    for row in study_rows:
        combination = str(row["reason_categories"])
        study_counts[combination] += 1
        mention_counts[combination] += int(row["response_study_mentions"])
    return [
        {
            "reason_category_combination": combination,
            "unique_excluded_studies": study_count,
            "response_study_mentions": mention_counts[combination],
        }
        for combination, study_count in sorted(
            study_counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def main() -> None:
    """Regenerate cited-excluded reason audit and descriptive count artifacts."""

    study_rows, category_order = build_study_audit_rows()
    category_rows = build_category_count_rows(study_rows, category_order)
    combination_rows = build_combination_count_rows(study_rows)
    write_csv(STUDY_AUDIT_PATH, study_rows)
    write_csv(CATEGORY_COUNTS_PATH, category_rows)
    write_csv(COMBINATION_COUNTS_PATH, combination_rows)

    total_mentions = sum(
        int(row["response_study_mentions"]) for row in study_rows
    )
    print(
        f"Classified {len(study_rows)} unique cited excluded studies "
        f"from {total_mentions} response-study mentions."
    )
    print(f"Wrote: {STUDY_AUDIT_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote: {CATEGORY_COUNTS_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote: {COMBINATION_COUNTS_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
