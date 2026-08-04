#!/usr/bin/env python3
"""Build the static multi-review retrieval-bias demo data."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from random import Random
from statistics import fmean, median, stdev
from typing import Any

from overlap_metrics import (
    calculate_balanced_label_permutation_baseline,
    calculate_blocked_mean_range_permutation_test,
    calculate_chi_square_test,
    calculate_dunn_posthoc_test,
    calculate_fisher_exact_test,
    calculate_fisher_posthoc_test,
    calculate_kruskal_wallis_test,
    calculate_mann_whitney_test,
    calculate_multi_set_jaccard,
    calculate_replicate_consistency,
    calculate_spearman_correlation,
    calculate_three_set_regions,
    calculate_two_set_regions,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.review_registry import (  # noqa: E402
    ANALYSIS_DATA_DIR,
    ReviewSource,
    review_sources,
)

DEFAULT_CHARACTERISTIC_ROWS = ANALYSIS_DATA_DIR / "recall_pattern_by_characteristic.csv"
DEFAULT_LOGISTIC_REGRESSION_RESULTS = (
    ANALYSIS_DATA_DIR / "logistic_regression_results.json"
)
DEFAULT_ROLE_DEPENDENCE_LOGISTIC_REGRESSION_RESULTS = (
    ANALYSIS_DATA_DIR / "role_dependence_logistic_regression_results.json"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data.js"

MODEL_ORDER = {"claude": 0, "gemini": 1, "gpt": 2}
CROSS_REVIEW_MODEL_LABELS = {
    "claude": "Claude",
    "gemini": "Gemini",
    "gpt": "ChatGPT",
}
ROLE_SHORT_LABELS = {
    "patient": "Patient",
    "clinician": "Clinician",
    "researcher": "Researcher",
}
CROSS_REVIEW_ROLE_LABELS = {
    role: {"shortLabel": label, "prompt": ""}
    for role, label in ROLE_SHORT_LABELS.items()
}
PERMUTATION_COUNT = 50_000
PERMUTATION_SEED = 20260715


def load_matches(path: Path) -> list[dict[str, str]]:
    """Read the curated study-match audit rows."""

    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_role_labels(readme_path: Path) -> dict[str, dict[str, str]]:
    """Read the three verbatim experiment prompts from a review README."""

    text = readme_path.read_text(encoding="utf-8")
    try:
        prompts_section = text.split("## Prompts", 1)[1].split("\n## ", 1)[0]
    except IndexError as exc:
        raise ValueError(f"Missing Prompts section in {readme_path}") from exc

    prompt_parts: dict[str, list[str]] = defaultdict(list)
    active_role = ""
    for line in prompts_section.splitlines():
        if line.startswith("### "):
            heading = line[4:].strip().lower()
            active_role = next(
                (
                    role
                    for role in ROLE_SHORT_LABELS
                    if role in heading
                ),
                "",
            )
            continue
        if active_role and line.startswith(">"):
            content = line[1:].strip()
            if content:
                prompt_parts[active_role].append(content)

    missing = set(ROLE_SHORT_LABELS) - set(prompt_parts)
    if missing:
        raise ValueError(
            f"Missing role prompts in {readme_path}: {sorted(missing)}"
        )
    return {
        role: {
            "shortLabel": ROLE_SHORT_LABELS[role],
            "prompt": " ".join(prompt_parts[role]),
        }
        for role in ROLE_SHORT_LABELS
    }


def load_model_metadata(
    readme_path: Path,
) -> tuple[dict[str, str], dict[str, str]]:
    """Read recorded chatbot labels and settings from a review run inventory."""

    text = readme_path.read_text(encoding="utf-8")
    try:
        inventory = text.split("## Run inventory", 1)[1].split("\n## ", 1)[0]
    except IndexError as exc:
        raise ValueError(f"Missing Run inventory section in {readme_path}") from exc

    model_labels: dict[str, str] = {}
    model_settings: dict[str, str] = {}
    for line in inventory.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] in {"Chatbot", "---"}:
            continue
        label = cells[0]
        lowered = label.lower()
        if "claude" in lowered:
            model = "claude"
        elif "gemini" in lowered:
            model = "gemini"
        elif "gpt" in lowered:
            model = "gpt"
        else:
            continue
        model_labels[model] = label
        model_settings[model] = cells[1]

    missing = set(MODEL_ORDER) - set(model_labels)
    if missing:
        raise ValueError(
            f"Missing chatbot inventory rows in {readme_path}: {sorted(missing)}"
        )
    return model_labels, model_settings


def split_cochrane_study_labels(value: str) -> list[str]:
    """Return every Cochrane label credited by one response-study row."""

    return [label.strip() for label in value.split(" || ") if label.strip()]


def load_ris_studies(text: str) -> list[dict[str, str]]:
    """Cluster Cochrane RIS reports into the study rows rendered by the demo."""

    records = []
    current: dict[str, list[str]] = defaultdict(list)
    for line in text.splitlines():
        if len(line) < 6 or line[2:6] != "  - ":
            continue
        tag, value = line[:2], line[6:]
        if tag == "ER":
            if current:
                records.append(current)
            current = defaultdict(list)
        else:
            current[tag].append(value)

    studies: dict[str, dict[str, str]] = {}
    for record in records:
        study_label = next(iter(record.get("NS", [])), "").strip()
        if not study_label or study_label in studies:
            continue
        authors = record.get("AU", [])
        author_text = ", ".join(authors[:3])
        if len(authors) > 3:
            author_text += ", et al."
        year = next(iter(record.get("DA", [])), "")[:4]
        title = next(iter(record.get("TI", []) or record.get("TT", [])), "").strip()
        citation_parts = [part for part in (author_text, year, title) if part]
        studies[study_label] = {
            "study_label": study_label,
            "reference_excerpt": ". ".join(citation_parts),
        }
    return list(studies.values())


def load_ris_reference_truth(
    included_text: str,
    excluded_text: str,
    review: dict[str, str],
) -> dict[str, Any]:
    """Build the benchmark-shaped truth needed by the demo directly from RIS files."""

    return {
        "review": review,
        "references": {
            "included_studies": load_ris_studies(included_text),
            "excluded_studies": load_ris_studies(excluded_text),
        },
    }


def display_path(path: Path) -> str:
    """Prefer a repository-relative source path when one is available."""

    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def prepare_experiment(
    benchmark: dict[str, Any],
    matches: list[dict[str, str]],
    *,
    experiment_id: str,
    navigation_label: str,
    dimension_labels: dict[str, dict[str, str]],
    dimension_order: tuple[str, ...],
    model_labels: dict[str, str],
    model_settings: dict[str, str],
    model_order: dict[str, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare one balanced retrieval matrix and its overlap context."""

    dimension_rank = {value: index for index, value in enumerate(dimension_order)}
    run_ids = sorted(
        {row["run_id"] for row in matches},
        key=lambda value: (
            model_order.get(value.split("-")[0], 99),
            dimension_rank.get(value.split("-")[1], 99),
            int(value.split("-")[2]),
        ),
    )
    runs_by_condition: dict[tuple[str, str], list[str]] = defaultdict(list)
    runs_by_model: dict[str, list[str]] = defaultdict(list)
    for run_id in run_ids:
        model, dimension_id, _ = run_id.split("-")
        if model not in model_labels:
            raise ValueError(f"Unknown chatbot model in run ID: {run_id}")
        if dimension_id not in dimension_labels:
            raise ValueError(f"Unknown comparison condition in run ID: {run_id}")
        runs_by_condition[(model, dimension_id)].append(run_id)
        runs_by_model[model].append(run_id)

    expected_conditions = {
        (model, dimension_id)
        for model in model_labels
        for dimension_id in dimension_order
    }
    missing = expected_conditions - set(runs_by_condition)
    extra = set(runs_by_condition) - expected_conditions
    if missing or extra:
        missing = sorted(missing)
        extra = sorted(extra)
        raise ValueError(f"Unbalanced experiment conditions; missing={missing}, extra={extra}")
    repetition_counts = {len(run_group) for run_group in runs_by_condition.values()}
    if len(repetition_counts) != 1:
        raise ValueError(f"Unequal repetition counts across conditions: {repetition_counts}")

    citation_count_by_run: dict[str, int] = defaultdict(int)
    included_sets_by_run: dict[str, set[str]] = defaultdict(set)
    excluded_sets_by_run: dict[str, set[str]] = defaultdict(set)
    candidate_sets_by_run: dict[str, set[str]] = defaultdict(set)
    for row in matches:
        run_id = row["run_id"]
        citation_count_by_run[run_id] += 1
        candidate = str(row.get("canonical_candidate", "")).strip()
        if candidate:
            candidate_sets_by_run[run_id].add(candidate)
        cochrane_labels = split_cochrane_study_labels(
            row.get("cochrane_study_label", "")
        )
        if row.get("ground_truth_status") == "included":
            included_sets_by_run[run_id].update(cochrane_labels)
        elif row.get("ground_truth_status") == "cochrane_excluded":
            excluded_sets_by_run[run_id].update(cochrane_labels)

    # Rows with conflicting bibliographic details (identity_issue=1) - almost
    # always a wrong author/year/journal on an otherwise correctly-identified
    # study, not a fabricated one; see build_citation_issue_summary.
    identity_issue_rows = [
        {
            "runId": row["run_id"],
            "model": row["model"],
            "roleId": row["role_id"],
            "reportedCitation": row.get("reported_citation", ""),
            "resolvedStudyLabel": row.get("cochrane_study_label") or row.get("canonical_candidate", ""),
            "notes": row.get("notes", ""),
        }
        for row in matches
        if row.get("identity_issue") == "1"
    ]
    matched_rows_by_model: dict[str, int] = defaultdict(int)
    matched_rows_by_role: dict[str, int] = defaultdict(int)
    matched_rows_by_model_role: dict[tuple[str, str], int] = defaultdict(int)
    for row in matches:
        model = row["model"]
        role_id = row["role_id"]
        matched_rows_by_model[model] += 1
        matched_rows_by_role[role_id] += 1
        matched_rows_by_model_role[(model, role_id)] += 1

    conditions = []
    condition_run_ids = []
    for model, dimension_id in sorted(
        expected_conditions,
        key=lambda value: (model_order[value[0]], dimension_rank[value[1]]),
    ):
        condition_runs = runs_by_condition[(model, dimension_id)]
        condition = dimension_labels[dimension_id]
        average_citation_count = (
            sum(citation_count_by_run[run_id] for run_id in condition_runs)
            / len(condition_runs)
            if condition_runs
            else None
        )
        conditions.append(
            {
                "conditionId": f"{model}-{dimension_id}",
                "model": model,
                "modelLabel": model_labels[model],
                "modelSetting": model_settings[model],
                "conditionLabel": condition["shortLabel"],
                "conditionPrompt": condition["prompt"],
                "repetitionCount": len(condition_runs),
                "averageCitationCount": average_citation_count,
            }
        )
        condition_run_ids.append(condition_runs)

    model_summaries = []
    for model in sorted(runs_by_model, key=lambda value: model_order[value]):
        model_runs = runs_by_model[model]
        model_summaries.append(
            {
                "model": model,
                "responseCount": len(model_runs),
                "averageCitationCount": sum(
                    citation_count_by_run[run_id] for run_id in model_runs
                )
                / len(model_runs),
            }
        )

    matches_by_study_run: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in matches:
        for cochrane_label in split_cochrane_study_labels(
            row.get("cochrane_study_label", "")
        ):
            matches_by_study_run[(cochrane_label, row["run_id"])].append(row)

    def study_rows(reference_status: str) -> list[dict[str, Any]]:
        """Aggregate each Cochrane study across the prepared conditions."""

        benchmark_key = f"{reference_status}_studies"
        expected_match_status = (
            "included" if reference_status == "included" else "cochrane_excluded"
        )
        studies = []
        for study in benchmark["references"][benchmark_key]:
            study_label = study["study_label"]
            condition_results = []
            for condition_runs in condition_run_ids:
                condition_matches = []
                for run_id in condition_runs:
                    candidates = [
                        row
                        for row in matches_by_study_run.get((study_label, run_id), [])
                        if row["ground_truth_status"] == expected_match_status
                    ]
                    if len(candidates) > 1:
                        raise ValueError(f"Multiple annotations for {study_label} in {run_id}")
                    condition_matches.extend(candidates)
                retrieved_count = len(condition_matches)
                repetition_count = len(condition_runs)
                condition_results.append(
                    {
                        "retrievedCount": retrieved_count,
                        "repetitionCount": repetition_count,
                        "retrievalRate": (
                            retrieved_count / repetition_count
                            if repetition_count
                            else None
                        ),
                        "identityIssueCount": sum(
                            row["identity_issue"] == "1" for row in condition_matches
                        ),
                    }
                )
            studies.append(
                {
                    "studyLabel": study_label,
                    "referenceExcerpt": str(study.get("reference_excerpt") or "").strip(),
                    "retrievedCount": sum(
                        result["retrievedCount"] for result in condition_results
                    ),
                    "conditionResults": condition_results,
                }
            )
        return studies

    included = study_rows("included")
    excluded = study_rows("excluded")
    included_sets_by_condition = {
        condition["conditionId"]: set().union(
            *(included_sets_by_run[run_id] for run_id in condition_run_ids[index])
        )
        for index, condition in enumerate(conditions)
    }
    experiment = {
        "experimentId": experiment_id,
        "navigationLabel": navigation_label,
        "overview": {
            "includedStudyCount": len(included),
            "excludedStudyCount": len(excluded),
            "conditionCount": len(conditions),
            "repetitionCount": len(run_ids),
        },
        "modelSummaries": model_summaries,
        "conditions": conditions,
        "sections": {
            "included": included,
            "excluded": excluded,
        },
    }
    analysis_context = {
        "runsByCondition": runs_by_condition,
        "includedSetsByRun": included_sets_by_run,
        "includedSetsByCondition": included_sets_by_condition,
        "citationCountByRun": citation_count_by_run,
        "candidateSetsByRun": candidate_sets_by_run,
        "excludedSetsByRun": excluded_sets_by_run,
        "identityIssueRows": identity_issue_rows,
        "matchedRowCount": len(matches),
        "matchedRowsByModel": matched_rows_by_model,
        "matchedRowsByRole": matched_rows_by_role,
        "matchedRowsByModelRole": matched_rows_by_model_role,
    }
    return experiment, analysis_context


def build_venn_panel(
    *,
    panel_id: str,
    color_scheme: str,
    title: str,
    subtitle: str,
    condition_groups: list[list[str]],
    set_labels: list[str],
    permutation_rule: str,
    permutation_baseline: dict[str, Any],
    included_sets_by_condition: dict[str, set[str]],
    universe_label: str,
    benchmark_study_count: int | None,
    recall_permutation_test: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare one exact partition from two or three retrieval-condition groups.

    `recall_permutation_test` is an optional blocked mean-range permutation
    test (see `calculate_blocked_mean_range_permutation_test`) on the recall
    percentages of this panel's own sets, distinct from `permutation_baseline`
    which tests the sets' Jaccard overlap. `universe_label` names the fixed
    population each set's recall is computed against (e.g. "Cochrane included
    studies"), shown in the demo's figure caption. `benchmark_study_count` is
    that population's size; pass None when there is no fixed external
    population to recall against (e.g. "all named candidates" - every study
    any condition ever named, which has no size independent of this panel's
    own union), in which case the panel's own union count is used and the
    "not recalled"/outside-circle concept does not apply.
    """

    study_sets = [
        set().union(
            *(included_sets_by_condition[condition_id] for condition_id in condition_group)
        )
        for condition_group in condition_groups
    ]
    multi_set_overlap = calculate_multi_set_jaccard(study_sets)
    if len(study_sets) == 2:
        regions = calculate_two_set_regions(study_sets)
    elif len(study_sets) == 3:
        regions = calculate_three_set_regions(study_sets)
    else:
        raise ValueError(f"Venn panels require two or three sets, received {len(study_sets)}")
    for region in regions:
        region["studyCount"] = len(region["studyLabels"])
    resolved_benchmark_count = (
        benchmark_study_count if benchmark_study_count is not None else multi_set_overlap["unionCount"]
    )
    return {
        "panelId": panel_id,
        "colorScheme": color_scheme,
        "title": title,
        "subtitle": subtitle,
        "conditionGroups": condition_groups,
        "setLabels": set_labels,
        "setCounts": [len(studies) for studies in study_sets],
        "unionCount": multi_set_overlap["unionCount"],
        "sharedAllCount": multi_set_overlap["sharedCount"],
        "multiSetJaccard": multi_set_overlap["jaccard"],
        "permutationRule": permutation_rule,
        "permutationBaseline": permutation_baseline,
        "recallPermutationTest": recall_permutation_test,
        "universeLabel": universe_label,
        "benchmarkStudyCount": resolved_benchmark_count,
        "regions": regions,
    }


def add_role_venn(
    experiment: dict[str, Any],
    context: dict[str, Any],
    *,
    model_labels: dict[str, str],
    model_order: dict[str, int],
    role_labels: dict[str, dict[str, str]],
) -> None:
    """Add pooled main effects above model-stratified post-hoc role overlaps."""

    runs_by_condition = context["runsByCondition"]
    included_sets_by_run = context["includedSetsByRun"]
    included_sets_by_condition = context["includedSetsByCondition"]
    role_models = tuple(sorted(model_labels, key=lambda model: model_order[model]))
    included_study_count = int(experiment["overview"]["includedStudyCount"])

    main_effect_rng = Random(PERMUTATION_SEED)
    chatbot_permutation = calculate_balanced_label_permutation_baseline(
        [
            [
                included_sets_by_run[run_id]
                for model in role_models
                for run_id in runs_by_condition[(model, role_id)]
            ]
            for role_id in ("patient", "clinician", "researcher")
        ],
        group_count=len(role_models),
        permutation_count=PERMUTATION_COUNT,
        rng=main_effect_rng,
    )
    role_permutation = calculate_balanced_label_permutation_baseline(
        [
            [
                included_sets_by_run[run_id]
                for role_id in ("patient", "clinician", "researcher")
                for run_id in runs_by_condition[(model, role_id)]
            ]
            for model in role_models
        ],
        group_count=3,
        permutation_count=PERMUTATION_COUNT,
        rng=main_effect_rng,
    )
    main_effect_panels = [
        build_venn_panel(
            panel_id="role-chatbot-main",
            color_scheme="role-chatbot",
            title="Chatbot",
            subtitle="Aggregated across all roles · 12 answers per set",
            condition_groups=[
                [
                    f"{model}-{role_id}"
                    for role_id in ("patient", "clinician", "researcher")
                ]
                for model in role_models
            ],
            set_labels=[model_labels[model] for model in role_models],
            permutation_rule=(
                "Chatbot labels shuffled within each role block, preserving four "
                "responses per chatbot"
            ),
            permutation_baseline=chatbot_permutation,
            included_sets_by_condition=included_sets_by_condition,
            universe_label="Cochrane included studies",
            benchmark_study_count=included_study_count,
        ),
        build_venn_panel(
            panel_id="role-main",
            color_scheme="role",
            title="User role",
            subtitle="Aggregated across all three chatbots · 12 answers per set",
            condition_groups=[
                [f"{model}-{role_id}" for model in role_models]
                for role_id in ("patient", "clinician", "researcher")
            ],
            set_labels=[
                role_labels[role_id]["shortLabel"]
                for role_id in ("patient", "clinician", "researcher")
            ],
            permutation_rule=(
                "Role labels shuffled within each chatbot block, preserving four "
                "responses per role"
            ),
            permutation_baseline=role_permutation,
            included_sets_by_condition=included_sets_by_condition,
            universe_label="Cochrane included studies",
            benchmark_study_count=included_study_count,
        ),
    ]

    post_hoc_rng = Random(PERMUTATION_SEED)
    post_hoc_panels = []
    for model in role_models:
        permutation_baseline = calculate_balanced_label_permutation_baseline(
            [
                [
                    included_sets_by_run[run_id]
                    for role_id in ("patient", "clinician", "researcher")
                    for run_id in runs_by_condition[(model, role_id)]
                ]
            ],
            group_count=3,
            permutation_count=PERMUTATION_COUNT,
            rng=post_hoc_rng,
        )
        post_hoc_panels.append(
            build_venn_panel(
                panel_id=f"{model}-role",
                color_scheme="role",
                title=model_labels[model],
                subtitle=(
                    "Patient, clinician, and researcher · 4 answers per set"
                ),
                condition_groups=[
                    [f"{model}-{role_id}"]
                    for role_id in ("patient", "clinician", "researcher")
                ],
                set_labels=[
                    role_labels[role_id]["shortLabel"]
                    for role_id in ("patient", "clinician", "researcher")
                ],
                permutation_rule=(
                    f"Role labels shuffled within the 12 {model_labels[model]} "
                    "answers, preserving four responses per role"
                ),
                permutation_baseline=permutation_baseline,
                included_sets_by_condition=included_sets_by_condition,
                universe_label="Cochrane included studies",
                benchmark_study_count=included_study_count,
            )
        )
    experiment["venn"] = {
        "studySet": "included",
        "membershipRule": (
            "Each set is the union of included study clusters retrieved across its "
            "contributing answers"
        ),
        "permutationAnalysis": {
            "method": "Balanced response-level label permutation",
            "permutationCount": PERMUTATION_COUNT,
            "seed": PERMUTATION_SEED,
            "intervalLevel": 0.95,
        },
        "panelGroups": [
            {
                "groupId": "main-effects",
                "title": "Main effects",
                "description": (
                    "Each comparison aggregates responses across the other "
                    "experimental dimension."
                ),
                "panels": main_effect_panels,
            },
            {
                "groupId": "post-hoc-effects",
                "title": "Exploratory post-hoc analyses",
                "description": "Role overlap is stratified by chatbot.",
                "panels": post_hoc_panels,
            },
        ],
    }


def prepare_review(
    source: ReviewSource,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and prepare one configured review experiment for the demo."""

    role_labels = load_role_labels(source.readme_path)
    model_labels, model_settings = load_model_metadata(source.readme_path)
    truth = load_ris_reference_truth(
        source.read_source_text("included_ris"),
        source.read_source_text("excluded_ris"),
        {
            "review_id": source.review_id,
            "review_title": source.review_title,
        },
    )
    experiment, context = prepare_experiment(
        truth,
        load_matches(source.matches_path),
        experiment_id=f"{source.review_id.lower()}-user-role",
        navigation_label=source.review_id,
        dimension_labels=role_labels,
        dimension_order=("patient", "clinician", "researcher"),
        model_labels=model_labels,
        model_settings=model_settings,
        model_order=MODEL_ORDER,
    )
    add_role_venn(
        experiment,
        context,
        model_labels=model_labels,
        model_order=MODEL_ORDER,
        role_labels=role_labels,
    )
    if source.review_id == "CD012751":
        experiment["venn"]["membershipRule"] = (
            "Each set is the union of included Cochrane study labels credited to "
            "retrieved study clusters across its contributing answers"
        )
    experiment["review"] = {
        "reviewId": source.review_id,
        "reviewTitle": source.review_title,
    }
    experiment["source"] = {
        "includedRis": source.display_source("included_ris"),
        "excludedRis": source.display_source("excluded_ris"),
        "matches": display_path(source.matches_path),
    }
    return experiment, context


def load_characteristic_rows(path: Path) -> list[dict[str, str]]:
    """Read the recall-pattern/characteristic join table (year, sample size, ...)."""

    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def compute_box_plot_stats(values: list[float]) -> dict[str, Any]:
    """Summarize one group's values as Tukey hinges plus 1.5*IQR outlier flags."""

    sorted_values = sorted(values)
    count = len(sorted_values)
    midpoint = count // 2
    lower_half = sorted_values[:midpoint]
    upper_half = sorted_values[midpoint + 1:] if count % 2 else sorted_values[midpoint:]
    first_quartile = median(lower_half)
    third_quartile = median(upper_half)
    interquartile_range = third_quartile - first_quartile
    lower_fence = first_quartile - 1.5 * interquartile_range
    upper_fence = third_quartile + 1.5 * interquartile_range
    inside_fences = [value for value in sorted_values if lower_fence <= value <= upper_fence]
    outliers = [value for value in sorted_values if value < lower_fence or value > upper_fence]
    return {
        "n": count,
        "min": sorted_values[0],
        "max": sorted_values[-1],
        "q1": first_quartile,
        "median": median(sorted_values),
        "q3": third_quartile,
        "whiskerLow": min(inside_fences) if inside_fences else sorted_values[0],
        "whiskerHigh": max(inside_fences) if inside_fences else sorted_values[-1],
        "outliers": outliers,
        "values": sorted_values,
    }


# Recall-status (mutually exclusive: recalled by at least one chatbot vs.
# not) and recall-combination (mutually exclusive exact chatbot combination,
# excluding the two single-study "Gemini only"/"Claude+Gemini" patterns)
# groupings, shared by build_characteristic_distributions and
# build_open_access_distribution so both use the same group definitions.
RECALL_STATUS_GROUPS = [
    ("not-recalled", "Not recalled", lambda row: row["recall_pattern"] == "Not recalled"),
    ("recalled", "Recalled", lambda row: row["recall_pattern"] != "Not recalled"),
]
RECALL_COMBINATION_GROUPS = [
    ("claude-only", "Claude only", lambda row: row["recall_pattern"] == "Claude only"),
    ("gpt-only", "GPT only", lambda row: row["recall_pattern"] == "GPT only"),
    ("gemini-gpt", "Gemini+GPT", lambda row: row["recall_pattern"] == "Gemini+GPT"),
    ("claude-gpt", "Claude+GPT", lambda row: row["recall_pattern"] == "Claude+GPT"),
    ("all-three", "All three", lambda row: row["recall_pattern"] == "All three"),
]


def build_characteristic_distributions(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Build year/sample-size/citations-per-year box-plot data for recall-status and recall-combination groups.

    Recall-combination groups are the exact set of chatbot(s) that recalled a
    study (e.g. "Claude only", "Claude+GPT", "All three"), read directly from
    the precomputed `recall_pattern` field - mutually exclusive, unlike a
    per-chatbot "did this chatbot recall it at least once" grouping, which
    would double-count a study recalled by multiple chatbots. "Gemini only"
    and "Claude+Gemini" are excluded here: each has only one study in the
    current data, which would add two single-point box plots for little
    signal; those two studies remain counted in the "recalled vs. not"
    comparison above. Each metric also gets a Kruskal-Wallis omnibus test
    across the recall-combination groups and, following that, Dunn's
    Bonferroni-adjusted pairwise post-hoc test between every pair of groups.
    """

    recall_status_groups = RECALL_STATUS_GROUPS
    recall_combination_groups = RECALL_COMBINATION_GROUPS

    def build_dimension(
        groups: list[tuple[str, str, Any]], field: str
    ) -> list[dict[str, Any]]:
        items = []
        for group_id, label, predicate in groups:
            values = [float(row[field]) for row in rows if predicate(row) and row[field].strip()]
            if not values:
                raise ValueError(f"No {field} values found for group {group_id}")
            items.append(
                {"groupId": group_id, "label": label, "stats": compute_box_plot_stats(values)}
            )
        return items

    def build_recall_status_test(items: list[dict[str, Any]]) -> dict[str, Any]:
        """Mann-Whitney U between the two mutually exclusive recall-status groups."""

        not_recalled = next(item for item in items if item["groupId"] == "not-recalled")
        recalled = next(item for item in items if item["groupId"] == "recalled")
        return calculate_mann_whitney_test(
            not_recalled["stats"]["values"],
            recalled["stats"]["values"],
            label_a="Not recalled",
            label_b="Recalled",
        )

    def build_recall_combination_test(items: list[dict[str, Any]]) -> dict[str, Any]:
        """Kruskal-Wallis across the mutually exclusive recall-combination groups."""

        return calculate_kruskal_wallis_test(
            [item["stats"]["values"] for item in items],
            labels=[item["label"] for item in items],
        )

    def build_recall_combination_posthoc(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Dunn's pairwise post-hoc comparisons following the Kruskal-Wallis test above."""

        comparisons = calculate_dunn_posthoc_test(
            [item["stats"]["values"] for item in items],
            labels=[item["label"] for item in items],
        )
        group_id_by_label = {item["label"]: item["groupId"] for item in items}
        for comparison in comparisons:
            comparison["groupIdA"] = group_id_by_label[comparison["groupLabelA"]]
            comparison["groupIdB"] = group_id_by_label[comparison["groupLabelB"]]
        return comparisons

    year_recall_status = build_dimension(recall_status_groups, "year")
    sample_size_recall_status = build_dimension(recall_status_groups, "sample_size")
    citations_per_year_recall_status = build_dimension(recall_status_groups, "citations_per_year")
    citation_count_recall_status = build_dimension(recall_status_groups, "citation_count")
    year_recall_combination = build_dimension(recall_combination_groups, "year")
    sample_size_recall_combination = build_dimension(recall_combination_groups, "sample_size")
    citations_per_year_recall_combination = build_dimension(recall_combination_groups, "citations_per_year")
    citation_count_recall_combination = build_dimension(recall_combination_groups, "citation_count")
    return {
        "year": {
            "recallStatus": year_recall_status,
            "recallStatusTest": build_recall_status_test(year_recall_status),
            "recallCombination": year_recall_combination,
            "recallCombinationTest": build_recall_combination_test(year_recall_combination),
            "recallCombinationPosthoc": build_recall_combination_posthoc(year_recall_combination),
        },
        "sampleSize": {
            "recallStatus": sample_size_recall_status,
            "recallStatusTest": build_recall_status_test(sample_size_recall_status),
            "recallCombination": sample_size_recall_combination,
            "recallCombinationTest": build_recall_combination_test(sample_size_recall_combination),
            "recallCombinationPosthoc": build_recall_combination_posthoc(sample_size_recall_combination),
        },
        "citationsPerYear": {
            "recallStatus": citations_per_year_recall_status,
            "recallStatusTest": build_recall_status_test(citations_per_year_recall_status),
            "recallCombination": citations_per_year_recall_combination,
            "recallCombinationTest": build_recall_combination_test(citations_per_year_recall_combination),
            "recallCombinationPosthoc": build_recall_combination_posthoc(citations_per_year_recall_combination),
        },
        "citationCount": {
            "recallStatus": citation_count_recall_status,
            "recallStatusTest": build_recall_status_test(citation_count_recall_status),
            "recallCombination": citation_count_recall_combination,
            "recallCombinationTest": build_recall_combination_test(citation_count_recall_combination),
            "recallCombinationPosthoc": build_recall_combination_posthoc(citation_count_recall_combination),
        },
    }


def build_open_access_distribution(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Build open-access rate data for recall-status and recall-combination groups.

    is_open_access is binary, unlike the four characteristics above, so this
    reports rates (open count / total with a known status) per group instead
    of box-plot statistics: a Fisher's exact test for the two mutually
    exclusive recall-status groups, and a chi-square omnibus test followed by
    Dunn-style Bonferroni-adjusted pairwise Fisher's exact tests for the five
    mutually exclusive recall-combination groups - the same statistical
    pairing (omnibus + pairwise post-hoc) as build_characteristic_distributions
    uses for its continuous metrics, adapted for a binary outcome. Reuses the
    same recall-status/recall-combination group definitions.
    """

    def rate_items(groups: list[tuple[str, str, Any]]) -> list[dict[str, Any]]:
        items = []
        for group_id, label, predicate in groups:
            known_values = [
                int(row["is_open_access"]) for row in rows
                if predicate(row) and row["is_open_access"].strip()
            ]
            if not known_values:
                raise ValueError(f"No is_open_access values found for group {group_id}")
            items.append(
                {
                    "groupId": group_id,
                    "label": label,
                    "openCount": sum(known_values),
                    "total": len(known_values),
                    "rate": sum(known_values) / len(known_values),
                }
            )
        return items

    recall_status_items = rate_items(RECALL_STATUS_GROUPS)
    recall_combination_items = rate_items(RECALL_COMBINATION_GROUPS)

    not_recalled_item = next(item for item in recall_status_items if item["groupId"] == "not-recalled")
    recalled_item = next(item for item in recall_status_items if item["groupId"] == "recalled")
    recall_status_test = calculate_fisher_exact_test(
        not_recalled_item["openCount"], not_recalled_item["total"],
        recalled_item["openCount"], recalled_item["total"],
        label_a="Not recalled", label_b="Recalled",
    )

    recall_combination_test = calculate_chi_square_test(
        [item["openCount"] for item in recall_combination_items],
        [item["total"] for item in recall_combination_items],
        labels=[item["label"] for item in recall_combination_items],
    )
    recall_combination_posthoc = calculate_fisher_posthoc_test(
        [item["openCount"] for item in recall_combination_items],
        [item["total"] for item in recall_combination_items],
        labels=[item["label"] for item in recall_combination_items],
    )
    group_id_by_label = {item["label"]: item["groupId"] for item in recall_combination_items}
    for comparison in recall_combination_posthoc:
        comparison["groupIdA"] = group_id_by_label[comparison["groupLabelA"]]
        comparison["groupIdB"] = group_id_by_label[comparison["groupLabelB"]]

    return {
        "recallStatus": recall_status_items,
        "recallStatusTest": recall_status_test,
        "recallCombination": recall_combination_items,
        "recallCombinationTest": recall_combination_test,
        "recallCombinationPosthoc": recall_combination_posthoc,
    }


# Role-recall-combination groups (mutually exclusive exact user-role
# combination, read from role_recall_pattern) focus on studies retrieved by
# the researcher role and compare them with studies retrieved by every role.
# Non-researcher-only patterns remain in the shared "recalled vs. not"
# comparison but are outside this narrower researcher-contribution analysis.
ROLE_RECALL_COMBINATION_GROUPS = [
    ("role-researcher-only", "Researcher only", lambda row: row["role_recall_pattern"] == "Researcher only"),
    (
        "role-clinician-researcher",
        "Clinician+Researcher",
        lambda row: row["role_recall_pattern"] == "Clinician+Researcher",
    ),
    (
        "role-patient-researcher",
        "Patient+Researcher",
        lambda row: row["role_recall_pattern"] == "Patient+Researcher",
    ),
    ("role-all-three", "All three", lambda row: row["role_recall_pattern"] == "All three"),
]


def build_role_characteristic_distributions(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Build year/sample-size/citations-per-year box-plot data for role-recall-combination groups.

    Mirrors build_characteristic_distributions's recall-combination
    treatment (Kruskal-Wallis omnibus plus Dunn's Bonferroni-adjusted
    pairwise post-hoc), grouped by which user role(s) recalled a study
    (role_recall_pattern) instead of which chatbot(s) did. The "recalled vs.
    not" comparison isn't repeated here: recall status doesn't depend on
    which dimension groups it, so it's identical to the recallStatus group
    build_characteristic_distributions already reports.
    """

    def build_dimension(field: str) -> list[dict[str, Any]]:
        items = []
        for group_id, label, predicate in ROLE_RECALL_COMBINATION_GROUPS:
            values = [float(row[field]) for row in rows if predicate(row) and row[field].strip()]
            if not values:
                raise ValueError(f"No {field} values found for group {group_id}")
            items.append(
                {"groupId": group_id, "label": label, "stats": compute_box_plot_stats(values)}
            )
        return items

    def build_combination_test(items: list[dict[str, Any]]) -> dict[str, Any]:
        return calculate_kruskal_wallis_test(
            [item["stats"]["values"] for item in items],
            labels=[item["label"] for item in items],
        )

    def build_combination_posthoc(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        comparisons = calculate_dunn_posthoc_test(
            [item["stats"]["values"] for item in items],
            labels=[item["label"] for item in items],
        )
        group_id_by_label = {item["label"]: item["groupId"] for item in items}
        for comparison in comparisons:
            comparison["groupIdA"] = group_id_by_label[comparison["groupLabelA"]]
            comparison["groupIdB"] = group_id_by_label[comparison["groupLabelB"]]
        return comparisons

    result: dict[str, Any] = {}
    for key, field in (
        ("year", "year"),
        ("sampleSize", "sample_size"),
        ("citationsPerYear", "citations_per_year"),
        ("citationCount", "citation_count"),
    ):
        items = build_dimension(field)
        result[key] = {
            "recallCombination": items,
            "recallCombinationTest": build_combination_test(items),
            "recallCombinationPosthoc": build_combination_posthoc(items),
        }
    return result


def build_role_open_access_distribution(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Build open-access rate data for role-recall-combination groups.

    Mirrors build_open_access_distribution's recall-combination treatment
    (chi-square omnibus plus Bonferroni-adjusted pairwise Fisher's exact
    post-hoc), grouped by role_recall_pattern instead of recall_pattern. The
    recall-status Fisher's exact test isn't repeated here for the same
    reason build_role_characteristic_distributions skips it.
    """

    items = []
    for group_id, label, predicate in ROLE_RECALL_COMBINATION_GROUPS:
        known_values = [
            int(row["is_open_access"]) for row in rows
            if predicate(row) and row["is_open_access"].strip()
        ]
        if not known_values:
            raise ValueError(f"No is_open_access values found for group {group_id}")
        items.append(
            {
                "groupId": group_id,
                "label": label,
                "openCount": sum(known_values),
                "total": len(known_values),
                "rate": sum(known_values) / len(known_values),
            }
        )

    combination_test = calculate_chi_square_test(
        [item["openCount"] for item in items],
        [item["total"] for item in items],
        labels=[item["label"] for item in items],
    )
    combination_posthoc = calculate_fisher_posthoc_test(
        [item["openCount"] for item in items],
        [item["total"] for item in items],
        labels=[item["label"] for item in items],
    )
    group_id_by_label = {item["label"]: item["groupId"] for item in items}
    for comparison in combination_posthoc:
        comparison["groupIdA"] = group_id_by_label[comparison["groupLabelA"]]
        comparison["groupIdB"] = group_id_by_label[comparison["groupLabelB"]]

    return {
        "recallCombination": items,
        "recallCombinationTest": combination_test,
        "recallCombinationPosthoc": combination_posthoc,
    }


# Role-universality groups pool the three retained role-recall-combination
# groups above into one "Researcher-dependent recall" group (every one of
# them includes the researcher role) and compare it against "Role-agnostic
# recall" (All three roles) as a plain two-group split. Unlike the four-way
# ROLE_RECALL_COMBINATION_GROUPS split above, this answers a narrower
# question directly: what distinguishes studies that needed a
# researcher-role response to surface at all, from studies any role's
# response finds. "Not recalled" and the non-researcher-only patterns omitted
# from ROLE_RECALL_COMBINATION_GROUPS are excluded from both groups here too.
ROLE_UNIVERSALITY_GROUPS = [
    (
        "role-dependent",
        "Researcher-dependent recall",
        lambda row: row["role_recall_pattern"] in {"Researcher only", "Clinician+Researcher", "Patient+Researcher"},
    ),
    ("role-agnostic", "Role-agnostic recall", lambda row: row["role_recall_pattern"] == "All three"),
]


def build_role_universality_distributions(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Build year/sample-size/citations-per-year box-plot data for role-universality groups.

    A two-group Mann-Whitney U comparison (Role-agnostic recall vs.
    Researcher-dependent recall), the same two-group treatment
    RECALL_STATUS_GROUPS gets in build_characteristic_distributions, applied
    to ROLE_UNIVERSALITY_GROUPS instead.
    """

    def build_dimension(field: str) -> list[dict[str, Any]]:
        items = []
        for group_id, label, predicate in ROLE_UNIVERSALITY_GROUPS:
            values = [float(row[field]) for row in rows if predicate(row) and row[field].strip()]
            if not values:
                raise ValueError(f"No {field} values found for group {group_id}")
            items.append(
                {"groupId": group_id, "label": label, "stats": compute_box_plot_stats(values)}
            )
        return items

    def build_universality_test(items: list[dict[str, Any]]) -> dict[str, Any]:
        dependent = next(item for item in items if item["groupId"] == "role-dependent")
        agnostic = next(item for item in items if item["groupId"] == "role-agnostic")
        return calculate_mann_whitney_test(
            agnostic["stats"]["values"],
            dependent["stats"]["values"],
            label_a="Role-agnostic recall",
            label_b="Researcher-dependent recall",
        )

    result: dict[str, Any] = {}
    for key, field in (
        ("year", "year"),
        ("sampleSize", "sample_size"),
        ("citationsPerYear", "citations_per_year"),
        ("citationCount", "citation_count"),
    ):
        items = build_dimension(field)
        result[key] = {
            "roleUniversality": items,
            "roleUniversalityTest": build_universality_test(items),
        }
    return result


def build_role_universality_open_access(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Build open-access rate data for role-universality groups (Fisher's exact test).

    Mirrors build_open_access_distribution's recall-status treatment
    (Fisher's exact on a 2x2 table), applied to ROLE_UNIVERSALITY_GROUPS.
    """

    items = []
    for group_id, label, predicate in ROLE_UNIVERSALITY_GROUPS:
        known_values = [
            int(row["is_open_access"]) for row in rows
            if predicate(row) and row["is_open_access"].strip()
        ]
        if not known_values:
            raise ValueError(f"No is_open_access values found for group {group_id}")
        items.append(
            {
                "groupId": group_id,
                "label": label,
                "openCount": sum(known_values),
                "total": len(known_values),
                "rate": sum(known_values) / len(known_values),
            }
        )

    dependent_item = next(item for item in items if item["groupId"] == "role-dependent")
    agnostic_item = next(item for item in items if item["groupId"] == "role-agnostic")
    test = calculate_fisher_exact_test(
        agnostic_item["openCount"], agnostic_item["total"],
        dependent_item["openCount"], dependent_item["total"],
        label_a="Role-agnostic recall", label_b="Researcher-dependent recall",
    )

    return {
        "roleUniversality": items,
        "roleUniversalityTest": test,
    }


def build_citation_issue_summary(
    prepared_reviews: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    """Summarize identity_issue-flagged citations (misattribution, not fabrication) per review.

    identity_issue marks a matched citation with conflicting bibliographic
    details - almost always a wrong author, year, or journal on an otherwise
    correctly-identified study, not an invented one. See
    README.md, "Citation issues (identity_issue) are not
    fabrication," for the full explanation and a dedicated fabrication check.
    This is purely a reporting summary for the demo; identity_issue is not
    used to filter any recall, Venn, or regression number elsewhere in this
    file.
    """

    reviews = []
    total_flagged = 0
    total_matched = 0
    matched_by_model: dict[str, int] = defaultdict(int)
    matched_by_role: dict[str, int] = defaultdict(int)
    matched_by_model_role: dict[tuple[str, str], int] = defaultdict(int)
    flagged_by_model: dict[str, int] = defaultdict(int)
    flagged_by_role: dict[str, int] = defaultdict(int)
    flagged_by_model_role: dict[tuple[str, str], int] = defaultdict(int)
    answer_ids_by_model: dict[str, set[tuple[str, str]]] = defaultdict(set)
    answer_ids_by_role: dict[str, set[tuple[str, str]]] = defaultdict(set)
    answer_ids_by_model_role: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    affected_answer_ids_by_model: dict[str, set[tuple[str, str]]] = defaultdict(set)
    affected_answer_ids_by_role: dict[str, set[tuple[str, str]]] = defaultdict(set)
    affected_answer_ids_by_model_role: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for experiment, context in prepared_reviews:
        review_id = experiment["review"]["reviewId"]
        flagged_rows = context["identityIssueRows"]
        matched_count = int(context["matchedRowCount"])
        total_flagged += len(flagged_rows)
        total_matched += matched_count
        for model, count in context["matchedRowsByModel"].items():
            matched_by_model[model] += count
        for role_id, count in context["matchedRowsByRole"].items():
            matched_by_role[role_id] += count
        for model_role, count in context["matchedRowsByModelRole"].items():
            matched_by_model_role[model_role] += count
        for (model, role_id), run_ids in context["runsByCondition"].items():
            answer_ids = {(review_id, run_id) for run_id in run_ids}
            answer_ids_by_model[model].update(answer_ids)
            answer_ids_by_role[role_id].update(answer_ids)
            answer_ids_by_model_role[(model, role_id)].update(answer_ids)
        for row in flagged_rows:
            model = row["model"]
            role_id = row["roleId"]
            answer_id = (review_id, row["runId"])
            flagged_by_model[model] += 1
            flagged_by_role[role_id] += 1
            flagged_by_model_role[(model, role_id)] += 1
            affected_answer_ids_by_model[model].add(answer_id)
            affected_answer_ids_by_role[role_id].add(answer_id)
            affected_answer_ids_by_model_role[(model, role_id)].add(answer_id)
        example = (
            min(flagged_rows, key=lambda row: (row["model"], row["roleId"], row["reportedCitation"]))
            if flagged_rows
            else None
        )
        reviews.append(
            {
                "reviewId": review_id,
                "flaggedCount": len(flagged_rows),
                "matchedCount": matched_count,
                "rate": len(flagged_rows) / matched_count if matched_count else 0.0,
                "example": (
                    {
                        key: value
                        for key, value in example.items()
                        if key != "runId"
                    }
                    if example
                    else None
                ),
            }
        )

    def issue_rate_item(
        *,
        flagged_count: int,
        matched_count: int,
        affected_answer_count: int,
        answer_count: int,
    ) -> dict[str, Any]:
        return {
            "flaggedCount": flagged_count,
            "matchedCount": matched_count,
            "rate": flagged_count / matched_count if matched_count else 0.0,
            "affectedAnswerCount": affected_answer_count,
            "answerCount": answer_count,
            "answerRate": affected_answer_count / answer_count if answer_count else 0.0,
        }

    by_model = [
        {
            "model": model,
            "label": CROSS_REVIEW_MODEL_LABELS[model],
            **issue_rate_item(
                flagged_count=flagged_by_model[model],
                matched_count=matched_by_model[model],
                affected_answer_count=len(affected_answer_ids_by_model[model]),
                answer_count=len(answer_ids_by_model[model]),
            ),
        }
        for model in sorted(CROSS_REVIEW_MODEL_LABELS, key=lambda value: MODEL_ORDER[value])
    ]
    by_role = [
        {
            "roleId": role_id,
            "label": ROLE_SHORT_LABELS[role_id],
            **issue_rate_item(
                flagged_count=flagged_by_role[role_id],
                matched_count=matched_by_role[role_id],
                affected_answer_count=len(affected_answer_ids_by_role[role_id]),
                answer_count=len(answer_ids_by_role[role_id]),
            ),
        }
        for role_id in ROLE_SHORT_LABELS
    ]
    by_model_role = [
        {
            "model": model,
            "modelLabel": CROSS_REVIEW_MODEL_LABELS[model],
            "roleId": role_id,
            "roleLabel": ROLE_SHORT_LABELS[role_id],
            **issue_rate_item(
                flagged_count=flagged_by_model_role[(model, role_id)],
                matched_count=matched_by_model_role[(model, role_id)],
                affected_answer_count=len(affected_answer_ids_by_model_role[(model, role_id)]),
                answer_count=len(answer_ids_by_model_role[(model, role_id)]),
            ),
        }
        for model in sorted(CROSS_REVIEW_MODEL_LABELS, key=lambda value: MODEL_ORDER[value])
        for role_id in ROLE_SHORT_LABELS
    ]
    total_affected_answers = sum(
        len(values) for values in affected_answer_ids_by_model_role.values()
    )
    total_answers = sum(len(values) for values in answer_ids_by_model_role.values())
    return {
        "reviews": reviews,
        "byModel": by_model,
        "byRole": by_role,
        "byModelRole": by_model_role,
        "totalFlagged": total_flagged,
        "totalMatched": total_matched,
        "overallRate": total_flagged / total_matched if total_matched else 0.0,
        "totalAffectedAnswers": total_affected_answers,
        "totalAnswers": total_answers,
        "overallAnswerRate": (
            total_affected_answers / total_answers if total_answers else 0.0
        ),
    }


# (field, axis label, log-scaled for display) for the four recall-pattern
# predictors, shared by build_predictor_correlations and build_characteristic_distributions.
PREDICTOR_VARIABLES = [
    ("year", "Publication year", False),
    ("sample_size", "Sample size", True),
    ("citations_per_year", "Citations per year", True),
    ("citation_count", "Total citations", True),
]


CORRELATION_GROUPS = [
    ("not-recalled", "Not recalled", lambda row: row["recall_pattern"] == "Not recalled"),
    ("recalled", "Recalled", lambda row: row["recall_pattern"] != "Not recalled"),
]


def build_predictor_correlations(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Build a ggpairs-style scatter-matrix payload for the four numeric predictors.

    A multicollinearity check before fitting a multiple logistic regression
    on recall pattern: if two predictors are strongly correlated, their
    individual regression coefficients become unstable. Only studies with
    all four predictors present are used (design is categorical and
    excluded). Correlations and grouped values are reported both overall and
    split by recall status - mutually exclusive, unlike the overlapping
    by-chatbot groups used elsewhere in this file - so the interactive
    scatter matrix can color points and break down correlations by group,
    matching a typical ggpairs/GGally-style pairwise plot.
    """

    complete_rows = [
        row for row in rows if all(row[field].strip() for field, _, _ in PREDICTOR_VARIABLES)
    ]
    if not complete_rows:
        raise ValueError("No studies have all four predictors present")
    values = {
        field: [float(row[field]) for row in complete_rows] for field, _, _ in PREDICTOR_VARIABLES
    }
    group_id_by_row = [
        next(group_id for group_id, _, predicate in CORRELATION_GROUPS if predicate(row))
        for row in complete_rows
    ]

    def correlation_for_predicate(x_field: str, y_field: str, predicate: Any) -> dict[str, Any]:
        x_subset, y_subset = [], []
        for x_value, y_value, row in zip(values[x_field], values[y_field], complete_rows):
            if predicate(row):
                x_subset.append(x_value)
                y_subset.append(y_value)
        return calculate_spearman_correlation(x_subset, y_subset)

    pairs = []
    for (x_field, x_label, x_log), (y_field, y_label, y_log) in combinations(PREDICTOR_VARIABLES, 2):
        correlations = {"overall": calculate_spearman_correlation(values[x_field], values[y_field])}
        for group_id, _, predicate in CORRELATION_GROUPS:
            correlations[group_id] = correlation_for_predicate(x_field, y_field, predicate)
        pairs.append(
            {
                "xField": x_field,
                "xLabel": x_label,
                "xLogScale": x_log,
                "yField": y_field,
                "yLabel": y_label,
                "yLogScale": y_log,
                "correlations": correlations,
                "points": [
                    {"x": x_value, "y": y_value, "group": group_id}
                    for x_value, y_value, group_id in zip(
                        values[x_field], values[y_field], group_id_by_row
                    )
                ],
            }
        )

    grouped_values = {
        field: {
            group_id: [
                value for value, row_group in zip(values[field], group_id_by_row) if row_group == group_id
            ]
            for group_id, _, _ in CORRELATION_GROUPS
        }
        for field, _, _ in PREDICTOR_VARIABLES
    }
    return {
        "studyCount": len(complete_rows),
        "groups": [
            {
                "groupId": group_id,
                "label": label,
                "n": group_id_by_row.count(group_id),
            }
            for group_id, label, _ in CORRELATION_GROUPS
        ],
        "variables": [
            {"field": field, "label": label, "logScale": log_scaled}
            for field, label, log_scaled in PREDICTOR_VARIABLES
        ],
        "groupedValues": grouped_values,
        "pairs": pairs,
    }


# (field, display label) in reporting order, matching the printed table in
# analyze_recall_logistic_regression.py. The intercept
# ("const") is handled separately since its odds ratio is not a meaningful
# quantity to display (see that script's print_summary for why).
LOGISTIC_REGRESSION_PREDICTOR_ORDER = [
    ("year", "Publication year"),
    ("log_sample_size", "log(Sample size)"),
    ("log_citations_per_year", "log(Citations per year)"),
    ("is_open_access", "Open access"),
]


def load_logistic_regression_results(path: Path) -> dict[str, Any]:
    """Load the pre-computed logistic regression results.

    Produced by analyze_recall_logistic_regression.py, which
    must be run before build_demo.py for this file to exist or be current.
    """

    return json.loads(path.read_text())


def build_logistic_regression_summary(results: dict[str, Any]) -> dict[str, Any]:
    """Shape the pre-computed logistic regression results for demo display."""

    coefficients = results["coefficients"]
    intercept = coefficients["const"]
    rows = []
    for field, label in LOGISTIC_REGRESSION_PREDICTOR_ORDER:
        values = coefficients[field]
        rows.append(
            {
                "field": field,
                "label": label,
                "coefficient": values["coefficient"],
                "clusteredStdErr": values["clusteredStdErr"],
                "clusteredPValue": values["clusteredPValue"],
                "naivePValue": values["naivePValue"],
                "oddsRatio": values["oddsRatio"],
                "oddsRatioCiLow": values["oddsRatioCiLow"],
                "oddsRatioCiHigh": values["oddsRatioCiHigh"],
                "vif": results["vif"][field],
            }
        )
    return {
        "n": results["n"],
        "nClusters": results["nClusters"],
        "citationsPerYearOffset": results["citationsPerYearOffset"],
        "intercept": {
            "coefficient": intercept["coefficient"],
            "clusteredStdErr": intercept["clusteredStdErr"],
            "clusteredPValue": intercept["clusteredPValue"],
            "naivePValue": intercept["naivePValue"],
        },
        "rows": rows,
        "pseudoRSquared": results["pseudoRSquared"],
        "logLikelihood": results["logLikelihood"],
        "llrPValue": results["llrPValue"],
    }


def build_cross_review_summary(
    prepared_reviews: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    model_labels: dict[str, str],
    model_order: dict[str, int],
    role_labels: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Aggregate main effects and blocked tests across configured review experiments."""

    if not prepared_reviews:
        raise ValueError("Cannot build a cross-review summary without review experiments")
    model_ids = tuple(sorted(model_labels, key=lambda model: model_order[model]))
    role_ids = ("patient", "clinician", "researcher")
    citation_values_by_model: dict[str, list[float]] = defaultdict(list)
    citation_values_by_role: dict[str, list[float]] = defaultdict(list)
    recall_values_by_model: dict[str, list[float]] = defaultdict(list)
    recall_values_by_role: dict[str, list[float]] = defaultdict(list)
    jaccard_all_by_model: dict[str, list[float]] = defaultdict(list)
    jaccard_all_by_role: dict[str, list[float]] = defaultdict(list)
    jaccard_included_by_model: dict[str, list[float]] = defaultdict(list)
    jaccard_included_by_role: dict[str, list[float]] = defaultdict(list)
    overall_included_recall_values: list[float] = []
    overall_excluded_recall_values: list[float] = []
    included_sets_by_group: dict[str, set[str]] = {
        **{f"chatbot-{model}": set() for model in model_ids},
        **{f"role-{role_id}": set() for role_id in role_ids},
        **{
            f"cell-{model}-{role_id}": set()
            for model in model_ids
            for role_id in role_ids
        },
    }
    # Excluded and all-candidates only need main-effect (chatbot/role) groups,
    # not per-cell post-hoc groups - the user asked to see all-named-candidate
    # and Cochrane-excluded-only Venn plots for the two main effects only.
    excluded_sets_by_group: dict[str, set[str]] = {
        **{f"chatbot-{model}": set() for model in model_ids},
        **{f"role-{role_id}": set() for role_id in role_ids},
    }
    candidate_sets_by_group: dict[str, set[str]] = {
        **{f"chatbot-{model}": set() for model in model_ids},
        **{f"role-{role_id}": set() for role_id in role_ids},
    }
    chatbot_recall_blocks = []
    role_recall_blocks = []
    chatbot_study_set_blocks = []
    role_study_set_blocks = []
    chatbot_excluded_recall_blocks = []
    role_excluded_recall_blocks = []
    chatbot_excluded_study_set_blocks = []
    role_excluded_study_set_blocks = []
    chatbot_candidate_study_set_blocks = []
    role_candidate_study_set_blocks = []
    # Post-hoc blocking: kept separate from the flat lists above so the main-effect
    # permutation tests keep drawing from the same RNG sequence as before.
    role_study_set_blocks_by_model: dict[str, list[list[set[str]]]] = defaultdict(list)
    chatbot_study_set_blocks_by_role: dict[str, list[list[set[str]]]] = defaultdict(list)
    role_recall_blocks_by_model: dict[str, list[list[float]]] = defaultdict(list)
    chatbot_recall_blocks_by_role: dict[str, list[list[float]]] = defaultdict(list)
    included_study_count = 0
    excluded_study_count = 0
    response_count = 0

    for experiment, context in prepared_reviews:
        review_id = experiment["review"]["reviewId"]
        review_included_count = int(experiment["overview"]["includedStudyCount"])
        if review_included_count < 1:
            raise ValueError(f"Cross-review recall requires included studies for {review_id}")
        review_excluded_count = int(experiment["overview"]["excludedStudyCount"])
        if review_excluded_count < 1:
            raise ValueError(f"Cross-review excluded-study recall requires excluded studies for {review_id}")
        included_study_count += review_included_count
        excluded_study_count += review_excluded_count
        runs_by_condition = context["runsByCondition"]
        included_sets_by_run = context["includedSetsByRun"]
        excluded_sets_by_run = context["excludedSetsByRun"]
        citation_count_by_run = context["citationCountByRun"]
        candidate_sets_by_run = context["candidateSetsByRun"]
        namespaced_sets_by_run = {
            run_id: {f"{review_id} · {study_label}" for study_label in study_labels}
            for run_id, study_labels in included_sets_by_run.items()
        }
        namespaced_excluded_sets_by_run = {
            run_id: {f"{review_id} · {study_label}" for study_label in study_labels}
            for run_id, study_labels in excluded_sets_by_run.items()
        }
        namespaced_candidate_sets_by_run = {
            run_id: {f"{review_id} · {candidate}" for candidate in candidates}
            for run_id, candidates in candidate_sets_by_run.items()
        }

        for model in model_ids:
            for role_id in role_ids:
                condition_runs = runs_by_condition[(model, role_id)]
                response_count += len(condition_runs)
                for run_id in condition_runs:
                    citations = float(citation_count_by_run[run_id])
                    recall = len(included_sets_by_run[run_id]) / review_included_count
                    excluded_recall = (
                        len(excluded_sets_by_run[run_id]) / review_excluded_count
                    )
                    citation_values_by_model[model].append(citations)
                    citation_values_by_role[role_id].append(citations)
                    recall_values_by_model[model].append(recall)
                    recall_values_by_role[role_id].append(recall)
                    overall_included_recall_values.append(recall)
                    overall_excluded_recall_values.append(excluded_recall)
                    included_sets_by_group[f"chatbot-{model}"].update(
                        namespaced_sets_by_run[run_id]
                    )
                    included_sets_by_group[f"role-{role_id}"].update(
                        namespaced_sets_by_run[run_id]
                    )
                    excluded_sets_by_group[f"chatbot-{model}"].update(
                        namespaced_excluded_sets_by_run.get(run_id, set())
                    )
                    excluded_sets_by_group[f"role-{role_id}"].update(
                        namespaced_excluded_sets_by_run.get(run_id, set())
                    )
                    candidate_sets_by_group[f"chatbot-{model}"].update(
                        namespaced_candidate_sets_by_run.get(run_id, set())
                    )
                    candidate_sets_by_group[f"role-{role_id}"].update(
                        namespaced_candidate_sets_by_run.get(run_id, set())
                    )
                    included_sets_by_group[f"cell-{model}-{role_id}"].update(
                        namespaced_sets_by_run[run_id]
                    )
                cell_all_candidates = calculate_replicate_consistency(
                    [candidate_sets_by_run[run_id] for run_id in condition_runs]
                )
                cell_included_only = calculate_replicate_consistency(
                    [included_sets_by_run[run_id] for run_id in condition_runs]
                )
                jaccard_all_by_model[model].append(cell_all_candidates["meanJaccard"])
                jaccard_all_by_role[role_id].append(cell_all_candidates["meanJaccard"])
                jaccard_included_by_model[model].append(cell_included_only["meanJaccard"])
                jaccard_included_by_role[role_id].append(cell_included_only["meanJaccard"])

        for role_id in role_ids:
            ordered_run_ids = [
                run_id
                for model in model_ids
                for run_id in runs_by_condition[(model, role_id)]
            ]
            recall_block = [
                len(included_sets_by_run[run_id]) / review_included_count
                for run_id in ordered_run_ids
            ]
            chatbot_recall_blocks.append(recall_block)
            chatbot_recall_blocks_by_role[role_id].append(recall_block)
            chatbot_study_set_blocks.append(
                [namespaced_sets_by_run[run_id] for run_id in ordered_run_ids]
            )
            chatbot_study_set_blocks_by_role[role_id].append(
                [namespaced_sets_by_run[run_id] for run_id in ordered_run_ids]
            )
            chatbot_excluded_recall_blocks.append(
                [
                    len(excluded_sets_by_run[run_id]) / review_excluded_count
                    for run_id in ordered_run_ids
                ]
            )
            chatbot_excluded_study_set_blocks.append(
                [namespaced_excluded_sets_by_run.get(run_id, set()) for run_id in ordered_run_ids]
            )
            chatbot_candidate_study_set_blocks.append(
                [namespaced_candidate_sets_by_run.get(run_id, set()) for run_id in ordered_run_ids]
            )
        for model in model_ids:
            ordered_run_ids = [
                run_id
                for role_id in role_ids
                for run_id in runs_by_condition[(model, role_id)]
            ]
            recall_block = [
                len(included_sets_by_run[run_id]) / review_included_count
                for run_id in ordered_run_ids
            ]
            role_recall_blocks.append(recall_block)
            role_recall_blocks_by_model[model].append(recall_block)
            role_study_set_blocks.append(
                [namespaced_sets_by_run[run_id] for run_id in ordered_run_ids]
            )
            role_study_set_blocks_by_model[model].append(
                [namespaced_sets_by_run[run_id] for run_id in ordered_run_ids]
            )
            role_excluded_recall_blocks.append(
                [
                    len(excluded_sets_by_run[run_id]) / review_excluded_count
                    for run_id in ordered_run_ids
                ]
            )
            role_excluded_study_set_blocks.append(
                [namespaced_excluded_sets_by_run.get(run_id, set()) for run_id in ordered_run_ids]
            )
            role_candidate_study_set_blocks.append(
                [namespaced_candidate_sets_by_run.get(run_id, set()) for run_id in ordered_run_ids]
            )

    if not (
        len(overall_included_recall_values)
        == len(overall_excluded_recall_values)
        == response_count
    ):
        raise ValueError("Cross-review overall recall did not cover every response")

    chatbot_recall_test = calculate_blocked_mean_range_permutation_test(
        chatbot_recall_blocks,
        group_count=len(model_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
    )
    role_recall_test = calculate_blocked_mean_range_permutation_test(
        role_recall_blocks,
        group_count=len(role_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
    )
    # Post-hoc recall tests: same blocked mean-range statistic as the two main-effect
    # tests above, but each one is restricted to a single chatbot's roles or a single
    # role's chatbots, blocked by review only (no role/chatbot block dimension left
    # to control for, since that's the one thing being tested here).
    role_recall_test_by_model = {
        model: calculate_blocked_mean_range_permutation_test(
            role_recall_blocks_by_model[model],
            group_count=len(role_ids),
            permutation_count=PERMUTATION_COUNT,
            rng=Random(PERMUTATION_SEED),
        )
        for model in model_ids
    }
    chatbot_recall_test_by_role = {
        role_id: calculate_blocked_mean_range_permutation_test(
            chatbot_recall_blocks_by_role[role_id],
            group_count=len(model_ids),
            permutation_count=PERMUTATION_COUNT,
            rng=Random(PERMUTATION_SEED),
        )
        for role_id in role_ids
    }

    chatbot_condition_groups = [[f"chatbot-{model}"] for model in model_ids]
    role_condition_groups = [[f"role-{role_id}"] for role_id in role_ids]
    chatbot_overlap = calculate_multi_set_jaccard(
        [included_sets_by_group[group[0]] for group in chatbot_condition_groups]
    )
    role_overlap = calculate_multi_set_jaccard(
        [included_sets_by_group[group[0]] for group in role_condition_groups]
    )
    chatbot_permutation = calculate_balanced_label_permutation_baseline(
        chatbot_study_set_blocks,
        group_count=len(model_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
        observed_jaccard=chatbot_overlap["jaccard"],
    )
    role_permutation = calculate_balanced_label_permutation_baseline(
        role_study_set_blocks,
        group_count=len(role_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
        observed_jaccard=role_overlap["jaccard"],
    )

    # Excluded-only and all-candidates main effects: same statistics as the
    # included-only main effects above, over a different universe. All-candidates
    # has no fixed external population to recall against (see build_venn_panel's
    # docstring), so it gets a Jaccard-overlap test only, not a recall-difference
    # test.
    chatbot_excluded_recall_test = calculate_blocked_mean_range_permutation_test(
        chatbot_excluded_recall_blocks,
        group_count=len(model_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
    )
    role_excluded_recall_test = calculate_blocked_mean_range_permutation_test(
        role_excluded_recall_blocks,
        group_count=len(role_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
    )
    chatbot_excluded_overlap = calculate_multi_set_jaccard(
        [excluded_sets_by_group[group[0]] for group in chatbot_condition_groups]
    )
    role_excluded_overlap = calculate_multi_set_jaccard(
        [excluded_sets_by_group[group[0]] for group in role_condition_groups]
    )
    chatbot_excluded_permutation = calculate_balanced_label_permutation_baseline(
        chatbot_excluded_study_set_blocks,
        group_count=len(model_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
        observed_jaccard=chatbot_excluded_overlap["jaccard"],
    )
    role_excluded_permutation = calculate_balanced_label_permutation_baseline(
        role_excluded_study_set_blocks,
        group_count=len(role_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
        observed_jaccard=role_excluded_overlap["jaccard"],
    )
    chatbot_candidate_overlap = calculate_multi_set_jaccard(
        [candidate_sets_by_group[group[0]] for group in chatbot_condition_groups]
    )
    role_candidate_overlap = calculate_multi_set_jaccard(
        [candidate_sets_by_group[group[0]] for group in role_condition_groups]
    )
    chatbot_candidate_permutation = calculate_balanced_label_permutation_baseline(
        chatbot_candidate_study_set_blocks,
        group_count=len(model_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
        observed_jaccard=chatbot_candidate_overlap["jaccard"],
    )
    role_candidate_permutation = calculate_balanced_label_permutation_baseline(
        role_candidate_study_set_blocks,
        group_count=len(role_ids),
        permutation_count=PERMUTATION_COUNT,
        rng=Random(PERMUTATION_SEED),
        observed_jaccard=role_candidate_overlap["jaccard"],
    )

    review_count = len(prepared_reviews)
    answer_counts = {
        *(len(citation_values_by_model[model]) for model in model_ids),
        *(len(citation_values_by_role[role_id]) for role_id in role_ids),
    }
    if len(answer_counts) != 1:
        raise ValueError(
            "Cross-review summary requires a common answer count across chatbot "
            "and role groups"
        )
    answers_per_group = answer_counts.pop()
    main_effect_panels = [
        build_venn_panel(
            panel_id="across-reviews-chatbot-main",
            color_scheme="role-chatbot",
            title="Chatbot",
            subtitle=(
                f"Aggregated across {review_count} reviews · "
                f"{answers_per_group} answers per set"
            ),
            condition_groups=chatbot_condition_groups,
            set_labels=[model_labels[model] for model in model_ids],
            permutation_rule=(
                "Chatbot labels shuffled within every review × role block, "
                "preserving four responses per chatbot"
            ),
            permutation_baseline=chatbot_permutation,
            included_sets_by_condition=included_sets_by_group,
            recall_permutation_test=chatbot_recall_test,
            universe_label="Cochrane included studies",
            benchmark_study_count=included_study_count,
        ),
        build_venn_panel(
            panel_id="across-reviews-role-main",
            color_scheme="role",
            title="User role",
            subtitle=(
                f"Aggregated across {review_count} reviews · "
                f"{answers_per_group} answers per set"
            ),
            condition_groups=role_condition_groups,
            set_labels=[role_labels[role_id]["shortLabel"] for role_id in role_ids],
            permutation_rule=(
                "Role labels shuffled within every review × chatbot block, "
                "preserving four responses per role"
            ),
            permutation_baseline=role_permutation,
            included_sets_by_condition=included_sets_by_group,
            recall_permutation_test=role_recall_test,
            universe_label="Cochrane included studies",
            benchmark_study_count=included_study_count,
        ),
    ]

    excluded_main_effect_panels = [
        build_venn_panel(
            panel_id="across-reviews-chatbot-excluded",
            color_scheme="role-chatbot",
            title="Chatbot",
            subtitle=(
                f"Aggregated across {review_count} reviews · "
                f"{answers_per_group} answers per set"
            ),
            condition_groups=chatbot_condition_groups,
            set_labels=[model_labels[model] for model in model_ids],
            permutation_rule=(
                "Chatbot labels shuffled within every review × role block, "
                "preserving four responses per chatbot"
            ),
            permutation_baseline=chatbot_excluded_permutation,
            included_sets_by_condition=excluded_sets_by_group,
            recall_permutation_test=chatbot_excluded_recall_test,
            universe_label="Cochrane excluded studies",
            benchmark_study_count=excluded_study_count,
        ),
        build_venn_panel(
            panel_id="across-reviews-role-excluded",
            color_scheme="role",
            title="User role",
            subtitle=(
                f"Aggregated across {review_count} reviews · "
                f"{answers_per_group} answers per set"
            ),
            condition_groups=role_condition_groups,
            set_labels=[role_labels[role_id]["shortLabel"] for role_id in role_ids],
            permutation_rule=(
                "Role labels shuffled within every review × chatbot block, "
                "preserving four responses per role"
            ),
            permutation_baseline=role_excluded_permutation,
            included_sets_by_condition=excluded_sets_by_group,
            recall_permutation_test=role_excluded_recall_test,
            universe_label="Cochrane excluded studies",
            benchmark_study_count=excluded_study_count,
        ),
    ]

    candidate_main_effect_panels = [
        build_venn_panel(
            panel_id="across-reviews-chatbot-candidates",
            color_scheme="role-chatbot",
            title="Chatbot",
            subtitle=(
                f"Aggregated across {review_count} reviews · "
                f"{answers_per_group} answers per set"
            ),
            condition_groups=chatbot_condition_groups,
            set_labels=[model_labels[model] for model in model_ids],
            permutation_rule=(
                "Chatbot labels shuffled within every review × role block, "
                "preserving four responses per chatbot"
            ),
            permutation_baseline=chatbot_candidate_permutation,
            included_sets_by_condition=candidate_sets_by_group,
            universe_label="All named candidates",
            benchmark_study_count=None,
        ),
        build_venn_panel(
            panel_id="across-reviews-role-candidates",
            color_scheme="role",
            title="User role",
            subtitle=(
                f"Aggregated across {review_count} reviews · "
                f"{answers_per_group} answers per set"
            ),
            condition_groups=role_condition_groups,
            set_labels=[role_labels[role_id]["shortLabel"] for role_id in role_ids],
            permutation_rule=(
                "Role labels shuffled within every review × chatbot block, "
                "preserving four responses per role"
            ),
            permutation_baseline=role_candidate_permutation,
            included_sets_by_condition=candidate_sets_by_group,
            universe_label="All named candidates",
            benchmark_study_count=None,
        ),
    ]

    post_hoc_answers_per_set = review_count * 4
    model_stratified_rng = Random(PERMUTATION_SEED)
    role_post_hoc_panels = []
    for model in model_ids:
        cell_condition_groups = [[f"cell-{model}-{role_id}"] for role_id in role_ids]
        cell_overlap = calculate_multi_set_jaccard(
            [included_sets_by_group[group[0]] for group in cell_condition_groups]
        )
        role_post_hoc_panels.append(
            build_venn_panel(
                panel_id=f"across-reviews-{model}-role",
                color_scheme="role",
                title=model_labels[model],
                subtitle=(
                    f"Patient, clinician, and researcher · aggregated across "
                    f"{review_count} reviews · {post_hoc_answers_per_set} answers per set"
                ),
                condition_groups=cell_condition_groups,
                set_labels=[role_labels[role_id]["shortLabel"] for role_id in role_ids],
                permutation_rule=(
                    f"Role labels shuffled within each review's {model_labels[model]} "
                    "block, preserving four responses per role"
                ),
                permutation_baseline=calculate_balanced_label_permutation_baseline(
                    role_study_set_blocks_by_model[model],
                    group_count=len(role_ids),
                    permutation_count=PERMUTATION_COUNT,
                    rng=model_stratified_rng,
                    observed_jaccard=cell_overlap["jaccard"],
                ),
                included_sets_by_condition=included_sets_by_group,
                recall_permutation_test=role_recall_test_by_model[model],
                universe_label="Cochrane included studies",
                benchmark_study_count=included_study_count,
            )
        )

    role_stratified_rng = Random(PERMUTATION_SEED)
    chatbot_post_hoc_panels = []
    for role_id in role_ids:
        cell_condition_groups = [[f"cell-{model}-{role_id}"] for model in model_ids]
        cell_overlap = calculate_multi_set_jaccard(
            [included_sets_by_group[group[0]] for group in cell_condition_groups]
        )
        chatbot_post_hoc_panels.append(
            build_venn_panel(
                panel_id=f"across-reviews-{role_id}-chatbot",
                color_scheme="role-chatbot",
                title=role_labels[role_id]["shortLabel"],
                subtitle=(
                    f"Claude, Gemini, and ChatGPT · aggregated across {review_count} "
                    f"reviews · {post_hoc_answers_per_set} answers per set"
                ),
                condition_groups=cell_condition_groups,
                set_labels=[model_labels[model] for model in model_ids],
                permutation_rule=(
                    "Chatbot labels shuffled within each review's "
                    f"{role_labels[role_id]['shortLabel']} block, preserving four "
                    "responses per chatbot"
                ),
                permutation_baseline=calculate_balanced_label_permutation_baseline(
                    chatbot_study_set_blocks_by_role[role_id],
                    group_count=len(model_ids),
                    permutation_count=PERMUTATION_COUNT,
                    rng=role_stratified_rng,
                    observed_jaccard=cell_overlap["jaccard"],
                ),
                included_sets_by_condition=included_sets_by_group,
                recall_permutation_test=chatbot_recall_test_by_role[role_id],
                universe_label="Cochrane included studies",
                benchmark_study_count=included_study_count,
            )
        )

    return {
        "viewId": "across-reviews",
        "viewType": "cross-review",
        "navigationLabel": "Across reviews",
        "review": {
            "reviewId": "Across reviews",
            "reviewTitle": f"Main effects across {review_count} balanced role experiments",
        },
        "overview": {
            "reviewCount": review_count,
            "responseCount": response_count,
            "answersPerGroup": answers_per_group,
            "includedStudyCount": included_study_count,
            "excludedStudyCount": excluded_study_count,
        },
        "metricDefinitions": {
            "citations": (
                "Mean ± sample SD of unique response-study rows per answer, including "
                "included, excluded, and out-of-set studies"
            ),
            "recall": (
                "Mean ± sample SD of response-level recall, normalized by each review's "
                "included-study denominator"
            ),
            "jaccardAllCandidates": (
                "Mean ± sample SD of within-cell replicate consistency: for every review "
                "× chatbot × role cell, the pairwise Jaccard similarity of retrieved-study "
                "sets is averaged across the cell's six replicate pairs, over every named "
                "candidate citation regardless of Cochrane status"
            ),
            "jaccardIncludedOnly": (
                "The same within-cell replicate-pair Jaccard average, restricted to "
                "candidates matched to a Cochrane-included study label"
            ),
        },
        "overallRecall": {
            "responseCount": response_count,
            "includedStudies": {
                "meanRecall": fmean(overall_included_recall_values),
                "recallSd": stdev(overall_included_recall_values),
            },
            "excludedStudies": {
                "meanRecall": fmean(overall_excluded_recall_values),
                "recallSd": stdev(overall_excluded_recall_values),
            },
        },
        "dimensions": [
            {
                "dimensionId": "chatbot",
                "title": "Chatbot",
                "items": [
                    {
                        "groupId": model,
                        "label": model_labels[model],
                        "meanCitationCount": fmean(citation_values_by_model[model]),
                        "citationCountSd": stdev(citation_values_by_model[model]),
                        "meanRecall": fmean(recall_values_by_model[model]),
                        "recallSd": stdev(recall_values_by_model[model]),
                        "meanJaccardAllCandidates": fmean(jaccard_all_by_model[model]),
                        "jaccardAllCandidatesSd": stdev(jaccard_all_by_model[model]),
                        "meanJaccardIncludedOnly": fmean(jaccard_included_by_model[model]),
                        "jaccardIncludedOnlySd": stdev(jaccard_included_by_model[model]),
                    }
                    for model in model_ids
                ],
                "recallPermutationTest": chatbot_recall_test,
            },
            {
                "dimensionId": "role",
                "title": "User role",
                "items": [
                    {
                        "groupId": role_id,
                        "label": role_labels[role_id]["shortLabel"],
                        "meanCitationCount": fmean(citation_values_by_role[role_id]),
                        "citationCountSd": stdev(citation_values_by_role[role_id]),
                        "meanRecall": fmean(recall_values_by_role[role_id]),
                        "recallSd": stdev(recall_values_by_role[role_id]),
                        "meanJaccardAllCandidates": fmean(jaccard_all_by_role[role_id]),
                        "jaccardAllCandidatesSd": stdev(jaccard_all_by_role[role_id]),
                        "meanJaccardIncludedOnly": fmean(jaccard_included_by_role[role_id]),
                        "jaccardIncludedOnlySd": stdev(jaccard_included_by_role[role_id]),
                    }
                    for role_id in role_ids
                ],
                "recallPermutationTest": role_recall_test,
            },
        ],
        "venn": {
            "studySet": "included",
            "membershipRule": (
                "Each set is the union of review-namespaced study labels retrieved "
                "across all contributing answers; see each panel group's own "
                "description for which studies are pooled (Cochrane included, "
                "Cochrane excluded, or all named candidates)"
            ),
            "permutationAnalysis": {
                "method": "Balanced response-level label permutation",
                "permutationCount": PERMUTATION_COUNT,
                "seed": PERMUTATION_SEED,
                "intervalLevel": 0.95,
            },
            "panelGroups": [
                {
                    "groupId": "main-effects",
                    "title": "Aggregated main effects",
                    "description": (
                        "Studies are namespaced by review before pooling; each "
                        "comparison aggregates responses across the other "
                        "experimental dimension."
                    ),
                    "panels": main_effect_panels,
                },
                {
                    "groupId": "main-effects-excluded",
                    "title": "Aggregated main effects — Cochrane excluded studies",
                    "description": (
                        "The same two main-effect comparisons, over Cochrane-excluded "
                        "studies instead of included ones - which chatbot(s) or role(s) "
                        "cite a study Cochrane considered and rejected."
                    ),
                    "panels": excluded_main_effect_panels,
                },
                {
                    "groupId": "main-effects-candidates",
                    "title": "Aggregated main effects — all named candidates",
                    "description": (
                        "The same two main-effect comparisons, over every study any "
                        "response named regardless of Cochrane status (included, "
                        "excluded, or out-of-set). Each set's rate is its share of this "
                        "panel's own pooled union, not a fixed external benchmark, so "
                        "there is no 'not recalled' region and no recall-difference test."
                    ),
                    "panels": candidate_main_effect_panels,
                },
                {
                    "groupId": "post-hoc-role-by-chatbot",
                    "title": "Role overlap by chatbot",
                    "description": (
                        "Each chatbot's three roles are compared using only that "
                        "chatbot's responses, aggregated across reviews. Blocked "
                        "permutations shuffle role labels within each review's block "
                        "for that chatbot."
                    ),
                    "panels": role_post_hoc_panels,
                },
                {
                    "groupId": "post-hoc-chatbot-by-role",
                    "title": "Chatbot overlap by role",
                    "description": (
                        "Each role's three chatbots are compared using only that "
                        "role's responses, aggregated across reviews. Blocked "
                        "permutations shuffle chatbot labels within each review's "
                        "block for that role."
                    ),
                    "panels": chatbot_post_hoc_panels,
                },
            ],
        },
    }


def build_all_reviews_payload(
    characteristic_rows_path: Path,
    logistic_regression_results_path: Path,
    role_dependence_logistic_regression_results_path: Path,
) -> dict[str, Any]:
    """Build the demo payload from every review in the shared registry."""

    sources = review_sources()
    prepared_reviews = [prepare_review(source) for source in sources]
    cross_review_summary = build_cross_review_summary(
        prepared_reviews,
        model_labels=CROSS_REVIEW_MODEL_LABELS,
        model_order=MODEL_ORDER,
        role_labels=CROSS_REVIEW_ROLE_LABELS,
    )
    characteristic_rows = load_characteristic_rows(characteristic_rows_path)
    characteristic_reviews = {row["review"] for row in characteristic_rows}
    expected_reviews = {source.review_id for source in sources}
    if characteristic_reviews != expected_reviews:
        raise ValueError(
            "Characteristic rows do not match the review registry; "
            f"missing={sorted(expected_reviews - characteristic_reviews)}, "
            f"extra={sorted(characteristic_reviews - expected_reviews)}"
        )

    cross_review_summary["characteristicDistributions"] = (
        build_characteristic_distributions(characteristic_rows)
    )
    cross_review_summary["openAccessDistribution"] = (
        build_open_access_distribution(characteristic_rows)
    )
    cross_review_summary["predictorCorrelations"] = (
        build_predictor_correlations(characteristic_rows)
    )
    cross_review_summary["logisticRegression"] = (
        build_logistic_regression_summary(
            load_logistic_regression_results(
                logistic_regression_results_path
            )
        )
    )
    cross_review_summary["citationIssueSummary"] = (
        build_citation_issue_summary(prepared_reviews)
    )
    cross_review_summary["roleCharacteristicDistributions"] = (
        build_role_characteristic_distributions(characteristic_rows)
    )
    cross_review_summary["roleOpenAccessDistribution"] = (
        build_role_open_access_distribution(characteristic_rows)
    )
    cross_review_summary["roleUniversalityDistributions"] = (
        build_role_universality_distributions(characteristic_rows)
    )
    cross_review_summary["roleUniversalityOpenAccess"] = (
        build_role_universality_open_access(characteristic_rows)
    )
    cross_review_summary["roleUniversalityLogisticRegression"] = (
        build_logistic_regression_summary(
            load_logistic_regression_results(
                role_dependence_logistic_regression_results_path
            )
        )
    )
    return {
        "artifactVersion": "2026-07-26-retrieval-bias-demo-v41",
        "crossReviewSummary": cross_review_summary,
        "experiments": [
            experiment for experiment, _ in prepared_reviews
        ],
    }


def run_registry_build() -> None:
    """Write the 20-review browser-ready JavaScript data artifact."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--characteristic-rows",
        type=Path,
        default=DEFAULT_CHARACTERISTIC_ROWS,
    )
    parser.add_argument(
        "--logistic-regression-results",
        type=Path,
        default=DEFAULT_LOGISTIC_REGRESSION_RESULTS,
    )
    parser.add_argument(
        "--role-dependence-logistic-regression-results",
        type=Path,
        default=DEFAULT_ROLE_DEPENDENCE_LOGISTIC_REGRESSION_RESULTS,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = build_all_reviews_payload(
        args.characteristic_rows,
        args.logistic_regression_results,
        args.role_dependence_logistic_regression_results,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=True, indent=2)
    args.output.write_text(
        f"window.RETRIEVAL_BIAS_DEMO_DATA = {serialized};\n",
        encoding="utf-8",
    )
    summary_overview = payload["crossReviewSummary"]["overview"]
    print(
        "Built Across reviews: "
        f"{summary_overview['reviewCount']} reviews, "
        f"{summary_overview['responseCount']} responses, "
        f"{summary_overview['includedStudyCount']} included labels"
    )
    for experiment in payload["experiments"]:
        overview = experiment["overview"]
        print(
            f"Built {experiment['navigationLabel']}: "
            f"{overview['includedStudyCount']} included, "
            f"{overview['excludedStudyCount']} excluded, "
            f"{overview['conditionCount']} conditions, "
            f"{overview['repetitionCount']} repetitions"
        )
    print(f"Wrote: {display_path(args.output)}")


if __name__ == "__main__":
    run_registry_build()
