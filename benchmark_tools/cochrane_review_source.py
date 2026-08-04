"""Minimal Cochrane source helpers used by the RIS reference resolver."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


SOURCE_REVIEWS_DIRNAME = "source_reviews"


def review_collection_name(pdf: Path) -> str:
    parts = pdf.parts
    if SOURCE_REVIEWS_DIRNAME in parts:
        index = parts.index(SOURCE_REVIEWS_DIRNAME)
        if index + 1 < len(parts):
            return parts[index + 1]
    return pdf.parent.name


def is_review_pdf_path(pdf: Path) -> bool:
    return SOURCE_REVIEWS_DIRNAME in pdf.parts


def collect_review_pdfs(paths: Iterable[Path]) -> list[Path]:
    pdfs: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdfs.append(path)
        elif path.is_dir():
            pdfs.extend(sorted(path.glob("*.pdf")))
            pdfs.extend(sorted(path.glob("*/*.pdf")))
            pdfs.extend(sorted(path.glob("*/*/*.pdf")))
    return sorted(
        {pdf for pdf in pdfs if is_review_pdf_path(pdf)},
        key=lambda pdf: (review_collection_name(pdf), pdf.stem),
    )


def find_review_source_file(
    source_root: Path,
    review_id: str,
    filename: str,
    *,
    preferred_dir_markers: Iterable[str] = (),
    required: bool = True,
) -> Path | None:
    """Find a review-specific source artifact under an issue/source folder."""
    candidates = [path for path in source_root.rglob(filename) if path.is_file()]
    if not candidates:
        if required:
            raise FileNotFoundError(f"Could not find {filename} under {source_root}")
        return None

    review_marker = review_id.lower()
    markers = [marker.lower() for marker in preferred_dir_markers if marker]

    def sort_key(path: Path) -> tuple[int, int, int, int, str]:
        parts = [part.lower() for part in path.parts]
        preferred_dir_score = (
            0 if any(any(marker in part for part in parts) for marker in markers) else 1
        )
        data_package_score = (
            0 if any(part.startswith(f"{review_marker}-sup-") for part in parts) else 1
        )
        review_file_score = 0 if path.name.lower().startswith(f"{review_marker}-") else 1
        return (preferred_dir_score, data_package_score, review_file_score, len(path.parts), str(path))

    return sorted(candidates, key=sort_key)[0]
