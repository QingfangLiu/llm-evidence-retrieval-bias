#!/usr/bin/env python3
"""Resolve each included study's PMIDs and fetch Semantic Scholar citation counts.

PMID resolution reuses the retained standalone reference-resolution pipeline
(`benchmark_tools/build_reference_indexing_from_cochrane_ris.py`) rather than
re-implementing it. That module tries, per RIS record, in order:

- `ris_explicit_pmid` - a PMID pattern found anywhere in the record's fields;
- `ris_doi_search` - a DOI found anywhere in the record's fields, searched via
  PubMed ESearch `"<doi>"[AID]`;
- `ris_citation_search` - an author+title (and author+journal+year) PubMed
  query, accepted only if the best candidate passes a scored check requiring
  title similarity, first-author match, and a supporting journal or year
  match, while rejecting corrections/errata/retraction notices.

One Cochrane study can have multiple linked RIS records (companion reports);
this resolves PMIDs per record and keeps the union for the study. Citation
counts are then fetched from the Semantic Scholar Graph API
(`POST /graph/v1/paper/batch`, `externalIds` lookup by PMID, no API key) for
every resolved PMID, and a study's `citation_count` is the maximum across its
resolved PMIDs' Semantic Scholar records - typically the main trial report,
since companion/follow-up papers are usually cited less than the original
trial. `citations_per_year` divides that by the number of years since the
study's Cochrane-reported publication year (see
`scripts/analyze_recall_by_characteristic.py`), floored at 1 year, specifically to
avoid confusing "cited a lot" with "has existed long enough to be cited a
lot" - recent studies mechanically have less time to accumulate citations
regardless of their eventual influence. `is_open_access` is Semantic
Scholar's `isOpenAccess` flag for that same best-matched (highest-citation)
PMID - not an OR across every resolved PMID, so it stays tied to the one
record `citation_count`/`citation_count_pmid` already describe.

Two artifacts are written:

- `data/cache/pmid_resolution_cache.json` / reuses the PubMed ESearch/EFetch caching
  built into the imported module, plus a local Semantic Scholar response
  cache, so repeat runs do not re-hit either API for already-seen records.
- `data/analysis/citation_counts_by_study.csv` - one row per included study, with its
  resolved PMIDs, resolution methods, Semantic Scholar match, citation
  count, open-access status, and citations per year. Blank `citation_count`
  means no PMID could be resolved with reasonable confidence, or none of its
  resolved PMIDs are
  in Semantic Scholar's corpus - not zero citations.

Run from the repository root, one review at a time while validating, or all
20 at once:

    python3 scripts/fetch_citation_counts.py --reviews CD012161
    python3 scripts/fetch_citation_counts.py
    python3 scripts/fetch_citation_counts.py --no-network

`--no-network` reuses only what is already cached (both PubMed and Semantic
Scholar), for iterating without spending new API calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_BIAS_DIR = REPO_ROOT
BENCHMARK_TOOLS_DIR = REPO_ROOT / "benchmark_tools"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BENCHMARK_TOOLS_DIR))

try:
    import build_reference_indexing_from_cochrane_ris as ris_lib  # noqa: E402
except ModuleNotFoundError:
    ris_lib = None  # type: ignore[assignment]
from shared.review_registry import (  # noqa: E402
    ANALYSIS_DATA_DIR,
    CACHE_DATA_DIR,
    REVIEW_SOURCES,
)

PMID_CACHE_PATH = CACHE_DATA_DIR / "pmid_resolution_cache.json"
SEMANTIC_SCHOLAR_CACHE_PATH = CACHE_DATA_DIR / "semantic_scholar_cache.json"
OUTPUT_PATH = ANALYSIS_DATA_DIR / "citation_counts_by_study.csv"
SEMANTIC_SCHOLAR_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
SEMANTIC_SCHOLAR_BATCH_SIZE = 250
SEMANTIC_SCHOLAR_THROTTLE_SECONDS = 1.1
CURRENT_YEAR = datetime.now().year


def require_ris_lib() -> Any:
    """Return the RIS reference-resolution module, or explain how to restore it."""

    if ris_lib is None:
        raise SystemExit(
            "Missing benchmark_tools/build_reference_indexing_from_cochrane_ris.py. "
            "Restore the retained benchmark_tools helper files before running "
            "scripts/fetch_citation_counts.py."
        )
    return ris_lib


def parse_ris_text(text: str) -> list[dict[str, list[str]]]:
    """Parse RIS text loaded from either an extracted package or ZIP member."""

    ris = require_ris_lib()
    records: list[dict[str, list[str]]] = []
    record: dict[str, list[str]] = {}
    current_tag = ""
    for line in text.splitlines():
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
            record[current_tag][-1] = ris.compact(
                f"{record[current_tag][-1]} {line.strip()}"
            )
    return records


def group_records_by_study_label(records: list[dict[str, list[str]]]) -> dict[str, list[dict[str, list[str]]]]:
    """Group RIS records into study clusters using the NS (study label) tag."""

    grouped: dict[str, list[dict[str, list[str]]]] = defaultdict(list)
    for index, record in enumerate(records):
        ns_values = record.get("NS", [])
        label = (
            ns_values[0].strip()
            if ns_values
            else require_ris_lib().label_from_record(record, index)
        )
        grouped[label].append(record)
    return grouped


def resolve_study_pmids(
    records: list[dict[str, list[str]]], *, cache: dict[str, Any], no_network: bool
) -> tuple[list[str], list[str]]:
    """Resolve the union of PMIDs and lookup methods across a study's records."""

    all_pmids: list[str] = []
    all_methods: list[str] = []
    for record in records:
        pmids, methods, _errors = require_ris_lib().resolve_record_pmids(
            record,
            cache=cache,
            cache_path=PMID_CACHE_PATH,
            no_network=no_network,
            enable_citation_search=True,
        )
        for pmid in pmids:
            if pmid not in all_pmids:
                all_pmids.append(pmid)
        for method in methods:
            if method not in all_methods:
                all_methods.append(method)
    return all_pmids, all_methods


def load_json_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def save_json_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")


def post_batch_with_retries(
    batch: list[str], *, max_attempts: int = 6, base_delay: float = 5.0
) -> requests.Response:
    """POST one Semantic Scholar batch request, retrying on 429/5xx with backoff."""

    last_response = None
    for attempt in range(1, max_attempts + 1):
        response = requests.post(
            SEMANTIC_SCHOLAR_BATCH_URL,
            params={"fields": "title,year,citationCount,externalIds,isOpenAccess"},
            json={"ids": [f"PMID:{pmid}" for pmid in batch]},
            timeout=30,
        )
        last_response = response
        if response.status_code not in (429, 500, 502, 503, 504):
            return response
        if attempt >= max_attempts:
            break
        retry_after = response.headers.get("Retry-After", "")
        try:
            delay = float(retry_after)
        except ValueError:
            delay = base_delay * (2 ** (attempt - 1))
        delay = min(delay, 60)
        print(
            f"Semantic Scholar returned HTTP {response.status_code}; "
            f"retrying in {delay:g}s ({attempt}/{max_attempts})"
        )
        time.sleep(delay)
    return last_response


def fetch_semantic_scholar_batch(
    pmids: list[str], *, cache: dict[str, Any], no_network: bool
) -> dict[str, dict[str, Any]]:
    """Fetch citationCount/year/title/isOpenAccess per PMID, using and updating the cache.

    A cached entry that predates the `isOpenAccess` field (cached before it was
    added to the requested fields) is treated as missing so it gets refetched
    once, rather than silently carrying a permanently blank isOpenAccess value.
    """

    found: dict[str, dict[str, Any]] = {}
    missing = [
        pmid for pmid in pmids
        if f"pmid::{pmid}" not in cache
        or (cache[f"pmid::{pmid}"] is not None and "isOpenAccess" not in cache[f"pmid::{pmid}"])
    ]
    for pmid in pmids:
        cached = cache.get(f"pmid::{pmid}")
        if cached is not None:
            found[pmid] = cached

    if not missing or no_network:
        return found

    for start in range(0, len(missing), SEMANTIC_SCHOLAR_BATCH_SIZE):
        batch = missing[start : start + SEMANTIC_SCHOLAR_BATCH_SIZE]
        response = post_batch_with_retries(batch)
        response.raise_for_status()
        results = response.json()
        for pmid, result in zip(batch, results):
            cache[f"pmid::{pmid}"] = result
            if result is not None:
                found[pmid] = result
        time.sleep(SEMANTIC_SCHOLAR_THROTTLE_SECONDS)
    return found


def load_year_by_label(review: str) -> dict[str, int | None]:
    """Reuse the same RIS year extraction as scripts/analyze_recall_by_characteristic.py."""

    import re

    text = REVIEW_SOURCES[review].read_source_text("included_ris")
    years: dict[str, int | None] = {}
    for record in text.split("ER  -"):
        label_match = re.search(r"^NS  - (.+)$", record, re.MULTILINE)
        if not label_match:
            continue
        label = label_match.group(1).strip()
        if label in years:
            continue
        year_match = re.search(r"^DA  - (\d{4})", record, re.MULTILINE)
        years[label] = int(year_match.group(1)) if year_match else None
    return years


def load_existing_rows(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {(row["review"], row["study_label"]): row for row in csv.DictReader(handle)}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "review", "study_label", "cochrane_year",
        "resolved_pmids", "resolution_methods", "matched_pmid_count",
        "citation_count", "citation_count_pmid", "is_open_access", "citations_per_year",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["review"], r["study_label"])):
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    """Resolve PMIDs and citation counts for the given reviews' included studies."""

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--reviews",
        nargs="+",
        choices=sorted(REVIEW_SOURCES),
        default=sorted(REVIEW_SOURCES),
    )
    parser.add_argument("--no-network", action="store_true", help="Use only cached API responses.")
    args = parser.parse_args()

    pmid_cache = load_json_cache(PMID_CACHE_PATH)
    s2_cache = load_json_cache(SEMANTIC_SCHOLAR_CACHE_PATH)
    existing_rows = load_existing_rows(OUTPUT_PATH)
    selected_reviews = set(args.reviews)
    existing_rows = {
        key: row
        for key, row in existing_rows.items()
        if key[0] not in selected_reviews
    }

    method_counts: dict[str, int] = defaultdict(int)
    unresolved_count = 0
    total = 0
    all_resolved_pmids: list[str] = []
    per_study_pmids: dict[tuple[str, str], list[str]] = {}
    per_study_methods: dict[tuple[str, str], list[str]] = {}
    per_study_year: dict[tuple[str, str], int | None] = {}

    for review in args.reviews:
        records = parse_ris_text(
            REVIEW_SOURCES[review].read_source_text("included_ris")
        )
        grouped = group_records_by_study_label(records)
        year_by_label = load_year_by_label(review)
        for label, study_records in grouped.items():
            total += 1
            pmids, methods = resolve_study_pmids(study_records, cache=pmid_cache, no_network=args.no_network)
            key = (review, label)
            per_study_pmids[key] = pmids
            per_study_methods[key] = methods
            per_study_year[key] = year_by_label.get(label)
            if pmids:
                for method in methods:
                    method_counts[method] += 1
                all_resolved_pmids.extend(pmid for pmid in pmids if pmid not in all_resolved_pmids)
            else:
                unresolved_count += 1
                method_counts["unresolved"] += 1

    save_json_cache(PMID_CACHE_PATH, pmid_cache)

    citation_data = fetch_semantic_scholar_batch(all_resolved_pmids, cache=s2_cache, no_network=args.no_network)
    save_json_cache(SEMANTIC_SCHOLAR_CACHE_PATH, s2_cache)

    citation_hits = 0
    open_access_hits = 0
    for (review, label), pmids in per_study_pmids.items():
        best_pmid, best_count, best_is_open_access = "", -1, None
        for pmid in pmids:
            result = citation_data.get(pmid)
            count = result.get("citationCount") if result else None
            if count is not None and count > best_count:
                best_pmid, best_count = pmid, count
                best_is_open_access = result.get("isOpenAccess")
        year = per_study_year[(review, label)]
        citations_per_year = ""
        if best_count >= 0 and year:
            citations_per_year = round(best_count / max(1, CURRENT_YEAR - year), 2)
            citation_hits += 1
        is_open_access = ""
        if best_is_open_access is not None:
            is_open_access = int(bool(best_is_open_access))
            open_access_hits += 1
        existing_rows[(review, label)] = {
            "review": review,
            "study_label": label,
            "cochrane_year": year if year else "",
            "resolved_pmids": ";".join(pmids),
            "resolution_methods": ";".join(per_study_methods[(review, label)]),
            "matched_pmid_count": len(pmids),
            "citation_count": best_count if best_count >= 0 else "",
            "citation_count_pmid": best_pmid,
            "is_open_access": is_open_access,
            "citations_per_year": citations_per_year,
        }

    write_csv(OUTPUT_PATH, list(existing_rows.values()))

    print(f"Reviews processed this run: {', '.join(args.reviews)}")
    print(f"Studies processed this run: {total}")
    print("PMID resolution method counts (this run; a study can use more than one method):")
    for method, count in sorted(method_counts.items(), key=lambda item: -item[1]):
        print(f"  {method:<20} {count}")
    print(f"Studies with at least one resolved PMID: {total - unresolved_count}/{total}")
    print(f"Unique PMIDs resolved: {len(all_resolved_pmids)}")
    print(f"Studies with a Semantic Scholar citation count and computable citations/year: {citation_hits}/{total}")
    print(f"Studies with a known open-access status: {open_access_hits}/{total}")
    print(f"Wrote: {PMID_CACHE_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote: {SEMANTIC_SCHOLAR_CACHE_PATH.relative_to(REPO_ROOT)}")
    print(f"Wrote: {OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(existing_rows)} total rows across all runs)")


if __name__ == "__main__":
    main()
