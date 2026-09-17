#!/usr/bin/env python3
"""Plot two response-level citation-share metrics in Figure 2's visual style.

Both versions divide by all distinct candidate study clusters cited in a
response. Version 1 counts Cochrane-included candidates in the numerator;
version 2 counts Cochrane-included and Cochrane-excluded candidates. Marginal
values average response-level ratios, giving every response equal weight.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import fmean, stdev

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, HPacker, TextArea, VPacker

from make_paper_figures import (
    CHATBOT_FULL_LABELS_WRAPPED,
    MODELS,
    PANEL_STYLES,
    ROLES,
    TEXT_COLOR,
    calculate_pairwise_tests,
    draw_chatbot_margin,
    draw_role_margin,
    load_candidate_status_responses,
    print_pairwise_results,
    review_clustered_bootstrap_intervals,
    save_figure_outputs,
)

FIGURES_DIR = Path(__file__).resolve().parent
OUTPUT_STEMS = {
    1: FIGURES_DIR / "figure_4_included_study_precision",
    2: FIGURES_DIR / "figure_5_included_excluded_study_precision",
}
METRIC_LABELS = {1: "precision", 2: "precision"}
DEFINITIONS = {
    1: {
        "title": "Included-only precision",
        "numerator_lines": (
            (("Distinct cited candidate clusters", False),),
            (("matched to", False), ("Cochrane-included", True), ("studies", False)),
        ),
    },
    2: {
        "title": "Included + excluded precision",
        "numerator_lines": (
            (("Distinct cited candidate clusters", False),),
            (("matched to", False), ("Cochrane-included", True), ("or", False)),
            (("Cochrane-excluded", True), ("studies", False)),
        ),
    },
}
DENOMINATOR = (
    "All distinct candidate clusters\n"
    "cited in the response"
)


def load_response_precision(version: int = 1) -> list[dict[str, str | int | float]]:
    """Use Figure 1's validated, study-cluster-deduplicated response counts."""

    if version not in OUTPUT_STEMS:
        raise ValueError(f"Unsupported precision version: {version}")
    records = load_candidate_status_responses()
    return [
        {
            "review": str(row["review"]),
            "run_id": str(row["run_id"]),
            "model": str(row["model"]),
            "role": str(row["role"]),
            "replicate": int(row["replicate"]),
            "precision": float(row["included_proportion"])
            + (float(row["excluded_proportion"]) if version == 2 else 0.0),
        }
        for row in records
    ]


def marginal_summaries(
    response_rows: list[dict[str, str | int | float]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Compute equally weighted response means and sample SDs."""

    summaries = {}
    for dimension, field, groups in (
        ("chatbot", "model", MODELS),
        ("role", "role", ROLES),
    ):
        summaries[dimension] = {}
        for group in groups:
            values = [
                float(row["precision"])
                for row in response_rows
                if row[field] == group
            ]
            if len(values) != 240:
                raise ValueError(
                    f"{dimension}/{group}: expected 240 responses, "
                    f"found {len(values)}"
                )
            summaries[dimension][group] = {
                "mean": fmean(values),
                "sd": stdev(values),
            }
    return summaries


def draw_definition_numerator(axis, version: int) -> None:
    """Center numerator lines while bolding only the Cochrane status terms."""

    lines = []
    for segments in DEFINITIONS[version]["numerator_lines"]:
        line = HPacker(
            children=[
                TextArea(
                    text,
                    textprops={
                        "fontsize": 8.6,
                        "color": TEXT_COLOR,
                        "fontweight": "bold" if bold else "normal",
                    },
                )
                for text, bold in segments
            ],
            align="baseline",
            pad=0,
            sep=3,
        )
        lines.append(line)
    numerator = VPacker(children=lines, align="center", pad=0, sep=1)
    axis.add_artist(
        AnnotationBbox(
            numerator,
            (0.65, 0.62 if version == 1 else 0.66),
            xycoords="axes fraction",
            box_alignment=(0.5, 0.5),
            frameon=False,
            pad=0,
        )
    )


def create_precision_figure(
    response_rows: list[dict[str, str | int | float]],
    summaries: dict[str, dict[str, dict[str, float]]],
    confidence_intervals: dict[str, dict[str, dict[str, float]]],
    pairwise_results: dict[str, list[dict[str, float | int | str]]],
    *,
    version: int = 1,
):
    """Draw the aligned chatbot margin, model-by-role heatmap, and role margin."""

    metric_label = METRIC_LABELS[version]
    definition = DEFINITIONS[version]
    interaction_means = np.empty((len(ROLES), len(MODELS)), dtype=float)
    for role_index, role in enumerate(ROLES):
        for model_index, model in enumerate(MODELS):
            values = [
                float(row["precision"])
                for row in response_rows
                if row["role"] == role and row["model"] == model
            ]
            if len(values) != 80:
                raise ValueError(
                    f"{model}/{role}: expected 80 responses, found {len(values)}"
                )
            interaction_means[role_index, model_index] = fmean(values)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    figure = plt.figure(figsize=(7.4, 6.0), facecolor="white")
    grid = figure.add_gridspec(
        2,
        2,
        width_ratios=(0.43, 0.57),
        height_ratios=(0.475, 0.525),
        hspace=0.28,
        wspace=0.09,
    )
    chatbot_axis = figure.add_subplot(grid[0, 0])
    definition_axis = figure.add_subplot(grid[0, 1])
    heatmap_axis = figure.add_subplot(grid[1, 0], sharex=chatbot_axis)
    role_axis = figure.add_subplot(grid[1, 1], sharey=heatmap_axis)
    for axis in (chatbot_axis, heatmap_axis, role_axis):
        axis.set_facecolor("white")

    draw_chatbot_margin(
        chatbot_axis,
        summaries=summaries["chatbot"],
        confidence_intervals=confidence_intervals["chatbot"],
        pairwise_results=pairwise_results["chatbot"],
        metric_label=metric_label,
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
        "Chatbot", fontsize=9, fontweight="bold", color=TEXT_COLOR, labelpad=7
    )
    heatmap_axis.set_ylabel(
        "User role", fontsize=9, fontweight="bold", color=TEXT_COLOR, labelpad=7
    )
    heatmap_axis.set_xticks(np.arange(-0.5, len(MODELS), 1), minor=True)
    heatmap_axis.set_yticks(np.arange(-0.5, len(ROLES), 1), minor=True)
    heatmap_axis.grid(which="minor", color="white", linewidth=2.0, zorder=2)
    heatmap_axis.tick_params(which="minor", length=0)
    for spine in heatmap_axis.spines.values():
        spine.set_visible(False)

    draw_role_margin(
        role_axis,
        summaries=summaries["role"],
        confidence_intervals=confidence_intervals["role"],
        pairwise_results=pairwise_results["role"],
        metric_label=metric_label,
    )

    definition_axis.set_axis_off()
    definition_axis.set_xlim(0, 1)
    definition_axis.set_ylim(0, 1)
    definition_axis.text(
        0.02,
        0.50,
        "Precision =",
        ha="left",
        va="center",
        fontsize=10.0,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    draw_definition_numerator(definition_axis, version)
    definition_axis.plot(
        [0.31, 0.99],
        [0.50, 0.50],
        color=TEXT_COLOR,
        linewidth=1.15,
    )
    definition_axis.text(
        0.65,
        0.38,
        DENOMINATOR,
        ha="center",
        va="center",
        fontsize=8.6,
        color=TEXT_COLOR,
        linespacing=1.15,
    )
    figure.subplots_adjust(left=0.115, right=0.985, top=0.91, bottom=0.15)
    chatbot_bbox = chatbot_axis.get_position()
    definition_bbox = definition_axis.get_position()
    figure.text(
        chatbot_bbox.x0,
        chatbot_bbox.y1 + 0.02,
        "Chatbot mean",
        ha="left",
        va="bottom",
        fontsize=10.5,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    figure.text(
        definition_bbox.x0,
        definition_bbox.y1 + 0.02,
        definition["title"],
        ha="left",
        va="bottom",
        fontsize=10.5,
        fontweight="bold",
        color=TEXT_COLOR,
    )
    return figure


def main() -> None:
    """Regenerate one requested precision version."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()

    response_rows = load_response_precision(args.version)
    summaries = marginal_summaries(response_rows)
    confidence_intervals = review_clustered_bootstrap_intervals(
        response_rows, metric_field="precision"
    )
    pairwise_results = calculate_pairwise_tests(
        response_rows, metric_field="precision"
    )
    save_figure_outputs(
        create_precision_figure(
            response_rows,
            summaries,
            confidence_intervals,
            pairwise_results,
            version=args.version,
        ),
        OUTPUT_STEMS[args.version],
    )
    print_pairwise_results(pairwise_results)


if __name__ == "__main__":
    main()
