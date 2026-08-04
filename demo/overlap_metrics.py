"""Reusable set and frequency overlap metrics for retrieval conditions."""

from __future__ import annotations

from collections.abc import Sequence, Set
from collections import Counter
from itertools import combinations
from math import erfc, isfinite, sqrt
from random import Random
from statistics import fmean, stdev
from typing import Any

from scipy.stats import chi2_contingency, fisher_exact, kruskal, spearmanr


def _summarize_permutation_values(values: Sequence[float]) -> dict[str, Any]:
    """Return the mean and central 95% nearest-rank interval."""

    sorted_values = sorted(values)

    def nearest_rank(probability: float) -> float:
        return sorted_values[round((len(sorted_values) - 1) * probability)]

    return {
        "mean": fmean(values),
        "interval95": {
            "lower": nearest_rank(0.025),
            "upper": nearest_rank(0.975),
        },
    }


def calculate_multi_set_jaccard(study_sets: Sequence[Set[str]]) -> dict[str, Any]:
    """Calculate the all-set intersection over the union for two or more sets."""

    if len(study_sets) < 2:
        raise ValueError(f"Expected at least two study sets, received {len(study_sets)}")
    normalized_sets = [set(studies) for studies in study_sets]
    shared_count = len(set.intersection(*normalized_sets))
    union_count = len(set.union(*normalized_sets))
    return {
        "sharedCount": shared_count,
        "unionCount": union_count,
        "jaccard": shared_count / union_count if union_count else None,
    }


def calculate_replicate_consistency(replicate_sets: Sequence[Set[str]]) -> dict[str, Any]:
    """Average pairwise Jaccard similarity across every replicate pair.

    Two empty replicate sets are treated as fully consistent (Jaccard 1.0) so
    a cell where every replicate retrieved zero matching studies is not
    penalized as maximally inconsistent.
    """

    if len(replicate_sets) < 2:
        raise ValueError(f"Expected at least two replicate sets, received {len(replicate_sets)}")
    normalized_sets = [set(studies) for studies in replicate_sets]
    pair_scores = [
        1.0 if not first and not second else len(first & second) / len(first | second)
        for first, second in combinations(normalized_sets, 2)
    ]
    return {
        "pairCount": len(pair_scores),
        "meanJaccard": fmean(pair_scores),
        "stdevJaccard": stdev(pair_scores) if len(pair_scores) > 1 else 0.0,
    }


def calculate_mann_whitney_test(
    sample_a: Sequence[float], sample_b: Sequence[float], *, label_a: str, label_b: str
) -> dict[str, Any]:
    """Two-sided normal-approximation Mann-Whitney U test between two samples.

    Intended for genuinely independent (non-overlapping) groups; two-sided
    p-value via the normal approximation with a tie correction, no scipy
    dependency.
    """

    if not sample_a or not sample_b:
        raise ValueError("Mann-Whitney U requires both samples to be non-empty")
    combined = sorted((value, 0) for value in sample_a) + sorted((value, 1) for value in sample_b)
    combined.sort(key=lambda pair: pair[0])
    ranks: list[float] = [0.0] * len(combined)
    index = 0
    while index < len(combined):
        end = index
        while end + 1 < len(combined) and combined[end + 1][0] == combined[index][0]:
            end += 1
        average_rank = (index + end) / 2 + 1
        for tie_index in range(index, end + 1):
            ranks[tie_index] = average_rank
        index = end + 1

    rank_sum_a = sum(rank for rank, (_, group) in zip(ranks, combined) if group == 0)
    n_a, n_b = len(sample_a), len(sample_b)
    u_a = rank_sum_a - n_a * (n_a + 1) / 2
    u_statistic = min(u_a, n_a * n_b - u_a)
    mean_u = n_a * n_b / 2
    tie_groups = Counter(value for value, _ in combined)
    tie_correction = sum(count**3 - count for count in tie_groups.values())
    n_total = n_a + n_b
    variance = (n_a * n_b / 12) * ((n_total + 1) - tie_correction / (n_total * (n_total - 1)))
    p_value = 1.0 if variance <= 0 else erfc(abs((u_statistic - mean_u) / sqrt(variance)) / sqrt(2))
    return {
        "method": "Mann-Whitney U",
        "comparisonLabel": f"{label_a} vs. {label_b}",
        "sampleSizeA": n_a,
        "sampleSizeB": n_b,
        "pValue": p_value,
        "significantAt05": p_value < 0.05,
    }


def calculate_kruskal_wallis_test(
    samples: Sequence[Sequence[float]], *, labels: Sequence[str]
) -> dict[str, Any]:
    """Kruskal-Wallis H test across two or more mutually exclusive, independent samples.

    The rank-based generalization of Mann-Whitney U to more than two groups.
    Intended for groups that do not overlap (unlike by-chatbot recall groups,
    which double-count studies recalled by multiple chatbots and would
    violate the independent-samples assumption this test relies on). Uses
    scipy.stats.kruskal for the H statistic and its chi-squared p-value.
    """

    if len(samples) != len(labels):
        raise ValueError(
            f"Expected one label per sample: {len(samples)} samples, {len(labels)} labels"
        )
    if len(samples) < 2:
        raise ValueError(f"Kruskal-Wallis requires at least two samples, received {len(samples)}")
    if any(not sample for sample in samples):
        raise ValueError("Kruskal-Wallis requires every sample to be non-empty")

    result = kruskal(*samples)
    return {
        "method": "Kruskal-Wallis H",
        "groupLabels": list(labels),
        "sampleSizes": [len(sample) for sample in samples],
        "statistic": float(result.statistic),
        "pValue": float(result.pvalue),
        "significantAt05": bool(result.pvalue < 0.05),
    }


def calculate_dunn_posthoc_test(
    samples: Sequence[Sequence[float]], *, labels: Sequence[str]
) -> list[dict[str, Any]]:
    """Dunn's pairwise post-hoc test following a significant Kruskal-Wallis, Bonferroni-adjusted.

    Ranks are pooled once across every group (not re-ranked per pair), so each
    pairwise comparison uses the same rank information the omnibus
    Kruskal-Wallis test itself is based on, rather than being equivalent to a
    separate two-sample Mann-Whitney U test. The tie-corrected normal
    approximation generalizes the variance term already used in
    calculate_mann_whitney_test from two groups to the full pooled sample.
    Raw two-sided p-values are Bonferroni-adjusted by the number of pairwise
    comparisons (k choose 2) to control the family-wise error rate.
    """

    if len(samples) != len(labels):
        raise ValueError(
            f"Expected one label per sample: {len(samples)} samples, {len(labels)} labels"
        )
    if len(samples) < 2:
        raise ValueError(f"Dunn's test requires at least two samples, received {len(samples)}")
    if any(not sample for sample in samples):
        raise ValueError("Dunn's test requires every sample to be non-empty")

    pooled = [
        (value, group_index)
        for group_index, sample in enumerate(samples)
        for value in sample
    ]
    pooled.sort(key=lambda pair: pair[0])
    total_n = len(pooled)
    ranks: list[float] = [0.0] * total_n
    index = 0
    while index < total_n:
        end = index
        while end + 1 < total_n and pooled[end + 1][0] == pooled[index][0]:
            end += 1
        average_rank = (index + end) / 2 + 1
        for tie_index in range(index, end + 1):
            ranks[tie_index] = average_rank
        index = end + 1

    sample_sizes = [len(sample) for sample in samples]
    rank_sums = [0.0] * len(samples)
    for rank, (_, group_index) in zip(ranks, pooled):
        rank_sums[group_index] += rank
    mean_ranks = [rank_sum / n for rank_sum, n in zip(rank_sums, sample_sizes)]

    tie_groups = Counter(value for value, _ in pooled)
    tie_correction = sum(count**3 - count for count in tie_groups.values())
    variance_term = total_n * (total_n + 1) / 12 - tie_correction / (12 * (total_n - 1))

    pair_indices = list(combinations(range(len(samples)), 2))
    comparisons = []
    for i, j in pair_indices:
        standard_error = sqrt(variance_term * (1 / sample_sizes[i] + 1 / sample_sizes[j]))
        z_statistic = (mean_ranks[i] - mean_ranks[j]) / standard_error if standard_error > 0 else 0.0
        raw_p_value = erfc(abs(z_statistic) / sqrt(2))
        adjusted_p_value = min(1.0, raw_p_value * len(pair_indices))
        comparisons.append(
            {
                "groupLabelA": labels[i],
                "groupLabelB": labels[j],
                "meanRankA": mean_ranks[i],
                "meanRankB": mean_ranks[j],
                "zStatistic": z_statistic,
                "pValueRaw": raw_p_value,
                "pValueBonferroni": adjusted_p_value,
                "significantAt05": adjusted_p_value < 0.05,
            }
        )
    return comparisons


def calculate_fisher_exact_test(
    open_count_a: int, total_a: int, open_count_b: int, total_b: int, *, label_a: str, label_b: str
) -> dict[str, Any]:
    """Two-sided Fisher's exact test on a 2x2 rate contingency table.

    The binary-outcome analog to calculate_mann_whitney_test: intended for a
    rate (e.g. open-access status) compared between two independent groups,
    rather than a continuous value. Uses scipy.stats.fisher_exact for the
    exact hypergeometric p-value.
    """

    if total_a <= 0 or total_b <= 0:
        raise ValueError("Fisher's exact test requires both groups to have at least one observation")
    if not 0 <= open_count_a <= total_a or not 0 <= open_count_b <= total_b:
        raise ValueError("Each open count must be between 0 and its group's total")

    table = [[open_count_a, total_a - open_count_a], [open_count_b, total_b - open_count_b]]
    _, p_value = fisher_exact(table)
    return {
        "method": "Fisher's exact",
        "comparisonLabel": f"{label_a} vs. {label_b}",
        "openCountA": open_count_a,
        "totalA": total_a,
        "openCountB": open_count_b,
        "totalB": total_b,
        "pValue": float(p_value),
        "significantAt05": bool(p_value < 0.05),
    }


def calculate_chi_square_test(
    open_counts: Sequence[int], totals: Sequence[int], *, labels: Sequence[str]
) -> dict[str, Any]:
    """Chi-square test of independence across two or more groups' rates.

    The categorical/binary-outcome analog to calculate_kruskal_wallis_test:
    intended for a rate compared across more than two independent groups.
    Uses scipy.stats.chi2_contingency without Yates' continuity correction,
    matching the standard test for tables with more than two rows.
    """

    if len(open_counts) != len(totals) or len(open_counts) != len(labels):
        raise ValueError("open_counts, totals, and labels must have matching lengths")
    if len(open_counts) < 2:
        raise ValueError(f"Chi-square test requires at least two groups, received {len(open_counts)}")
    if any(total <= 0 for total in totals):
        raise ValueError("Chi-square test requires every group to have at least one observation")
    if any(not 0 <= open_count <= total for open_count, total in zip(open_counts, totals)):
        raise ValueError("Each open count must be between 0 and its group's total")

    table = [[open_count, total - open_count] for open_count, total in zip(open_counts, totals)]
    statistic, p_value, degrees_of_freedom, _expected = chi2_contingency(table, correction=False)
    return {
        "method": "Chi-square test of independence",
        "groupLabels": list(labels),
        "totals": list(totals),
        "statistic": float(statistic),
        "degreesOfFreedom": int(degrees_of_freedom),
        "pValue": float(p_value),
        "significantAt05": bool(p_value < 0.05),
    }


def calculate_fisher_posthoc_test(
    open_counts: Sequence[int], totals: Sequence[int], *, labels: Sequence[str]
) -> list[dict[str, Any]]:
    """Pairwise Fisher's exact tests across every pair of groups, Bonferroni-adjusted.

    The categorical/binary-outcome analog to calculate_dunn_posthoc_test: a
    post-hoc follow-up to a significant calculate_chi_square_test result,
    identifying which specific pairs of groups' rates differ. Raw two-sided
    p-values are Bonferroni-adjusted by the number of pairwise comparisons.
    """

    if len(open_counts) != len(totals) or len(open_counts) != len(labels):
        raise ValueError("open_counts, totals, and labels must have matching lengths")
    if len(open_counts) < 2:
        raise ValueError(f"Fisher's post-hoc test requires at least two groups, received {len(open_counts)}")
    if any(total <= 0 for total in totals):
        raise ValueError("Fisher's post-hoc test requires every group to have at least one observation")
    if any(not 0 <= open_count <= total for open_count, total in zip(open_counts, totals)):
        raise ValueError("Each open count must be between 0 and its group's total")

    pair_indices = list(combinations(range(len(open_counts)), 2))
    comparisons = []
    for i, j in pair_indices:
        table = [
            [open_counts[i], totals[i] - open_counts[i]],
            [open_counts[j], totals[j] - open_counts[j]],
        ]
        _, raw_p_value = fisher_exact(table)
        raw_p_value = float(raw_p_value)
        adjusted_p_value = min(1.0, raw_p_value * len(pair_indices))
        comparisons.append(
            {
                "groupLabelA": labels[i],
                "groupLabelB": labels[j],
                "rateA": open_counts[i] / totals[i],
                "rateB": open_counts[j] / totals[j],
                "pValueRaw": raw_p_value,
                "pValueBonferroni": adjusted_p_value,
                "significantAt05": bool(adjusted_p_value < 0.05),
            }
        )
    return comparisons


def calculate_spearman_correlation(x: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    """Spearman rank correlation and significance between two equal-length samples.

    Rank-based rather than a Pearson correlation on raw values, so it is
    invariant to monotonic transforms (e.g. log-scaling a right-skewed
    variable for display does not change this) and is not distorted by
    heavy-tailed predictors like sample size or citation counts. Uses
    scipy.stats.spearmanr for the correlation and its p-value rather than
    hand-rolling a t-distribution p-value calculation.
    """

    if len(x) != len(y):
        raise ValueError(f"Samples must be the same length: {len(x)} vs {len(y)}")
    if len(x) < 2:
        raise ValueError(f"Spearman correlation requires at least two pairs, received {len(x)}")

    result = spearmanr(x, y)
    return {"n": len(x), "rho": float(result.statistic), "pValue": float(result.pvalue)}


def calculate_balanced_label_permutation_baseline(
    study_set_blocks: Sequence[Sequence[Set[str]]],
    group_count: int,
    permutation_count: int,
    rng: Random,
    observed_jaccard: float | None = None,
) -> dict[str, Any]:
    """Summarize multi-set Jaccard after balanced relabeling within blocks.

    Each response-level study set stays intact. Within every preserved-factor
    block, the sets are shuffled and divided evenly among the requested number
    of labels before the labels are aggregated across blocks.
    """

    if group_count < 2:
        raise ValueError(f"Expected at least two permutation groups, received {group_count}")
    if permutation_count < 1:
        raise ValueError(
            f"Expected at least one label permutation, received {permutation_count}"
        )
    normalized_blocks = [
        [set(studies) for studies in study_set_block]
        for study_set_block in study_set_blocks
    ]
    if not normalized_blocks:
        raise ValueError("Expected at least one permutation block")
    for block_index, study_set_block in enumerate(normalized_blocks):
        if not study_set_block or len(study_set_block) % group_count:
            raise ValueError(
                "Each permutation block must divide evenly among groups; "
                f"block {block_index} contains {len(study_set_block)} sets"
            )

    jaccard_values = []
    for _ in range(permutation_count):
        permuted_groups = [set() for _ in range(group_count)]
        for study_set_block in normalized_blocks:
            shuffled_sets = list(study_set_block)
            rng.shuffle(shuffled_sets)
            group_size = len(shuffled_sets) // group_count
            for group_index, permuted_group in enumerate(permuted_groups):
                start = group_index * group_size
                for studies in shuffled_sets[start : start + group_size]:
                    permuted_group.update(studies)
        jaccard = calculate_multi_set_jaccard(permuted_groups)["jaccard"]
        if jaccard is None:
            raise ValueError("Cannot calculate a permutation baseline from empty study sets")
        jaccard_values.append(jaccard)

    permutation_summary = _summarize_permutation_values(jaccard_values)
    result = {
        "meanJaccard": permutation_summary["mean"],
        "interval95": permutation_summary["interval95"],
    }
    if observed_jaccard is not None:
        if not 0 <= observed_jaccard <= 1:
            raise ValueError(f"Observed Jaccard must be between 0 and 1: {observed_jaccard}")
        lower_tail_p_value = (
            1 + sum(value <= observed_jaccard for value in jaccard_values)
        ) / (permutation_count + 1)
        result["lowerTailPValue"] = lower_tail_p_value
        result["significantlyBelowAt05"] = lower_tail_p_value < 0.05
    return result


def calculate_blocked_mean_range_permutation_test(
    value_blocks: Sequence[Sequence[float]],
    group_count: int,
    permutation_count: int,
    rng: Random,
) -> dict[str, Any]:
    """Test an omnibus group difference using a blocked balanced permutation.

    Values in each block must be ordered as equally sized contiguous groups.
    The observed statistic is the range between the largest and smallest group
    means. Permutations shuffle labels within each block and preserve group size.
    """

    if group_count < 2:
        raise ValueError(f"Expected at least two permutation groups, received {group_count}")
    if permutation_count < 1:
        raise ValueError(
            f"Expected at least one label permutation, received {permutation_count}"
        )
    normalized_blocks = [[float(value) for value in block] for block in value_blocks]
    if not normalized_blocks:
        raise ValueError("Expected at least one permutation block")
    for block_index, block in enumerate(normalized_blocks):
        if not block or len(block) % group_count:
            raise ValueError(
                "Each permutation block must divide evenly among groups; "
                f"block {block_index} contains {len(block)} values"
            )
        if not all(isfinite(value) for value in block):
            raise ValueError(f"Permutation block {block_index} contains a non-finite value")

    def calculate_group_means(blocks: Sequence[Sequence[float]]) -> list[float]:
        grouped_values = [[] for _ in range(group_count)]
        for block in blocks:
            group_size = len(block) // group_count
            for group_index, group_values in enumerate(grouped_values):
                start = group_index * group_size
                group_values.extend(block[start : start + group_size])
        return [fmean(group_values) for group_values in grouped_values]

    observed_means = calculate_group_means(normalized_blocks)
    observed_statistic = max(observed_means) - min(observed_means)
    null_statistics = []
    for _ in range(permutation_count):
        shuffled_blocks = []
        for block in normalized_blocks:
            shuffled_block = list(block)
            rng.shuffle(shuffled_block)
            shuffled_blocks.append(shuffled_block)
        permuted_means = calculate_group_means(shuffled_blocks)
        null_statistics.append(max(permuted_means) - min(permuted_means))

    null_summary = _summarize_permutation_values(null_statistics)
    p_value = (
        1 + sum(value >= observed_statistic for value in null_statistics)
    ) / (permutation_count + 1)
    return {
        "groupMeans": observed_means,
        "statistic": "Range of group mean recall",
        "observedStatistic": observed_statistic,
        "nullMeanStatistic": null_summary["mean"],
        "interval95": null_summary["interval95"],
        "pValue": p_value,
        "significantAt05": p_value < 0.05,
    }


def calculate_three_set_regions(
    study_sets: Sequence[Set[str]],
) -> list[dict[str, Any]]:
    """Partition exactly three study sets into the seven Venn regions."""

    if len(study_sets) != 3:
        raise ValueError(f"Expected exactly three study sets, received {len(study_sets)}")
    first, second, third = (set(studies) for studies in study_sets)
    region_definitions = (
        ("firstOnly", [0], first - second - third),
        ("secondOnly", [1], second - first - third),
        ("thirdOnly", [2], third - first - second),
        ("firstSecondOnly", [0, 1], (first & second) - third),
        ("firstThirdOnly", [0, 2], (first & third) - second),
        ("secondThirdOnly", [1, 2], (second & third) - first),
        ("allThree", [0, 1, 2], first & second & third),
    )
    return [
        {
            "regionId": region_id,
            "memberIndexes": member_indexes,
            "studyLabels": sorted(region_studies),
        }
        for region_id, member_indexes, region_studies in region_definitions
    ]


def calculate_two_set_regions(
    study_sets: Sequence[Set[str]],
) -> list[dict[str, Any]]:
    """Partition exactly two study sets into their three overlap regions."""

    if len(study_sets) != 2:
        raise ValueError(f"Expected exactly two study sets, received {len(study_sets)}")
    first, second = (set(studies) for studies in study_sets)
    region_definitions = (
        ("firstOnly", [0], first - second),
        ("secondOnly", [1], second - first),
        ("both", [0, 1], first & second),
    )
    return [
        {
            "regionId": region_id,
            "memberIndexes": member_indexes,
            "studyLabels": sorted(region_studies),
        }
        for region_id, member_indexes, region_studies in region_definitions
    ]
