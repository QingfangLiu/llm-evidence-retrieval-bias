#!/usr/bin/env python3
"""Cross-tabulate chatbot and user-role recall patterns against study characteristics.

For each of the 20 balanced user-role experiments, this groups every
Cochrane-included study two ways: by which chatbots (Claude, Gemini, GPT)
retrieved it at least once across all 12 responses (four replicates times
three roles), and separately by which user roles (patient, clinician,
researcher) retrieved it at least once across all 12 responses (four
replicates times three chatbots). Both recall patterns are joined against
six study characteristics:

- publication year, read directly from each review's included RIS export;
- sample size, read from each review's own analysis data
  (`<REVIEW>-analysis-data/<REVIEW>-data-rows.csv`), the same per-study rows
  that produce the review's forest plots. For each study this takes the
  largest (Experimental N + Control N) seen across all of its analysis rows.
  That is Cochrane's own analyzed sample size, not a re-derived estimate, but
  it can run a little below a study's originally enrolled/randomized total
  when an outcome had missing data for some participants - the maximum
  across a study's rows is used as the closest available proxy for its
  total. A live PubMed abstract fetch (tried first, see git history) reached
  only ~15-20% coverage with meaningfully more uncertainty per value; this
  local source covers ~88% of included studies with no network dependency,
  so it replaced the PubMed approach entirely;
- citations per year, read from `citation_counts_by_study.csv` (written by
  `fetch_citation_counts.py`). That script resolves each study's PMIDs via
  the repository's existing Cochrane RIS reference-resolution pipeline
  (explicit PMID, DOI search, then a validated citation search - see its
  module docstring), fetches citation counts from the Semantic Scholar Graph
  API, and divides by years-since-publication so studies aren't penalized
  just for being newer and having had less time to accumulate citations.
  Citations per year is a proxy for scholarly impact, not for how likely a
  study is to appear in LLM training data specifically - a caveat worth
  keeping in mind when interpreting results;
- total citations (raw `citation_count`, same source as citations per year).
  Reported alongside citations per year rather than instead of it: a raw
  count is confounded with a study's age (older studies have simply had more
  time to accumulate citations), so citations per year is the primary impact
  measure and total citations is a secondary, unnormalized view of the same
  underlying data;
- open-access status (`is_open_access`, same source and same best-matched
  PMID as citation_count/citations_per_year). A binary characteristic rather
  than a continuous one, so it is reported as a rate with a Fisher's exact
  test instead of the mean/median/Mann-Whitney treatment the four numeric
  characteristics get. Tests whether a study being freely accessible (rather
  than paywalled) predicts chatbot recall independent of its citation impact
  - plausible if open-access full text is more likely to appear in whatever
  corpus or web search a chatbot draws on than an abstract-only paywalled
  record;
- design, read from the curated match tables' `design` field. This is only
  defined for studies that at least one response actually named, since a
  design label is assigned when a candidate citation is curated. It cannot
  describe the "not recalled" bucket and is reported only among recalled
  studies.

Year, sample size, citations per year, total citations, and open-access
status are all properties of the review's own data or of the study's
publication record, available regardless of whether any chatbot ever named
the study, so all five can be compared across the full recall-pattern
spectrum including "not recalled." Design cannot.
"""

from __future__ import annotations

import csv
import io
import math
import re
import statistics as stats
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import fisher_exact

from review_registry import review_sources

REPO_ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_BIAS_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = RETRIEVAL_BIAS_DIR / "recall_pattern_by_characteristic.csv"
MODELS = ("claude", "gemini", "gpt")
MODEL_LABELS = {"claude": "Claude", "gemini": "Gemini", "gpt": "GPT"}
ROLES = ("patient", "clinician", "researcher")
ROLE_LABELS = {"patient": "Patient", "clinician": "Clinician", "researcher": "Researcher"}

def load_max_sample_size_by_label(text: str) -> dict[str, int]:
    """Map each study to its largest (Experimental N + Control N) analysis row.

    Cochrane's analysis-data rows report the number analyzed per outcome, per
    study, which is what feeds the review's forest plots. A study can have a
    lower analyzed N on some outcomes than others (missing data), so the
    maximum across all of a study's rows is the closest available proxy for
    its total analyzed sample size. Studies the review never pooled into a
    quantitative analysis (narrative-only inclusion) are absent here.
    """

    totals: dict[str, int] = {}
    for row in csv.DictReader(io.StringIO(text)):
        label = row["Study"].strip()
        if not label:
            continue
        parts = [
            int(value)
            for value in (row["Experimental N"].strip(), row["Control N"].strip())
            if value
        ]
        if not parts:
            continue
        total = sum(parts)
        if total > totals.get(label, 0):
            totals[label] = total
    return totals


def load_citation_metrics() -> tuple[
    dict[tuple[str, str], float], dict[tuple[str, str], int], dict[tuple[str, str], bool]
]:
    """Map (review, study_label) to citations/year, raw citation_count, and open-access status.

    All three come from fetch_citation_counts.py's output. citations_per_year
    is the primary impact measure (see its module docstring for why: it
    controls for a study's age, unlike a raw count); citation_count is kept
    alongside it so both the age-normalized and raw pictures are visible,
    per the user's request rather than only reporting one. is_open_access is
    Semantic Scholar's flag for the same best-matched PMID citation_count
    already uses.
    """

    path = RETRIEVAL_BIAS_DIR / "citation_counts_by_study.csv"
    citations_per_year: dict[tuple[str, str], float] = {}
    citation_count: dict[tuple[str, str], int] = {}
    is_open_access: dict[tuple[str, str], bool] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (row["review"], row["study_label"])
            per_year_value = row["citations_per_year"].strip()
            if per_year_value:
                citations_per_year[key] = float(per_year_value)
            count_value = row["citation_count"].strip()
            if count_value:
                citation_count[key] = int(count_value)
            open_access_value = row["is_open_access"].strip()
            if open_access_value:
                is_open_access[key] = bool(int(open_access_value))
    return citations_per_year, citation_count, is_open_access


def load_ris_year_by_label(text: str) -> dict[str, int | None]:
    """Map each Cochrane study label to its first record's publication year."""

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


def coarse_design(design: str) -> str:
    """Collapse a free-text design string into a small set of categories."""

    lowered = design.lower()
    if not lowered:
        return "(no curated design; study was never named by a response)"
    if "cluster" in lowered:
        return "cluster-randomized"
    if "crossover" in lowered or "cross-over" in lowered:
        return "crossover RCT"
    if "cohort" in lowered:
        return "cohort (non-randomized)"
    if "registry" in lowered:
        return "registry"
    if "randomi" in lowered or "rct" in lowered:
        return "parallel-group RCT (or unspecified RCT)"
    return f"other / {design}"


def classify_recall_pattern(models: set[str]) -> str:
    """Label which chatbot(s) recalled a study, from its recalling model set."""

    if not models:
        return "Not recalled"
    if len(models) == 3:
        return "All three"
    if len(models) == 1:
        return f"{MODEL_LABELS[next(iter(models))]} only"
    missing = next(iter(set(MODELS) - models))
    return "+".join(MODEL_LABELS[m] for m in MODELS if m != missing)


def classify_role_recall_pattern(roles: set[str]) -> str:
    """Label which user role(s) recalled a study, from its recalling role set."""

    if not roles:
        return "Not recalled"
    if len(roles) == 3:
        return "All three"
    if len(roles) == 1:
        return f"{ROLE_LABELS[next(iter(roles))]} only"
    missing = next(iter(set(ROLES) - roles))
    return "+".join(ROLE_LABELS[r] for r in ROLES if r != missing)


def build_rows() -> list[dict[str, object]]:
    """Join recall pattern, year, sample size, citation metrics, open-access status, and design for every included study."""

    rows: list[dict[str, object]] = []
    citations_per_year_by_key, citation_count_by_key, is_open_access_by_key = load_citation_metrics()
    for source in review_sources():
        review = source.review_id
        year_by_label = load_ris_year_by_label(
            source.read_source_text("included_ris")
        )
        sample_size_by_label = load_max_sample_size_by_label(
            source.read_source_text("analysis_rows")
        )
        with source.matches_path.open(newline="", encoding="utf-8") as handle:
            matches = list(csv.DictReader(handle))
        included_rows = [row for row in matches if row["ground_truth_status"] == "included"]

        recalled_by: dict[str, set[str]] = defaultdict(set)
        recalled_by_role: dict[str, set[str]] = defaultdict(set)
        design_by_label: dict[str, str] = {}
        design_conflicts: dict[str, set[str]] = defaultdict(set)
        for row in included_rows:
            labels = [label.strip() for label in row["cochrane_study_label"].split("||") if label.strip()]
            design = row["design"].strip()
            for label in labels:
                recalled_by[label].add(row["model"])
                recalled_by_role[label].add(row["role_id"])
                design_conflicts[label].add(design)
                design_by_label[label] = design

        conflicting = {label: values for label, values in design_conflicts.items() if len(values) > 1}
        if conflicting:
            raise ValueError(f"{review}: inconsistent design values per study: {conflicting}")

        for label, year in year_by_label.items():
            models = recalled_by.get(label, set())
            roles = recalled_by_role.get(label, set())
            rows.append(
                {
                    "review": review,
                    "study_label": label,
                    "year": year,
                    "sample_size": sample_size_by_label.get(label),
                    "citations_per_year": citations_per_year_by_key.get((review, label)),
                    "citation_count": citation_count_by_key.get((review, label)),
                    "is_open_access": (
                        int(is_open_access_by_key[(review, label)])
                        if (review, label) in is_open_access_by_key
                        else None
                    ),
                    "recalled_by_claude": int("claude" in models),
                    "recalled_by_gemini": int("gemini" in models),
                    "recalled_by_gpt": int("gpt" in models),
                    "recall_pattern": classify_recall_pattern(models),
                    "recalled_by_patient": int("patient" in roles),
                    "recalled_by_clinician": int("clinician" in roles),
                    "recalled_by_researcher": int("researcher" in roles),
                    "role_recall_pattern": classify_role_recall_pattern(roles),
                    "design_raw": design_by_label.get(label, ""),
                    "design_category": coarse_design(design_by_label.get(label, "")),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write a non-empty recall/characteristic table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def mann_whitney_u_p_value(sample_a: list[float], sample_b: list[float]) -> float:
    """Two-sided normal-approximation Mann-Whitney U p-value (no scipy dependency)."""

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
    u = min(u_a, n_a * n_b - u_a)
    mean_u = n_a * n_b / 2
    tie_groups = Counter(value for value, _ in combined)
    tie_correction = sum(count**3 - count for count in tie_groups.values())
    n_total = n_a + n_b
    variance = (n_a * n_b / 12) * ((n_total + 1) - tie_correction / (n_total * (n_total - 1)))
    if variance <= 0:
        return 1.0
    z = (u - mean_u) / math.sqrt(variance)
    return math.erfc(abs(z) / math.sqrt(2))


def print_numeric_field_by_pattern(
    rows: list[dict[str, object]],
    by_pattern: dict[str, list[dict[str, object]]],
    pattern_order: list[str],
    field: str,
    field_label: str,
    precision: int = 0,
) -> None:
    """Print per-pattern mean/median/n for a numeric field, plus a two-group test.

    The two-group test compares "Not recalled" against every recalled
    pattern pooled together, since most individual patterns are too small
    (some have n=1) to test on their own.
    """

    print(f"\n{field_label} by recall pattern (mean / median / n with a known value):")
    for pattern in pattern_order:
        values = [row[field] for row in by_pattern[pattern] if row[field] is not None]
        if values:
            print(
                f"  {pattern:<16} mean={stats.mean(values):.{precision}f}  "
                f"median={stats.median(values):.{precision}f}  n={len(values)}"
            )

    recalled = [row[field] for row in rows if row["recall_pattern"] != "Not recalled" and row[field] is not None]
    not_recalled = [row[field] for row in rows if row["recall_pattern"] == "Not recalled" and row[field] is not None]
    if recalled and not_recalled:
        p_value = mann_whitney_u_p_value(not_recalled, recalled)
        print(
            f"Mann-Whitney U, not-recalled vs. recalled-by-at-least-one {field_label.lower()}: "
            f"p={p_value:.4g}"
        )


def print_open_access_by_recall_status(rows: list[dict[str, object]]) -> None:
    """Print open-access rates and a Fisher's exact test for recalled vs. not recalled.

    is_open_access is binary (unlike year/sample_size/citations), so this
    reports counts and a rate per recall-status group with a 2x2 Fisher's
    exact test on the contingency table, rather than reusing
    print_numeric_field_by_pattern's mean/median/Mann-Whitney treatment.
    """

    recalled = [
        row["is_open_access"] for row in rows
        if row["recall_pattern"] != "Not recalled" and row["is_open_access"] is not None
    ]
    not_recalled = [
        row["is_open_access"] for row in rows
        if row["recall_pattern"] == "Not recalled" and row["is_open_access"] is not None
    ]
    print("\nOpen-access status by recall status (known status only):")
    for label, values in (("Not recalled", not_recalled), ("Recalled", recalled)):
        if values:
            open_count = sum(values)
            print(f"  {label:<16} open access {open_count}/{len(values)} ({100 * open_count / len(values):.0f}%)")
        else:
            print(f"  {label:<16} n=0")
    if recalled and not_recalled:
        contingency_table = [
            [sum(not_recalled), len(not_recalled) - sum(not_recalled)],
            [sum(recalled), len(recalled) - sum(recalled)],
        ]
        _, p_value = fisher_exact(contingency_table)
        print(
            "Fisher's exact test, not-recalled vs. recalled-by-at-least-one open-access rate: "
            f"p={p_value:.4g}"
        )


def print_role_recall_pattern_counts(rows: list[dict[str, object]]) -> None:
    """Print role-recall-pattern counts (which role(s) recalled each study).

    "Not recalled" is identical to the chatbot recall_pattern's "Not
    recalled" group (recall doesn't depend on which dimension groups it), so
    that group's mean/median/test output isn't reprinted here - only the
    combination counts, which build_demo.py's role-based combination panels
    read directly.
    """

    role_pattern_order = [
        "Not recalled", "Patient only", "Clinician only", "Researcher only",
        "Patient+Clinician", "Patient+Researcher", "Clinician+Researcher", "All three",
    ]
    by_role_pattern: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_role_pattern[str(row["role_recall_pattern"])].append(row)

    print("\nRole-recall-pattern counts:")
    for pattern in role_pattern_order:
        print(f"  {pattern:<20} {len(by_role_pattern[pattern])}")


def print_summary(rows: list[dict[str, object]]) -> None:
    """Print recall-pattern counts, per-pattern year/sample-size stats, and design cross-tab."""

    pattern_order = [
        "Not recalled", "Claude only", "Gemini only", "GPT only",
        "Claude+Gemini", "Claude+GPT", "Gemini+GPT", "All three",
    ]
    by_pattern: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_pattern[str(row["recall_pattern"])].append(row)

    print(f"Included studies: {len(rows)}")
    print("\nRecall-pattern counts:")
    for pattern in pattern_order:
        print(f"  {pattern:<16} {len(by_pattern[pattern])}")

    print_numeric_field_by_pattern(rows, by_pattern, pattern_order, "year", "Publication year")
    print_numeric_field_by_pattern(rows, by_pattern, pattern_order, "sample_size", "Sample size")
    print_numeric_field_by_pattern(
        rows, by_pattern, pattern_order, "citations_per_year", "Citations per year", precision=2
    )
    print_numeric_field_by_pattern(rows, by_pattern, pattern_order, "citation_count", "Total citations")
    print_open_access_by_recall_status(rows)
    print_role_recall_pattern_counts(rows)

    print(
        "\nDesign category among recalled studies only (design is undefined for "
        "studies no response ever named, so 'Not recalled' is excluded here):"
    )
    design_totals: Counter[str] = Counter()
    design_cross: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if row["recall_pattern"] == "Not recalled":
            continue
        category = str(row["design_category"])
        design_totals[category] += 1
        design_cross[str(row["recall_pattern"])][category] += 1
    for category, total in design_totals.most_common():
        print(f"  {total:4d}  {category}")
    print()
    designs_order = [category for category, _ in design_totals.most_common()]
    header = "Pattern".ljust(16) + "".join(category[:22].ljust(24) for category in designs_order)
    print(header)
    for pattern in pattern_order:
        if pattern == "Not recalled":
            continue
        line = pattern.ljust(16)
        for category in designs_order:
            n = design_cross[pattern][category]
            total = design_totals[category]
            pct = 100 * n / total if total else 0
            line += f"{n}/{total} ({pct:.0f}%)".ljust(24)
        print(line)

    for pattern in ("Not recalled", "Claude only", "Gemini only", "GPT only"):
        labels = sorted(
            f"{row['review']} · {row['study_label']} ({row['year']})"
            for row in by_pattern[pattern]
        )
        print(f"\n{pattern} ({len(labels)}):")
        for label in labels:
            print(f"  {label}")

    print(f"\nWrote: {OUTPUT_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the recall-pattern/characteristic join and print the summary."""

    rows = build_rows()
    write_csv(OUTPUT_PATH, rows)
    print_summary(rows)


if __name__ == "__main__":
    main()
