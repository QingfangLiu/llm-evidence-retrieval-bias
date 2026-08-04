#!/usr/bin/env python3
"""Multiple logistic regression on recall pattern: year, sample size, citations/year, open access.

Answers whether these four characteristics have independent effects on
whether at least one chatbot recalled a study, after controlling for the
others - the pairwise comparisons and correlation matrix in
`scripts/analyze_recall_by_characteristic.py` and the demo can show that each
characteristic differs between "recalled" and "not recalled" on its own,
but not whether that holds once the others are accounted for.

Model: logit(P(recalled)) ~ year + log(sample_size) + log(citations_per_year + 0.01) + is_open_access

- Outcome is binary: recalled by at least one chatbot vs. not recalled by
  any (the same mutually exclusive split used throughout this analysis).
- Sample size and citations per year are log-transformed (citations per
  year gets a +0.01 offset since it can be exactly 0), matching the
  log-scaled treatment used throughout the charts, so a few extreme values
  do not dominate the fit. is_open_access is already binary (0/1) and needs
  no transform.
- Total citations is deliberately excluded: it correlates 0.80 with
  citations per year (see the demo's Predictor correlations section, or
  this script's own VIF check), so including both would make their
  individual coefficients unstable. Citations per year is used as the
  primary impact measure for the reasons documented in
  scripts/analyze_recall_by_characteristic.py.
- Uses `statsmodels.Logit` rather than a hand-rolled implementation -
  logistic regression's fitting and inference are easy to get subtly wrong
  by hand, and statsmodels is a standard, trusted implementation already a
  dependency of this repo.
- Standard errors are clustered by review (20 clusters): studies are nested
  within reviews, which mildly violates the independence assumption a plain
  logistic regression relies on. Clustering only changes standard errors
  and p-values, not the point estimates (coefficients/odds ratios) - see
  the printed comparison against non-clustered standard errors.
- Reports Variance Inflation Factors (VIF) as the actual multicollinearity
  diagnostic for the fitted model, since pairwise correlations (used
  earlier) only catch two-way relationships and can miss a predictor being
  predictable from a *combination* of the others.

Only included studies with year, sample size, citations per year, and
open-access status all present are used (complete-case analysis). In
practice this does not narrow the population further than the three-
predictor model used before it: citations_per_year and is_open_access come
from the same best-matched PMID (see scripts/fetch_citation_counts.py), so a
study with one has the other.

Run from the repository root:

    python3 scripts/analyze_recall_logistic_regression.py

Writes `logistic_regression_results.json` (coefficients, odds ratios, 95%
CIs, p-values, VIFs, and fit statistics) and prints a summary.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

REPO_ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_BIAS_DIR = REPO_ROOT
INPUT_PATH = RETRIEVAL_BIAS_DIR / "recall_pattern_by_characteristic.csv"
OUTPUT_PATH = RETRIEVAL_BIAS_DIR / "logistic_regression_results.json"
CITATIONS_PER_YEAR_OFFSET = 0.01
PREDICTORS = ["year", "log_sample_size", "log_citations_per_year", "is_open_access"]


def load_complete_case_frame() -> pd.DataFrame:
    """Load studies with year, sample size, citations per year, and open-access status all present."""

    with INPUT_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    complete = [
        row for row in rows
        if row["year"].strip()
        and row["sample_size"].strip()
        and row["citations_per_year"].strip()
        and row["is_open_access"].strip()
    ]
    if not complete:
        raise ValueError(
            f"No studies have year, sample size, citations per year, and open-access status all present in {INPUT_PATH}"
        )

    frame = pd.DataFrame(complete)
    frame["year"] = frame["year"].astype(float)
    frame["sample_size"] = frame["sample_size"].astype(float)
    frame["citations_per_year"] = frame["citations_per_year"].astype(float)
    frame["is_open_access"] = frame["is_open_access"].astype(float)
    frame["recalled"] = (frame["recall_pattern"] != "Not recalled").astype(int)
    frame["log_sample_size"] = frame["sample_size"].apply(math.log)
    frame["log_citations_per_year"] = (frame["citations_per_year"] + CITATIONS_PER_YEAR_OFFSET).apply(math.log)
    return frame


def fit_model(frame: pd.DataFrame, *, cluster_by_review: bool):
    """Fit the logistic regression, optionally with review-clustered standard errors."""

    design_matrix = sm.add_constant(frame[PREDICTORS])
    outcome = frame["recalled"]
    if cluster_by_review:
        return sm.Logit(outcome, design_matrix).fit(
            cov_type="cluster", cov_kwds={"groups": frame["review"]}, disp=0
        )
    return sm.Logit(outcome, design_matrix).fit(disp=0)


def compute_vif(frame: pd.DataFrame) -> dict[str, float]:
    """Variance Inflation Factor per predictor, from the model's own design matrix."""

    design_matrix = sm.add_constant(frame[PREDICTORS])
    return {
        column: variance_inflation_factor(design_matrix.values, index)
        for index, column in enumerate(design_matrix.columns)
        if column != "const"
    }


def build_result_payload(frame: pd.DataFrame, clustered_result, naive_result, vif: dict[str, float]) -> dict[str, Any]:
    """Assemble the coefficient table, odds ratios, VIFs, and fit statistics."""

    odds_ratios = np.exp(clustered_result.params)
    odds_ratio_ci = np.exp(clustered_result.conf_int())
    coefficients = {}
    for name in clustered_result.params.index:
        coefficients[name] = {
            "coefficient": float(clustered_result.params[name]),
            "clusteredStdErr": float(clustered_result.bse[name]),
            "clusteredPValue": float(clustered_result.pvalues[name]),
            "naivePValue": float(naive_result.pvalues[name]),
            "oddsRatio": float(odds_ratios[name]),
            "oddsRatioCiLow": float(odds_ratio_ci.loc[name, 0]),
            "oddsRatioCiHigh": float(odds_ratio_ci.loc[name, 1]),
        }
    return {
        "n": int(len(frame)),
        "nClusters": int(frame["review"].nunique()),
        "citationsPerYearOffset": CITATIONS_PER_YEAR_OFFSET,
        "coefficients": coefficients,
        "vif": {name: float(value) for name, value in vif.items()},
        "pseudoRSquared": float(clustered_result.prsquared),
        "logLikelihood": float(clustered_result.llf),
        "llrPValue": float(clustered_result.llr_pvalue),
    }


def print_summary(payload: dict[str, Any]) -> None:
    """Print the coefficient table, VIFs, and fit statistics."""

    print(f"n={payload['n']} studies, {payload['nClusters']} review clusters")
    print(
        f"citations_per_year log-transformed as log(citations_per_year + {payload['citationsPerYearOffset']})"
    )
    print("\nCoefficients (review-clustered standard errors):")
    print(f"  {'predictor':<24}{'coef':>9}{'clust.SE':>10}{'clust.p':>10}{'naive.p':>10}{'OR':>8}{'95% CI':>18}")
    for name, values in payload["coefficients"].items():
        # The intercept's odds ratio (odds when every predictor equals zero,
        # i.e. year 0) is not a meaningful quantity to interpret - only its
        # coefficient/p-value are shown, matching standard practice.
        is_intercept = name == "const"
        ratio_display = "—" if is_intercept else f"{values['oddsRatio']:.3f}"
        ci_display = "—" if is_intercept else f"({values['oddsRatioCiLow']:.2f}, {values['oddsRatioCiHigh']:.2f})"
        print(
            f"  {name:<24}{values['coefficient']:>9.4f}{values['clusteredStdErr']:>10.4f}"
            f"{values['clusteredPValue']:>10.4f}{values['naivePValue']:>10.4f}"
            f"{ratio_display:>8}{ci_display:>18}"
        )
    print("\nVariance Inflation Factor (values well under ~5 indicate no serious multicollinearity):")
    for name, value in payload["vif"].items():
        print(f"  {name:<24}{value:>8.3f}")
    print(
        f"\nPseudo R-squared (McFadden): {payload['pseudoRSquared']:.4f}  "
        f"Log-likelihood: {payload['logLikelihood']:.2f}  "
        f"LLR p-value (vs. null model): {payload['llrPValue']:.4g}"
    )
    print(f"\nWrote: {OUTPUT_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Fit the clustered and naive logistic regressions and report results."""

    frame = load_complete_case_frame()
    clustered_result = fit_model(frame, cluster_by_review=True)
    naive_result = fit_model(frame, cluster_by_review=False)
    vif = compute_vif(frame)
    payload = build_result_payload(frame, clustered_result, naive_result, vif)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print_summary(payload)


if __name__ == "__main__":
    main()
