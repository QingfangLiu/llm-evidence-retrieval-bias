#!/usr/bin/env python3
"""Multiple logistic regression on role dependence: year, sample size, citations/year, open access.

Companion to scripts/analyze_recall_logistic_regression.py, restricted to the
two role-universality groups build_demo.py's ROLE_UNIVERSALITY_GROUPS renders:
studies recalled by all three user roles ("Role-agnostic recall") versus
studies recalled by only some of the three retained role-recall-combination
groups - Researcher only, Clinician+Researcher, Patient+Researcher - every
one of which required a researcher-role response to surface the study
("Researcher-dependent recall"). Studies never recalled by any response, and
the three non-researcher-only patterns omitted from the combination panels
(Patient only, Clinician only, Patient+Clinician), are excluded from both
groups here, same as in the demo panels.

Model: logit(P(researcher-dependent recall)) ~ year + log(sample_size) +
log(citations_per_year + 0.01) + is_open_access

Answers whether these four characteristics independently predict needing a
researcher-role response to surface a study, once the others are controlled
for - the two-group box plots and Fisher's exact test in
scripts/analyze_recall_by_characteristic.py and the demo can show that each
characteristic differs between the two groups on its own, but not whether that
holds once the others are accounted for.
Outcome is coded 1 for "Researcher-dependent recall" so a positive
coefficient means higher values of that predictor make researcher-dependence
more likely - directly answering "what does claiming to be a researcher
additionally unlock." See scripts/analyze_recall_logistic_regression.py's
docstring for the log-transform, clustering, and VIF rationale, all reused
unchanged here.

Run from the repository root:

    python3 scripts/analyze_role_dependence_logistic_regression.py

Writes `role_dependence_logistic_regression_results.json` (coefficients, odds
ratios, 95% CIs, p-values, VIFs, and fit statistics) and prints a summary.
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
OUTPUT_PATH = RETRIEVAL_BIAS_DIR / "role_dependence_logistic_regression_results.json"
CITATIONS_PER_YEAR_OFFSET = 0.01
PREDICTORS = ["year", "log_sample_size", "log_citations_per_year", "is_open_access"]
ROLE_AGNOSTIC_PATTERN = "All three"
RESEARCHER_DEPENDENT_PATTERNS = {"Researcher only", "Clinician+Researcher", "Patient+Researcher"}


def load_complete_case_frame() -> pd.DataFrame:
    """Load role-agnostic/researcher-dependent studies with all four predictors present."""

    with INPUT_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    complete = [
        row for row in rows
        if row["role_recall_pattern"] in RESEARCHER_DEPENDENT_PATTERNS | {ROLE_AGNOSTIC_PATTERN}
        and row["year"].strip()
        and row["sample_size"].strip()
        and row["citations_per_year"].strip()
        and row["is_open_access"].strip()
    ]
    if not complete:
        raise ValueError(
            f"No role-agnostic/researcher-dependent studies have year, sample size, citations "
            f"per year, and open-access status all present in {INPUT_PATH}"
        )

    frame = pd.DataFrame(complete)
    frame["year"] = frame["year"].astype(float)
    frame["sample_size"] = frame["sample_size"].astype(float)
    frame["citations_per_year"] = frame["citations_per_year"].astype(float)
    frame["is_open_access"] = frame["is_open_access"].astype(float)
    frame["researcher_dependent"] = (frame["role_recall_pattern"] != ROLE_AGNOSTIC_PATTERN).astype(int)
    frame["log_sample_size"] = frame["sample_size"].apply(math.log)
    frame["log_citations_per_year"] = (frame["citations_per_year"] + CITATIONS_PER_YEAR_OFFSET).apply(math.log)
    return frame


def fit_model(frame: pd.DataFrame, *, cluster_by_review: bool):
    """Fit the logistic regression, optionally with review-clustered standard errors."""

    design_matrix = sm.add_constant(frame[PREDICTORS])
    outcome = frame["researcher_dependent"]
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
