#!/usr/bin/env python3
"""Create publication figures for the retrieval-bias experiments.

Figure 1 aligns a grayscale chatbot-by-role recall heatmap with marginal
chatbot and user-role bar charts. The marginal means come from the committed
demo artifact, while heatmap cells and review-clustered bootstrap confidence
intervals reconstruct response-level recall from the committed match tables.
Pairwise tests use blocked, balanced label permutations and Holm-adjusted
significance brackets. A top-right panel shows marginal replicate consistency
for included-study retrieval using mean within-cell Jaccard similarity.

Figure 2 shows cross-review included- and excluded-study overlap as four
UpSet plots stratified by chatbot and user role.
Figure 3 ranks the high-level Cochrane exclusion reasons assigned to
chatbot-cited excluded studies and aligns each category with up to three
deterministically selected, manually shortened examples.
Figure 4 shows the mean within-response composition of retrieved candidates by
Cochrane status, overall and stratified by chatbot and user role.
Figure 5 shows the same four overlap comparisons as Figure 2 using
proportional-circle Venn panels.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from statistics import fmean, stdev
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.patches import Circle, Patch, Rectangle
from matplotlib.ticker import PercentFormatter

FIGURES_DIR = Path(__file__).resolve().parent
RETRIEVAL_BIAS_DIR = FIGURES_DIR.parent
REPO_ROOT = RETRIEVAL_BIAS_DIR
DEMO_DATA_PATH = REPO_ROOT / "retrieval_bias_demo" / "data.js"
FIGURE_1_OUTPUT_STEM = (
    FIGURES_DIR / "figure_1_retrieval_recall_by_chatbot_and_role"
)
FIGURE_2_OUTPUT_STEM = FIGURES_DIR / "figure_2_study_overlap"
FIGURE_3_OUTPUT_STEM = FIGURES_DIR / "figure_3_cited_excluded_reasons"
FIGURE_4_OUTPUT_STEM = FIGURES_DIR / "figure_4_candidate_status_composition"
FIGURE_5_OUTPUT_STEM = FIGURES_DIR / "figure_5_proportional_venn_overlap"
CITED_EXCLUDED_STUDY_AUDIT_PATH = (
    RETRIEVAL_BIAS_DIR / "data" / "analysis" / "cited_excluded_study_reason_audit.csv"
)
CITED_EXCLUDED_REASON_COUNTS_PATH = (
    RETRIEVAL_BIAS_DIR / "data" / "analysis" / "cited_excluded_reason_counts.csv"
)
FIGURE_3_ANNOTATIONS_PATH = (
    RETRIEVAL_BIAS_DIR / "data" / "curation" / "figure_3_example_annotations.csv"
)
ROLE_CONSISTENCY_PATH = (
    RETRIEVAL_BIAS_DIR / "data" / "analysis" / "role_consistency_jaccard.csv"
)

sys.path.insert(0, str(RETRIEVAL_BIAS_DIR))
from llm_evidence_retrieval_bias.review_registry import review_sources

MODELS = ("claude", "gemini", "gpt")
ROLES = ("patient", "clinician", "researcher")
DIMENSION_GROUPS = {"chatbot": MODELS, "role": ROLES}
PAIRWISE_PERMUTATION_COUNT = 50_000
PAIRWISE_PERMUTATION_SEED = 20_260_715
PAIRWISE_CHUNK_SIZE = 2_000
REVIEW_BOOTSTRAP_COUNT = 50_000
REVIEW_BOOTSTRAP_SEED = 20_260_727

PANEL_STYLES = {
    "chatbot": {
        "panel_label": "A",
        "title": "Chatbot",
        "labels": {
            "claude": "Claude",
            "gemini": "Gemini",
            "gpt": "ChatGPT",
        },
        "colors": {
            "claude": "#54A600",
            "gemini": "#168FCA",
            "gpt": "#C4145A",
        },
    },
    "role": {
        "panel_label": "B",
        "title": "User role",
        "labels": {
            "patient": "Patient",
            "clinician": "Clinician",
            "researcher": "Researcher",
        },
        "colors": {
            "patient": "#2468E8",
            "clinician": "#7C3AED",
            "researcher": "#D88B00",
        },
    },
}

CHATBOT_FULL_LABELS = {
    "claude": "Claude Sonnet 5",
    "gemini": "Gemini 3.1 Pro",
    "gpt": "ChatGPT 5.5",
}
CHATBOT_FULL_LABELS_WRAPPED = {
    "claude": "Claude\nSonnet 5",
    "gemini": "Gemini\n3.1 Pro",
    "gpt": "ChatGPT\n5.5",
}

TEXT_COLOR = "#20252B"
MUTED_TEXT_COLOR = "#5D6871"
GRID_COLOR = "#E5E7E9"
UPSET_COLOR = "#303942"
INACTIVE_DOT_COLOR = "#D8DDE1"
NOT_RECALLED_COLOR = "#AEB6BC"

CANDIDATE_STATUS_ORDER = ("included", "excluded", "other")
CANDIDATE_STATUS_LABELS = {
    "included": "Cochrane included",
    "excluded": "Cochrane excluded",
    "other": "Other",
}
CANDIDATE_STATUS_COLORS = {
    "included": "#009E73",
    "excluded": "#D55E00",
    "other": "#A7ADB2",
}

REASON_CATEGORY_LABELS = {
    "population": "Population",
    "intervention": "Intervention",
    "comparator": "Comparator",
    "outcome": "Outcome",
    "study_design": "Study design",
    "setting": "Setting",
    "timing_or_follow_up": "Timing or follow-up",
    "unit_of_analysis": "Unit of analysis",
    "publication_or_trial_status": "Publication or\ntrial status",
    "insufficient_or_unavailable_data": "Insufficient or\nunavailable data",
    "unspecified_eligibility": "Unspecified\neligibility",
}


def load_demo_data() -> dict[str, Any]:
    """Load the generated retrieval-bias demo artifact."""

    source = DEMO_DATA_PATH.read_text(encoding="utf-8")
    prefix = "window.RETRIEVAL_BIAS_DEMO_DATA = "
    if not source.startswith(prefix):
        raise ValueError(f"Unexpected data wrapper in {DEMO_DATA_PATH}")
    return json.loads(source.removeprefix(prefix).rstrip().removesuffix(";"))


def load_response_recall(
    demo_data: dict[str, Any],
) -> list[dict[str, str | int | float]]:
    """Reconstruct included-study recall for every response from match tables."""

    denominators = {
        experiment["review"]["reviewId"]: int(
            experiment["overview"]["includedStudyCount"]
        )
        for experiment in demo_data["experiments"]
    }
    response_rows: list[dict[str, str | int | float]] = []

    for source in review_sources():
        with source.matches_path.open(newline="", encoding="utf-8") as handle:
            match_rows = list(csv.DictReader(handle))

        included_by_run: dict[str, set[str]] = defaultdict(set)
        metadata_by_run: dict[str, tuple[str, str, int]] = {}
        for row in match_rows:
            run_id = row["run_id"]
            metadata = (row["model"], row["role_id"], int(row["replicate"]))
            previous = metadata_by_run.setdefault(run_id, metadata)
            if previous != metadata:
                raise ValueError(
                    f"{source.review_id}: conflicting metadata for {run_id}"
                )
            if row["ground_truth_status"] != "included":
                continue
            included_by_run[run_id].update(
                label.strip()
                for label in row["cochrane_study_label"].split("||")
                if label.strip()
            )

        if len(metadata_by_run) != 36:
            raise ValueError(
                f"{source.review_id}: expected 36 responses, "
                f"found {len(metadata_by_run)}"
            )
        denominator = denominators[source.review_id]
        for run_id, (model, role, replicate) in metadata_by_run.items():
            response_rows.append(
                {
                    "review": source.review_id,
                    "run_id": run_id,
                    "model": model,
                    "role": role,
                    "replicate": replicate,
                    "recall": len(included_by_run[run_id]) / denominator,
                }
            )

    if len(response_rows) != 720:
        raise ValueError(f"Expected 720 responses, found {len(response_rows)}")
    return response_rows


def dimension_summaries(
    demo_data: dict[str, Any],
) -> dict[str, dict[str, dict[str, float]]]:
    """Read the displayed mean and sample SD for each chatbot and role."""

    summaries: dict[str, dict[str, dict[str, float]]] = {}
    for dimension in demo_data["crossReviewSummary"]["dimensions"]:
        dimension_id = dimension["dimensionId"]
        summaries[dimension_id] = {
            item["groupId"]: {
                "mean": float(item["meanRecall"]),
                "sd": float(item["recallSd"]),
            }
            for item in dimension["items"]
        }
    return summaries


def validate_summaries(
    response_rows: list[dict[str, str | int | float]],
    summaries: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Confirm reconstructed response recall matches the committed demo values."""

    record_fields = {"chatbot": "model", "role": "role"}
    for dimension, groups in DIMENSION_GROUPS.items():
        record_field = record_fields[dimension]
        for group in groups:
            values = [
                float(row["recall"])
                for row in response_rows
                if row[record_field] == group
            ]
            expected = summaries[dimension][group]
            if not (
                np.isclose(fmean(values), expected["mean"])
                and np.isclose(stdev(values), expected["sd"])
            ):
                raise ValueError(
                    f"{dimension}/{group}: reconstructed response statistics "
                    "do not match the committed demo artifact"
                )


def load_included_jaccard_summaries() -> dict[str, dict[str, dict[str, float]]]:
    """Read included-study replicate consistency marginals and CIs."""

    with ROLE_CONSISTENCY_PATH.open(newline="", encoding="utf-8") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["scope"] == "included_only"
        ]
    if not rows:
        raise ValueError(f"No included_only rows in {ROLE_CONSISTENCY_PATH}")

    review_ids = sorted({row["review"] for row in rows})
    sample_indexes = np.random.default_rng(REVIEW_BOOTSTRAP_SEED).integers(
        0,
        len(review_ids),
        size=(REVIEW_BOOTSTRAP_COUNT, len(review_ids)),
    )
    record_fields = {"chatbot": "model", "role": "role"}
    expected_within_review = {"chatbot": len(ROLES), "role": len(MODELS)}
    summaries: dict[str, dict[str, dict[str, float]]] = {}

    for dimension, groups in DIMENSION_GROUPS.items():
        record_field = record_fields[dimension]
        review_means = np.empty((len(review_ids), len(groups)), dtype=float)
        for review_index, review_id in enumerate(review_ids):
            for group_index, group in enumerate(groups):
                values = [
                    float(row["mean_jaccard"])
                    for row in rows
                    if row["review"] == review_id and row[record_field] == group
                ]
                if len(values) != expected_within_review[dimension]:
                    raise ValueError(
                        f"{review_id}/{dimension}/{group}: expected "
                        f"{expected_within_review[dimension]} included-only "
                        f"Jaccard rows, found {len(values)}"
                    )
                review_means[review_index, group_index] = fmean(values)

        bootstrap_means = review_means[sample_indexes].mean(axis=1)
        lower, upper = np.quantile(
            bootstrap_means,
            (0.025, 0.975),
            axis=0,
        )
        summaries[dimension] = {
            group: {
                "mean": float(review_means[:, group_index].mean()),
                "low": float(lower[group_index]),
                "high": float(upper[group_index]),
            }
            for group_index, group in enumerate(groups)
        }
    return summaries


def review_clustered_bootstrap_intervals(
    response_rows: list[dict[str, str | int | float]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Estimate percentile CIs by resampling reviews with all responses intact."""

    review_ids = sorted({str(row["review"]) for row in response_rows})
    if len(review_ids) != 20:
        raise ValueError(f"Expected 20 review clusters, found {len(review_ids)}")

    rng = np.random.default_rng(REVIEW_BOOTSTRAP_SEED)
    sample_indexes = rng.integers(
        0,
        len(review_ids),
        size=(REVIEW_BOOTSTRAP_COUNT, len(review_ids)),
    )
    record_fields = {"chatbot": "model", "role": "role"}
    intervals: dict[str, dict[str, dict[str, float]]] = {}

    for dimension, groups in DIMENSION_GROUPS.items():
        record_field = record_fields[dimension]
        review_means = np.empty((len(review_ids), len(groups)), dtype=float)
        for review_index, review_id in enumerate(review_ids):
            for group_index, group in enumerate(groups):
                values = [
                    float(row["recall"])
                    for row in response_rows
                    if (
                        row["review"] == review_id
                        and row[record_field] == group
                    )
                ]
                if len(values) != 12:
                    raise ValueError(
                        f"{review_id}/{dimension}/{group}: expected 12 "
                        f"response recalls, found {len(values)}"
                    )
                review_means[review_index, group_index] = fmean(values)

        bootstrap_means = review_means[sample_indexes].mean(axis=1)
        lower, upper = np.quantile(
            bootstrap_means,
            (0.025, 0.975),
            axis=0,
        )
        intervals[dimension] = {
            group: {
                "low": float(lower[group_index]),
                "high": float(upper[group_index]),
            }
            for group_index, group in enumerate(groups)
        }

    return intervals


def blocked_pairwise_permutation_test(
    response_rows: list[dict[str, str | int | float]],
    *,
    dimension: str,
    first_group: str,
    second_group: str,
    seed: int,
) -> dict[str, float | int | str]:
    """Compare two groups while permuting labels within balanced blocks."""

    record_field = "model" if dimension == "chatbot" else "role"
    blocking_field = "role" if dimension == "chatbot" else "model"
    blocks: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: {first_group: [], second_group: []}
    )
    for row in response_rows:
        group = str(row[record_field])
        if group not in (first_group, second_group):
            continue
        block = (str(row["review"]), str(row[blocking_field]))
        blocks[block][group].append(float(row["recall"]))

    block_values: list[list[float]] = []
    for block, values in sorted(blocks.items()):
        if not (
            len(values[first_group]) == 4 and len(values[second_group]) == 4
        ):
            raise ValueError(
                f"{dimension} pair {first_group}/{second_group}: "
                f"unbalanced block {block}"
            )
        block_values.append(values[first_group] + values[second_group])

    values = np.asarray(block_values, dtype=float)
    group_size = values.shape[0] * 4
    observed = abs(values[:, :4].mean() - values[:, 4:].mean())
    total = float(values.sum())
    rng = np.random.default_rng(seed)
    extreme_count = 0
    completed = 0

    while completed < PAIRWISE_PERMUTATION_COUNT:
        chunk_size = min(
            PAIRWISE_CHUNK_SIZE, PAIRWISE_PERMUTATION_COUNT - completed
        )
        random_keys = rng.random((chunk_size, values.shape[0], 8))
        first_indexes = np.argpartition(
            random_keys, kth=4, axis=2
        )[:, :, :4]
        expanded_values = np.broadcast_to(
            values, (chunk_size,) + values.shape
        )
        first_sums = np.take_along_axis(
            expanded_values, first_indexes, axis=2
        ).sum(axis=(1, 2))
        permuted_differences = np.abs(
            first_sums / group_size - (total - first_sums) / group_size
        )
        extreme_count += int(
            np.count_nonzero(permuted_differences >= observed - 1e-15)
        )
        completed += chunk_size

    return {
        "first_group": first_group,
        "second_group": second_group,
        "mean_difference": float(observed),
        "raw_p_value": (extreme_count + 1)
        / (PAIRWISE_PERMUTATION_COUNT + 1),
        "extreme_count": extreme_count,
    }


def holm_adjust(
    pairwise_results: list[dict[str, float | int | str]],
) -> None:
    """Add Holm-adjusted p-values to pairwise test results in place."""

    ordered_indexes = sorted(
        range(len(pairwise_results)),
        key=lambda index: float(pairwise_results[index]["raw_p_value"]),
    )
    running_adjusted = 0.0
    result_count = len(pairwise_results)
    for rank, index in enumerate(ordered_indexes):
        raw_p_value = float(pairwise_results[index]["raw_p_value"])
        adjusted = min(1.0, (result_count - rank) * raw_p_value)
        running_adjusted = max(running_adjusted, adjusted)
        pairwise_results[index]["holm_p_value"] = running_adjusted


def calculate_pairwise_tests(
    response_rows: list[dict[str, str | int | float]],
) -> dict[str, list[dict[str, float | int | str]]]:
    """Calculate the three Holm-adjusted pairwise tests per panel."""

    results: dict[str, list[dict[str, float | int | str]]] = {}
    for dimension_index, (dimension, groups) in enumerate(
        DIMENSION_GROUPS.items()
    ):
        dimension_results = []
        for pair_index, (first_group, second_group) in enumerate(
            combinations(groups, 2)
        ):
            dimension_results.append(
                blocked_pairwise_permutation_test(
                    response_rows,
                    dimension=dimension,
                    first_group=first_group,
                    second_group=second_group,
                    seed=(
                        PAIRWISE_PERMUTATION_SEED
                        + dimension_index * 100
                        + pair_index
                    ),
                )
            )
        holm_adjust(dimension_results)
        results[dimension] = dimension_results
    return results


def significance_label(p_value: float) -> str:
    """Convert an adjusted p-value to a conventional significance label."""

    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "ns"


def draw_pairwise_bracket(
    axis,
    *,
    first_x: int,
    second_x: int,
    height: float,
    label: str,
) -> None:
    """Draw one conventional significance bracket above two bars."""

    bracket_height = 0.018
    axis.plot(
        [
            first_x,
            first_x,
            second_x,
            second_x,
        ],
        [
            height - bracket_height,
            height,
            height,
            height - bracket_height,
        ],
        color=TEXT_COLOR,
        linewidth=1.0,
        zorder=8,
    )
    axis.text(
        (first_x + second_x) / 2,
        height + 0.012,
        label,
        color=TEXT_COLOR,
        fontsize=9,
        fontweight="bold",
        ha="center",
        va="bottom",
        zorder=9,
    )


def draw_role_pairwise_bracket(
    axis,
    *,
    first_y: int,
    second_y: int,
    position: float,
    label: str,
) -> None:
    """Draw a significance bracket beside two horizontal role bars."""

    bracket_width = 0.018
    axis.plot(
        [
            position - bracket_width,
            position,
            position,
            position - bracket_width,
        ],
        [
            first_y,
            first_y,
            second_y,
            second_y,
        ],
        color=TEXT_COLOR,
        linewidth=1.0,
        zorder=8,
    )
    axis.text(
        position + 0.014,
        (first_y + second_y) / 2,
        label,
        color=TEXT_COLOR,
        fontsize=9,
        fontweight="bold",
        ha="left",
        va="center",
        zorder=9,
    )


def draw_chatbot_margin(
    axis,
    *,
    summaries: dict[str, dict[str, float]],
    confidence_intervals: dict[str, dict[str, float]],
    pairwise_results: list[dict[str, float | int | str]],
) -> None:
    """Draw chatbot marginal means above the aligned heatmap columns."""

    style = PANEL_STYLES["chatbot"]
    groups = MODELS
    x_positions = np.arange(len(groups))
    mean_values = [summaries[group]["mean"] for group in groups]
    lower_bounds = [confidence_intervals[group]["low"] for group in groups]
    upper_bounds = [confidence_intervals[group]["high"] for group in groups]
    confidence_errors = np.asarray(
        [
            [
                mean_value - lower_bound
                for mean_value, lower_bound in zip(
                    mean_values, lower_bounds
                )
            ],
            [
                upper_bound - mean_value
                for mean_value, upper_bound in zip(
                    mean_values, upper_bounds
                )
            ],
        ]
    )
    colors = [style["colors"][group] for group in groups]

    bars = axis.bar(
        x_positions,
        mean_values,
        width=0.62,
        yerr=confidence_errors,
        capsize=4,
        color=colors,
        edgecolor=TEXT_COLOR,
        linewidth=0.7,
        error_kw={
            "ecolor": TEXT_COLOR,
            "elinewidth": 1.15,
            "capthick": 1.15,
        },
        zorder=3,
    )
    for bar, mean_value in zip(bars, mean_values):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            0.025,
            f"{100 * mean_value:.1f}%",
            ha="center",
            va="bottom",
            color="white",
            fontsize=8,
            fontweight="bold",
            zorder=5,
        )

    axis.set_ylabel(
        "Mean response-level\nrecall (%)",
        fontsize=9,
        fontweight="bold",
        color=TEXT_COLOR,
        labelpad=7,
    )
    axis.set_xticks(x_positions)
    axis.set_xlim(-0.62, 2.62)
    axis.set_ylim(0, 1.22)
    axis.set_yticks(np.arange(0, 1.01, 0.2))
    axis.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    axis.grid(axis="y", color=GRID_COLOR, linewidth=0.7, zorder=0)
    axis.tick_params(
        axis="x",
        which="both",
        bottom=False,
        labelbottom=False,
    )
    axis.tick_params(
        axis="y",
        length=3,
        width=0.7,
        color=TEXT_COLOR,
        labelsize=8,
    )
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(TEXT_COLOR)
    axis.spines["bottom"].set_color(TEXT_COLOR)
    axis.spines["left"].set_linewidth(0.8)
    axis.spines["bottom"].set_linewidth(0.8)

    pair_order = ((0, 1), (1, 2), (0, 2))
    pair_lookup = {
        frozenset(
            (str(result["first_group"]), str(result["second_group"]))
        ): result
        for result in pairwise_results
    }
    bracket_heights: list[float] = []
    for pair_index, (first_x, second_x) in enumerate(pair_order):
        first_group = groups[first_x]
        second_group = groups[second_x]
        result = pair_lookup[frozenset((first_group, second_group))]
        if pair_index < 2:
            height = max(upper_bounds[first_x], upper_bounds[second_x]) + 0.06
        else:
            height = max(
                max(upper_bounds[first_x], upper_bounds[second_x]) + 0.06,
                max(bracket_heights) + 0.11,
            )
        bracket_heights.append(height)
        draw_pairwise_bracket(
            axis,
            first_x=first_x,
            second_x=second_x,
            height=height,
            label=significance_label(float(result["holm_p_value"])),
        )


def draw_role_margin(
    axis,
    *,
    summaries: dict[str, dict[str, float]],
    confidence_intervals: dict[str, dict[str, float]],
    pairwise_results: list[dict[str, float | int | str]],
) -> None:
    """Draw user-role marginal means beside the aligned heatmap rows."""

    style = PANEL_STYLES["role"]
    groups = ROLES
    y_positions = np.arange(len(groups))
    mean_values = [summaries[group]["mean"] for group in groups]
    lower_bounds = [confidence_intervals[group]["low"] for group in groups]
    upper_bounds = [confidence_intervals[group]["high"] for group in groups]
    confidence_errors = np.asarray(
        [
            [
                mean_value - lower_bound
                for mean_value, lower_bound in zip(
                    mean_values, lower_bounds
                )
            ],
            [
                upper_bound - mean_value
                for mean_value, upper_bound in zip(
                    mean_values, upper_bounds
                )
            ],
        ]
    )
    colors = [style["colors"][group] for group in groups]

    bars = axis.barh(
        y_positions,
        mean_values,
        height=0.62,
        xerr=confidence_errors,
        capsize=4,
        color=colors,
        edgecolor=TEXT_COLOR,
        linewidth=0.7,
        error_kw={
            "ecolor": TEXT_COLOR,
            "elinewidth": 1.15,
            "capthick": 1.15,
        },
        zorder=3,
    )
    for bar, mean_value in zip(bars, mean_values):
        axis.text(
            0.025,
            bar.get_y() + bar.get_height() / 2,
            f"{100 * mean_value:.1f}%",
            ha="left",
            va="center",
            color="white",
            fontsize=8,
            fontweight="bold",
            zorder=5,
        )

    axis.set_title(
        "User-role mean",
        loc="left",
        pad=10,
        fontsize=10.5,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    axis.set_xlabel(
        "Mean response-level recall (%)",
        fontsize=9,
        fontweight="bold",
        color=TEXT_COLOR,
        labelpad=7,
    )
    axis.set_yticks(y_positions)
    axis.set_ylim(len(groups) - 0.5, -0.5)
    axis.set_xlim(0, 1.22)
    axis.set_xticks(np.arange(0, 1.01, 0.2))
    axis.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    axis.grid(axis="x", color=GRID_COLOR, linewidth=0.7, zorder=0)
    axis.tick_params(
        axis="y",
        which="both",
        left=False,
        labelleft=False,
    )
    axis.tick_params(
        axis="x",
        length=3,
        width=0.7,
        color=TEXT_COLOR,
        labelsize=8,
    )
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(TEXT_COLOR)
    axis.spines["bottom"].set_color(TEXT_COLOR)
    axis.spines["left"].set_linewidth(0.8)
    axis.spines["bottom"].set_linewidth(0.8)

    pair_order = ((0, 1), (1, 2), (0, 2))
    pair_lookup = {
        frozenset(
            (str(result["first_group"]), str(result["second_group"]))
        ): result
        for result in pairwise_results
    }
    bracket_positions: list[float] = []
    for pair_index, (first_y, second_y) in enumerate(pair_order):
        first_group = groups[first_y]
        second_group = groups[second_y]
        result = pair_lookup[frozenset((first_group, second_group))]
        if pair_index < 2:
            position = max(
                upper_bounds[first_y], upper_bounds[second_y]
            ) + 0.06
        else:
            position = max(
                max(upper_bounds[first_y], upper_bounds[second_y]) + 0.06,
                max(bracket_positions) + 0.12,
            )
        bracket_positions.append(position)
        draw_role_pairwise_bracket(
            axis,
            first_y=first_y,
            second_y=second_y,
            position=position,
            label=significance_label(float(result["holm_p_value"])),
        )


def draw_consistency_bar_axis(
    axis,
    *,
    dimension: str,
    summaries_by_group: dict[str, dict[str, float]],
    show_y_label: bool,
) -> None:
    """Draw one compact marginal included-study Jaccard bar chart."""

    groups = MODELS if dimension == "chatbot" else ROLES
    style = PANEL_STYLES[dimension]
    labels = (
        [CHATBOT_FULL_LABELS_WRAPPED[group] for group in groups]
        if dimension == "chatbot"
        else [style["labels"][group] for group in groups]
    )
    values = [summaries_by_group[group]["mean"] for group in groups]
    lower_bounds = [summaries_by_group[group]["low"] for group in groups]
    upper_bounds = [summaries_by_group[group]["high"] for group in groups]
    confidence_errors = np.asarray(
        [
            [
                value - lower_bound
                for value, lower_bound in zip(values, lower_bounds)
            ],
            [
                upper_bound - value
                for value, upper_bound in zip(values, upper_bounds)
            ],
        ]
    )
    colors = [style["colors"][group] for group in groups]
    x_positions = np.arange(len(groups))

    bars = axis.bar(
        x_positions,
        values,
        width=0.64,
        yerr=confidence_errors,
        capsize=3,
        color=colors,
        edgecolor=TEXT_COLOR,
        linewidth=0.65,
        error_kw={
            "ecolor": TEXT_COLOR,
            "elinewidth": 0.9,
            "capthick": 0.9,
        },
        zorder=3,
    )
    for bar, value, upper_bound in zip(bars, values, upper_bounds):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            min(upper_bound + 0.025, 0.92),
            f"{value:.2f}",
            ha="center",
            va="bottom",
            color=TEXT_COLOR,
            fontsize=7.5,
            fontweight="bold",
            zorder=5,
        )

    axis.set_xticks(x_positions, labels)
    axis.set_xlim(-0.55, len(groups) - 0.45)
    axis.set_ylim(0, 1.0)
    axis.set_yticks(
        np.arange(0, 1.01, 0.25),
        ["0", "0.25", "0.50", "0.75", "1.00"],
    )
    axis.grid(axis="y", color=GRID_COLOR, linewidth=0.65, zorder=0)
    axis.tick_params(axis="x", length=0, pad=4, labelsize=7.0)
    if dimension == "role":
        for label in axis.get_xticklabels():
            label.set_rotation(28)
            label.set_ha("right")
    axis.tick_params(
        axis="y",
        length=3,
        width=0.65,
        color=TEXT_COLOR,
        labelsize=7.4,
        labelleft=show_y_label,
    )
    if show_y_label:
        axis.set_ylabel(
            "Pairwise Jaccard",
            fontsize=7.8,
            fontweight="bold",
            color=TEXT_COLOR,
            labelpad=3,
        )
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(TEXT_COLOR)
    axis.spines["bottom"].set_color(TEXT_COLOR)
    axis.spines["left"].set_linewidth(0.75)
    axis.spines["bottom"].set_linewidth(0.75)


def draw_included_jaccard_margins(
    chatbot_axis,
    role_axis,
    *,
    summaries: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Draw included-study replicate consistency marginals in Figure 1."""

    draw_consistency_bar_axis(
        chatbot_axis,
        dimension="chatbot",
        summaries_by_group=summaries["chatbot"],
        show_y_label=True,
    )
    draw_consistency_bar_axis(
        role_axis,
        dimension="role",
        summaries_by_group=summaries["role"],
        show_y_label=False,
    )


def create_figure_1(
    summaries: dict[str, dict[str, dict[str, float]]],
    confidence_intervals: dict[str, dict[str, dict[str, float]]],
    pairwise_results: dict[
        str, list[dict[str, float | int | str]]
    ],
    response_rows: list[dict[str, str | int | float]],
    included_jaccard_summaries: dict[str, dict[str, dict[str, float]]],
):
    """Build Figure 1 as a heatmap with aligned marginal summaries."""

    interaction_means = np.empty((len(ROLES), len(MODELS)), dtype=float)
    for role_index, role in enumerate(ROLES):
        for model_index, model in enumerate(MODELS):
            values = [
                float(row["recall"])
                for row in response_rows
                if row["role"] == role and row["model"] == model
            ]
            if len(values) != 80:
                raise ValueError(
                    f"{model}/{role}: expected 80 response recalls, "
                    f"found {len(values)}"
                )
            interaction_means[role_index, model_index] = fmean(values)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    figure = plt.figure(figsize=(7.4, 6.6), facecolor="white")
    grid = figure.add_gridspec(
        2,
        2,
        width_ratios=(0.43, 0.57),
        height_ratios=(0.475, 0.525),
        hspace=0.28,
        wspace=0.09,
    )
    chatbot_axis = figure.add_subplot(grid[0, 0])
    consistency_tint_axis = figure.add_subplot(grid[0, 1])
    consistency_tint_axis.set_zorder(0)
    consistency_tint_axis.set_facecolor("#F7F8FA")
    consistency_tint_axis.set_xticks([])
    consistency_tint_axis.set_yticks([])
    for spine in consistency_tint_axis.spines.values():
        spine.set_visible(False)
    consistency_grid = grid[0, 1].subgridspec(
        2,
        3,
        width_ratios=(0.16, 1, 1),
        height_ratios=(1, 0.22),
        wspace=0.18,
        hspace=0.0,
    )
    consistency_chatbot_axis = figure.add_subplot(consistency_grid[0, 1])
    consistency_role_axis = figure.add_subplot(
        consistency_grid[0, 2],
        sharey=consistency_chatbot_axis,
    )
    heatmap_axis = figure.add_subplot(grid[1, 0], sharex=chatbot_axis)
    role_axis = figure.add_subplot(grid[1, 1], sharey=heatmap_axis)
    for axis in (
        chatbot_axis,
        consistency_chatbot_axis,
        consistency_role_axis,
        heatmap_axis,
        role_axis,
    ):
        axis.set_facecolor("white")
    for axis in (consistency_chatbot_axis, consistency_role_axis):
        axis.set_facecolor("#F7F8FA")

    draw_chatbot_margin(
        chatbot_axis,
        summaries=summaries["chatbot"],
        confidence_intervals=confidence_intervals["chatbot"],
        pairwise_results=pairwise_results["chatbot"],
    )
    draw_included_jaccard_margins(
        consistency_chatbot_axis,
        consistency_role_axis,
        summaries=included_jaccard_summaries,
    )

    heatmap_axis.imshow(
        interaction_means,
        cmap="Greys",
        vmin=0,
        vmax=1,
        aspect="equal",
        interpolation="nearest",
        extent=(-0.5, 2.5, 2.5, -0.5),
        zorder=1,
    )
    for role_index in range(len(ROLES)):
        for model_index in range(len(MODELS)):
            mean_value = interaction_means[role_index, model_index]
            heatmap_axis.text(
                model_index,
                role_index,
                f"{100 * mean_value:.1f}%",
                ha="center",
                va="center",
                fontsize=8.5,
                fontweight="bold",
                color="white" if mean_value >= 0.5 else TEXT_COLOR,
                zorder=3,
            )
    heatmap_axis.set_xticks(
        np.arange(len(MODELS)),
        [CHATBOT_FULL_LABELS_WRAPPED[model] for model in MODELS],
    )
    heatmap_axis.set_yticks(
        np.arange(len(ROLES)),
        [PANEL_STYLES["role"]["labels"][role] for role in ROLES],
    )
    heatmap_axis.tick_params(
        axis="x",
        top=True,
        labeltop=True,
        bottom=False,
        labelbottom=False,
        length=0,
        pad=5,
        labelsize=8.5,
    )
    heatmap_axis.tick_params(axis="y", length=0, pad=6, labelsize=8.5)
    heatmap_axis.set_xlabel(
        "Chatbot",
        fontsize=9,
        fontweight="bold",
        color=TEXT_COLOR,
        labelpad=7,
    )
    heatmap_axis.set_ylabel(
        "User role",
        fontsize=9,
        fontweight="bold",
        color=TEXT_COLOR,
        labelpad=7,
    )
    heatmap_axis.set_xticks(np.arange(-0.5, len(MODELS), 1), minor=True)
    heatmap_axis.set_yticks(np.arange(-0.5, len(ROLES), 1), minor=True)
    heatmap_axis.grid(
        which="minor",
        color="white",
        linewidth=2.0,
        zorder=2,
    )
    heatmap_axis.tick_params(which="minor", length=0)
    for spine in heatmap_axis.spines.values():
        spine.set_visible(False)

    draw_role_margin(
        role_axis,
        summaries=summaries["role"],
        confidence_intervals=confidence_intervals["role"],
        pairwise_results=pairwise_results["role"],
    )

    figure.subplots_adjust(
        left=0.115,
        right=0.985,
        top=0.93,
        bottom=0.15,
    )
    tint_bbox = consistency_tint_axis.get_position()
    consistency_tint_axis.set_position(
        [
            tint_bbox.x0 - 0.02,
            tint_bbox.y0,
            tint_bbox.width + 0.02,
            tint_bbox.height + 0.02,
        ]
    )
    consistency_left_bbox = consistency_chatbot_axis.get_position()
    consistency_right_bbox = consistency_role_axis.get_position()
    top_title_y = max(
        consistency_left_bbox.y1, consistency_right_bbox.y1
    ) + 0.02
    chatbot_bbox = chatbot_axis.get_position()
    figure.text(
        chatbot_bbox.x0,
        top_title_y,
        "Chatbot mean",
        ha="left",
        va="bottom",
        fontsize=10.5,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    figure.text(
        (consistency_left_bbox.x0 + consistency_right_bbox.x1) / 2,
        top_title_y,
        "Recall consistency",
        ha="center",
        va="bottom",
        fontsize=10.2,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    return figure


def load_main_overlap_panels(
    demo_data: dict[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Load included and excluded overlap panels by chatbot and user role."""

    panel_ids = {
        "included": {
            "chatbot": "across-reviews-chatbot-main",
            "role": "across-reviews-role-main",
        },
        "excluded": {
            "chatbot": "across-reviews-chatbot-excluded",
            "role": "across-reviews-role-excluded",
        },
    }
    panels_by_id = {
        panel["panelId"]: panel
        for panel_group in demo_data["crossReviewSummary"]["venn"][
            "panelGroups"
        ]
        for panel in panel_group["panels"]
    }
    panels = {
        study_status: {
            dimension: panels_by_id[panel_id]
            for dimension, panel_id in dimension_panel_ids.items()
        }
        for study_status, dimension_panel_ids in panel_ids.items()
    }
    for study_status, panels_by_dimension in panels.items():
        for dimension, panel in panels_by_dimension.items():
            if (
                len(panel["setLabels"]) != 3
                or len(panel["setCounts"]) != 3
                or len(panel["regions"]) != 7
                or panel["benchmarkStudyCount"] is None
            ):
                raise ValueError(
                    f"{study_status} {dimension}: expected a complete "
                    "three-set overlap panel"
                )
            partition_total = sum(
                int(region["studyCount"]) for region in panel["regions"]
            )
            if partition_total != int(panel["unionCount"]):
                raise ValueError(
                    f"{study_status} {dimension}: intersection counts do not "
                    "match union count"
                )
    return panels


def draw_upset_panel(
    figure,
    subplot_spec,
    *,
    dimension: str,
    study_status: str,
    panel_label: str,
    panel: dict[str, Any],
) -> None:
    """Draw one three-set UpSet panel plus its known-universe complement."""

    if study_status not in {"included", "excluded"}:
        raise ValueError(f"Unexpected study status: {study_status}")
    paper_font_scale = 1.35
    style = PANEL_STYLES[dimension]
    groups = DIMENSION_GROUPS[dimension]
    benchmark_count = int(panel["benchmarkStudyCount"])
    not_recalled_count = benchmark_count - int(panel["unionCount"])
    set_counts = [int(count) for count in panel["setCounts"]]
    if list(panel["setLabels"]) != [
        style["labels"][group] for group in groups
    ]:
        raise ValueError(f"{dimension}: unexpected set-label order")

    intersections = sorted(
        (
            {
                "members": tuple(int(index) for index in region["memberIndexes"]),
                "count": int(region["studyCount"]),
            }
            for region in panel["regions"]
        ),
        key=lambda intersection: (
            -int(intersection["count"]),
            -len(intersection["members"]),
            intersection["members"],
        ),
    )
    intersection_x = np.arange(len(intersections), dtype=float)
    not_recalled_x = float(len(intersections)) + 0.65

    inner = subplot_spec.subgridspec(
        2,
        2,
        width_ratios=(1.28, 2.72),
        height_ratios=(2.35, 1.0),
        wspace=0.055,
        hspace=0.04,
    )
    context_axis = figure.add_subplot(inner[0, 0])
    intersection_axis = figure.add_subplot(inner[0, 1])
    set_size_axis = figure.add_subplot(inner[1, 0])
    matrix_axis = figure.add_subplot(inner[1, 1])

    context_axis.axis("off")
    context_axis.text(
        0.0,
        1.04,
        f"{panel_label}  {style['title']}",
        transform=context_axis.transAxes,
        fontsize=10.5 * paper_font_scale,
        fontweight="bold",
        color=TEXT_COLOR,
        ha="left",
        va="bottom",
    )
    intersection_counts = [
        int(intersection["count"]) for intersection in intersections
    ]
    all_bar_x = np.append(intersection_x, not_recalled_x)
    intersection_ymax = 260 if study_status == "included" else 110
    not_recalled_bar_height = not_recalled_count
    complement_is_truncated = not_recalled_count >= intersection_ymax
    if complement_is_truncated:
        not_recalled_bar_height = 0.88 * intersection_ymax
    all_bar_heights = intersection_counts + [not_recalled_bar_height]
    all_bar_labels = intersection_counts + [not_recalled_count]
    bar_colors = [UPSET_COLOR] * len(intersections) + [NOT_RECALLED_COLOR]
    intersection_axis.bar(
        all_bar_x,
        all_bar_heights,
        width=0.68,
        color=bar_colors,
        edgecolor=TEXT_COLOR,
        linewidth=0.55,
        zorder=3,
    )
    label_offset = 5 if study_status == "included" else 2
    for x_position, height, count in zip(
        all_bar_x, all_bar_heights, all_bar_labels
    ):
        intersection_axis.text(
            x_position,
            height + label_offset,
            str(count),
            ha="center",
            va="bottom",
            fontsize=7.5 * paper_font_scale,
            fontweight="bold",
            color=TEXT_COLOR,
        )
    if complement_is_truncated:
        break_y = 0.71 * intersection_ymax
        for x_offset in (-0.10, 0.10):
            intersection_axis.plot(
                (
                    not_recalled_x - 0.18 + x_offset,
                    not_recalled_x + 0.18 + x_offset,
                ),
                (break_y - 2.2, break_y + 2.2),
                color="white",
                linewidth=1.4,
                solid_capstyle="round",
                zorder=5,
            )
    intersection_axis.axvline(
        not_recalled_x - 0.65,
        color=GRID_COLOR,
        linewidth=0.9,
        zorder=1,
    )
    intersection_axis.set_title(
        f"Cochrane {study_status} (N = {benchmark_count})",
        loc="left",
        fontsize=8.5 * paper_font_scale,
        fontweight="bold",
        color=TEXT_COLOR,
        pad=6,
    )
    intersection_axis.set_ylabel(
        "Number of studies",
        fontsize=8 * paper_font_scale,
        color=TEXT_COLOR,
    )
    intersection_axis.set_xlim(-0.55, not_recalled_x + 0.55)
    intersection_axis.set_ylim(0, intersection_ymax)
    intersection_axis.set_yticks(
        np.arange(0, 251, 50)
        if study_status == "included"
        else np.arange(0, 101, 25)
    )
    intersection_axis.set_xticks([])
    intersection_axis.grid(
        axis="y", color=GRID_COLOR, linewidth=0.7, zorder=0
    )
    intersection_axis.tick_params(
        axis="y", labelsize=7.5 * paper_font_scale, length=3
    )
    intersection_axis.spines["top"].set_visible(False)
    intersection_axis.spines["right"].set_visible(False)
    intersection_axis.spines["bottom"].set_color(TEXT_COLOR)
    intersection_axis.spines["left"].set_color(TEXT_COLOR)
    intersection_axis.spines["bottom"].set_linewidth(0.75)
    intersection_axis.spines["left"].set_linewidth(0.75)

    row_positions = np.arange(3)
    set_colors = [style["colors"][group] for group in groups]
    set_size_axis.barh(
        row_positions,
        set_counts,
        height=0.64,
        color=set_colors,
        edgecolor=TEXT_COLOR,
        linewidth=0.5,
        zorder=3,
    )
    set_size_axis_max = 340 if study_status == "included" else 125
    for row_position, count in zip(row_positions, set_counts):
        label_is_inside = count >= 0.40 * set_size_axis_max
        set_size_axis.text(
            count - 8 if label_is_inside else count + 4,
            row_position,
            (
                f"{count}/{benchmark_count}\n"
                f"({100 * count / benchmark_count:.1f}%)"
            ),
            ha="left" if label_is_inside else "right",
            va="center",
            fontsize=6.1 * paper_font_scale,
            fontweight="bold",
            color="white" if label_is_inside else TEXT_COLOR,
            linespacing=0.95,
            zorder=4,
        )
    set_size_axis.set_yticks(
        row_positions,
        [style["labels"][group] for group in groups],
    )
    set_size_axis.set_ylim(2.5, -0.5)
    set_size_axis.set_xlim(set_size_axis_max, 0)
    set_size_axis.set_xticks(
        (0, 100, 200, 300)
        if study_status == "included"
        else (0, 25, 50, 75, 100)
    )
    set_size_axis.set_xlabel(
        (
            "Studies cited by each chatbot"
            if dimension == "chatbot"
            else "Studies cited by each role"
        ),
        fontsize=7.5 * paper_font_scale,
        color=TEXT_COLOR,
    )
    set_size_axis.grid(
        axis="x", color=GRID_COLOR, linewidth=0.7, zorder=0
    )
    set_size_axis.tick_params(
        axis="x",
        labelsize=7 * paper_font_scale,
        length=3,
        color=TEXT_COLOR,
    )
    set_size_axis.tick_params(
        axis="y",
        labelsize=7.5 * paper_font_scale,
        length=0,
        pad=4,
    )
    set_size_axis.spines["top"].set_visible(False)
    set_size_axis.spines["right"].set_color(TEXT_COLOR)
    set_size_axis.spines["left"].set_visible(False)
    set_size_axis.spines["bottom"].set_color(TEXT_COLOR)
    set_size_axis.spines["right"].set_linewidth(0.75)
    set_size_axis.spines["bottom"].set_linewidth(0.75)

    for row_position in row_positions:
        matrix_axis.axhline(
            row_position, color=GRID_COLOR, linewidth=0.65, zorder=0
        )
    for x_position, intersection in zip(
        intersection_x, intersections
    ):
        members = tuple(intersection["members"])
        matrix_axis.scatter(
            [x_position] * 3,
            row_positions,
            s=18,
            color=INACTIVE_DOT_COLOR,
            edgecolors="none",
            zorder=2,
        )
        if len(members) > 1:
            matrix_axis.plot(
                [x_position, x_position],
                [min(members), max(members)],
                color=UPSET_COLOR,
                linewidth=1.5,
                zorder=3,
            )
        matrix_axis.scatter(
            [x_position] * len(members),
            members,
            s=30,
            color=UPSET_COLOR,
            edgecolors="none",
            zorder=4,
        )
    matrix_axis.scatter(
        [not_recalled_x] * 3,
        row_positions,
        s=28,
        marker="x",
        linewidths=1.1,
        color=NOT_RECALLED_COLOR,
        zorder=4,
    )
    matrix_axis.axvline(
        not_recalled_x - 0.65,
        color=GRID_COLOR,
        linewidth=0.9,
        zorder=1,
    )
    matrix_axis.set_xlim(-0.55, not_recalled_x + 0.55)
    matrix_axis.set_ylim(2.5, -0.5)
    matrix_axis.set_yticks([])
    matrix_axis.set_xticks([not_recalled_x], ["Not\ncited"])
    matrix_axis.tick_params(
        axis="x", labelsize=7 * paper_font_scale, length=0, pad=4
    )
    for spine in matrix_axis.spines.values():
        spine.set_visible(False)


def create_figure_2(demo_data: dict[str, Any]):
    """Build Figure 2 as included/excluded chatbot and role UpSet plots."""

    panels = load_main_overlap_panels(demo_data)
    figure = plt.figure(figsize=(10.4, 9.2), facecolor="white")
    outer = figure.add_gridspec(2, 2, wspace=0.23, hspace=0.30)
    panel_specs = (
        ("included", "chatbot", "A"),
        ("included", "role", "B"),
        ("excluded", "chatbot", "C"),
        ("excluded", "role", "D"),
    )
    for panel_index, (study_status, dimension, panel_label) in enumerate(
        panel_specs
    ):
        draw_upset_panel(
            figure,
            outer[panel_index // 2, panel_index % 2],
            dimension=dimension,
            study_status=study_status,
            panel_label=panel_label,
            panel=panels[study_status][dimension],
        )
    figure.subplots_adjust(left=0.055, right=0.992, top=0.96, bottom=0.055)
    return figure


VENN_REGION_POSITIONS = {
    "firstOnly": (-1.16, 0.30),
    "secondOnly": (1.15, 0.39),
    "thirdOnly": (0.28, -1.18),
    "firstSecondOnly": (-0.02, 0.86),
    "firstThirdOnly": (-0.46, -0.38),
    "secondThirdOnly": (0.69, -0.38),
    "allThree": (0.13, 0.08),
}

VENN_REGION_MEMBERSHIP = {
    "firstOnly": (True, False, False),
    "secondOnly": (False, True, False),
    "thirdOnly": (False, False, True),
    "firstSecondOnly": (True, True, False),
    "firstThirdOnly": (True, False, True),
    "secondThirdOnly": (False, True, True),
    "allThree": (True, True, True),
}


def compute_venn_region_label_positions(
    centers: list[tuple[float, float]],
    radii: list[float],
) -> dict[str, tuple[float, float]]:
    """Locate each Venn region's label at its true geometric centroid.

    Circle radii scale with each set's count, so a fixed label position drifts
    out of its region whenever a panel's circles are unevenly sized. This
    samples a dense grid over the diagram bounds and averages the coordinates
    that fall in each region, falling back to VENN_REGION_POSITIONS for a
    region with no geometric area. Called by draw_proportional_venn_panel.
    """

    grid_x, grid_y = np.meshgrid(
        np.linspace(-1.85, 1.85, 700),
        np.linspace(-1.55, 1.75, 700),
    )
    inside_circle = [
        (grid_x - center_x) ** 2 + (grid_y - center_y) ** 2 <= radius**2
        for (center_x, center_y), radius in zip(centers, radii)
    ]
    positions = {}
    for region_id, membership in VENN_REGION_MEMBERSHIP.items():
        region_mask = np.ones_like(grid_x, dtype=bool)
        for set_mask, is_member in zip(inside_circle, membership):
            region_mask &= set_mask if is_member else ~set_mask
        if region_mask.any():
            positions[region_id] = (
                float(grid_x[region_mask].mean()),
                float(grid_y[region_mask].mean()),
            )
        else:
            positions[region_id] = VENN_REGION_POSITIONS[region_id]
    return positions


def draw_proportional_venn_panel(
    figure,
    subplot_spec,
    *,
    dimension: str,
    study_status: str,
    panel_label: str,
    panel: dict[str, Any],
) -> None:
    """Draw one three-set Venn panel with circle area scaled to set size."""

    if study_status not in {"included", "excluded"}:
        raise ValueError(f"Unexpected study status: {study_status}")
    style = PANEL_STYLES[dimension]
    groups = DIMENSION_GROUPS[dimension]
    expected_labels = [style["labels"][group] for group in groups]
    if list(panel["setLabels"]) != expected_labels:
        raise ValueError(f"{dimension}: unexpected set-label order")

    benchmark_count = int(panel["benchmarkStudyCount"])
    union_count = int(panel["unionCount"])
    not_recalled_count = benchmark_count - union_count
    shared_all_count = int(panel["sharedAllCount"])
    set_counts = [int(count) for count in panel["setCounts"]]
    regions = {
        region["regionId"]: int(region["studyCount"])
        for region in panel["regions"]
    }
    if set(regions) != set(VENN_REGION_POSITIONS):
        raise ValueError(
            f"{study_status} {dimension}: unexpected Venn region IDs"
        )

    inner = subplot_spec.subgridspec(
        1,
        2,
        width_ratios=(3.0, 1.08),
        wspace=0.07,
    )
    diagram_axis = figure.add_subplot(inner[0, 0])
    summary_axis = figure.add_subplot(inner[0, 1])
    diagram_axis.set_aspect("equal")
    diagram_axis.axis("off")
    summary_axis.axis("off")

    status_label = (
        "Cochrane included" if study_status == "included" else "Cochrane excluded"
    )
    diagram_axis.text(
        -1.95,
        1.89,
        f"{panel_label}  {style['title']}",
        ha="left",
        va="top",
        fontsize=10.8,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    diagram_axis.text(
        -1.68,
        1.68,
        f"{status_label} studies (N = {benchmark_count})",
        ha="left",
        va="top",
        fontsize=8.6,
        color=TEXT_COLOR,
    )
    box_left = -1.76
    box_bottom = -1.53
    box_width = 3.52
    box_height = 3.04
    diagram_axis.add_patch(
        Rectangle(
            (box_left, box_bottom),
            box_width,
            box_height,
            facecolor="white",
            edgecolor=TEXT_COLOR,
            linewidth=1.3,
            zorder=0,
        )
    )

    max_count = max(set_counts)
    max_radius = 1.16
    radii = [
        max_radius * math.sqrt(count / max_count)
        for count in set_counts
    ]
    centers = [(-0.58, 0.26), (0.58, 0.34), (0.12, -0.28)]
    set_colors = [style["colors"][group] for group in groups]
    for center, radius, color in zip(centers, radii, set_colors):
        diagram_axis.add_patch(
            Circle(
                center,
                radius,
                facecolor=color,
                edgecolor=TEXT_COLOR,
                linewidth=0.8,
                alpha=0.30,
                zorder=1,
            )
        )

    region_label_positions = compute_venn_region_label_positions(centers, radii)
    for region_id, (x_position, y_position) in region_label_positions.items():
        count = regions[region_id]
        diagram_axis.text(
            x_position,
            y_position,
            str(count),
            ha="center",
            va="center",
            fontsize=8.4 if count else 7.0,
            fontweight="bold",
            color=TEXT_COLOR if count else MUTED_TEXT_COLOR,
            bbox={
                "boxstyle": "round,pad=0.16",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.82,
            },
            zorder=5,
        )

    diagram_axis.text(
        1.33,
        -1.34,
        f"Not cited\n{not_recalled_count}",
        ha="center",
        va="center",
        fontsize=7.7,
        fontweight="bold",
        color=TEXT_COLOR,
        linespacing=0.95,
        bbox={
            "boxstyle": "round,pad=0.23",
            "facecolor": "#F6F7F8",
            "edgecolor": GRID_COLOR,
        },
        zorder=6,
    )
    diagram_axis.set_xlim(-1.86, 1.86)
    diagram_axis.set_ylim(-1.62, 1.98)

    box_top = box_bottom + box_height
    summary_axis.text(
        0.0,
        box_top,
        f"Studies cited (of {benchmark_count})",
        ha="left",
        va="top",
        fontsize=8.7,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    studies_cited_labels = (
        [CHATBOT_FULL_LABELS[group] for group in groups]
        if dimension == "chatbot"
        else expected_labels
    )
    for index, (label, count, color) in enumerate(
        zip(studies_cited_labels, set_counts, set_colors)
    ):
        y_position = 1.18 - index * 0.47
        summary_axis.scatter(
            [0.05],
            [y_position],
            s=56,
            color=color,
            alpha=0.78,
            edgecolors=TEXT_COLOR,
            linewidths=0.35,
        )
        summary_axis.text(
            0.15,
            y_position,
            f"{label}\n{count} ({100 * count / benchmark_count:.1f}%)",
            ha="left",
            va="center",
            fontsize=7.3,
            color=TEXT_COLOR,
            linespacing=1.05,
        )

    pair_specs = (
        ("firstSecondOnly", 0, 1),
        ("firstThirdOnly", 0, 2),
        ("secondThirdOnly", 1, 2),
    )
    jaccard_lines = [
        f"All three: {shared_all_count} ({100 * shared_all_count / union_count:.1f}%)"
    ]
    for region_id, first_index, second_index in pair_specs:
        pair_intersection = regions[region_id] + shared_all_count
        pair_union = (
            set_counts[first_index] + set_counts[second_index] - pair_intersection
        )
        jaccard_lines.append(
            f"{expected_labels[first_index]}–{expected_labels[second_index]}: "
            f"{pair_intersection} ({100 * pair_intersection / pair_union:.1f}%)"
        )
    summary_axis.text(
        0.0,
        -0.32,
        f"Overlap (of {union_count} cited)",
        ha="left",
        va="top",
        fontsize=8.7,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    summary_axis.text(
        0.0,
        -0.70,
        "\n".join(jaccard_lines),
        ha="left",
        va="top",
        fontsize=7.4,
        color=TEXT_COLOR,
        linespacing=1.52,
    )
    summary_axis.set_xlim(0, 1)
    summary_axis.set_ylim(-1.62, 1.98)


def create_figure_5(demo_data: dict[str, Any]):
    """Build Figure 5 as proportional-circle versions of Figure 2 panels."""

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    panels = load_main_overlap_panels(demo_data)
    figure = plt.figure(figsize=(10.4, 6.9), facecolor="white")
    outer = figure.add_gridspec(2, 2, wspace=0.20, hspace=0.10)
    panel_specs = (
        ("included", "chatbot", "A"),
        ("included", "role", "B"),
        ("excluded", "chatbot", "C"),
        ("excluded", "role", "D"),
    )
    for panel_index, (study_status, dimension, panel_label) in enumerate(
        panel_specs
    ):
        draw_proportional_venn_panel(
            figure,
            outer[panel_index // 2, panel_index % 2],
            dimension=dimension,
            study_status=study_status,
            panel_label=panel_label,
            panel=panels[study_status][dimension],
        )
    figure.subplots_adjust(left=0.045, right=0.985, top=0.96, bottom=0.045)
    return figure


def load_figure_3_rows() -> tuple[list[dict[str, Any]], int]:
    """Load and validate Figure 3 counts and deterministic example annotations."""

    with CITED_EXCLUDED_STUDY_AUDIT_PATH.open(
        newline="", encoding="utf-8"
    ) as handle:
        study_rows = list(csv.DictReader(handle))
    with CITED_EXCLUDED_REASON_COUNTS_PATH.open(
        newline="", encoding="utf-8"
    ) as handle:
        count_rows = list(csv.DictReader(handle))
    with FIGURE_3_ANNOTATIONS_PATH.open(
        newline="", encoding="utf-8"
    ) as handle:
        annotation_rows = list(csv.DictReader(handle))

    study_keys = {
        (row["review"], row["study_label"])
        for row in study_rows
    }
    if len(study_keys) != len(study_rows):
        raise ValueError(
            f"{CITED_EXCLUDED_STUDY_AUDIT_PATH.name}: duplicate study key"
        )
    total_studies = len(study_rows)
    if not total_studies:
        raise ValueError(
            f"{CITED_EXCLUDED_STUDY_AUDIT_PATH.name}: no study rows"
        )

    annotations_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in annotation_rows:
        key = (row["reason_category"], row["review"], row["study_label"])
        if key in annotations_by_key:
            raise ValueError(
                f"{FIGURE_3_ANNOTATIONS_PATH.name}: duplicate annotation {key}"
            )
        if not row["display_label"].strip() or not row["example_detail"].strip():
            raise ValueError(
                f"{FIGURE_3_ANNOTATIONS_PATH.name}: incomplete annotation {key}"
            )
        annotations_by_key[key] = row

    figure_rows: list[dict[str, Any]] = []
    expected_annotation_keys: set[tuple[str, str, str]] = set()
    seen_categories: set[str] = set()
    for category_position, count_row in enumerate(count_rows):
        category = count_row["reason_category"]
        if category not in REASON_CATEGORY_LABELS:
            raise ValueError(f"Figure 3 has no display label for {category}")
        if category in seen_categories:
            raise ValueError(
                f"{CITED_EXCLUDED_REASON_COUNTS_PATH.name}: duplicate {category}"
            )
        seen_categories.add(category)

        category_studies = [
            row
            for row in study_rows
            if category in row["reason_categories"].split(";")
        ]
        count = len(category_studies)
        expected_count = int(count_row["unique_excluded_studies"])
        if count != expected_count:
            raise ValueError(
                f"{category}: count artifact reports {expected_count}, "
                f"study audit contains {count}"
            )
        percent = 100 * count / total_studies
        expected_percent = float(
            count_row["percent_of_unique_excluded_studies"]
        )
        if round(percent, 1) != expected_percent:
            raise ValueError(
                f"{category}: percent artifact reports {expected_percent}, "
                f"study audit implies {percent:.1f}"
            )

        selected_studies = sorted(
            category_studies,
            key=lambda row: (
                -int(row["response_study_mentions"]),
                row["review"],
                row["study_label"],
            ),
        )[:3]
        examples = []
        for study in selected_studies:
            annotation_key = (
                category,
                study["review"],
                study["study_label"],
            )
            expected_annotation_keys.add(annotation_key)
            annotation = annotations_by_key.get(annotation_key)
            if annotation is None:
                raise ValueError(
                    f"{FIGURE_3_ANNOTATIONS_PATH.name}: missing "
                    f"deterministically selected example {annotation_key}"
                )
            examples.append(
                {
                    "display_label": annotation["display_label"],
                    "detail": annotation["example_detail"],
                    "response_study_mentions": int(
                        study["response_study_mentions"]
                    ),
                }
            )
        figure_rows.append(
            {
                "category": category,
                "display_label": REASON_CATEGORY_LABELS[category],
                "category_position": category_position,
                "count": count,
                "percent": percent,
                "examples": examples,
            }
        )

    annotation_keys = set(annotations_by_key)
    if annotation_keys != expected_annotation_keys:
        missing = sorted(expected_annotation_keys - annotation_keys)
        stale = sorted(annotation_keys - expected_annotation_keys)
        raise ValueError(
            "Figure 3 annotations must exactly cover the deterministic "
            f"selection; missing={missing}, stale={stale}"
        )

    figure_rows.sort(
        key=lambda row: (-row["count"], row["category_position"])
    )
    return figure_rows, total_studies


def create_figure_3(
    figure_rows: list[dict[str, Any]], total_studies: int
):
    """Build Figure 3 as ranked bars aligned with qualitative examples."""

    paper_font_scale = 1.6
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    figure = plt.figure(figsize=(10.4, 9.2), facecolor="white")
    grid = figure.add_gridspec(
        1,
        2,
        width_ratios=(0.36, 0.64),
        wspace=0.055,
    )
    bar_axis = figure.add_subplot(grid[0])
    example_axis = figure.add_subplot(grid[1], sharey=bar_axis)
    for axis in (bar_axis, example_axis):
        axis.set_facecolor("white")

    y_positions = np.arange(len(figure_rows))
    counts = [row["count"] for row in figure_rows]
    bar_axis.barh(
        y_positions,
        counts,
        height=0.58,
        color=UPSET_COLOR,
        edgecolor=TEXT_COLOR,
        linewidth=0.65,
        zorder=3,
    )
    for y_position, row in zip(y_positions, figure_rows):
        bar_axis.text(
            row["count"] + 0.7,
            y_position,
            f"{row['count']}/{total_studies} ({row['percent']:.1f}%)",
            ha="left",
            va="center",
            fontsize=7.4 * paper_font_scale,
            fontweight="bold",
            color=TEXT_COLOR,
            zorder=4,
        )

    bar_axis.set_title(
        "A  Exclusion category",
        loc="left",
        pad=10,
        fontsize=10.5 * paper_font_scale,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    bar_axis.set_yticks(
        y_positions,
        [row["display_label"] for row in figure_rows],
    )
    bar_axis.set_ylim(len(figure_rows) - 0.5, -0.5)
    bar_axis.set_xlim(0, 56)
    bar_axis.set_xticks((0, 10, 20, 30, 40))
    bar_axis.set_xlabel(
        "Cited excluded studies, n",
        fontsize=8 * paper_font_scale,
        color=TEXT_COLOR,
        labelpad=6,
    )
    bar_axis.grid(axis="x", color=GRID_COLOR, linewidth=0.7, zorder=0)
    bar_axis.tick_params(
        axis="x",
        labelsize=7.5 * paper_font_scale,
        length=3,
        color=TEXT_COLOR,
    )
    bar_axis.tick_params(
        axis="y",
        labelsize=7.4 * paper_font_scale,
        length=0,
        pad=6,
    )
    bar_axis.spines["top"].set_visible(False)
    bar_axis.spines["right"].set_visible(False)
    bar_axis.spines["left"].set_visible(False)
    bar_axis.spines["bottom"].set_color(TEXT_COLOR)
    bar_axis.spines["bottom"].set_linewidth(0.75)

    example_axis.set_title(
        "B  Examples: study and Cochrane exclusion reason",
        loc="left",
        pad=10,
        fontsize=10.5 * paper_font_scale,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    example_axis.set_xlim(0, 1)
    example_axis.tick_params(
        axis="both",
        which="both",
        left=False,
        bottom=False,
        labelleft=False,
        labelbottom=False,
    )
    for spine in example_axis.spines.values():
        spine.set_visible(False)

    for boundary in np.arange(0.5, len(figure_rows), 1):
        bar_axis.axhline(
            boundary, color=GRID_COLOR, linewidth=0.65, zorder=0
        )
        example_axis.axhline(
            boundary, color=GRID_COLOR, linewidth=0.65, zorder=0
        )

    for y_position, row in zip(y_positions, figure_rows):
        examples = row["examples"]
        offsets = (-0.21, 0.0, 0.21) if len(examples) == 3 else (-0.105, 0.105)
        for offset, example in zip(offsets, examples):
            example_axis.text(
                0.0,
                y_position + offset,
                example["display_label"],
                ha="left",
                va="center",
                fontsize=6.1 * paper_font_scale,
                fontweight="bold",
                color=TEXT_COLOR,
            )
            example_axis.text(
                0.36,
                y_position + offset,
                example["detail"],
                ha="left",
                va="center",
                fontsize=6.1 * paper_font_scale,
                color=TEXT_COLOR,
            )

    figure.subplots_adjust(
        left=0.16,
        right=0.995,
        top=0.945,
        bottom=0.06,
    )
    return figure


def load_candidate_status_responses() -> list[dict[str, Any]]:
    """Build one candidate-status composition record per chatbot response."""

    response_rows: list[dict[str, Any]] = []
    for source in review_sources():
        with source.matches_path.open(newline="", encoding="utf-8") as handle:
            match_rows = list(csv.DictReader(handle))

        metadata_by_run: dict[str, tuple[str, str, int]] = {}
        counts_by_run: dict[str, dict[str, int]] = defaultdict(
            lambda: {status: 0 for status in CANDIDATE_STATUS_ORDER}
        )
        candidates_by_run: dict[str, set[str]] = defaultdict(set)
        for row in match_rows:
            run_id = row["run_id"]
            metadata = (row["model"], row["role_id"], int(row["replicate"]))
            previous = metadata_by_run.setdefault(run_id, metadata)
            if previous != metadata:
                raise ValueError(
                    f"{source.review_id}: conflicting metadata for {run_id}"
                )

            candidate = row["canonical_candidate"].strip()
            if not candidate:
                raise ValueError(
                    f"{source.review_id}/{run_id}: empty canonical candidate"
                )
            if candidate in candidates_by_run[run_id]:
                raise ValueError(
                    f"{source.review_id}/{run_id}: duplicate candidate "
                    f"{candidate!r}"
                )
            candidates_by_run[run_id].add(candidate)

            ground_truth_status = row["ground_truth_status"]
            if ground_truth_status == "included":
                status = "included"
            elif ground_truth_status == "cochrane_excluded":
                status = "excluded"
            else:
                status = "other"
            counts_by_run[run_id][status] += 1

        if len(metadata_by_run) != 36:
            raise ValueError(
                f"{source.review_id}: expected 36 responses, "
                f"found {len(metadata_by_run)}"
            )

        for run_id, (model, role, replicate) in metadata_by_run.items():
            counts = counts_by_run[run_id]
            candidate_count = sum(counts.values())
            if candidate_count < 1:
                raise ValueError(
                    f"{source.review_id}/{run_id}: response has no candidates"
                )
            response_rows.append(
                {
                    "review": source.review_id,
                    "run_id": run_id,
                    "model": model,
                    "role": role,
                    "replicate": replicate,
                    "candidate_count": candidate_count,
                    **{
                        f"{status}_proportion": counts[status]
                        / candidate_count
                        for status in CANDIDATE_STATUS_ORDER
                    },
                }
            )

    if len(response_rows) != 720:
        raise ValueError(
            f"Expected 720 candidate-composition records, "
            f"found {len(response_rows)}"
        )
    return response_rows


def summarize_candidate_status_group(
    rows: list[dict[str, Any]],
    *,
    group_id: str,
    label: str,
) -> dict[str, Any]:
    """Summarize mean within-response composition for one plotted group."""

    if not rows:
        raise ValueError(f"No candidate-composition rows for {group_id}")
    proportions = {
        status: fmean(
            float(row[f"{status}_proportion"]) for row in rows
        )
        for status in CANDIDATE_STATUS_ORDER
    }
    if not np.isclose(sum(proportions.values()), 1.0):
        raise ValueError(
            f"{group_id}: mean candidate-status proportions do not sum to 1"
        )
    return {
        "group_id": group_id,
        "label": label,
        "response_count": len(rows),
        "mean_candidate_count": fmean(
            int(row["candidate_count"]) for row in rows
        ),
        "proportions": proportions,
    }


def build_candidate_status_summaries(
    response_rows: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Prepare Figure 4 groups in stable overall and marginal order."""

    model_labels = CHATBOT_FULL_LABELS
    role_labels = PANEL_STYLES["role"]["labels"]
    return {
        "overall": [
            summarize_candidate_status_group(
                response_rows,
                group_id="overall",
                label="All responses",
            )
        ],
        "chatbot": [
            summarize_candidate_status_group(
                [
                    row
                    for row in response_rows
                    if row["model"] == model
                ],
                group_id=model,
                label=model_labels[model],
            )
            for model in MODELS
        ],
        "role": [
            summarize_candidate_status_group(
                [
                    row
                    for row in response_rows
                    if row["role"] == role
                ],
                group_id=role,
                label=role_labels[role],
            )
            for role in ROLES
        ],
    }


CANDIDATE_STATUS_SHORT_LABELS = {
    "included": "included",
    "excluded": "excluded",
    "other": "other",
}

MIN_LABELED_SEGMENT_WIDTH_FRACTION = 0.055


def draw_candidate_status_panel(
    axis,
    *,
    panel_label: str,
    title: str,
    summaries: list[dict[str, Any]],
    x_max: float,
    show_x_label: bool,
) -> None:
    """Draw one Figure 4 panel as bars scaled to mean studies/response.

    Bar length encodes each group's mean candidate count on a shared scale
    across all panels; stacked segment widths encode composition. Segments
    too narrow to hold an inside label are instead named in the row's
    trailing annotation, where a short bar always leaves room to spare.
    """

    y_positions = np.arange(len(summaries))
    lengths = np.asarray(
        [float(summary["mean_candidate_count"]) for summary in summaries]
    )
    min_labeled_width = MIN_LABELED_SEGMENT_WIDTH_FRACTION * x_max
    left_edges = np.zeros(len(summaries), dtype=float)
    unlabeled_segments: list[list[tuple[str, float]]] = [
        [] for _ in summaries
    ]
    for status in CANDIDATE_STATUS_ORDER:
        proportions = np.asarray(
            [float(summary["proportions"][status]) for summary in summaries]
        )
        widths = proportions * lengths
        bars = axis.barh(
            y_positions,
            widths,
            left=left_edges,
            height=0.60,
            color=CANDIDATE_STATUS_COLORS[status],
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
        for row_index, (bar, width, proportion) in enumerate(
            zip(bars, widths, proportions)
        ):
            if width < min_labeled_width:
                unlabeled_segments[row_index].append((status, proportion))
                continue
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_y() + bar.get_height() / 2,
                f"{100 * proportion:.1f}%",
                ha="center",
                va="center",
                fontsize=8.2,
                fontweight="bold",
                color=(
                    TEXT_COLOR if status == "other" else "white"
                ),
                zorder=4,
            )
        left_edges += widths

    for y_position, summary, length, row_unlabeled in zip(
        y_positions, summaries, lengths, unlabeled_segments
    ):
        annotation = (
            f"n={summary['response_count']} · "
            f"{summary['mean_candidate_count']:.1f} studies/response"
        )
        if row_unlabeled:
            named_shares = " · ".join(
                f"{CANDIDATE_STATUS_SHORT_LABELS[status]} {100 * proportion:.1f}%"
                for status, proportion in row_unlabeled
            )
            annotation = f"{named_shares}  ·  {annotation}"
        axis.text(
            length + x_max * 0.02,
            y_position,
            annotation,
            ha="left",
            va="center",
            fontsize=8,
            color=MUTED_TEXT_COLOR,
        )

    axis.set_title(
        f"{panel_label}  {title}",
        loc="left",
        pad=8,
        fontsize=10.5,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    axis.set_yticks(
        y_positions,
        [summary["label"] for summary in summaries],
    )
    axis.set_ylim(len(summaries) - 0.55, -0.55)
    axis.set_xlim(0, x_max * 1.18)
    axis.set_xlabel(
        (
            "Mean studies retrieved per response (bar length)"
            if show_x_label
            else ""
        ),
        fontsize=9,
        color=TEXT_COLOR,
        labelpad=7,
    )
    axis.set_axisbelow(True)
    axis.grid(axis="x", color=GRID_COLOR, linewidth=0.7, zorder=0)
    axis.tick_params(
        axis="x",
        labelsize=8,
        length=3,
        color=TEXT_COLOR,
    )
    axis.tick_params(
        axis="y",
        labelsize=8.5,
        length=0,
        pad=7,
    )
    for spine in axis.spines.values():
        spine.set_visible(False)


def create_figure_4(
    summaries: dict[str, list[dict[str, Any]]],
):
    """Build Figure 4 as overall and marginal candidate-status compositions."""

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    figure, axes = plt.subplots(
        3,
        1,
        figsize=(7.4, 6.5),
        facecolor="white",
        gridspec_kw={
            "height_ratios": (1.0, 2.0, 2.0),
            "hspace": 0.72,
        },
    )
    panel_specs = (
        ("overall", "A", "Overall"),
        ("chatbot", "B", "By chatbot"),
        ("role", "C", "By user role"),
    )
    x_max = max(
        summary["mean_candidate_count"]
        for group in summaries.values()
        for summary in group
    )
    for panel_index, (axis, (key, panel_label, title)) in enumerate(
        zip(axes, panel_specs)
    ):
        axis.set_facecolor("white")
        draw_candidate_status_panel(
            axis,
            panel_label=panel_label,
            title=title,
            summaries=summaries[key],
            x_max=x_max,
            show_x_label=panel_index == len(panel_specs) - 1,
        )

    figure.legend(
        handles=[
            Patch(
                facecolor=CANDIDATE_STATUS_COLORS[status],
                edgecolor="none",
                label=CANDIDATE_STATUS_LABELS[status],
            )
            for status in CANDIDATE_STATUS_ORDER
        ],
        loc="upper center",
        bbox_to_anchor=(0.53, 0.992),
        ncol=3,
        frameon=False,
        fontsize=9,
        handlelength=1.3,
        columnspacing=1.8,
    )
    figure.subplots_adjust(
        left=0.20,
        right=0.985,
        top=0.88,
        bottom=0.065,
    )
    return figure


def save_figure_outputs(figure, output_stem: Path) -> None:
    """Write one figure as PDF, normalized SVG, and 600-dpi PNG."""

    for extension in ("pdf", "svg", "png"):
        output_path = output_stem.with_suffix(f".{extension}")
        save_options = {
            "bbox_inches": "tight",
            "pad_inches": 0.03,
            "facecolor": figure.get_facecolor(),
        }
        if extension == "png":
            save_options["dpi"] = 600
        figure.savefig(output_path, **save_options)
        if extension == "svg":
            svg_lines = output_path.read_text(encoding="utf-8").splitlines()
            output_path.write_text(
                "\n".join(line.rstrip() for line in svg_lines) + "\n",
                encoding="utf-8",
            )
        print(f"Wrote: {output_path.relative_to(REPO_ROOT)}")
    plt.close(figure)


def print_pairwise_results(
    pairwise_results: dict[
        str, list[dict[str, float | int | str]]
    ],
) -> None:
    """Print exact pairwise results represented by the figure's stars."""

    for dimension in ("chatbot", "role"):
        print(f"{PANEL_STYLES[dimension]['title']} pairwise tests:")
        for result in pairwise_results[dimension]:
            first_group = str(result["first_group"])
            second_group = str(result["second_group"])
            adjusted_p = float(result["holm_p_value"])
            print(
                f"  {first_group} vs {second_group}: "
                f"difference={100 * float(result['mean_difference']):.2f} "
                f"percentage points, raw p={float(result['raw_p_value']):.6g}, "
                f"Holm p={adjusted_p:.6g} "
                f"({significance_label(adjusted_p)})"
            )


def main() -> None:
    """Load current artifacts and write all retrieval-bias paper figures."""

    demo_data = load_demo_data()
    summaries = dimension_summaries(demo_data)
    response_rows = load_response_recall(demo_data)
    validate_summaries(response_rows, summaries)
    included_jaccard_summaries = load_included_jaccard_summaries()
    confidence_intervals = review_clustered_bootstrap_intervals(response_rows)
    pairwise_results = calculate_pairwise_tests(response_rows)
    save_figure_outputs(
        create_figure_1(
            summaries,
            confidence_intervals,
            pairwise_results,
            response_rows,
            included_jaccard_summaries,
        ),
        FIGURE_1_OUTPUT_STEM,
    )
    save_figure_outputs(create_figure_2(demo_data), FIGURE_2_OUTPUT_STEM)
    figure_3_rows, cited_excluded_study_count = load_figure_3_rows()
    save_figure_outputs(
        create_figure_3(figure_3_rows, cited_excluded_study_count),
        FIGURE_3_OUTPUT_STEM,
    )
    candidate_status_responses = load_candidate_status_responses()
    candidate_status_summaries = build_candidate_status_summaries(
        candidate_status_responses
    )
    save_figure_outputs(
        create_figure_4(candidate_status_summaries),
        FIGURE_4_OUTPUT_STEM,
    )
    save_figure_outputs(create_figure_5(demo_data), FIGURE_5_OUTPUT_STEM)
    print_pairwise_results(pairwise_results)


if __name__ == "__main__":
    main()
