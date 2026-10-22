#!/usr/bin/env python3
"""Export the recorded role prompts without the study-finding instructions.

Run from the repository root:
    python3 scripts/export_retrieval_questions.py

Uses only the Python standard library and the committed review READMEs/registry.
Output order and formatting are deterministic. Original prompts are not edited.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shared.review_registry import review_sources  # noqa: E402

ROLE_HEADINGS = {
    "Patient": "patient",
    "Clinician": "clinician",
    "Researcher": "researcher",
    "Evidence-synthesis researcher": "researcher",
}
ROLES = ("patient", "clinician", "researcher")
INSTRUCTIONS = (
    "Find individual primary studies on this. Do not use systematic reviews, "
    "meta-analyses, narrative reviews, committee opinions, practice guidelines, "
    "or editorials/comments."
)
LIST_INSTRUCTION = "List the primary studies in the end."


def normalize(text: str) -> str:
    """Unwrap Markdown line wrapping without changing words or punctuation."""
    return " ".join(text.split())


def read_questions(readme: Path) -> dict[str, str]:
    text = readme.read_text(encoding="utf-8")
    section = re.search(r"^## Prompts\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if section is None:
        raise ValueError(f"Missing Prompts section: {readme}")

    questions = {}
    blocks = re.split(r"^### (.+)\n", section.group(1), flags=re.M)
    for heading, body in zip(blocks[1::2], blocks[2::2]):
        role = ROLE_HEADINGS.get(heading.strip())
        if role is None or role in questions:
            raise ValueError(f"Unknown or duplicate role {heading!r}: {readme}")
        # Preserve paragraph boundaries; unwrap only lines inside each paragraph.
        quoted = "\n".join(
            line[1:].strip() for line in body.splitlines() if line.startswith(">")
        )
        paragraphs = [normalize(p) for p in quoted.split("\n\n") if p.strip()]
        original = normalize(quoted)
        before, marker, after = original.partition(INSTRUCTIONS)
        # Fail on changed instruction wording instead of silently exporting it.
        if not marker or after.strip() not in ("", LIST_INSTRUCTION):
            raise ValueError(f"Unexpected instruction suffix for {role}: {readme}")
        question = "\n\n".join(paragraphs).split("Find individual primary studies", 1)[0].strip()
        if not question or normalize(question) != before.strip():
            raise ValueError(f"Question extraction changed content for {role}: {readme}")
        questions[role] = question

    if set(questions) != set(ROLES):
        raise ValueError(f"Expected all three roles: {readme}")
    return questions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "retrieval_questions",
        help="Destination for questions.txt and questions.json",
    )
    args = parser.parse_args()

    records = []
    for source in review_sources():
        questions = read_questions(source.readme_path)
        for role in ROLES:
            records.append({
                "question_id": f"{source.review_id}-{role}",
                "review_id": source.review_id,
                "review_title": source.review_title,
                "role": role,
                "source_readme": str(source.readme_path.relative_to(REPO_ROOT)),
                "question": questions[role],
            })

    lines = [
        "Retrieval evaluation questions",
        f"{len(records)} questions across {len(records) // len(ROLES)} clinical topics.",
        "Grouped by review ID, then patient, clinician, and researcher.",
        "Role introductions and clinical wording are preserved from the original prompts.",
        "The study-finding instructions have been removed.",
        "Regenerate from the repository root: python3 scripts/export_retrieval_questions.py",
        "",
    ]
    for index, record in enumerate(records, 1):
        if record["role"] == "patient":
            lines.extend(["=" * 80, f'{record["review_id"]}: {record["review_title"]}', ""])
        lines.extend([
            f'{index:02d}. {record["role"].capitalize()} [{record["question_id"]}]',
            "",
            record["question"],
            "",
        ])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "questions.txt").write_text("\n".join(lines), encoding="utf-8")
    (args.output_dir / "questions.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(records)} questions to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
