#!/usr/bin/env python3
"""Build benchmark reference sections from Cochrane included/excluded RIS exports.

The active curation path imports this module directly and embeds reference data
in benchmark JSON. The CLI remains available for optional diagnostic TSV
exports, not as an active staging step.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable
import unicodedata


COCHRANE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = COCHRANE_ROOT / "archived" / "legacy_provisional_data"
DEFAULT_CACHE = COCHRANE_ROOT / "archived" / "legacy_cache" / "cochrane_ris_reference_cache.json"
DEFAULT_SOURCE_ROOT = COCHRANE_ROOT / "source_reviews"
RIS_SOURCE = "cochrane_ris"
REFERENCE_ROW_IDENTITY_FIELDS = {"review_group", "review_pdf", "review_id"}
SUMMARY_ROW_IDENTITY_FIELDS = {"review_group", "review_pdf", "review_id"}

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cochrane_review_source import collect_review_pdfs, find_review_source_file, review_collection_name  # noqa: E402
from reference_indexing_schema import (  # noqa: E402
    EXCLUDED_SUMMARY_FIELDNAMES,
    PMID_FIELDNAMES,
    REPORT_FIELDNAMES,
    STUDY_FIELDNAMES,
    SUMMARY_FIELDNAMES,
    TRIAL_REGISTRY_FIELDNAMES,
    cell,
    registry_type,
    registry_url,
    unique_preserve_order,
    write_tsv,
)
from pubmed_utils import pmids_to_pmc_info, pubmed_efetch_details, pubmed_esearch  # noqa: E402


DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
PMID_RE = re.compile(r"\b(?:PMID|PubMed)\s*:?\s*(\d{4,9})\b", re.IGNORECASE)
NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
REGISTRY_RE = re.compile(
    r"\b(?:"
    r"EUCTR\d{4}[-\u2010-\u2015]\d{6}[-\u2010-\u2015]\d{2}(?:[-\u2010-\u2015][A-Z]{2})?|"
    r"ChiCTR\d+|"
    r"ISRCTN\d+|"
    r"ACTRN\d+|"
    r"IRCT\d+|"
    r"CTRI/\d{4}/\d{2}/\d+|"
    r"DRKS\d+"
    r")\b",
    re.IGNORECASE,
)
TITLE_STOPWORDS = {
    "about",
    "after",
    "among",
    "analysis",
    "and",
    "article",
    "based",
    "between",
    "case",
    "clinical",
    "controlled",
    "during",
    "effect",
    "effects",
    "for",
    "from",
    "group",
    "into",
    "journal",
    "letter",
    "methods",
    "of",
    "on",
    "outcomes",
    "patients",
    "pilot",
    "randomised",
    "randomized",
    "report",
    "results",
    "study",
    "the",
    "therapy",
    "trial",
    "treatment",
    "using",
    "versus",
    "with",
}
CITATION_MATCH_TITLE_RATIO = 0.88
CITATION_MATCH_STRONG_TITLE_RATIO = 0.96
CITATION_MATCH_MIN_SCORE = 4
NON_ARTICLE_TITLE_PREFIXES = (
    "correction to",
    "erratum",
    "comment on",
    "reply to",
    "retraction",
    "retracted",
)
NON_ARTICLE_PUBLICATION_TYPES = {
    "comment",
    "published erratum",
    "retracted publication",
    "retraction of publication",
}


def compact(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", compact(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower()
    return " ".join(text.split())


def title_tokens(title: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(title))
    return [
        token
        for token in tokens
        if len(token) >= 4 and token not in TITLE_STOPWORDS and not token.isdigit()
    ]


def first_author_last_name(record: dict[str, list[str]]) -> str:
    author = first(record, "AU")
    if not author:
        return ""
    return normalize_text(author.split(",", 1)[0]).split(" ", 1)[0]


def article_first_author_last_name(article: dict[str, Any]) -> str:
    authors = article.get("authors") or []
    if not authors:
        return ""
    return normalize_text(str(authors[0]).split(",", 1)[0]).split(" ", 1)[0]


def journal_similarity(left: str, right: str) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
    return max(overlap, difflib.SequenceMatcher(None, left_norm, right_norm).ratio())


def year_distance(left: str, right: str) -> int | None:
    if not left or not right:
        return None
    try:
        return abs(int(left) - int(right))
    except ValueError:
        return None


def is_secondary_pubmed_notice(title: str, publication_types: Iterable[str]) -> bool:
    title_norm = normalize_text(title)
    if any(title_norm.startswith(normalize_text(prefix)) for prefix in NON_ARTICLE_TITLE_PREFIXES):
        return True
    pub_types = {normalize_text(value) for value in publication_types}
    return bool(pub_types & {normalize_text(value) for value in NON_ARTICLE_PUBLICATION_TYPES})


def split_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return unique_preserve_order(part for item in value for part in split_values(item))
    text = compact(value)
    if not text or text in {".", "[]", "{}"}:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def join_values(values: Iterable[str]) -> str:
    return ";".join(unique_preserve_order(compact(value) for value in values if compact(value)))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_ris(path: Path) -> list[dict[str, list[str]]]:
    records: list[dict[str, list[str]]] = []
    record: dict[str, list[str]] = {}
    current_tag = ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        if len(line) >= 6 and line[2:6] == "  - ":
            tag = line[:2]
            value = line[6:].strip()
            if tag == "TY":
                record = {"TY": [value]}
            elif tag == "ER":
                if record:
                    records.append(record)
                record = {}
            else:
                record.setdefault(tag, []).append(value)
            current_tag = tag
        elif current_tag and record:
            record[current_tag][-1] = compact(f"{record[current_tag][-1]} {line.strip()}")
    return records


def normalize_doi(value: str) -> str:
    value = compact(value).rstrip(".,;:)]}")
    value = re.split(r"\s+-\s+|\s+PMID:|\s+PubMed|\s+PMC|\s+DOI", value, maxsplit=1, flags=re.IGNORECASE)[0]
    return value.replace(" ", "").lower()


def normalize_registry_id(value: str) -> str:
    value = compact(value)
    value = value.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
    value = value.replace("\u2013", "-").replace("\u2014", "-").replace("\u2015", "-")
    return value


def first(record: dict[str, list[str]], tag: str) -> str:
    return compact(record.get(tag, [""])[0])


def year_from_record(record: dict[str, list[str]]) -> str:
    date = first(record, "DA")
    match = re.search(r"\b(?:19|20)\d{2}\b", date)
    return match.group(0) if match else ""


def authors_text(record: dict[str, list[str]]) -> str:
    authors = [compact(author) for author in record.get("AU", []) if compact(author)]
    return "; ".join(authors)


def citation_text(record: dict[str, list[str]]) -> str:
    parts = [
        authors_text(record),
        first(record, "TI"),
        first(record, "JF"),
        year_from_record(record),
    ]
    volume = first(record, "VL")
    issue = first(record, "IS")
    pages = "-".join(part for part in [first(record, "SP"), first(record, "EP")] if part)
    tail = "; ".join(part for part in [volume, issue, pages] if part)
    if tail:
        parts.append(tail)
    notes = record.get("N1", [])
    if notes:
        parts.append("Notes: " + " ".join(compact(note) for note in notes if compact(note)))
    return compact(". ".join(part for part in parts if part))


def dois_from_record(record: dict[str, list[str]]) -> list[str]:
    values = [normalize_doi(value) for value in record.get("DO", [])]
    for tag_values in record.values():
        for value in tag_values:
            values.extend(normalize_doi(match) for match in DOI_RE.findall(value))
    return unique_preserve_order(value for value in values if value.startswith("10."))


def pmids_from_record(record: dict[str, list[str]]) -> list[str]:
    values: list[str] = []
    for tag_values in record.values():
        for value in tag_values:
            values.extend(PMID_RE.findall(value))
    return unique_preserve_order(values)


def registry_ids_from_record(record: dict[str, list[str]]) -> list[str]:
    values: list[str] = []
    for tag_values in record.values():
        for value in tag_values:
            values.extend(match.upper() for match in NCT_RE.findall(value))
            values.extend(normalize_registry_id(match) for match in REGISTRY_RE.findall(value))
    return unique_preserve_order(values)


def label_from_record(record: dict[str, list[str]], fallback_order: int) -> str:
    label = first(record, "NS")
    if label:
        return label
    first_author = first(record, "AU").split(",", 1)[0]
    year = year_from_record(record)
    if first_author and year:
        return f"{first_author} {year}"
    return f"RIS record {fallback_order}"


def output_review_pdf(pdf: Path) -> str:
    try:
        return str(pdf.relative_to(COCHRANE_ROOT.parent))
    except ValueError:
        return str(pdf)


def ris_stem_candidates(pdf: Path) -> list[str]:
    """Return RIS filename stems for a review PDF, including base Cochrane IDs."""
    stems = [pdf.stem]
    match = re.match(r"^(CD\d+)", pdf.stem)
    if match:
        stems.append(match.group(1))
    return unique_preserve_order(stems)


def find_ris_pair(pdf: Path) -> tuple[Path | None, Path | None]:
    for stem in ris_stem_candidates(pdf):
        included = find_review_source_file(
            pdf.parent,
            stem,
            f"{stem}-included.ris",
            preferred_dir_markers=(f"{stem}-study-data", "study-data"),
            required=False,
        )
        excluded = find_review_source_file(
            pdf.parent,
            stem,
            f"{stem}-excluded.ris",
            preferred_dir_markers=(f"{stem}-study-data", "study-data"),
            required=False,
        )
        if included or excluded:
            return included, excluded
    return None, None


def cached_esearch(
    query: str,
    *,
    cache: dict[str, Any],
    cache_path: Path,
    no_network: bool,
    retmax: int = 10,
) -> tuple[list[str], str]:
    key = f"esearch::{query}"
    cached = cache.get(key)
    if isinstance(cached, list):
        return [str(value) for value in cached], ""
    if isinstance(cached, dict) and cached.get("error"):
        if no_network:
            return [], str(cached.get("error"))
    if no_network:
        return [], "not_searched_no_network"
    try:
        pmids = pubmed_esearch(query, retmax=retmax)
    except Exception as exc:  # pragma: no cover - network defensive path
        return [], str(exc)
    cache[key] = pmids
    save_json(cache_path, cache)
    time.sleep(0.34)
    return [str(value) for value in pmids], ""


def cached_esearch_by_doi(doi: str, *, cache: dict[str, Any], cache_path: Path, no_network: bool) -> tuple[list[str], str]:
    query = f'"{doi}"[AID]'
    return cached_esearch(query, cache=cache, cache_path=cache_path, no_network=no_network, retmax=10)


def citation_search_queries(record: dict[str, list[str]]) -> list[str]:
    title = first(record, "TI")
    author = first_author_last_name(record)
    if not title:
        return []

    tokens = title_tokens(title)
    strongest = tokens[:5]
    queries: list[str] = []

    if author and strongest:
        title_clause = " AND ".join(f"{token}[Title]" for token in strongest)
        queries.append(f"{author}[Author] AND ({title_clause})")

    journal = first(record, "JF")
    year = year_from_record(record)
    if author and journal and year:
        try:
            year_int = int(year)
            year_clause = f"({year_int - 1}:{year_int + 1}[pdat])"
        except ValueError:
            year_clause = ""
        journal_clause = f'"{journal}"[Journal]'
        parts = [f"{author}[Author]", journal_clause]
        if year_clause:
            parts.append(year_clause)
        queries.append(" AND ".join(parts))

    return unique_preserve_order(queries)


def citation_match_score(record: dict[str, list[str]], article: dict[str, Any]) -> tuple[int, list[str]]:
    expected_title = first(record, "TI")
    candidate_title = compact(article.get("title"))
    title_ratio = difflib.SequenceMatcher(
        None,
        normalize_text(expected_title),
        normalize_text(candidate_title),
    ).ratio()
    reasons = [f"title_ratio={title_ratio:.2f}"]
    score = 0

    expected_author = first_author_last_name(record)
    candidate_author = article_first_author_last_name(article)
    author_match = bool(expected_author and expected_author == candidate_author)
    if author_match:
        score += 2
        reasons.append("first_author_match")
    elif expected_author or candidate_author:
        reasons.append(f"first_author_mismatch:{expected_author or '?'}!={candidate_author or '?'}")

    if title_ratio >= CITATION_MATCH_STRONG_TITLE_RATIO:
        score += 3
    elif title_ratio >= CITATION_MATCH_TITLE_RATIO:
        score += 2

    journal_ratio = journal_similarity(first(record, "JF"), compact(article.get("journal")))
    if journal_ratio >= 0.85:
        score += 1
        reasons.append("journal_match")
    elif journal_ratio > 0:
        reasons.append(f"journal_ratio={journal_ratio:.2f}")

    distance = year_distance(year_from_record(record), compact(article.get("year")))
    if distance is None:
        reasons.append("year_missing")
    elif distance <= 1:
        score += 1
        reasons.append(f"year_within_{distance}")
    else:
        reasons.append(f"year_distance={distance}")

    return score, reasons


def accepted_citation_match(record: dict[str, list[str]], article: dict[str, Any]) -> tuple[bool, str]:
    expected_is_notice = is_secondary_pubmed_notice(first(record, "TI"), [])
    candidate_is_notice = is_secondary_pubmed_notice(
        compact(article.get("title")),
        article.get("publication_types") or [],
    )
    if candidate_is_notice and not expected_is_notice:
        return False, "secondary_pubmed_notice"

    score, reasons = citation_match_score(record, article)
    title_ratio = 0.0
    for reason in reasons:
        if reason.startswith("title_ratio="):
            title_ratio = float(reason.split("=", 1)[1])
            break
    has_author = "first_author_match" in reasons
    has_supporting_field = any(
        reason.startswith("journal_match") or reason.startswith("year_within_")
        for reason in reasons
    )
    accepted = (
        score >= CITATION_MATCH_MIN_SCORE
        and title_ratio >= CITATION_MATCH_TITLE_RATIO
        and has_author
        and has_supporting_field
    )
    return accepted, ",".join([f"score={score}", *reasons])


def cached_esearch_by_citation(
    record: dict[str, list[str]],
    *,
    cache: dict[str, Any],
    cache_path: Path,
    no_network: bool,
) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    queries = citation_search_queries(record)
    if not queries:
        return [], [], []

    seen_pmids: list[str] = []
    for query in queries:
        pmids, error = cached_esearch(query, cache=cache, cache_path=cache_path, no_network=no_network, retmax=20)
        if error and error != "not_searched_no_network":
            errors.append(f"citation_search_failed:{query}:{error}")
            continue
        pmids = [pmid for pmid in unique_preserve_order(pmids) if pmid not in seen_pmids]
        seen_pmids.extend(pmids)
        if not pmids:
            continue
        metadata = cached_metadata(pmids, cache=cache, cache_path=cache_path, no_network=no_network)
        for pmid in pmids:
            article = metadata.get(pmid) or {}
            ok, reason = accepted_citation_match(record, article)
            if ok:
                return [pmid], ["ris_citation_search"], unique_preserve_order(errors)

    return [], [], unique_preserve_order(errors)


def cached_metadata(pmids: list[str], *, cache: dict[str, Any], cache_path: Path, no_network: bool) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    missing = []
    for pmid in unique_preserve_order(pmids):
        key = f"efetch::{pmid}"
        if isinstance(cache.get(key), dict):
            found[pmid] = cache[key]
        else:
            missing.append(pmid)
    if missing and not no_network:
        for article in pubmed_efetch_details(missing):
            pmid = compact(article.get("pmid"))
            if pmid:
                cache[f"efetch::{pmid}"] = article
                found[pmid] = article
        save_json(cache_path, cache)
        time.sleep(0.34)
    return found


def cached_pmcids(pmids: list[str], *, cache: dict[str, Any], cache_path: Path, no_network: bool) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    missing = []
    for pmid in unique_preserve_order(pmids):
        key = f"pmc::{pmid}"
        if isinstance(cache.get(key), dict):
            found[pmid] = cache[key]
        else:
            missing.append(pmid)
    if missing and not no_network:
        found_new = pmids_to_pmc_info(missing)
        for pmid in missing:
            cache[f"pmc::{pmid}"] = found_new.get(pmid, {})
            found[pmid] = cache[f"pmc::{pmid}"]
        save_json(cache_path, cache)
        time.sleep(0.34)
    return found


def resolve_record_pmids(
    record: dict[str, list[str]],
    *,
    cache: dict[str, Any],
    cache_path: Path,
    no_network: bool,
    enable_citation_search: bool,
) -> tuple[list[str], list[str], list[str]]:
    direct_pmids = pmids_from_record(record)
    methods = ["ris_explicit_pmid"] if direct_pmids else []
    errors = []
    resolved = list(direct_pmids)
    if not resolved:
        for doi in dois_from_record(record):
            pmids, error = cached_esearch_by_doi(doi, cache=cache, cache_path=cache_path, no_network=no_network)
            if error and error != "not_searched_no_network":
                errors.append(f"doi_search_failed:{doi}:{error}")
            if pmids:
                resolved.extend(pmids[:1])
                methods.append("ris_doi_search")
                break
    if not resolved and enable_citation_search:
        pmids, citation_methods, citation_errors = cached_esearch_by_citation(
            record,
            cache=cache,
            cache_path=cache_path,
            no_network=no_network,
        )
        resolved.extend(pmids)
        methods.extend(citation_methods)
        errors.extend(citation_errors)
    return unique_preserve_order(resolved), unique_preserve_order(methods), unique_preserve_order(errors)


def record_candidate_type(
    record: dict[str, list[str]],
    pmids: list[str],
    registry_ids: list[str],
    methods: list[str],
) -> str:
    if pmids:
        if pmids_from_record(record):
            return "explicit_pmid"
        if "ris_doi_search" in methods or dois_from_record(record):
            return "doi"
        return "citation"
    if dois_from_record(record):
        return "doi"
    if registry_ids:
        return "nct_id"
    return "title"


def candidate_text(record: dict[str, list[str]], candidate_type: str, pmids: list[str], registry_ids: list[str]) -> str:
    if candidate_type == "explicit_pmid":
        return join_values(pmids)
    if candidate_type == "doi":
        return join_values(dois_from_record(record))
    if candidate_type == "nct_id":
        return join_values(registry_ids)
    return first(record, "TI")


def build_section_rows(
    *,
    records: list[dict[str, list[str]]],
    section_type: str,
    review_group: str,
    review_pdf: str,
    review_id: str,
    cache: dict[str, Any],
    cache_path: Path,
    no_network: bool,
    enable_citation_search: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    report_rows: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_pmids: list[str] = []

    for index, record in enumerate(records, start=1):
        label = label_from_record(record, index)
        registry_ids = registry_ids_from_record(record)
        resolved_pmids, methods, errors = resolve_record_pmids(
            record,
            cache=cache,
            cache_path=cache_path,
            no_network=no_network,
            enable_citation_search=enable_citation_search,
        )
        all_pmids.extend(resolved_pmids)
        row = {
            "_record": record,
            "review_group": review_group,
            "review_pdf": review_pdf,
            "review_id": review_id,
            "study_label": label,
            "report_index": len(grouped[label]) + 1,
            "matched_pmids": resolved_pmids,
            "pmcids": [],
            "lookup_methods": methods,
            "lookup_errors": errors,
            "registry_ids": registry_ids,
            "reference_excerpt": citation_text(record),
            "pubmed_titles": "",
        }
        grouped[label].append(row)
        report_rows.append(row)

    metadata = cached_metadata(all_pmids, cache=cache, cache_path=cache_path, no_network=no_network)
    pmc_map = cached_pmcids(all_pmids, cache=cache, cache_path=cache_path, no_network=no_network)

    for row in report_rows:
        pmcids = unique_preserve_order(
            compact(pmc_map.get(pmid, {}).get("pmcid"))
            for pmid in split_values(row["matched_pmids"])
            if compact(pmc_map.get(pmid, {}).get("pmcid"))
        )
        row["pmcids"] = pmcids
        row["pubmed_titles"] = join_values(
            compact(metadata.get(pmid, {}).get("title"))
            for pmid in split_values(row["matched_pmids"])
            if compact(metadata.get(pmid, {}).get("title"))
        )

    study_rows: list[dict[str, Any]] = []
    pmid_rows: list[dict[str, Any]] = []
    registry_rows: list[dict[str, Any]] = []
    final_report_rows: list[dict[str, Any]] = []

    for label, rows in grouped.items():
        all_direct_pmids = unique_preserve_order(pmid for row in rows for pmid in pmids_from_record(row["_record"]))
        all_matched_pmids = unique_preserve_order(pmid for row in rows for pmid in split_values(row["matched_pmids"]))
        all_pmcids = unique_preserve_order(pmcid for row in rows for pmcid in split_values(row["pmcids"]))
        all_dois = unique_preserve_order(doi for row in rows for doi in dois_from_record(row["_record"]))
        all_registry_ids = unique_preserve_order(registry_id for row in rows for registry_id in row["registry_ids"])
        all_methods = unique_preserve_order(method for row in rows for method in split_values(row["lookup_methods"]))
        all_errors = unique_preserve_order(error for row in rows for error in split_values(row["lookup_errors"]))
        excerpt = " ".join(row["reference_excerpt"] for row in rows)
        study_rows.append(
            {
                "review_group": review_group,
                "review_pdf": review_pdf,
                "review_id": review_id,
                "study_label": label,
                "reference_status": section_type,
                "explicit_pmids": all_direct_pmids,
                "dois": all_dois,
                "nct_ids": [value for value in all_registry_ids if value.upper().startswith("NCT")],
                "trial_registry_ids": all_registry_ids,
                "matched_pmids": all_matched_pmids,
                "pmcids": all_pmcids,
                "n_pmids": len(all_matched_pmids),
                "n_pmcids": len(all_pmcids),
                "has_pubmed": bool(all_matched_pmids),
                "has_pmc": bool(all_pmcids),
                "lookup_methods": all_methods,
                "title_queries": unique_preserve_order(first(row["_record"], "TI") for row in rows if first(row["_record"], "TI")),
                "lookup_errors": all_errors,
                "reference_excerpt": excerpt[:600],
            }
        )

        for row in rows:
            record = row["_record"]
            registry_ids = row["registry_ids"]
            pmids = split_values(row["matched_pmids"])
            methods = split_values(row["lookup_methods"])
            candidate_type = record_candidate_type(record, pmids, registry_ids, methods)
            final_report_rows.append(
                {
                    "review_group": review_group,
                    "review_pdf": review_pdf,
                    "review_id": review_id,
                    "study_label": label,
                    "report_index": row["report_index"],
                    "candidate_type": candidate_type,
                    "candidate_text": candidate_text(record, candidate_type, pmids, registry_ids),
                    "query_text": first(record, "TI") if candidate_type == "title" else candidate_text(record, candidate_type, pmids, registry_ids),
                    "matched_pmids": pmids,
                    "pmcids": row["pmcids"],
                    "n_pmids": len(pmids),
                    "n_pmcids": len(split_values(row["pmcids"])),
                    "has_pubmed": bool(pmids),
                    "has_pmc": bool(split_values(row["pmcids"])),
                    "lookup_methods": row["lookup_methods"],
                    "lookup_errors": row["lookup_errors"],
                    "pubmed_titles": row["pubmed_titles"],
                    "reference_excerpt": row["reference_excerpt"][:600],
                }
            )

            for idx, pmid in enumerate(pmids):
                pmcids = split_values(row["pmcids"])
                pmcid = pmcids[idx] if idx < len(pmcids) else ""
                article = metadata.get(pmid, {})
                pmid_rows.append(
                    {
                        "review_group": review_group,
                        "review_pdf": review_pdf,
                        "review_id": review_id,
                        "study_label": label,
                        "pmid": pmid,
                        "pmcid": pmcid,
                        "in_pmc": bool(pmcid),
                        "match_methods": row["lookup_methods"],
                        "title": article.get("title") or first(record, "TI"),
                        "journal": article.get("journal") or first(record, "JF"),
                        "year": article.get("year") or year_from_record(record),
                        "doi": article.get("doi") or (dois_from_record(record)[0] if dois_from_record(record) else ""),
                        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        "pmc_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else "",
                    }
                )

        for registry_id in all_registry_ids:
            registry_rows.append(
                {
                    "review_group": review_group,
                    "review_pdf": review_pdf,
                    "review_id": review_id,
                    "study_label": label,
                    "registry_type": registry_type(registry_id),
                    "registry_id": registry_id,
                    "registry_url": registry_url(registry_id),
                    "source": RIS_SOURCE,
                    "lookup_status": "extracted_from_ris",
                    "notes": "",
                    "reference_excerpt": excerpt[:600],
                }
            )

    summary_rows = build_summary_rows(study_rows, section_type)
    return study_rows, final_report_rows, pmid_rows, registry_rows, summary_rows


def build_summary_rows(study_rows: list[dict[str, Any]], section_type: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in study_rows:
        grouped[(compact(row.get("review_group")), compact(row.get("review_pdf")), compact(row.get("review_id")))].append(row)
    out = []
    for (review_group, review_pdf, review_id), rows in sorted(grouped.items()):
        n_blocks = len(rows)
        with_pmid = sum(bool(split_values(row.get("matched_pmids"))) for row in rows)
        with_pmc = sum(bool(split_values(row.get("pmcids"))) for row in rows)
        unique_pmids = unique_preserve_order(pmid for row in rows for pmid in split_values(row.get("matched_pmids")))
        unique_pmcids = unique_preserve_order(pmcid for row in rows for pmcid in split_values(row.get("pmcids")))
        key_name = "included_study_blocks" if section_type == "included" else "excluded_study_blocks"
        out.append(
            {
                "review_group": review_group,
                "review_pdf": review_pdf,
                "review_id": review_id,
                key_name: n_blocks,
                "study_blocks_with_explicit_pmid": sum(bool(split_values(row.get("explicit_pmids"))) for row in rows),
                "study_blocks_with_doi": sum(bool(split_values(row.get("dois"))) for row in rows),
                "study_blocks_with_any_pmid": with_pmid,
                "study_blocks_with_any_pmc": with_pmc,
                "unique_pmids": len(unique_pmids),
                "unique_pmcids": len(unique_pmcids),
                "percent_blocks_with_any_pmid": f"{(with_pmid / n_blocks * 100):.1f}" if n_blocks else "0.0",
                "percent_blocks_with_any_pmc": f"{(with_pmc / n_blocks * 100):.1f}" if n_blocks else "0.0",
                "lookup_errors": unique_preserve_order(error for row in rows for error in split_values(row.get("lookup_errors"))),
            }
        )
    return out


def json_rows(rows: list[dict[str, Any]], fieldnames: list[str], *, drop_fields: set[str] | None = None) -> list[dict[str, str]]:
    drop_fields = drop_fields or set()
    return [
        {
            field: cell(row.get(field, ""))
            for field in fieldnames
            if field not in drop_fields
        }
        for row in rows
    ]


def first_json_row(rows: list[dict[str, Any]], fieldnames: list[str], *, drop_fields: set[str] | None = None) -> dict[str, str]:
    converted = json_rows(rows, fieldnames, drop_fields=drop_fields)
    return converted[0] if converted else {}


def build_benchmark_reference_json(
    pdf: Path,
    *,
    review_id: str | None = None,
    cache_path: Path = DEFAULT_CACHE,
    no_network: bool = False,
    citation_search_included: bool = True,
    citation_search_excluded: bool = True,
) -> dict[str, Any]:
    """Return benchmark-shaped reference sections from Cochrane RIS exports."""
    cache = load_json(cache_path)
    included_ris, excluded_ris = find_ris_pair(pdf)
    review_group = review_collection_name(pdf)
    review_pdf = output_review_pdf(pdf)
    output_review_id = review_id or pdf.stem

    included: tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]
    excluded: tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]
    included = ([], [], [], [], [])
    excluded = ([], [], [], [], [])

    if included_ris:
        included = build_section_rows(
            records=parse_ris(included_ris),
            section_type="included",
            review_group=review_group,
            review_pdf=review_pdf,
            review_id=output_review_id,
            cache=cache,
            cache_path=cache_path,
            no_network=no_network,
            enable_citation_search=citation_search_included,
        )
    if excluded_ris:
        excluded = build_section_rows(
            records=parse_ris(excluded_ris),
            section_type="excluded",
            review_group=review_group,
            review_pdf=review_pdf,
            review_id=output_review_id,
            cache=cache,
            cache_path=cache_path,
            no_network=no_network,
            enable_citation_search=citation_search_excluded,
        )

    save_json(cache_path, cache)
    return {
        "pubmed_pmc_summary": first_json_row(
            included[4],
            SUMMARY_FIELDNAMES,
            drop_fields=SUMMARY_ROW_IDENTITY_FIELDS,
        ),
        "references": {
            "included_studies": json_rows(included[0], STUDY_FIELDNAMES, drop_fields=REFERENCE_ROW_IDENTITY_FIELDS),
            "included_pubmed_records": json_rows(included[2], PMID_FIELDNAMES, drop_fields=REFERENCE_ROW_IDENTITY_FIELDS),
            "included_report_candidates": json_rows(included[1], REPORT_FIELDNAMES, drop_fields=REFERENCE_ROW_IDENTITY_FIELDS),
            "included_trial_registry_records": json_rows(
                included[3],
                TRIAL_REGISTRY_FIELDNAMES,
                drop_fields=REFERENCE_ROW_IDENTITY_FIELDS,
            ),
            "excluded_studies": json_rows(excluded[0], STUDY_FIELDNAMES, drop_fields=REFERENCE_ROW_IDENTITY_FIELDS),
            "excluded_pubmed_records": json_rows(excluded[2], PMID_FIELDNAMES, drop_fields=REFERENCE_ROW_IDENTITY_FIELDS),
            "excluded_report_candidates": json_rows(excluded[1], REPORT_FIELDNAMES, drop_fields=REFERENCE_ROW_IDENTITY_FIELDS),
            "excluded_trial_registry_records": json_rows(
                excluded[3],
                TRIAL_REGISTRY_FIELDNAMES,
                drop_fields=REFERENCE_ROW_IDENTITY_FIELDS,
            ),
            "excluded_pubmed_summary": json_rows(
                excluded[4],
                EXCLUDED_SUMMARY_FIELDNAMES,
                drop_fields=SUMMARY_ROW_IDENTITY_FIELDS,
            ),
        },
    }


def write_manifest(path: Path, *, input_files: list[Path], output_dir: Path, counts: dict[str, int]) -> None:
    payload = {
        "generated_by": Path(__file__).name,
        "source": "Cochrane RIS included/excluded exports",
        "input_files": [str(path) for path in input_files],
        "output_dir": str(output_dir),
        "counts": counts,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Cochrane RIS reference indexing data; the CLI writes optional diagnostic TSV exports."
    )
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--review-id", action="append", default=[], help="Optional review ID filter, e.g. CD013524.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument(
        "--citation-search-excluded",
        action="store_true",
        help="Also run PubMed citation fallback for excluded-study RIS records. Included records use it by default.",
    )
    return parser.parse_args()


def selected_pdf(pdf: Path, wanted: set[str]) -> bool:
    return not wanted or pdf.stem in wanted


def main() -> int:
    args = parse_args()
    wanted = {value.strip() for value in args.review_id if value.strip()}
    cache = load_json(args.cache)

    all_included: list[dict[str, Any]] = []
    all_included_reports: list[dict[str, Any]] = []
    all_included_pmids: list[dict[str, Any]] = []
    all_included_registries: list[dict[str, Any]] = []
    all_included_summary: list[dict[str, Any]] = []
    all_excluded: list[dict[str, Any]] = []
    all_excluded_reports: list[dict[str, Any]] = []
    all_excluded_pmids: list[dict[str, Any]] = []
    all_excluded_registries: list[dict[str, Any]] = []
    all_excluded_summary: list[dict[str, Any]] = []
    input_files: list[Path] = []

    pdfs = [pdf for pdf in collect_review_pdfs([args.root]) if selected_pdf(pdf, wanted)]
    for pdf in pdfs:
        included_ris, excluded_ris = find_ris_pair(pdf)
        review_group = review_collection_name(pdf)
        review_pdf = output_review_pdf(pdf)
        review_id = pdf.stem
        print(f"processing {review_id}: included={bool(included_ris)} excluded={bool(excluded_ris)}")
        if included_ris:
            input_files.append(included_ris)
            rows = parse_ris(included_ris)
            built = build_section_rows(
                records=rows,
                section_type="included",
                review_group=review_group,
                review_pdf=review_pdf,
                review_id=review_id,
                cache=cache,
                cache_path=args.cache,
                no_network=args.no_network,
                enable_citation_search=True,
            )
            all_included.extend(built[0])
            all_included_reports.extend(built[1])
            all_included_pmids.extend(built[2])
            all_included_registries.extend(built[3])
            all_included_summary.extend(built[4])
        if excluded_ris:
            input_files.append(excluded_ris)
            rows = parse_ris(excluded_ris)
            built = build_section_rows(
                records=rows,
                section_type="excluded",
                review_group=review_group,
                review_pdf=review_pdf,
                review_id=review_id,
                cache=cache,
                cache_path=args.cache,
                no_network=args.no_network,
                enable_citation_search=args.citation_search_excluded,
            )
            all_excluded.extend(built[0])
            all_excluded_reports.extend(built[1])
            all_excluded_pmids.extend(built[2])
            all_excluded_registries.extend(built[3])
            all_excluded_summary.extend(built[4])

    save_json(args.cache, cache)
    write_tsv(args.output_dir / "included_study_indexing.tsv", STUDY_FIELDNAMES, all_included)
    write_tsv(args.output_dir / "included_report_indexing.tsv", REPORT_FIELDNAMES, all_included_reports)
    write_tsv(args.output_dir / "included_pubmed_records.tsv", PMID_FIELDNAMES, all_included_pmids)
    write_tsv(args.output_dir / "included_trial_registry_records.tsv", TRIAL_REGISTRY_FIELDNAMES, all_included_registries)
    write_tsv(args.output_dir / "pubmed_pmc_summary.tsv", SUMMARY_FIELDNAMES, all_included_summary)
    write_tsv(args.output_dir / "excluded_study_indexing.tsv", STUDY_FIELDNAMES, all_excluded)
    write_tsv(args.output_dir / "excluded_report_indexing.tsv", REPORT_FIELDNAMES, all_excluded_reports)
    write_tsv(args.output_dir / "excluded_pubmed_records.tsv", PMID_FIELDNAMES, all_excluded_pmids)
    write_tsv(args.output_dir / "excluded_trial_registry_records.tsv", TRIAL_REGISTRY_FIELDNAMES, all_excluded_registries)
    write_tsv(args.output_dir / "excluded_pubmed_summary.tsv", EXCLUDED_SUMMARY_FIELDNAMES, all_excluded_summary)
    counts = {
        "included_study_rows": len(all_included),
        "included_report_rows": len(all_included_reports),
        "included_pubmed_rows": len(all_included_pmids),
        "included_registry_rows": len(all_included_registries),
        "excluded_study_rows": len(all_excluded),
        "excluded_report_rows": len(all_excluded_reports),
        "excluded_pubmed_rows": len(all_excluded_pmids),
        "excluded_registry_rows": len(all_excluded_registries),
    }
    write_manifest(args.output_dir / "reference_indexing_source_manifest.json", input_files=input_files, output_dir=args.output_dir, counts=counts)
    for key, value in counts.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
