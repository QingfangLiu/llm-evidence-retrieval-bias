"""Tests for retrieval-bias overlap and blocked-permutation metrics."""

from random import Random
from unittest import TestCase

from overlap_metrics import (
    calculate_balanced_label_permutation_baseline,
    calculate_blocked_mean_range_permutation_test,
    calculate_chi_square_test,
    calculate_dunn_posthoc_test,
    calculate_fisher_exact_test,
    calculate_fisher_posthoc_test,
    calculate_kruskal_wallis_test,
    calculate_mann_whitney_test,
    calculate_replicate_consistency,
    calculate_spearman_correlation,
)


class SpearmanCorrelationTests(TestCase):
    """Validate the rank-based correlation helper."""

    def test_perfectly_monotonic_samples_have_rho_one(self) -> None:
        result = calculate_spearman_correlation([1, 2, 3, 4, 5], [10, 20, 30, 40, 50])

        self.assertAlmostEqual(result["rho"], 1.0, places=6)
        self.assertEqual(result["n"], 5)
        self.assertLess(result["pValue"], 0.05)

    def test_is_invariant_to_monotonic_transforms(self) -> None:
        import math

        x = [1, 2, 3, 4, 5]
        y = [2, 8, 3, 40, 15]

        raw = calculate_spearman_correlation(x, y)
        log_y = [math.log(value) for value in y]  # a monotonic transform of y
        transformed = calculate_spearman_correlation(x, log_y)

        # log() preserves y's rank order, so both rho and its p-value should
        # match exactly regardless of the monotonic transform applied to y.
        self.assertAlmostEqual(raw["rho"], transformed["rho"], places=6)
        self.assertAlmostEqual(raw["pValue"], transformed["pValue"], places=6)

    def test_unrelated_samples_are_not_significant(self) -> None:
        # An order that is its own reverse-then-shuffle has near-zero rank
        # correlation with a plain ascending sequence.
        result = calculate_spearman_correlation([1, 2, 3, 4, 5, 6], [3, 1, 6, 2, 5, 4])

        self.assertGreater(result["pValue"], 0.05)

    def test_inversely_related_samples_have_rho_negative_one(self) -> None:
        result = calculate_spearman_correlation([1, 2, 3, 4], [4, 3, 2, 1])

        self.assertAlmostEqual(result["rho"], -1.0, places=6)

    def test_rejects_mismatched_lengths(self) -> None:
        with self.assertRaisesRegex(ValueError, "same length"):
            calculate_spearman_correlation([1, 2, 3], [1, 2])


class MannWhitneyTests(TestCase):
    """Validate the two-sample Mann-Whitney U helper."""

    def test_identical_samples_are_not_significant(self) -> None:
        result = calculate_mann_whitney_test(
            [1, 2, 3, 4], [1, 2, 3, 4], label_a="A", label_b="B"
        )

        self.assertAlmostEqual(result["pValue"], 1.0, places=6)
        self.assertFalse(result["significantAt05"])
        self.assertEqual(result["sampleSizeA"], 4)
        self.assertEqual(result["sampleSizeB"], 4)

    def test_clearly_separated_samples_are_significant(self) -> None:
        result = calculate_mann_whitney_test(
            [1, 2, 3, 4, 5], [101, 102, 103, 104, 105], label_a="Low", label_b="High"
        )

        self.assertLess(result["pValue"], 0.01)
        self.assertTrue(result["significantAt05"])
        self.assertEqual(result["comparisonLabel"], "Low vs. High")

    def test_rejects_an_empty_sample(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            calculate_mann_whitney_test([], [1, 2], label_a="A", label_b="B")


class KruskalWallisTests(TestCase):
    """Validate the multi-sample Kruskal-Wallis helper."""

    def test_identical_samples_are_not_significant(self) -> None:
        result = calculate_kruskal_wallis_test(
            [[1, 2, 3], [1, 2, 3], [1, 2, 3]], labels=["A", "B", "C"]
        )

        self.assertGreater(result["pValue"], 0.05)
        self.assertFalse(result["significantAt05"])
        self.assertEqual(result["sampleSizes"], [3, 3, 3])

    def test_clearly_separated_samples_are_significant(self) -> None:
        result = calculate_kruskal_wallis_test(
            [[1, 2, 3, 4], [51, 52, 53, 54], [101, 102, 103, 104]],
            labels=["Low", "Mid", "High"],
        )

        self.assertLess(result["pValue"], 0.01)
        self.assertTrue(result["significantAt05"])
        self.assertEqual(result["groupLabels"], ["Low", "Mid", "High"])

    def test_rejects_fewer_than_two_samples(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two samples"):
            calculate_kruskal_wallis_test([[1, 2, 3]], labels=["A"])

    def test_rejects_an_empty_sample(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            calculate_kruskal_wallis_test([[1, 2], []], labels=["A", "B"])

    def test_rejects_mismatched_label_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "one label per sample"):
            calculate_kruskal_wallis_test([[1, 2], [3, 4]], labels=["A"])


class DunnPosthocTests(TestCase):
    """Validate the Bonferroni-adjusted pairwise post-hoc helper."""

    def test_identical_samples_have_no_significant_pairs(self) -> None:
        comparisons = calculate_dunn_posthoc_test(
            [[1, 2, 3], [1, 2, 3], [1, 2, 3]], labels=["A", "B", "C"]
        )

        self.assertEqual(len(comparisons), 3)
        self.assertTrue(all(not c["significantAt05"] for c in comparisons))
        self.assertTrue(all(c["pValueBonferroni"] >= c["pValueRaw"] for c in comparisons))

    def test_clearly_separated_groups_have_all_pairs_significant(self) -> None:
        # Larger per-group samples than the omnibus Kruskal-Wallis test uses:
        # a pairwise post-hoc test is inherently less powerful once its raw
        # p-value is Bonferroni-adjusted, so small adjacent-group differences
        # need more data to clear that stricter bar.
        comparisons = calculate_dunn_posthoc_test(
            [list(range(1, 21)), list(range(101, 121)), list(range(201, 221))],
            labels=["Low", "Mid", "High"],
        )

        self.assertEqual(len(comparisons), 3)
        self.assertTrue(all(c["significantAt05"] for c in comparisons))
        low_vs_high = next(
            c for c in comparisons if {c["groupLabelA"], c["groupLabelB"]} == {"Low", "High"}
        )
        self.assertLess(low_vs_high["meanRankA"], low_vs_high["meanRankB"])

    def test_bonferroni_p_never_exceeds_one(self) -> None:
        comparisons = calculate_dunn_posthoc_test(
            [[1, 2], [1, 2], [1, 2], [1, 2], [1, 2]], labels=["A", "B", "C", "D", "E"]
        )

        self.assertEqual(len(comparisons), 10)
        self.assertTrue(all(c["pValueBonferroni"] <= 1.0 for c in comparisons))

    def test_rejects_fewer_than_two_samples(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two samples"):
            calculate_dunn_posthoc_test([[1, 2, 3]], labels=["A"])

    def test_rejects_an_empty_sample(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            calculate_dunn_posthoc_test([[1, 2], []], labels=["A", "B"])

    def test_rejects_mismatched_label_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "one label per sample"):
            calculate_dunn_posthoc_test([[1, 2], [3, 4]], labels=["A"])


class FisherExactTests(TestCase):
    """Validate the two-sample binary-rate Fisher's exact helper."""

    def test_identical_rates_are_not_significant(self) -> None:
        result = calculate_fisher_exact_test(5, 10, 5, 10, label_a="A", label_b="B")

        self.assertAlmostEqual(result["pValue"], 1.0, places=6)
        self.assertFalse(result["significantAt05"])
        self.assertEqual(result["comparisonLabel"], "A vs. B")

    def test_clearly_separated_rates_are_significant(self) -> None:
        result = calculate_fisher_exact_test(19, 20, 1, 20, label_a="High", label_b="Low")

        self.assertLess(result["pValue"], 0.001)
        self.assertTrue(result["significantAt05"])

    def test_rejects_an_empty_group(self) -> None:
        with self.assertRaisesRegex(ValueError, "both groups"):
            calculate_fisher_exact_test(0, 0, 1, 2, label_a="A", label_b="B")

    def test_rejects_an_out_of_range_open_count(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and its group's total"):
            calculate_fisher_exact_test(5, 3, 1, 2, label_a="A", label_b="B")


class ChiSquareTests(TestCase):
    """Validate the multi-group rate chi-square helper."""

    def test_identical_rates_are_not_significant(self) -> None:
        result = calculate_chi_square_test([5, 5, 5], [10, 10, 10], labels=["A", "B", "C"])

        self.assertGreater(result["pValue"], 0.05)
        self.assertFalse(result["significantAt05"])
        self.assertEqual(result["totals"], [10, 10, 10])

    def test_clearly_separated_rates_are_significant(self) -> None:
        result = calculate_chi_square_test([1, 10, 19], [20, 20, 20], labels=["Low", "Mid", "High"])

        self.assertLess(result["pValue"], 0.001)
        self.assertTrue(result["significantAt05"])

    def test_rejects_fewer_than_two_groups(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two groups"):
            calculate_chi_square_test([5], [10], labels=["A"])

    def test_rejects_mismatched_lengths(self) -> None:
        with self.assertRaisesRegex(ValueError, "matching lengths"):
            calculate_chi_square_test([5, 5], [10], labels=["A", "B"])


class FisherPosthocTests(TestCase):
    """Validate the Bonferroni-adjusted pairwise binary-rate post-hoc helper."""

    def test_identical_rates_have_no_significant_pairs(self) -> None:
        comparisons = calculate_fisher_posthoc_test([5, 5, 5], [10, 10, 10], labels=["A", "B", "C"])

        self.assertEqual(len(comparisons), 3)
        self.assertTrue(all(not c["significantAt05"] for c in comparisons))
        self.assertTrue(all(c["pValueBonferroni"] >= c["pValueRaw"] for c in comparisons))

    def test_clearly_separated_groups_have_extreme_pair_significant(self) -> None:
        comparisons = calculate_fisher_posthoc_test([1, 10, 19], [20, 20, 20], labels=["Low", "Mid", "High"])

        self.assertEqual(len(comparisons), 3)
        low_vs_high = next(
            c for c in comparisons if {c["groupLabelA"], c["groupLabelB"]} == {"Low", "High"}
        )
        self.assertTrue(low_vs_high["significantAt05"])

    def test_rejects_fewer_than_two_groups(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two groups"):
            calculate_fisher_posthoc_test([5], [10], labels=["A"])

    def test_rejects_mismatched_lengths(self) -> None:
        with self.assertRaisesRegex(ValueError, "matching lengths"):
            calculate_fisher_posthoc_test([5, 5], [10], labels=["A", "B"])


class ReplicateConsistencyTests(TestCase):
    """Validate the within-cell replicate Jaccard consistency helper."""

    def test_identical_replicates_are_fully_consistent(self) -> None:
        result = calculate_replicate_consistency([{"a", "b"}, {"a", "b"}, {"a", "b"}])

        self.assertEqual(result["pairCount"], 3)
        self.assertEqual(result["meanJaccard"], 1.0)
        self.assertEqual(result["stdevJaccard"], 0.0)

    def test_disjoint_replicates_are_fully_inconsistent(self) -> None:
        result = calculate_replicate_consistency([{"a"}, {"b"}])

        self.assertEqual(result["pairCount"], 1)
        self.assertEqual(result["meanJaccard"], 0.0)

    def test_two_empty_replicates_count_as_fully_consistent(self) -> None:
        result = calculate_replicate_consistency([set(), set()])

        self.assertEqual(result["meanJaccard"], 1.0)

    def test_rejects_fewer_than_two_replicates(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least two replicate sets"):
            calculate_replicate_consistency([{"a"}])


class OverlapPermutationTests(TestCase):
    """Validate deterministic permutation summaries and tail directions."""

    def test_jaccard_lower_tail_is_one_when_every_permutation_is_identical(self) -> None:
        result = calculate_balanced_label_permutation_baseline(
            [[{"a"}, {"a"}, {"a"}, {"a"}, {"a"}, {"a"}]],
            group_count=3,
            permutation_count=100,
            rng=Random(7),
            observed_jaccard=1.0,
        )

        self.assertEqual(result["meanJaccard"], 1.0)
        self.assertEqual(result["lowerTailPValue"], 1.0)
        self.assertFalse(result["significantlyBelowAt05"])

    def test_blocked_mean_range_uses_the_observed_group_order(self) -> None:
        result = calculate_blocked_mean_range_permutation_test(
            [
                [1, 1, 0, 0, 0, 0],
                [1, 1, 0, 0, 0, 0],
            ],
            group_count=3,
            permutation_count=500,
            rng=Random(11),
        )

        self.assertEqual(result["groupMeans"], [1.0, 0.0, 0.0])
        self.assertEqual(result["observedStatistic"], 1.0)
        self.assertGreater(result["pValue"], 0)
        self.assertLessEqual(result["pValue"], 1)

    def test_blocked_mean_range_rejects_unbalanced_blocks(self) -> None:
        with self.assertRaisesRegex(ValueError, "divide evenly"):
            calculate_blocked_mean_range_permutation_test(
                [[0.1, 0.2, 0.3, 0.4]],
                group_count=3,
                permutation_count=10,
                rng=Random(3),
            )
