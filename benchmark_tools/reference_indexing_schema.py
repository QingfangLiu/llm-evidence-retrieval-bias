"""Shared TSV schemas and helpers for Cochrane reference indexing."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable


STUDY_FIELDNAMES = [
    "review_group",
    "review_pdf",
    "review_id",
    "study_label",
    "reference_status",
    "explicit_pmids",
    "dois",
    "nct_ids",
    "trial_registry_ids",
    "matched_pmids",
    "pmcids",
    "n_pmids",
    "n_pmcids",
    "has_pubmed",
    "has_pmc",
    "lookup_methods",
    "title_queries",
    "lookup_errors",
    "reference_excerpt",
]

REPORT_FIELDNAMES = [
    "review_group",
    "review_pdf",
    "review_id",
    "study_label",
    "report_index",
    "candidate_type",
    "candidate_text",
    "query_text",
    "matched_pmids",
    "pmcids",
    "n_pmids",
    "n_pmcids",
    "has_pubmed",
    "has_pmc",
    "lookup_methods",
    "lookup_errors",
    "pubmed_titles",
    "reference_excerpt",
]

PMID_FIELDNAMES = [
    "review_group",
    "review_pdf",
    "review_id",
    "study_label",
    "pmid",
    "pmcid",
    "in_pmc",
    "match_methods",
    "title",
    "journal",
    "year",
    "doi",
    "pubmed_url",
    "pmc_url",
]

TRIAL_REGISTRY_FIELDNAMES = [
    "review_group",
    "review_pdf",
    "review_id",
    "study_label",
    "registry_type",
    "registry_id",
    "registry_url",
    "source",
    "lookup_status",
    "notes",
    "reference_excerpt",
]

SUMMARY_FIELDNAMES = [
    "review_group",
    "review_pdf",
    "review_id",
    "included_study_blocks",
    "study_blocks_with_explicit_pmid",
    "study_blocks_with_doi",
    "study_blocks_with_any_pmid",
    "study_blocks_with_any_pmc",
    "unique_pmids",
    "unique_pmcids",
    "percent_blocks_with_any_pmid",
    "percent_blocks_with_any_pmc",
    "lookup_errors",
]

EXCLUDED_SUMMARY_FIELDNAMES = [
    "review_group",
    "review_pdf",
    "review_id",
    "excluded_study_blocks",
    "study_blocks_with_explicit_pmid",
    "study_blocks_with_doi",
    "study_blocks_with_any_pmid",
    "study_blocks_with_any_pmc",
    "unique_pmids",
    "unique_pmcids",
    "percent_blocks_with_any_pmid",
    "percent_blocks_with_any_pmc",
    "lookup_errors",
]


def compact(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").split()).strip()


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = compact(value)
        if not value or value in {".", "[]", "{}"} or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def cell(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple, set)):
        text = ";".join(unique_preserve_order(str(item) for item in value))
    else:
        text = compact(value)
    return text if text else "."


def write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: cell(row.get(field, "")) for field in fieldnames})


def registry_url(registry_id: str) -> str:
    registry_id = compact(registry_id)
    upper = registry_id.upper()
    if upper.startswith("NCT"):
        return f"https://clinicaltrials.gov/study/{upper}"
    if upper.startswith("ISRCTN"):
        return f"https://www.isrctn.com/{upper}"
    if upper.startswith("EUCTR"):
        return f"https://www.clinicaltrialsregister.eu/ctr-search/search?query={registry_id}"
    if upper.startswith("CHICTR"):
        return f"https://trialsearch.who.int/Trial2.aspx?TrialID={registry_id}"
    return ""


def registry_type(registry_id: str) -> str:
    upper = compact(registry_id).upper()
    if upper.startswith("NCT"):
        return "NCT"
    if upper.startswith("ISRCTN"):
        return "ISRCTN"
    if upper.startswith("EUCTR"):
        return "EUCTR"
    if upper.startswith("CHICTR"):
        return "ChiCTR"
    if upper.startswith("ACTRN"):
        return "ACTRN"
    return "registry"
