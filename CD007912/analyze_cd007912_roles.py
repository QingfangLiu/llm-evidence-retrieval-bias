#!/usr/bin/env python3
"""Curate terminal study lists from the CD007912 user-role experiment."""

from __future__ import annotations

import csv
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_DIR = Path(__file__).resolve().parent
SOURCE_ZIP = (
    REPO_ROOT
    / "source_reviews"
    / "2026_issue_7"
    / "CD007912-SUP-07-dataPackage.zip"
)
MATCHES_PATH = REVIEW_DIR / "cd007912_role_study_matches.csv"
ROLES = ("patient", "clinician", "researcher")
MODELS = ("claude", "gemini", "gpt")
EXPECTED_LIST_ENTRIES = {"claude": 137, "gemini": 44, "gpt": 211}
EXPECTED_RESPONSE_STUDY_ROWS = 363
EXPECTED_COHCRANE_LABELS = {
    "included": 18,
    "cochrane_excluded": 80,
    "cochrane_awaiting": 9,
    "cochrane_ongoing": 10,
}
RIS_MEMBERS = {
    "included": "CD007912-study-data/CD007912-included.ris",
    "cochrane_excluded": "CD007912-study-data/CD007912-excluded.ris",
    "cochrane_awaiting": "CD007912-study-data/CD007912-awaiting.ris",
    "cochrane_ongoing": "CD007912-study-data/CD007912-ongoing.ris",
}


@dataclass(frozen=True)
class CandidateInfo:
    """Canonical information for one response-level study candidate."""

    label: str
    status: str
    cochrane_labels: tuple[str, ...] = ()
    design: str = ""
    note: str = ""


OUTSIDE_CANDIDATES = {
    "fransen_2001_knee": CandidateInfo(
        "Fransen 2001 knee trial",
        "outside_other",
        design="randomized controlled trial",
        note="The cited trial concerns knee osteoarthritis rather than hip osteoarthritis.",
    ),
    "fukumoto_resistance": CandidateInfo(
        "Fukumoto high- versus low-velocity resistance trial",
        "outside_other",
        design="randomized active-comparator trial",
    ),
    "osteras_pilot": CandidateInfo(
        "Østerås medical-exercise pilot trial",
        "outside_other",
        design="randomized active-comparator pilot trial",
    ),
    "hall_weight_loss": CandidateInfo(
        "Hall weight-loss plus exercise trial",
        "outside_other",
        design="randomized active-comparator trial",
    ),
    "hope_trial": CandidateInfo(
        "Bennell 2018 HOPE trial",
        "outside_other",
        design="randomized controlled trial",
        note=(
            "Both groups received home exercise; the randomized contrast tested "
            "prior pain-coping training."
        ),
    ),
    "fernandes_case_report": CandidateInfo(
        "Fernandes 2010 therapeutic-exercise case report",
        "invalid_publication_type",
        design="case report",
        note="The paper describes one patient and calls for a later randomized trial.",
    ),
    "van_baar_systematic_review": CandidateInfo(
        "van Baar 1999 systematic review",
        "invalid_publication_type",
        design="systematic review",
        note="The response explicitly lists a systematic review as a primary study.",
    ),
    "hermann_preoperative": CandidateInfo(
        "Hermann 2016 preoperative resistance-training trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "saw_2016": CandidateInfo(
        "Saw 2016 preoperative exercise-and-education trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "hoogeboom_2010": CandidateInfo(
        "Hoogeboom 2010 preoperative exercise pilot",
        "outside_other",
        design="randomized pilot trial",
    ),
    "svinoy_2025": CandidateInfo(
        "Svinøy 2025 prehabilitation trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "frydendal_2024": CandidateInfo(
        "Frydendal 2024 PROHIP trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "talonpoika_2026": CandidateInfo(
        "Talonpoika 2026 hip-arthroplasty comparison trial",
        "outside_other",
        design="randomized controlled trial",
    ),
    "cleat_results": CandidateInfo(
        "Wainwright 2025 CLEAT results",
        "cochrane_excluded",
        ("Wainwright 2023",),
        "randomized controlled trial",
        "The results report is grouped with the source-package CLEAT protocol label.",
    ),
    "kjeldsen_results": CandidateInfo(
        "Kjeldsen 2024 Hip Booster trial",
        "cochrane_excluded",
        ("Kjeldsen 2022",),
        "cluster-randomized active-comparator trial",
        "The results report is grouped with the source-package Hip Booster protocol label.",
    ),
    "olsen_2022": CandidateInfo(
        "Olsen 2022 body-awareness trial",
        "outside_other",
        design="randomized controlled trial",
    ),
}


def normalize(text: str) -> str:
    """Normalize citation text for stable review-specific matching."""

    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def zip_text(member: str) -> str:
    """Read one UTF-8 text member directly from the Cochrane ZIP package."""

    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(member).decode("utf-8-sig")


def ris_records(member: str) -> list[str]:
    """Split one RIS member into records carrying Cochrane study labels."""

    return [
        record
        for record in re.split(r"^ER  -\s*$", zip_text(member), flags=re.MULTILINE)
        if re.search(r"^NS  - .+$", record, re.MULTILINE)
    ]


def ris_study_labels(member: str) -> set[str]:
    """Read unique Cochrane study labels from one RIS member in the ZIP."""

    return {
        match.group(1).strip()
        for match in re.finditer(r"^NS  - (.+)$", zip_text(member), re.MULTILINE)
    }


def ris_pubmed_ids(member: str) -> dict[str, set[str]]:
    """Return explicit PubMed IDs grouped by Cochrane study label."""

    identifiers: dict[str, set[str]] = defaultdict(set)
    for record in ris_records(member):
        label_match = re.search(r"^NS  - (.+)$", record, re.MULTILINE)
        if not label_match:
            continue
        label = label_match.group(1).strip()
        identifiers[label].update(
            match.group(1)
            for match in re.finditer(
                r"^C3  - PubMed\s+(\d+)\s*$", record, re.MULTILINE
            )
        )
    return identifiers


def load_source_candidates() -> tuple[
    dict[str, CandidateInfo], list[tuple[str, str]], list[tuple[str, str]]
]:
    """Build source candidates plus exact report-title and DOI lookup rows."""

    candidates: dict[str, CandidateInfo] = {}
    title_rows: list[tuple[str, str]] = []
    doi_rows: list[tuple[str, str]] = []
    design_by_status = {
        "included": "Cochrane-included study cluster",
        "cochrane_excluded": "Cochrane-excluded study",
        "cochrane_awaiting": "study awaiting classification",
        "cochrane_ongoing": "ongoing study",
    }
    for status, member in RIS_MEMBERS.items():
        for label in sorted(ris_study_labels(member)):
            key = f"source:{status}:{label}"
            candidates[key] = CandidateInfo(
                label,
                status,
                (label,),
                design_by_status[status],
            )
        for record in ris_records(member):
            label = re.search(r"^NS  - (.+)$", record, re.MULTILINE).group(1).strip()
            key = f"source:{status}:{label}"
            for title in re.findall(r"^(?:TI|TT)  - (.+)$", record, re.MULTILINE):
                title_text = normalize(title)
                if len(title_text) >= 30:
                    title_rows.append((title_text, key))
            for doi in re.findall(r"^DO  - (.+)$", record, re.MULTILINE):
                doi_text = normalize(doi)
                if doi_text:
                    doi_rows.append((doi_text, key))
    return candidates, title_rows, doi_rows


SOURCE_CANDIDATES, SOURCE_TITLE_ROWS, SOURCE_DOI_ROWS = load_source_candidates()
CANDIDATES = {**SOURCE_CANDIDATES, **OUTSIDE_CANDIDATES}


def source_key(status: str, label: str) -> str:
    """Return a validated source candidate key."""

    key = f"source:{status}:{label}"
    if key not in SOURCE_CANDIDATES:
        raise ValueError(f"Unknown source candidate: {status} {label}")
    return key


def exact_source_keys(text: str) -> tuple[str, ...]:
    """Resolve copied source report titles and identifiers without fuzzy matching."""

    matches = {
        key
        for title, key in SOURCE_TITLE_ROWS
        if title in text or (len(text) >= 50 and text in title)
    }
    matches.update(key for doi, key in SOURCE_DOI_ROWS if doi in text)
    return tuple(sorted(matches))


def resolve_candidate(entry: str) -> tuple[str, ...]:
    """Resolve one terminal-list entry to one or more study clusters."""

    text = normalize(entry)

    if "systematic review of randomized clinical trials" in text:
        return ("van_baar_systematic_review",)
    if text.startswith("juhakoski"):
        return (source_key("included", "Juhakoski 2011"),)

    exact = exact_source_keys(text)
    if len(exact) == 1:
        return exact

    phrase_rules = (
        (("pmid 24846036",), source_key("cochrane_excluded", "Bennell 2014")),
        (("pmid 27129607",), source_key("cochrane_excluded", "Bieler 2017")),
        (("pmid 28971551",), source_key("cochrane_excluded", "Bieler 2017")),
        (("pmid 24931956",), source_key("cochrane_excluded", "Villadsen 2014")),
        (("pmid 25249361",), source_key("included", "Krauß 2014")),
        (("pmid 21078702",), source_key("included", "Juhakoski 2011")),
        (("pmid 15940775",), source_key("included", "Tak 2005")),
        (("pmc8393441",), source_key("included", "Krauß 2014")),
        (
            ("effect of physical therapy on pain and function", "bennell"),
            source_key("cochrane_excluded", "Bennell 2014"),
        ),
        (
            ("van baar", "effectiveness of exercise", "hip or knee"),
            source_key("included", "van Baar 1998"),
        ),
        (("fernandes", "efficacy of patient education"), source_key("included", "Fernandes 2010")),
        (("svege", "postpone total hip replacement"), source_key("included", "Fernandes 2010")),
        (
            ("svege", "long term effect of exercise therapy"),
            source_key("included", "Fernandes 2010"),
        ),
        (("juhakoski",), source_key("included", "Juhakoski 2011")),
        (("effectiveness and cost consequences",), source_key("included", "Juhakoski 2011")),
        (("french", "empart"), source_key("included", "French 2013")),
        (
            ("french", "exercise and manual physiotherapy arthritis"),
            source_key("included", "French 2013"),
        ),
        (("fransen", "nairn"), source_key("included", "Fransen 2007")),
        (
            ("fransen", "physical activity for osteoarthritis management"),
            source_key("included", "Fransen 2007"),
        ),
        (("abbott", "manual therapy", "usual care"), source_key("included", "Abbott 2013")),
        (("moa trial",), source_key("included", "Abbott 2013")),
        (("foley", "hydrotherapy improve strength"), source_key("included", "Foley 2003")),
        (
            ("hopman rock", "health educational and exercise"),
            source_key("included", "Hopman-Rock 2000"),
        ),
        (("thompson", "group based exercise program"), source_key("included", "Thompson 2020")),
        (("hall", "phoenix"), source_key("included", "Hall 2025")),
        (("bieler", "exercise induced effects"), source_key("cochrane_excluded", "Bieler 2017")),
        (
            ("veehof", "behavioural graded activity"),
            source_key("cochrane_excluded", "Veenhof 2006"),
        ),
        (
            ("veenhof", "behavioral graded activity"),
            source_key("cochrane_excluded", "Veenhof 2006"),
        ),
        (("pisters", "long term effectiveness"), source_key("cochrane_excluded", "Pisters 2010b")),
        (("pain coping skills training before home exercise",), "hope_trial"),
        (("development of a therapeutic exercise program",), "fernandes_case_report"),
        (("very low calorie weight loss diet",), "hall_weight_loss"),
        (("very low calorie diet and exercise",), "hall_weight_loss"),
        (("fransen", "physical therapy is effective", "knee"), "fransen_2001_knee"),
        (("fransen", "physical therapy is effective", "hip"), "fransen_2001_knee"),
        (("systematic review of randomized clinical trials",), "van_baar_systematic_review"),
        (("high velocity", "low velocity"), "fukumoto_resistance"),
        (("fukumoto", "high velocity resistance training"), "fukumoto_resistance"),
        (("fukumoto", "gait kinematics and kinetics"), "fukumoto_resistance"),
        (("medical exercise therapy", "pilot"), "osteras_pilot"),
        (("preoperative progressive explosive",), "hermann_preoperative"),
        (("significant improvements in pain after",), "saw_2016"),
        (("saw", "pre operative exercise and education"), "saw_2016"),
        (("preoperative therapeutic exercise in frail",), "hoogeboom_2010"),
        (("effect of prehabilitation for older patients",), "svinoy_2025"),
        (("total hip replacement or resistance training",), "frydendal_2024"),
        (("training load and pain response", "prohip"), "frydendal_2024"),
        (("kjeldsen",), "kjeldsen_results"),
        (("prohip",), "frydendal_2024"),
        (("total hip arthroplasty compared with conservative",), "talonpoika_2026"),
        (("talonpoika", "total hip arthroplasty versus nonoperative"), "talonpoika_2026"),
        (("cycling and education intervention",), "cleat_results"),
        (("progressive resistance training or neuromuscular exercise",), "kjeldsen_results"),
        (("booster sessions for maintaining",), "kjeldsen_results"),
        (("targeted gluteal exercise versus sham",), source_key("cochrane_ongoing", "Semciw 2018")),
        (("my hip exercise",), source_key("cochrane_ongoing", "Bennell 2023")),
        (
            ("efficacy of conservative treatment regimes", "hip school"),
            source_key("included", "Krauß 2014"),
        ),
        (("hip school trial", "published protocol"), source_key("included", "Krauß 2014")),
        (("empart protocol",), source_key("included", "French 2013")),
        (("nct02884531",), "olsen_2022"),
        (("nct01700933",), "osteras_pilot"),
        (("basic body awareness therapy",), "olsen_2022"),
    )
    for phrases, key in phrase_rules:
        if all(phrase in text for phrase in phrases):
            return (key,)

    if exact:
        return exact
    raise ValueError(f"Unresolved terminal-list entry: {entry}")


def citation_identity_note(entry: str, key: str) -> str:
    """Return an audit note when a citation resolves despite conflicting details."""

    text = normalize(entry)
    if key == source_key("included", "Fernandes 2010") and "thuko" in text:
        return (
            "The authors identify the Fernandes cluster, but the response "
            "incorrectly calls it THüKo."
        )
    if key == source_key("included", "Krauß 2014") and text.startswith("svege"):
        return (
            "The THüKo title and acronym identify Krauß 2014, but the response "
            "gives authors and a journal from the Fernandes cluster."
        )
    if key == source_key("included", "Krauß 2014") and text.startswith("bieler"):
        return (
            "The report title identifies the Krauß 2014 cluster, but the response "
            "gives Bieler as lead author."
        )
    if key == source_key("included", "Teirlinck 2016") and text.startswith("bieler"):
        return "The title identifies Teirlinck 2016, but the response gives Bieler as lead author."
    if key == source_key("included", "Teirlinck 2016") and text.startswith("pisters"):
        return (
            "The title identifies Teirlinck 2016, but the response gives authors "
            "from a different trial."
        )
    if key == source_key("included", "Teirlinck 2016") and text.startswith("van der"):
        return (
            "The title identifies Teirlinck 2016, but the response gives uncertain, "
            "incorrect authors."
        )
    if key == source_key("included", "French 2013") and text.startswith("svege"):
        return (
            "The EMPART protocol is identifiable, but the response gives authors "
            "from the Fernandes cluster."
        )
    if key == "osteras_pilot" and text.startswith("bieler"):
        return (
            "The title identifies the Østerås pilot, but the response gives Bieler "
            "as lead author."
        )
    if key == "osteras_pilot" and text.startswith(("angelsvik", "fjellstad")):
        return (
            "The trial title identifies the Østerås pilot, but the response gives "
            "an incorrect lead author."
        )
    if key == "osteras_pilot" and any(
        journal in text
        for journal in (
            "musculoskelet sci pract",
            "musculoskeletal science and practice",
            "osteoarthritis cartilage",
            "physiotherapy theory and practice",
        )
    ):
        return (
            "The title identifies the Østerås pilot, but the response gives "
            "conflicting journal details."
        )
    if key == "olsen_2022" and text.startswith("ahlborg"):
        return (
            "The trial registration identifies Olsen 2022, but the response gives "
            "an uncertain, incorrect lead author."
        )
    if key == "frydendal_2024" and text.startswith("bieler"):
        return "The PROHIP report is identifiable, but the response gives Bieler as lead author."
    if key == "kjeldsen_results" and "prohip" in text:
        return (
            "The intervention contrast identifies the Hip Booster trial, but the "
            "response incorrectly calls it PROHIP."
        )
    if key == "fransen_2001_knee" and "osteoarthritis of the hip" in text:
        return (
            "The author, year, and journal identify the knee trial, but the response "
            "changes the title to hip osteoarthritis."
        )
    if (
        key == source_key("included", "Thompson 2020")
        and "group based exercise program" in text
    ):
        return (
            "The authors and journal identify Thompson 2020, but the response gives "
            "a non-source title."
        )
    if key == "saw_2016" and "functional recovery" in text:
        return (
            "The authors and journal identify Saw 2016, but the response gives a "
            "conflicting publication title."
        )
    if key == source_key("cochrane_excluded", "Bieler 2017") and "2021" in text:
        return (
            "The report resolves to the Bieler cluster, but the response gives the "
            "wrong publication year."
        )
    return ""


def extract_terminal_list(path: Path) -> list[str]:
    """Extract only entries inside the response's dedicated final study list."""

    lines = path.read_text(encoding="utf-8").splitlines()
    if path.stem in {
        "claude-researcher-1",
        "claude-researcher-3",
        "claude-researcher-4",
    }:
        entries = [
            match.group(1).strip()
            for line in lines
            if (match := re.match(r"^\s*\d+[.)]\s+(.+)$", line))
        ]
        if entries:
            return entries
        raise ValueError(f"No cohesive study-list entries in {path.name}")

    heading_indexes = []
    for index, line in enumerate(lines):
        heading = normalize(line)
        if path.stem.startswith("gemini-"):
            if (line.startswith("#") or line.startswith("**")) and heading.startswith(
                ("references", "primary studies")
            ):
                heading_indexes.append(index)
        elif (
            line.startswith("#")
            and heading.startswith(
                (
                    "primary studies",
                    "individual primary studies",
                    "list of primary studies",
                )
            )
        ) or re.match(
            r"^\*\*(?:primary studies|individual primary studies|list of primary studies)[^*]*\*\*:?\s*$",
            line.strip(),
            re.IGNORECASE,
        ):
            heading_indexes.append(index)
    if not heading_indexes:
        raise ValueError(f"No terminal study-list heading in {path.name}")

    block = lines[heading_indexes[-1] + 1 :]
    if path.stem.startswith("gemini-"):
        entries = []
        for index, line in enumerate(block):
            if "Cited by:" not in line:
                continue
            previous = index - 1
            while previous >= 0 and not block[previous].strip():
                previous -= 1
            if previous >= 0:
                entries.append(re.sub(r"^\s*\d+[.)]\s+", "", block[previous].strip()))
        if entries:
            return entries
    numbered = [
        match.group(1).strip()
        for line in block
        if (match := re.match(r"^\s*\d+[.)]\s+(.+)$", line))
    ]
    if numbered:
        return numbered
    raise ValueError(f"No terminal study-list entries in {path.name}")


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
    empty = sorted(
        name
        for name in expected
        if not (REVIEW_DIR / name).read_text(encoding="utf-8").strip()
    )
    if empty:
        raise ValueError(f"Empty response files: {empty}")
    return [REVIEW_DIR / name for name in sorted(expected)]


def validate_cochrane_labels() -> None:
    """Require every Cochrane-classified candidate label to occur in its RIS."""

    labels_by_status = {
        status: ris_study_labels(member) for status, member in RIS_MEMBERS.items()
    }
    observed_counts = {
        status: len(labels) for status, labels in labels_by_status.items()
    }
    if observed_counts != EXPECTED_COHCRANE_LABELS:
        raise ValueError(
            "Cochrane source-label count mismatch; "
            f"expected={EXPECTED_COHCRANE_LABELS}, observed={observed_counts}"
        )
    for candidate in CANDIDATES.values():
        if candidate.status not in labels_by_status:
            continue
        for label in candidate.cochrane_labels:
            if label not in labels_by_status[candidate.status]:
                raise ValueError(f"{candidate.status} label not in RIS: {label}")


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
            for key in resolve_candidate(entry):
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
                    "source_file": f"CD007912/{path.name}",
                    "reported_citation": " || ".join(citations),
                    "canonical_candidate": candidate.label,
                    "ground_truth_status": candidate.status,
                    "cochrane_study_label": " || ".join(candidate.cochrane_labels),
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
    if EXPECTED_RESPONSE_STUDY_ROWS and len(rows) != EXPECTED_RESPONSE_STUDY_ROWS:
        raise ValueError(
            "Response-study row count mismatch; "
            f"expected={EXPECTED_RESPONSE_STUDY_ROWS}, observed={len(rows)}"
        )

    labels_by_run_status: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        labels_by_run_status[(str(row["run_id"]), str(row["ground_truth_status"]))].extend(
            label.strip()
            for label in str(row["cochrane_study_label"]).split(" || ")
            if label.strip()
        )
    for run_status, labels in labels_by_run_status.items():
        duplicates = [label for label, count in Counter(labels).items() if count > 1]
        if duplicates:
            raise ValueError(f"Duplicate Cochrane labels in {run_status}: {duplicates}")
    return rows, raw_counts


def write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    """Write a non-empty audit table with stable column order."""

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def included_labels(row: dict[str, str | int]) -> set[str]:
    """Return included Cochrane study labels credited by one audit row."""

    if row["ground_truth_status"] != "included":
        return set()
    return {
        label.strip()
        for label in str(row["cochrane_study_label"]).split(" || ")
        if label.strip()
    }


def print_summary(
    rows: list[dict[str, str | int]], raw_counts: dict[str, int]
) -> None:
    """Print compact extraction, classification, and recall checks."""

    included_truth = ris_study_labels(RIS_MEMBERS["included"])
    included_pmids = ris_pubmed_ids(RIS_MEMBERS["included"])
    by_run: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    for row in rows:
        by_run[str(row["run_id"])].append(row)
    print(f"Runs: {len(response_paths())}")
    print(f"Terminal-list entries: {sum(raw_counts.values())}")
    print(f"Response-study rows after within-response deduplication: {len(rows)}")
    print(
        "Statuses: "
        + ", ".join(
            f"{status}={count}"
            for status, count in sorted(
                Counter(str(row["ground_truth_status"]) for row in rows).items()
            )
        )
    )
    for model in MODELS:
        run_ids = [run_id for run_id in raw_counts if run_id.startswith(f"{model}-")]
        print(
            f"{model}: {sum(raw_counts[run_id] for run_id in run_ids)} entries; "
            f"{sum(len(by_run.get(run_id, [])) for run_id in run_ids)} response-study rows"
        )
    print("Included-study recall by run:")
    for path in response_paths():
        run_id = path.stem
        retrieved = set().union(
            *(included_labels(row) for row in by_run.get(run_id, []))
        )
        print(f"  {run_id}: {len(retrieved)}/{len(included_truth)}")
    retrieved_all = set().union(*(included_labels(row) for row in rows))
    print(
        f"Pooled included coverage: {len(retrieved_all)}/{len(included_truth)}; "
        f"missed labels={','.join(sorted(included_truth - retrieved_all)) or 'none'}"
    )
    if not set().union(*included_pmids.values()):
        print("Included-study PMID coverage: unavailable (no explicit PubMed IDs in RIS)")
    print(f"Wrote: {MATCHES_PATH.relative_to(REPO_ROOT)}")


def main() -> None:
    """Regenerate the terminal-list-only curated match table for CD007912."""

    rows, raw_counts = build_match_rows()
    write_csv(MATCHES_PATH, rows)
    print_summary(rows, raw_counts)


if __name__ == "__main__":
    main()
