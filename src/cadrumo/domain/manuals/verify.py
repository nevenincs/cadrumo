"""Verification report builder for ``aeat manual verify``.

:func:`verify_manual_dir` walks a committed manual part, validates every JSON
file against the strict :class:`Manual` and :class:`Section` schema, and reports
dangling cross-references, missing multilingual completeness, and load failures
as :class:`ManualVerificationIssue` rows in a
:class:`ManualVerificationReport`.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.config import Settings, load_settings
from ...core.errors.severity import BaseSeverity
from ...core.i18n import tr
from ...core.logging import get_logger
from ...core.models import STRICT_FROZEN_CONFIG
from .errors import ManifestError, ManualNotFoundError, ManualParseError, ManualReviewRequiredError
from .loader import iter_sections, load_manual, resolve_part_root
from .schema import ManualId, ManualPart, Section

_logger = get_logger(__name__)


class ManualVerificationIssue(BaseModel):
    """Single issue flagged by the verifier.

    Attributes:
        level: Severity, shared with every other diagnostic and validation
            issue in the project via :class:`~cadrumo.core.errors.BaseSeverity`.
        code: Stable identifier for the issue category.
        message: Human-readable description, including the offending path.
    """

    model_config = STRICT_FROZEN_CONFIG

    level: BaseSeverity
    code: str = Field(description="Stable identifier for the issue category.")
    message: str = Field(description="Human-readable description, including the offending path.")


class ManualVerificationReport(BaseModel):
    """Aggregate report returned by :func:`verify_manual_dir`.

    Attributes:
        manual_id: Identifier of the verified handbook.
        year: Tax year.
        part: Volume split within the year.
        issues: Every :class:`ManualVerificationIssue` collected during
            the walk.
    """

    model_config = STRICT_FROZEN_CONFIG

    manual_id: ManualId
    year: int
    part: ManualPart
    issues: tuple[ManualVerificationIssue, ...] = Field(default_factory=tuple)

    @property
    def errors(self) -> tuple[ManualVerificationIssue, ...]:
        """Return only the :class:`ManualVerificationIssue` items at :attr:`~cadrumo.core.errors.BaseSeverity.ERROR`."""
        return tuple(issue for issue in self.issues if issue.level is BaseSeverity.ERROR)

    @property
    def warnings(self) -> tuple[ManualVerificationIssue, ...]:
        """Return only the issues at :attr:`~cadrumo.core.errors.BaseSeverity.WARNING`.

        Returns:
            Tuple of :class:`ManualVerificationIssue` objects with warning-level severity.
        """
        return tuple(issue for issue in self.issues if issue.level is BaseSeverity.WARNING)

    @property
    def ok(self) -> bool:
        """True when the report contains no ``error`` issues."""
        return not self.errors


def _section_multilingual_warnings(section: Section) -> list[ManualVerificationIssue]:
    """Warn when a :class:`~cadrumo.domain.manuals.Section` is missing translation keys."""
    issues: list[ManualVerificationIssue] = []
    for field_name, translatable in (("title", section.title), ("summary", section.summary)):
        if not translatable:
            issues.append(
                ManualVerificationIssue(
                    level=BaseSeverity.WARNING,
                    code="missing-translation",
                    message=tr(
                        "cli.registry.manuals.verify_missing_translation",
                        default="section %{section_id}: %{field_name} missing translation key",
                        section_id=section.section_id,
                        field_name=field_name,
                    ),
                ),
            )
    return issues


def _collect_section_ids(sections: tuple[Section, ...]) -> set[str]:
    """Return the set of known section IDs for cross-reference checks."""
    return {section.section_id for section in sections}


def _cross_reference_issues(
    sections: tuple[Section, ...],
    known_section_ids: set[str],
) -> list[ManualVerificationIssue]:
    """Flag rules and sections referencing unknown section IDs."""
    issues: list[ManualVerificationIssue] = []
    for section in sections:
        for target in section.references_sections:
            if target not in known_section_ids:
                issues.append(
                    ManualVerificationIssue(
                        level=BaseSeverity.ERROR,
                        code="dangling-section-ref",
                        message=tr(
                            "cli.registry.manuals.verify_dangling_section_ref",
                            default="section %{section_id} references unknown section %{target}",
                            section_id=section.section_id,
                            target=target,
                        ),
                    ),
                )
        for rule in section.rules:
            for target in rule.references_sections:
                if target not in known_section_ids:
                    issues.append(
                        ManualVerificationIssue(
                            level=BaseSeverity.ERROR,
                            code="dangling-section-ref",
                            message=tr(
                                "cli.registry.manuals.verify_dangling_rule_section_ref",
                                default="rule %{rule_id} references unknown section %{target}",
                                rule_id=rule.rule_id,
                                target=target,
                            ),
                        ),
                    )
    return issues


def verify_manual_dir(
    *,
    manual_id: ManualId,
    year: int,
    part: ManualPart = ManualPart.SINGLE,
    review_required: bool | None = None,
    settings: Settings | None = None,
) -> ManualVerificationReport:
    """Verify every record under a manual part on disk.

    Args:
        manual_id: Handbook identifier.
        year: Tax year.
        part: Volume split within the year.
        review_required: Reserved for the future soft-review gate
            (sentinel-based reviewer placeholders). Currently this
            flag has no effect because the ``_Reviewer`` constrained
            type already enforces a non-empty reviewer at load time;
            records failing that constraint surface as ``load-failed``
            errors. Defaults to the ``CADRUMO_MANUALS_REVIEW_REQUIRED``
            setting value.
        settings: Optional settings instance.

    Returns:
        A :class:`ManualVerificationReport` summarising every issue found.

    Raises:
        ManualNotFoundError: If neither the structure nor the manifest
            exists for the requested manual part.
    """
    resolved = settings or load_settings()
    # Explicit no-op for v1; kept to lock the CLI surface. See docstring.
    _ = review_required if review_required is not None else resolved.cadrumo_manuals_review_required

    part_root = resolve_part_root(manual_id=manual_id, year=year, part=part, settings=resolved)
    issues: list[ManualVerificationIssue] = []

    if not part_root.exists():
        raise ManualNotFoundError(f"manual part root does not exist: {part_root}")

    manifest_path = part_root / "manifest.json"
    if not manifest_path.exists():
        issues.append(
            ManualVerificationIssue(
                level=BaseSeverity.WARNING,
                code="missing-manifest",
                message=tr(
                    "cli.registry.manuals.verify_missing_manifest",
                    default="%{manifest_path} is absent; run 'aeat manual fetch' to materialise it",
                    manifest_path=manifest_path,
                ),
            ),
        )

    structure_dir = part_root / "structure"
    if not (structure_dir / "manual.json").exists():
        # Default state: structure/ is empty. Nothing to validate beyond the manifest.
        return ManualVerificationReport(
            manual_id=manual_id,
            year=year,
            part=part,
            issues=tuple(issues),
        )

    try:
        manual = load_manual(manual_id, year, part, settings=resolved)
    except (ManualParseError, ManualNotFoundError, ManifestError) as exc:
        _logger.warning(
            "manual load failed %s/%s/%s",
            manual_id.value,
            year,
            part.value,
            exc_info=True,
        )
        issues.append(
            ManualVerificationIssue(
                level=BaseSeverity.ERROR,
                code="load-failed",
                message=str(exc),
            ),
        )
        return ManualVerificationReport(
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
        issues.extend(_section_multilingual_warnings(section))
    issues.extend(_cross_reference_issues(sections_tuple, known_ids))

    _logger.debug(
        "verify %s/%s/%s: %d issue(s)",
        manual_id.value,
        year,
        part.value,
        len(issues),
    )
    return ManualVerificationReport(
        manual_id=manual_id,
        year=year,
        part=part,
        issues=tuple(issues),
    )


def raise_on_errors(report: ManualVerificationReport) -> None:
    """Raise :exc:`ManualReviewRequiredError` if the report has errors.

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
            translated_message="cli.registry.manuals.verify_failed",
            context={
                "manual_id": report.manual_id.value,
                "year": report.year,
                "part": report.part.value,
                "messages": messages,
            },
        )
