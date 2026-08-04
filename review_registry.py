"""Shared source-package registry for the 20 retrieval-bias review experiments.

Issue 6 packages are stored as extracted directories, while Issue 7 packages
remain ZIP archives.  The aggregate analyses and demo use this registry so
they read the same included/excluded RIS and analysis-data sources without
copying package-layout assumptions into each consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parent
RETRIEVAL_BIAS_DIR = Path(__file__).resolve().parent
SOURCE_REVIEWS_DIR = REPO_ROOT / "source_reviews"

SOURCE_FILENAMES = {
    "included_ris": "{review}-included.ris",
    "excluded_ris": "{review}-excluded.ris",
    "analysis_rows": "{review}-data-rows.csv",
}


@dataclass(frozen=True)
class ReviewSource:
    """Describe one review experiment and its Cochrane source package."""

    review_id: str
    review_title: str
    source_package: Path

    @property
    def matches_path(self) -> Path:
        return (
            RETRIEVAL_BIAS_DIR
            / self.review_id
            / f"{self.review_id.lower()}_role_study_matches.csv"
        )

    @property
    def readme_path(self) -> Path:
        return RETRIEVAL_BIAS_DIR / self.review_id / "README.md"

    def source_locator(self, source_kind: str) -> tuple[Path, str | None]:
        """Return the package path and optional ZIP member for one source kind."""

        try:
            filename = SOURCE_FILENAMES[source_kind].format(review=self.review_id)
        except KeyError as exc:
            raise ValueError(f"Unknown review source kind: {source_kind}") from exc

        if not self.source_package.exists():
            relative_package = self.source_package.relative_to(REPO_ROOT)
            raise FileNotFoundError(
                f"{self.review_id}: missing source package {relative_package}. "
                "Restore source_reviews/ from the former parent repo to regenerate "
                "review analyses, cross-review characteristics, citation audits, or "
                "the demo data."
            )

        if self.source_package.suffix == ".zip":
            with ZipFile(self.source_package) as archive:
                matches = [
                    member
                    for member in archive.namelist()
                    if member.endswith(f"/{filename}") or member == filename
                ]
            if len(matches) != 1:
                raise ValueError(
                    f"{self.review_id}: expected one {filename} in "
                    f"{self.source_package}, found {len(matches)}"
                )
            return self.source_package, matches[0]

        matches = list(self.source_package.rglob(filename))
        if len(matches) != 1:
            raise ValueError(
                f"{self.review_id}: expected one {filename} below "
                f"{self.source_package}, found {len(matches)}"
            )
        return matches[0], None

    def read_source_text(self, source_kind: str) -> str:
        """Read one RIS/CSV source from either an extracted package or ZIP."""

        path, member = self.source_locator(source_kind)
        if member is None:
            return path.read_text(encoding="utf-8-sig")
        with ZipFile(path) as archive:
            return archive.read(member).decode("utf-8-sig")

    def display_source(self, source_kind: str) -> str:
        """Return a repository-relative source locator for reporting."""

        path, member = self.source_locator(source_kind)
        display_path = str(path.relative_to(REPO_ROOT))
        return f"{display_path} :: {member}" if member else display_path


REVIEW_SOURCES = {
    source.review_id: source
    for source in (
        ReviewSource(
            "CD000510",
            "Prophylactic versus selective surfactant administration in preterm infants",
            SOURCE_REVIEWS_DIR / "2026_issue_7" / "CD000510-dataPackage.zip",
        ),
        ReviewSource(
            "CD001452",
            "Venepuncture versus heel lance for blood sampling in term neonates",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD001452-SUP-06-dataPackage.zip",
        ),
        ReviewSource(
            "CD005354",
            "Recombinant follicle-stimulating hormone (rFSH) versus other "
            "recombinant or urinary gonadotropins for ovarian stimulation in "
            "assisted reproductive technology cycles",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD005354-SUP-07-dataPackage.zip",
        ),
        ReviewSource(
            "CD007654",
            "Long-term effects of weight-reducing drugs in people with hypertension",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD007654-SUP-06-dataPackage",
        ),
        ReviewSource(
            "CD007912",
            "Exercise for osteoarthritis of the hip",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD007912-SUP-07-dataPackage.zip",
        ),
        ReviewSource(
            "CD009532",
            "Oral or parenteral iron supplementation to reduce deferral, iron "
            "deficiency and/or anaemia in blood donors",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD009532-SUP-08-dataPackage",
        ),
        ReviewSource(
            "CD009958",
            "Repositioning for pressure injury prevention in adults",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD009958-SUP-07-dataPackage",
        ),
        ReviewSource(
            "CD010051",
            "Topical ciclosporine A therapy for dry eye disease",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD010051-SUP-07-dataPackage.zip",
        ),
        ReviewSource(
            "CD010461",
            "Advanced sperm selection techniques for assisted reproduction",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD010461-SUP-07-dataPackage",
        ),
        ReviewSource(
            "CD012161",
            "(Ultra-)short-acting insulin analogues for adults with type 1 "
            "diabetes mellitus on multiple daily injections: a network meta-analysis",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD012161-SUP-06-dataPackage",
        ),
        ReviewSource(
            "CD012751",
            "Biologic drugs for induction and maintenance of remission in Crohn's "
            "disease: a network meta-analysis",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD012751-SUP-07-dataPackage",
        ),
        ReviewSource(
            "CD013776",
            "Blue versus white light for transurethral resection of non-muscle "
            "invasive bladder cancer",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD013776-SUP-06-dataPackage",
        ),
        ReviewSource(
            "CD015136",
            "Clinical effectiveness of telepharmacy services in patients with "
            "non-communicable diseases in ambulatory care settings",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD015136-SUP-08-dataPackage",
        ),
        ReviewSource(
            "CD015156",
            "Non-surgical treatment for lower limb apophyseal injuries",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD015156-SUP-07-dataPackage.zip",
        ),
        ReviewSource(
            "CD015186",
            "Minimally invasive trabecular meshwork surgery for open-angle glaucoma",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD015186-SUP-08-dataPackage.zip",
        ),
        ReviewSource(
            "CD015264",
            "Vitamin B12 supplementation for growth, development, and cognition "
            "in children",
            SOURCE_REVIEWS_DIR
            / "2026_issue_6"
            / "CD015264-SUP-08-dataPackage",
        ),
        ReviewSource(
            "CD015898",
            "Larger versus smaller red blood cell volume per transfusion in "
            "hospitalized adults, children and preterm neonates",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD015898-SUP-07-dataPackage.zip",
        ),
        ReviewSource(
            "CD015934",
            "Interventions for smoking cessation in inpatient psychiatry settings",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD015934-SUP-07-dataPackage.zip",
        ),
        ReviewSource(
            "CD016085",
            "Blood pressure management in reperfused ischemic stroke",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD016085-SUP-08-dataPackage.zip",
        ),
        ReviewSource(
            "CD016104",
            "Perioperative immune checkpoint inhibitors with or without "
            "chemotherapy versus placebo/no treatment in elderly people with "
            "localized non-small cell lung cancer",
            SOURCE_REVIEWS_DIR
            / "2026_issue_7"
            / "CD016104-SUP-07-dataPackage.zip",
        ),
    )
}


def review_sources() -> tuple[ReviewSource, ...]:
    """Return all configured review sources in review-ID order."""

    return tuple(REVIEW_SOURCES[review_id] for review_id in sorted(REVIEW_SOURCES))
