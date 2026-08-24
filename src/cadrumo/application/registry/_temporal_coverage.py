"""Validated temporal and authority-grade evidence for registry revisions.

The closure report needs to know whether every registered revision can be
selected by the law axes it declares and whether its declared authority grade
is actually reachable through the validated snapshot boundary.  This module
keeps those two facts together without deciding the broader cross-authority
closure outcome.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator

from ...core import STRICT_FROZEN_CONFIG, RegistryAuthorityGrade, RegistrySelectorPeriodCode
from ...domain.calculations.registry import (
    ModeloId,
    ModeloRevision,
    RegistrySnapshotError,
    RegistryValidationError,
    RevisionId,
    ValidatedRegistryAuthority,
)

TemporalCoverageStatus = Literal["validated", "refused"]
TemporalCoverageFailureCode = Literal[
    "law_selection_refused",
    "selected_revision_mismatch",
    "undeclared_authority_grade",
    "declared_grade_snapshot_refused",
    "snapshot_revision_mismatch",
]


class TemporalRevisionCoverage(BaseModel):
    """Validated temporal evidence for one registered modelo revision.

    A ``validated`` row proves that a coordinate declared by the revision's
    selector chose that same revision without an injected revision id and that
    the validated snapshot boundary admitted its declared authority grade.
    ``refused`` rows retain the exact failed boundary rather than silently
    omitting the revision from the release denominator.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    revision: RevisionId
    filing_year: int = Field(ge=2000, le=2099)
    period: RegistrySelectorPeriodCode
    selected_revision: RevisionId | None = None
    declared_authority_grade: RegistryAuthorityGrade | None = None
    status: TemporalCoverageStatus
    failure_code: TemporalCoverageFailureCode | None = None
    failure_detail: str | None = Field(default=None, min_length=1, max_length=1024)

    @model_validator(mode="after")
    def _validate_outcome_shape(self) -> TemporalRevisionCoverage:
        if self.status == "validated":
            if self.selected_revision != self.revision:
                raise ValueError("validated temporal coverage must select its declared revision")
            if self.declared_authority_grade is None:
                raise ValueError("validated temporal coverage requires a declared authority grade")
            if self.failure_code is not None or self.failure_detail is not None:
                raise ValueError("validated temporal coverage cannot carry a refusal")
            return self
        if self.failure_code is None or self.failure_detail is None:
            raise ValueError("refused temporal coverage requires a typed failure code and detail")
        if self.failure_code == "law_selection_refused":
            if self.selected_revision is not None:
                raise ValueError("law-selection refusal cannot retain a selected revision")
            return self
        if self.failure_code == "selected_revision_mismatch":
            if self.selected_revision is None or self.selected_revision == self.revision:
                raise ValueError("selected-revision mismatch requires a conflicting selected revision")
            return self
        if self.failure_code == "undeclared_authority_grade":
            if self.selected_revision != self.revision:
                raise ValueError("undeclared-grade refusal requires the registered selected revision")
            if self.declared_authority_grade is not None:
                raise ValueError("undeclared-grade refusal cannot carry a declared authority grade")
            return self
        if self.failure_code == "declared_grade_snapshot_refused":
            if self.selected_revision != self.revision:
                raise ValueError("declared-grade snapshot refusal requires the registered selected revision")
            if self.declared_authority_grade is None:
                raise ValueError("declared-grade snapshot refusal requires a declared authority grade")
            return self
        if self.failure_code == "snapshot_revision_mismatch":
            if self.selected_revision is None or self.selected_revision == self.revision:
                raise ValueError("snapshot-revision mismatch requires a conflicting snapshot revision")
            if self.declared_authority_grade is None:
                raise ValueError("snapshot-revision mismatch requires a declared authority grade")
        return self


class TemporalCoverageReport(BaseModel):
    """The complete temporal and authority-grade denominator for one authority."""

    model_config = STRICT_FROZEN_CONFIG

    rows: tuple[TemporalRevisionCoverage, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_revision_coordinates(self) -> TemporalCoverageReport:
        coordinates = tuple((row.modelo, row.revision) for row in self.rows)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("temporal coverage report must contain each modelo revision exactly once")
        return self

    @computed_field
    @property
    def fully_validated(self) -> bool:
        """Return whether every registered revision reached its declared grade."""
        return all(row.status == "validated" for row in self.rows)

    @computed_field
    @property
    def refused_rows(self) -> tuple[TemporalRevisionCoverage, ...]:
        """Return every visible temporal or authority-grade refusal."""
        return tuple(row for row in self.rows if row.status == "refused")


def compose_temporal_coverage(*, authority: ValidatedRegistryAuthority) -> TemporalCoverageReport:
    """Compose temporal evidence from validated, law-selected registry revisions.

    The selection coordinate comes only from the revision's declared selector.
    Each coordinate is first resolved through ``inspect_revision`` without a
    revision-id filter.  A matching revision with a declared authority grade is
    then admitted through ``snapshot`` at that exact grade.  Consequently, an
    ungraded, unselectable, or over-claimed revision remains a row with an
    explicit refusal rather than becoming an absent denominator member.
    """
    authority.validate_registry()
    rows: list[TemporalRevisionCoverage] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            filing_year, period = _law_selection_coordinate(revision)
            rows.append(
                _compose_revision_temporal_coverage(
                    authority=authority,
                    modelo_id=modelo.id,
                    revision_id=revision.id,
                    filing_year=filing_year,
                    period=period,
                    declared_authority_grade=revision.authority_grade,
                ),
            )
    return TemporalCoverageReport(rows=tuple(rows))


def _law_selection_coordinate(revision: ModeloRevision) -> tuple[int, RegistrySelectorPeriodCode]:
    """Return one coordinate declared by a revision's temporal selector.

    The authoritative registry has already validated every selector before this
    projection runs, so absence of both forms is an explicit authority failure
    rather than a reason to manufacture a representative year.
    """
    selector = revision.period_selector
    filing_year = selector.years[0] if selector.years else selector.year_from
    if filing_year is None:
        raise RegistryValidationError(f"revision {revision.id!r} declares no law-selectable filing year")
    return filing_year, selector.periods[0]


def _compose_revision_temporal_coverage(
    *,
    authority: ValidatedRegistryAuthority,
    modelo_id: ModeloId,
    revision_id: RevisionId,
    filing_year: int,
    period: RegistrySelectorPeriodCode,
    declared_authority_grade: RegistryAuthorityGrade | None,
) -> TemporalRevisionCoverage:
    """Build one row, preserving an explicit refusal at each authority boundary."""
    base = {
        "modelo": modelo_id,
        "revision": revision_id,
        "filing_year": filing_year,
        "period": period,
        "declared_authority_grade": declared_authority_grade,
    }
    try:
        inspection = authority.inspect_revision(modelo_id, filing_year=filing_year, period=period)
    except (RegistrySnapshotError, RegistryValidationError) as exc:
        return TemporalRevisionCoverage(
            **base,
            status="refused",
            failure_code="law_selection_refused",
            failure_detail=_failure_detail(exc),
        )
    selected_revision = str(inspection.revision_id)
    if selected_revision != revision_id:
        return TemporalRevisionCoverage(
            **base,
            selected_revision=selected_revision,
            status="refused",
            failure_code="selected_revision_mismatch",
            failure_detail=(
                f"law selection returned revision {selected_revision!r} instead of the registered "
                f"revision {revision_id!r}"
            ),
        )
    if declared_authority_grade is None:
        return TemporalRevisionCoverage(
            **base,
            selected_revision=selected_revision,
            status="refused",
            failure_code="undeclared_authority_grade",
            failure_detail="the law-selected revision declares no authority grade",
        )
    try:
        snapshot = authority.snapshot(
            modelo_id,
            filing_year=filing_year,
            period=period,
            grade=declared_authority_grade,
        )
    except RegistryValidationError as exc:
        return TemporalRevisionCoverage(
            **base,
            selected_revision=selected_revision,
            status="refused",
            failure_code="declared_grade_snapshot_refused",
            failure_detail=_failure_detail(exc),
        )
    snapshot_revision = str(snapshot.revision.id)
    if snapshot_revision != revision_id:
        return TemporalRevisionCoverage(
            **base,
            selected_revision=snapshot_revision,
            status="refused",
            failure_code="snapshot_revision_mismatch",
            failure_detail=(
                f"validated snapshot returned revision {snapshot_revision!r} instead of the registered "
                f"revision {revision_id!r}"
            ),
        )
    return TemporalRevisionCoverage(
        **base,
        selected_revision=snapshot_revision,
        status="validated",
    )


def _failure_detail(error: RegistrySnapshotError | RegistryValidationError) -> str:
    """Keep the first refusal line bounded and stable for report consumers."""
    return str(error).splitlines()[0][:1024]


__all__ = [
    "TemporalCoverageReport",
    "TemporalRevisionCoverage",
    "compose_temporal_coverage",
]
