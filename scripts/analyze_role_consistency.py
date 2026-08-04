#!/usr/bin/env python3
"""Measure within-cell replicate consistency across all role experiments.

Each review's `data/reviews/*/*_role_study_matches.csv` records the studies one response
retrieved. For every (review, model, role) cell there are four independent
replicates. This script computes the pairwise Jaccard similarity between
every replicate pair in a cell, in two scopes:

- ``all_candidates``: every resolved candidate the response named, regardless
  of Cochrane status. This measures raw run-to-run output stability.
- ``included_only``: only candidates matched to a Cochrane-included study
  label. This measures how consistently a model/role finds the same correct
  studies, independent of noise from out-of-scope or hallucinated citations.

A cell's mean Jaccard across its six replicate pairs is a self-consistency
score: 1.0 means all four replicates named the same study set, 0.0 means no
overlap between any pair. It writes one row per (review, model, role, scope)
to `data/analysis/role_consistency_jaccard.csv`.
"""

from __future__ import annotations

import csv
import itertools
import statistics as stats
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared.review_registry import (  # noqa: E402
    ANALYSIS_DATA_DIR,
    review_sources,
)

RETRIEVAL_BIAS_DIR = REPO_ROOT
OUTPUT_PATH = ANALYSIS_DATA_DIR / "role_consistency_jaccard.csv"
MODELS = ("claude", "gemini", "gpt")
ROLES = ("patient", "clinician", "researcher")


def match_csv_paths() -> list[Path]:
    """Return every registered review's role-study-matches CSV."""

    return [source.matches_path for source in review_sources()]


def review_id_from_path(path: Path) -> str:
    return path.parent.name


def replicate_sets(
    rows: list[dict[str, str]],
    key_field: str,
    replicate_keys: set[tuple[str, str, str]],
) -> dict[tuple[str, str, str], set[str]]:
    """Map (model, role, replicate) to the set of distinct candidate identities."""

    sets: dict[tuple[str, str, str], set[str]] = {
        key: set() for key in replicate_keys
    }
    for row in rows:
        value = row[key_field].strip()
        if not value:
            continue
        values = (
            [part.strip() for part in value.split("||") if part.strip()]
            if key_field == "cochrane_study_label"
            else [value]
        )
        sets[(row["model"], row["role_id"], row["replicate"])].update(values)
    return sets


def validate_run_matrix(
    review: str, replicate_keys: set[tuple[str, str, str]]
) -> None:
    """Require four recorded replicates for every model-role cell."""

    expected_replicates = {"1", "2", "3", "4"}
    problems = {}
    for model in MODELS:
        for role in ROLES:
            found = {
                replicate
                for key_model, key_role, replicate in replicate_keys
                if key_model == model and key_role == role
            }
            if found != expected_replicates:
                problems[f"{model}/{role}"] = sorted(found)
    if problems:
        raise ValueError(f"{review}: incomplete replicate matrix: {problems}")


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def cell_scores(
    sets_by_replicate: dict[tuple[str, str, str], set[str]], model: str, role: str
) -> tuple[list[float], list[int]]:
    """Return pairwise Jaccard scores and set sizes for one (model, role) cell."""

    replicates = sorted(
        rk for rk in sets_by_replicate if rk[0] == model and rk[1] == role
    )
    pairs = itertools.combinations(replicates, 2)
    scores = [
        jaccard(sets_by_replicate[r1], sets_by_replicate[r2]) for r1, r2 in pairs
    ]
    sizes = [len(sets_by_replicate[r]) for r in replicates]
    return scores, sizes


def build_rows() -> list[dict[str, str | int | float]]:
    """Compute per (review, model, role, scope) consistency rows."""

    scopes = {
        "all_candidates": "canonical_candidate",
        "included_only": "cochrane_study_label",
    }
    rows: list[dict[str, str | int | float]] = []
    for path in match_csv_paths():
        review = review_id_from_path(path)
        with path.open(newline="", encoding="utf-8") as handle:
            all_rows = list(csv.DictReader(handle))
        replicate_keys = {
            (row["model"], row["role_id"], row["replicate"])
            for row in all_rows
        }
        validate_run_matrix(review, replicate_keys)
        for scope, key_field in scopes.items():
            source_rows = (
                all_rows
                if scope == "all_candidates"
                else [r for r in all_rows if r["ground_truth_status"] == "included"]
            )
            sets = replicate_sets(source_rows, key_field, replicate_keys)
            for model in MODELS:
                for role in ROLES:
                    scores, sizes = cell_scores(sets, model, role)
                    if not scores:
                        continue
                    rows.append(
                        {
                            "review": review,
                            "model": model,
                            "role": role,
                            "scope": scope,
                            "n_replicates": len(sizes),
                            "n_pairs": len(scores),
                            "mean_jaccard": round(stats.mean(scores), 3),
                            "stdev_jaccard": round(
                                stats.stdev(scores) if len(scores) > 1 else 0.0, 3
                            ),
                            "mean_set_size": round(stats.mean(sizes), 2),
                        }
                    )
    return rows


def write_csv(path: Path, rows: list[dict[str, str | int | float]]) -> None:
    """Write a non-empty consistency table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, str | int | float]]) -> None:
    """Print aggregate self-consistency by model, per scope."""

    for scope in ("all_candidates", "included_only"):
        print(f"=== {scope} ===")
        by_model: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            if row["scope"] == scope:
                by_model[str(row["model"])].append(float(row["mean_jaccard"]))
        for model in MODELS:
            values = by_model[model]
            print(
                f"  {model:<8} n_cells={len(values):<3} "
                f"mean_jaccard={stats.mean(values):.3f} "
                f"stdev={stats.stdev(values):.3f}"
            )
    print(f"Wrote: {OUTPUT_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the cross-review role-consistency Jaccard table."""

    rows = build_rows()
    write_csv(OUTPUT_PATH, rows)
    print_summary(rows)


if __name__ == "__main__":
    main()
