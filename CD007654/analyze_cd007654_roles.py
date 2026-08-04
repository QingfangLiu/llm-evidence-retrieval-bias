#!/usr/bin/env python3
"""Analyze CD007654 using only each response's terminal study list.

The extractor implements the review-specific boundary documented in README.md.
It preserves every terminal-list citation, resolves citations to study clusters,
deduplicates companion reports within a response, validates Cochrane labels
against the RIS exports, and writes the review's audit table.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_DIR = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_6"
    / "CD007654-SUP-06-dataPackage"
    / "CD007654-study-data"
)
MATCHES_PATH = REVIEW_DIR / "cd007654_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 137, "gemini": 43, "gpt": 200}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical identity and CD007654 ground-truth status of one candidate."""

    label: str
    status: str
    cochrane_label: str = ""
    design: str = ""
    note: str = ""


CANDIDATES = {
    # Cochrane-included study clusters. Companion reports share one key.
    "bakris": CandidateInfo(
        "Bakris 2002", "included", "Bakris 2002", "randomized controlled trial"
    ),
    "cocco": CandidateInfo(
        "Cocco 2005", "included", "Cocco 2005", "randomized controlled trial"
    ),
    "conquer": CandidateInfo(
        "CONQUER", "included", "CONQUER 2013", "randomized controlled trial"
    ),
    "guy_grand": CandidateInfo(
        "Guy-Grand 2004",
        "included",
        "Guy-Grand 2004",
        "randomized controlled trial",
    ),
    "light": CandidateInfo(
        "LIGHT", "included", "Nissen 2016", "randomized cardiovascular-outcome trial"
    ),
    "step1": CandidateInfo(
        "STEP 1", "included", "STEP 1 2023", "randomized controlled trial"
    ),
    "surmount1": CandidateInfo(
        "SURMOUNT-1",
        "included",
        "SURMOUNT-1 2024",
        "randomized controlled trial",
    ),
    "xendos": CandidateInfo(
        "XENDOS", "included", "XENDOS 2001-2006", "randomized controlled trial"
    ),
    # Study clusters explicitly excluded by the Cochrane package.
    "broom": CandidateInfo(
        "UK Multimorbidity Study",
        "cochrane_excluded",
        "Broom 2002",
        "randomized controlled trial",
    ),
    "camellia": CandidateInfo(
        "CAMELLIA-TIMI 61",
        "cochrane_excluded",
        "CAMELLIA-TIMI 2018",
        "randomized cardiovascular-outcome trial",
    ),
    "cor_i": CandidateInfo(
        "COR-I", "cochrane_excluded", "COR-I 2010", "randomized controlled trial"
    ),
    "cor_ii": CandidateInfo(
        "COR-II", "cochrane_excluded", "COR-II 2013", "randomized controlled trial"
    ),
    "equip": CandidateInfo(
        "EQUIP", "cochrane_excluded", "EQUIP 2012", "randomized controlled trial"
    ),
    "faria": CandidateInfo(
        "Faria 2002", "cochrane_excluded", "Faria 2002", "clinical trial"
    ),
    "mcmahon_2000": CandidateInfo(
        "McMahon 2000",
        "cochrane_excluded",
        "McMahon 2000",
        "randomized controlled trial",
    ),
    "mcmahon_2002": CandidateInfo(
        "McMahon 2002",
        "cochrane_excluded",
        "McMahon 2002",
        "randomized controlled trial",
    ),
    "scale_obesity": CandidateInfo(
        "SCALE Obesity and Prediabetes",
        "cochrane_excluded",
        "SCALE obesity and prediabetes 2014",
        "randomized controlled trial",
    ),
    "scout": CandidateInfo(
        "SCOUT",
        "cochrane_excluded",
        "SCOUT 2010",
        "randomized cardiovascular-outcome trial",
    ),
    "select": CandidateInfo(
        "SELECT",
        "cochrane_excluded",
        "Ryan 2020",
        "randomized cardiovascular-outcome trial",
        "The Cochrane package identifies SELECT under its rationale-and-design report.",
    ),
    "sequel": CandidateInfo(
        "SEQUEL",
        "cochrane_excluded",
        "SEQUEL 2014",
        "randomized extension study",
    ),
    "sharma": CandidateInfo(
        "Sharma 2002",
        "cochrane_excluded",
        "Sharma 2002",
        "non-randomized intervention study",
    ),
    "sjostrom": CandidateInfo(
        "Sjöström 1998",
        "cochrane_excluded",
        "Sjöström 1998",
        "randomized controlled trial",
    ),
    "step4": CandidateInfo(
        "STEP 4", "cochrane_excluded", "STEP 4 2021", "randomized controlled trial"
    ),
    "step5": CandidateInfo(
        "STEP 5", "cochrane_excluded", "Garvey 2021", "randomized controlled trial"
    ),
    "step6": CandidateInfo(
        "STEP 6", "cochrane_excluded", "STEP 6 2022", "randomized controlled trial"
    ),
    # Other identifiable primary-study clusters named in terminal lists.
    "astrup_liraglutide": CandidateInfo(
        "Astrup liraglutide obesity trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "bloch": CandidateInfo(
        "Bloch 2003", "outside_other", design="randomized controlled trial"
    ),
    "cagrisema": CandidateInfo(
        "REDEFINE 1", "outside_other", design="randomized controlled trial"
    ),
    "crescendo": CandidateInfo(
        "CRESCENDO", "outside_other", design="randomized cardiovascular-outcome trial"
    ),
    "derosa": CandidateInfo(
        "Derosa 2005", "outside_other", design="comparative clinical trial"
    ),
    "gateway": CandidateInfo(
        "GATEWAY",
        "outside_other",
        design="randomized bariatric-surgery trial",
        note="The intervention is surgery rather than a weight-loss medicine.",
    ),
    "hazenberg": CandidateInfo(
        "Hazenberg 2000", "outside_other", design="randomized controlled trial"
    ),
    "liakos": CandidateInfo(
        "Liakos liraglutide ambulatory-BP trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "nakou": CandidateInfo(
        "Nakou 2008", "outside_other", design="clinical trial"
    ),
    "phentermine_abpm": CandidateInfo(
        "Phentermine/topiramate ambulatory-BP trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "queens": CandidateInfo(
        "QUEEN's study", "outside_other", design="randomized controlled trial"
    ),
    "scale_ibt": CandidateInfo(
        "SCALE IBT", "outside_other", design="randomized controlled trial"
    ),
    "scale_insulin": CandidateInfo(
        "SCALE Insulin", "outside_other", design="randomized controlled trial"
    ),
    "scholze": CandidateInfo(
        "Hypertension-Obesity-Sibutramine study",
        "outside_other",
        design="clinical trial",
    ),
    "step_hfpef": CandidateInfo(
        "STEP-HFpEF", "outside_other", design="randomized controlled trial"
    ),
    "step_hfpef_dm": CandidateInfo(
        "STEP-HFpEF DM", "outside_other", design="randomized controlled trial"
    ),
    "summit": CandidateInfo(
        "SUMMIT", "outside_other", design="randomized controlled trial"
    ),
    "surmount3": CandidateInfo(
        "SURMOUNT-3", "outside_other", design="randomized controlled trial"
    ),
    "surmount5": CandidateInfo(
        "SURMOUNT-5", "outside_other", design="randomized controlled trial"
    ),
    "sustain6": CandidateInfo(
        "SUSTAIN-6", "outside_other", design="randomized cardiovascular-outcome trial"
    ),
    "tonstad": CandidateInfo(
        "Tonstad topiramate hypertension trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "wilding_topiramate": CandidateInfo(
        "Wilding topiramate obesity trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "verma_orlistat": CandidateInfo(
        "Verma 2014 Lucknow orlistat trial",
        "outside_other",
        design="randomized placebo-controlled trial",
        note="Resolved from the sparse list entry; DOI 10.9790/0853-13816770.",
    ),
    "ardissino": CandidateInfo(
        "Ardissino 2022",
        "outside_observational",
        design="propensity-score-matched cohort study",
    ),
    # Listed publications or entries that do not identify one eligible primary study.
    "pooled_scale": CandidateInfo(
        "Pooled SCALE post hoc analysis",
        "invalid_publication_type",
        design="pooled secondary analysis",
    ),
    "pooled_step": CandidateInfo(
        "Pooled STEP analysis",
        "invalid_publication_type",
        design="pooled secondary analysis",
    ),
}


def normalize(text: str) -> str:
    """Normalize punctuation and Markdown enough for ordered identity rules."""

    return (
        text.lower()
        .replace("–", "-")
        .replace("—", "-")
        .replace("‑", "-")
        .replace("\u00a0", " ")
    )


def extract_terminal_list(path: Path) -> list[str]:
    """Extract only entries inside the response's dedicated terminal list."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if path.stem == "claude-researcher-4":
        entries = []
        for line in lines:
            if line.startswith("A few notes on scope:"):
                break
            if line.startswith("- "):
                entries.append(line[2:].strip())
        return entries

    heading_indexes = []
    for index, line in enumerate(lines):
        lowered = normalize(line)
        heading_like = line.startswith("#") or line.startswith("**")
        if not heading_like:
            continue
        if path.stem.startswith("gemini-"):
            if "references" in lowered or "primary studies" in lowered:
                heading_indexes.append(index)
        elif "primary studies" in lowered:
            heading_indexes.append(index)
    if not heading_indexes:
        raise ValueError(f"No terminal study-list heading in {path.name}")

    block = lines[heading_indexes[-1] + 1 :]
    numbered = [
        match.group(1).strip()
        for line in block
        if (match := re.match(r"^\d+\.\s+(.+)$", line))
    ]
    if numbered:
        return numbered

    if path.stem.startswith("gemini-"):
        return [
            line.strip()
            for line in block
            if "doi.org/" in line.lower() and not line.lower().startswith("cited by:")
        ]
    raise ValueError(f"No terminal study-list entries in {path.name}")


def resolve_candidate(entry: str) -> str:
    """Resolve one extracted citation with ordered review-specific rules."""

    text = normalize(entry)

    if "individual patient data meta-analysis" in text or "pooled primary-data" in text:
        return "pooled_step"
    if "five randomized controlled step trials" in text:
        return "pooled_step"
    if "post hoc analysis from scale randomized controlled trials" in text:
        return "pooled_scale"

    if "redefine 1" in text or "cagrisema" in text:
        return "cagrisema"
    if (
        "step-hfpef" in text
        or "heart failure with preserved ejection fraction" in text
        or "obesity-related heart failure and type 2 diabetes" in text
    ):
        if "tirzepatide" in text or "summit" in text or "packer" in text:
            return "summit"
        if "type 2 diabetes" in text or "obesity-related heart failure and type 2" in text:
            return "step_hfpef_dm"
        return "step_hfpef"

    if "sustain 6" in text or "sustain-6" in text or "nct01720446" in text:
        return "sustain6"
    if (
        "select" in text
        or "nejmoa2307563" in text
        or "semaglutide and cardiovascular outcomes in obesity without diabetes"
        in text
    ):
        return "select"

    if "step 6" in text:
        return "step6"
    if "step 5" in text:
        return "step5"
    if "step 4" in text and "step 1 and 4" not in text:
        return "step4"
    if "step 1" in text or "nejmoa2032183" in text or "once-weekly semaglutide in adults" in text:
        return "step1"

    if "surmount-5" in text:
        return "surmount5"
    if "surmount-3" in text:
        return "surmount3"
    if (
        "surmount-1" in text
        or "nejmoa2206038" in text
        or "39536238" in text
        or "tirzepatide once weekly for the treatment of obesity" in text
        or "tirzepatide for obesity treatment and diabetes prevention" in text
    ):
        return "surmount1"

    if "scale insulin" in text:
        return "scale_insulin"
    if "scale ibt" in text or "liraglutide 3.0 mg and intensive behavioral therapy" in text:
        return "scale_ibt"
    if (
        "scale obesity" in text
        or "nejmoa1411892" in text
        or "3 years of liraglutide versus placebo" in text
        or "three years of liraglutide versus placebo" in text
        or "a randomized, controlled trial of 3.0 mg of liraglutide" in text
    ):
        return "scale_obesity"
    if "effects of liraglutide in the treatment of obesity" in text:
        return "astrup_liraglutide"
    if "liraglutide on ambulatory blood pressure" in text:
        return "liakos"

    if (
        "38304225" in text
        or "pmc10831272" in text
        or "nct05215418" in text
        or "phentermine/topiramate extended-release, phentermine, and placebo "
        "on ambulatory blood pressure" in text
    ):
        return "phentermine_abpm"
    if "changes in cardiovascular risk associated with phentermine" in text:
        return "conquer"
    if (
        "conquer" in text
        or "effects of low-dose, controlled-release, phentermine" in text
        or "effects of low-dose controlled-release phentermine" in text
    ):
        return "conquer"
    if (
        "equip" in text
        or "controlled-release phentermine/topiramate in severely obese adults"
        in text
    ):
        return "equip"
    if (
        "sequel" in text
        or "two-year sustained weight loss and metabolic benefits with "
        "controlled-release phentermine" in text
    ):
        return "sequel"
    if "queen's" in text:
        return "queens"
    if "topiramate in the treatment of obese subjects with essential hypertension" in text:
        return "tonstad"
    if "long-term efficacy and safety of topiramate" in text:
        return "wilding_topiramate"

    if "orlistat improves blood pressure control" in text:
        return "bakris"
    if "sufficient weight reduction decreases cardiovascular complications" in text:
        return "cocco"
    if "orlistat in hypertensive overweight/obese patients" in text:
        return "bloch"
    if "effects of orlistat on obesity-related diseases" in text:
        return "guy_grand"
    if (
        "uk multimorbidity study" in text
        or "randomised trial of the effect of orlistat on body weight and "
        "cardiovascular disease risk profile" in text
    ):
        return "broom"
    if "effect of orlistat-induced weight loss" in text:
        return "sharma"
    if "randomised placebo-controlled trial of orlistat for weight loss" in text:
        return "sjostrom"
    if "xendos" in text or "xenical in the prevention of diabetes" in text:
        return "xendos"
    if "lucknow" in text and "orlistat" in text:
        return "verma_orlistat"
    if "comparative evaluation of orlistat and sibutramine" in text:
        return "derosa"

    if "light" in text or (
        "naltrexone-bupropion" in text
        and "major adverse cardiovascular events" in text
    ):
        return "light"
    if "cor-i" in text or "effect of naltrexone plus bupropion on weight loss" in text:
        return "cor_i"
    if (
        "cor-ii" in text
        or "randomized, phase 3 trial of naltrexone" in text
        or "randomized phase 3 trial of naltrexone" in text
    ):
        return "cor_ii"

    if "camellia" in text or "cardiovascular safety of lorcaserin" in text:
        return "camellia"
    if "scout" in text or "effect of sibutramine on cardiovascular outcomes" in text:
        return "scout"
    if "crescendo" in text or "rimonabant for prevention of cardiovascular events" in text:
        return "crescendo"
    if "efficacy and safety of sibutramine in obese white and african american" in text:
        return "mcmahon_2000"
    if (
        "sibutramine is safe and effective for weight loss" in text
        or "sibutramine in hypertensives clinical study" in text
    ):
        return "mcmahon_2002"
    if "effects of sibutramine on the treatment of obesity" in text:
        return "faria"
    if "randomized, double-blind, placebo-controlled, multicenter study of sibutramine" in text:
        return "hazenberg"
    if "optimal treatment of obesity-related hypertension" in text or "hos study" in text:
        return "scholze"
    if "sibutramine plus verapamil" in text:
        return "nakou"

    if (
        "gateway" in text
        or "effects of bariatric surgery in obese patients with hypertension" in text
        or "three-year outcomes of bariatric surgery" in text
    ):
        return "gateway"
    if "long-term cardiovascular outcomes after orlistat therapy" in text:
        return "ardissino"

    raise ValueError(f"Unresolved terminal-list entry: {entry}")


def citation_identity_note(entry: str, key: str) -> str:
    """Return an audit note when a citation resolves despite conflicting details."""

    text = normalize(entry)
    if key == "bloch" and ("faria" in text or "sharma" in text):
        return (
            "The title identifies Bloch 2003, but the response supplies a "
            "different lead author."
        )
    if key == "phentermine_abpm" and ("jordan" in text or "blüher" in text):
        return (
            "The title identifies the ambulatory-BP trial, but the response "
            "supplies a different lead author."
        )
    if (
        key == "conquer"
        and "changes in cardiovascular risk" in text
        and ("jordan" in text or "bays" in text)
    ):
        return (
            "The title identifies the Davidson CONQUER report, but the response "
            "supplies a different lead author."
        )
    if (
        key == "surmount1"
        and "stratified analyses" in text
        and re.match(r"(?:\*\*)?de lemos", text)
    ):
        return (
            "The title identifies the Krumholz SURMOUNT-1 report, but the "
            "response supplies de Lemos as lead author."
        )
    if key == "summit" and "kosiborod" in text:
        return (
            "The title identifies the Packer SUMMIT report, but the response "
            "supplies Kosiborod as lead author."
        )
    if key == "tonstad" and "mcmahon" in text:
        return (
            "The title identifies the Tonstad topiramate trial, but the response "
            "supplies McMahon as lead author."
        )
    if key == "wilding_topiramate" and "tonstad" in text:
        return (
            "The title identifies a different topiramate obesity trial than the "
            "supplied Tonstad attribution."
        )
    if key == "bakris" and "sharma" in text:
        return (
            "The title identifies Bakris 2002, but the response supplies Sharma "
            "and Golay as authors."
        )
    if key == "sharma" and "wadden" in text:
        return "The title identifies Sharma 2002, but the response supplies Wadden as lead author."
    if key == "surmount5" and "comparative-effectiveness cohort study" in text:
        return (
            "The named trial is identifiable, but the supplied link is described "
            "as a separate cohort source."
        )
    if key == "pooled_step" and "jordan" in text:
        return (
            "The publication is identifiable as a pooled analysis, but the "
            "response supplies a conflicting lead author."
        )
    return ""


def ris_study_labels(path: Path) -> set[str]:
    """Read unique Cochrane study labels from an RIS export."""

    return {
        match.group(1).strip()
        for match in re.finditer(
            r"^NS  - (.+)$", path.read_text(encoding="utf-8-sig"), re.MULTILINE
        )
    }


def response_paths() -> list[Path]:
    """Return the complete expected 3-model, 3-role, 4-replicate file set."""

    expected = {
        f"{model}-{role}-{replicate}.md"
        for model in MODELS
        for role in ROLES
        for replicate in range(1, 5)
    }
    available = {
        path.name for path in REVIEW_DIR.glob("*.md") if path.name != "README.md"
    }
    if available != expected:
        missing = sorted(expected - available)
        stale = sorted(available - expected)
        raise ValueError(f"Response file mismatch; missing={missing}, stale={stale}")
    return [REVIEW_DIR / name for name in sorted(expected)]


def validate_cochrane_labels() -> None:
    """Require every Cochrane-classified candidate label to occur in its RIS."""

    labels_by_status = {
        "included": ris_study_labels(SOURCE_DIR / "CD007654-included.ris"),
        "cochrane_excluded": ris_study_labels(SOURCE_DIR / "CD007654-excluded.ris"),
    }
    for candidate in CANDIDATES.values():
        if candidate.status in labels_by_status:
            if candidate.cochrane_label not in labels_by_status[candidate.status]:
                raise ValueError(
                    f"{candidate.status} label not in RIS: {candidate.cochrane_label}"
                )


def build_match_rows() -> tuple[list[dict[str, str | int]], dict[str, int]]:
    """Build one row per deduplicated study cluster in each terminal list."""

    validate_cochrane_labels()
    rows: list[dict[str, str | int]] = []
    raw_counts: dict[str, int] = {}
    for path in response_paths():
        run_id = path.stem
        model, role_id, replicate_text = run_id.split("-")
        entries = extract_terminal_list(path)
        raw_counts[run_id] = len(entries)
        grouped: dict[str, list[str]] = defaultdict(list)
        identity_notes: dict[str, list[str]] = defaultdict(list)
        for entry in entries:
            key = resolve_candidate(entry)
            grouped[key].append(entry)
            if note := citation_identity_note(entry, key):
                identity_notes[key].append(note)

        for key, citations in grouped.items():
            candidate = CANDIDATES[key]
            notes = list(dict.fromkeys(identity_notes[key]))
            if len(citations) > 1:
                notes.append(
                    f"Grouped {len(citations)} terminal-list citations to one study cluster."
                )
            if candidate.note:
                notes.append(candidate.note)
            rows.append(
                {
                    "run_id": run_id,
                    "model": model,
                    "role_id": role_id,
                    "replicate": int(replicate_text),
                    "source_file": f"CD007654/{path.name}",
                    "reported_citation": " || ".join(citations),
                    "canonical_candidate": candidate.label,
                    "ground_truth_status": candidate.status,
                    "cochrane_study_label": candidate.cochrane_label,
                    "design": candidate.design,
                    "identity_issue": int(bool(identity_notes[key])),
                    "notes": "; ".join(notes),
                }
            )

    observed_entries = Counter()
    for run_id, count in raw_counts.items():
        observed_entries[run_id.split("-")[0]] += count
    if dict(observed_entries) != EXPECTED_LIST_ENTRIES:
        raise ValueError(
            "Terminal-list entry count mismatch; "
            f"expected={EXPECTED_LIST_ENTRIES}, observed={dict(observed_entries)}"
        )
    return rows, raw_counts


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write a non-empty audit table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def print_summary(
    rows: list[dict[str, str | int]], raw_counts: dict[str, int]
) -> None:
    """Print compact extraction and included-study recall checks."""

    included_truth = ris_study_labels(SOURCE_DIR / "CD007654-included.ris")
    by_run: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for row in rows:
        by_run[str(row["run_id"])].append(row)

    model_entries = Counter()
    model_clusters = Counter()
    for run_id, run_rows in by_run.items():
        model = run_id.split("-")[0]
        model_entries[model] += raw_counts[run_id]
        model_clusters[model] += len(run_rows)

    print(f"Runs: {len(by_run)}")
    print(f"Terminal-list entries: {sum(raw_counts.values())}")
    print(f"Deduplicated study clusters: {len(rows)}")
    for model in MODELS:
        print(
            f"{model}: {model_entries[model]} entries; "
            f"{model_clusters[model]} deduplicated clusters"
        )
    print("Included-study recall by run:")
    for run_id in sorted(by_run):
        retrieved = {
            str(row["cochrane_study_label"])
            for row in by_run[run_id]
            if row["ground_truth_status"] == "included"
        }
        print(f"  {run_id}: {len(retrieved)}/{len(included_truth)}")
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the list-only curated match table for CD007654."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
