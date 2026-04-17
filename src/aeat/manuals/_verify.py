"""Verification report builder for ``aeat manual verify``.

Walks a committed manual part, validates every JSON file against the
strict schema, and reports dangling cross-references, missing
trilingual completeness, and records lacking reviewer metadata. The
report is a pydantic model so the CLI can render it deterministically
and so tests can assert on its shape.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..config import Settings, load_settings
from ..i18n import Language
from ..logging import get_logger
from ._loader import iter_sections, load_manual, resolve_part_root
from ._schema import ManualId, ManualPart, Section
from .errors import ManifestError, ManualNotFoundError, ManualParseError, ManualReviewRequiredError

_logger = get_logger(__name__)


class VerificationIssue(BaseModel):
    """Single issue flagged by the verifier."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    level: str = Field(description="Either 'error' or 'warning'.")
    code: str = Field(description="Stable identifier for the issue category.")
    message: str = Field(description="Human-readable description, including the offending path.")


class VerificationReport(BaseModel):
    """Aggregate report returned by :func:`verify_manual_dir`."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    manual_id: ManualId
    year: int
    part: ManualPart
    issues: tuple[VerificationIssue, ...] = Field(default_factory=tuple)

    @property
    def errors(self) -> tuple[VerificationIssue, ...]:
        """Return only the ``level == 'error'`` issues."""
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def warnings(self) -> tuple[VerificationIssue, ...]:
        """Return only the ``level == 'warning'`` issues."""
        return tuple(issue for issue in self.issues if issue.level == "warning")

    @property
    def ok(self) -> bool:
        """True when the report contains no ``error`` issues."""
        return not self.errors


def _section_trilingual_warnings(section: Section) -> list[VerificationIssue]:
    """Warn when a ``Section`` is missing ``en`` or ``hu`` translations."""
    issues: list[VerificationIssue] = []
    for field_name, translatable in (("title", section.title), ("summary", section.summary)):
        for lang in (Language.EN, Language.HU):
            if not translatable.get(lang.value):
                issues.append(
                    VerificationIssue(
                        level="warning",
                        code="missing-translation",
                        message=(f"section {section.section_id!r}: {field_name} missing '{lang.value}' translation"),
                    )
                )
    return issues


def _collect_section_ids(sections: tuple[Section, ...]) -> set[str]:
    """Return the set of known section IDs for cross-reference checks."""
    return {section.section_id for section in sections}


def _cross_reference_issues(
    sections: tuple[Section, ...],
    known_section_ids: set[str],
) -> list[VerificationIssue]:
    """Flag rules and sections referencing unknown section IDs."""
    issues: list[VerificationIssue] = []
    for section in sections:
        for target in section.references_sections:
            if target not in known_section_ids:
                issues.append(
                    VerificationIssue(
                        level="error",
                        code="dangling-section-ref",
                        message=(f"section {section.section_id!r} references unknown section {target!r}"),
                    )
                )
        for rule in section.rules:
            for target in rule.references_sections:
                if target not in known_section_ids:
                    issues.append(
                        VerificationIssue(
                            level="error",
                            code="dangling-section-ref",
                            message=(f"rule {rule.rule_id!r} references unknown section {target!r}"),
                        )
                    )
    return issues


def verify_manual_dir(
    *,
    manual_id: ManualId,
    year: int,
    part: ManualPart = ManualPart.SINGLE,
    review_required: bool | None = None,
    settings: Settings | None = None,
) -> VerificationReport:
    """Verify every record under a manual part on disk.

    Args:
        manual_id: Handbook identifier.
        year: Tax year.
        part: Volume split within the year.
        review_required: Reserved for the future soft-review gate
            (sentinel-based reviewer placeholders). In v1 this flag
            has no effect because ``_schema._Reviewer`` already
            enforces a non-empty reviewer at load time; records
            failing that constraint surface as ``load-failed``
            errors. Defaults to the ``AEAT_MANUALS_REVIEW_REQUIRED``
            setting value.
        settings: Optional settings instance.

    Returns:
        A :class:`VerificationReport` summarising every issue found.

    Raises:
        ManualNotFoundError: If neither the structure nor the manifest
            exists for the requested manual part.
    """
    resolved = settings or load_settings()
    # Explicit no-op for v1; kept to lock the CLI surface. See docstring.
    _ = review_required if review_required is not None else resolved.aeat_manuals_review_required

    part_root = resolve_part_root(manual_id=manual_id, year=year, part=part, settings=resolved)
    issues: list[VerificationIssue] = []

    if not part_root.exists():
        raise ManualNotFoundError(f"manual part root does not exist: {part_root}")

    manifest_path = part_root / "manifest.json"
    if not manifest_path.exists():
        issues.append(
            VerificationIssue(
                level="warning",
                code="missing-manifest",
                message=f"{manifest_path} is absent; run 'aeat manual fetch' to materialise it",
            )
        )

    structure_dir = part_root / "structure"
    if not (structure_dir / "manual.json").exists():
        # v1 default state: structure/ is empty. Nothing to validate beyond the manifest.
        return VerificationReport(
            manual_id=manual_id,
            year=year,
            part=part,
            issues=tuple(issues),
        )

    try:
        manual = load_manual(manual_id, year, part, settings=resolved)
    except (ManualParseError, ManualNotFoundError, ManifestError) as exc:
        issues.append(
            VerificationIssue(
                level="error",
                code="load-failed",
                message=str(exc),
            )
        )
        return VerificationReport(
            manual_id=manual_id,
            year=year,
            part=part,
            issues=tuple(issues),
        )

    sections: list[Section] = []
    for section in iter_sections(manual, settings=resolved):
        sections.append(section)
    sections_tuple = tuple(sections)
    known_ids = _collect_section_ids(sections_tuple)

    for section in sections_tuple:
        issues.extend(_section_trilingual_warnings(section))
    issues.extend(_cross_reference_issues(sections_tuple, known_ids))

    _logger.info(
        "verify %s/%s/%s: %d issue(s)",
        manual_id.value,
        year,
        part.value,
        len(issues),
    )
    return VerificationReport(
        manual_id=manual_id,
        year=year,
        part=part,
        issues=tuple(issues),
    )


def raise_on_errors(report: VerificationReport) -> None:
    """Raise :class:`ManualReviewRequiredError` if the report has errors.

    Thin helper so the CLI can collapse a report into a non-zero exit
    without re-implementing the error-check logic.

    Args:
        report: Report produced by :func:`verify_manual_dir`.

    Raises:
        ManualReviewRequiredError: When the report contains any
            ``error``-level issues.
    """
    if not report.ok:
        messages = "; ".join(issue.message for issue in report.errors)
        raise ManualReviewRequiredError(
            f"verification failed for {report.manual_id.value}/{report.year}/{report.part.value}: {messages}"
        )
