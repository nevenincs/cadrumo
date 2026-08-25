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
    RegistrySnapshotError,
    RegistryValidationError,
    RevisionId,
    ValidatedRegistryAuthority,
    coverage_assessment_horizon,
    revision_selection_coordinates,
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
    """Validated temporal evidence for one law-selected revision coordinate.

    A ``validated`` row proves that its exact filing-year and declared-period
    selector coordinate chose the owning revision without an injected revision
    id and that the validated snapshot boundary admitted its declared authority
    grade.  ``refused`` rows retain the failed cell rather than allowing a
    first-year success to hide a later unsupported span.
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


class TemporalRevisionCoverageSummary(BaseModel):
    """Full temporal matrix result for one registered revision.

    The release predicate remains revision-scoped, while its temporal limb is
    now derived from every coordinate that revision claims through the current
    supported-year horizon.  This summary is therefore an aggregation of the
    cells, never a separately selected representative coordinate.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    revision: RevisionId
    declared_authority_grade: RegistryAuthorityGrade | None = None
    coordinates: tuple[TemporalRevisionCoverage, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_coordinate_membership(self) -> TemporalRevisionCoverageSummary:
        coordinates = tuple((row.filing_year, row.period) for row in self.coordinates)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("temporal revision coverage cannot contain a coordinate more than once")
        if coordinates != tuple(sorted(coordinates)):
            raise ValueError("temporal revision coverage coordinates must be deterministically ordered")
        for row in self.coordinates:
            if row.modelo != self.modelo or row.revision != self.revision:
                raise ValueError("temporal revision coverage coordinate must match its summary revision")
            if row.declared_authority_grade is not self.declared_authority_grade:
                raise ValueError("temporal revision coverage coordinate must match its summary authority grade")
        return self

    @computed_field
    @property
    def status(self) -> TemporalCoverageStatus:
        """Return validated only when every claimed coordinate validated."""
        return "validated" if all(row.status == "validated" for row in self.coordinates) else "refused"

    @computed_field
    @property
    def failure_code(self) -> TemporalCoverageFailureCode | None:
        """Return the first deterministic failure while retaining all failed cells."""
        return next((row.failure_code for row in self.coordinates if row.status == "refused"), None)

    @computed_field
    @property
    def failure_detail(self) -> str | None:
        """Return the first deterministic failure detail for release rendering."""
        return next((row.failure_detail for row in self.coordinates if row.status == "refused"), None)

    @computed_field
    @property
    def refused_coordinates(self) -> tuple[TemporalRevisionCoverage, ...]:
        """Expose every refused coordinate rather than reducing it to one summary field."""
        return tuple(row for row in self.coordinates if row.status == "refused")


class TemporalCoverageReport(BaseModel):
    """The complete temporal and authority-grade denominator for one authority."""

    model_config = STRICT_FROZEN_CONFIG

    rows: tuple[TemporalRevisionCoverage, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_matrix_coordinates(self) -> TemporalCoverageReport:
        coordinates = tuple((row.modelo, row.revision, row.filing_year, row.period) for row in self.rows)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("temporal coverage report must contain each law-selected coordinate exactly once")
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

    @computed_field
    @property
    def revision_summaries(self) -> tuple[TemporalRevisionCoverageSummary, ...]:
        """Aggregate every matrix cell back to the release predicate's revision denominator."""
        grouped: dict[tuple[ModeloId, RevisionId], list[TemporalRevisionCoverage]] = {}
        for row in self.rows:
            grouped.setdefault((row.modelo, row.revision), []).append(row)
        return tuple(
            TemporalRevisionCoverageSummary(
                modelo=modelo,
                revision=revision,
                declared_authority_grade=coordinates[0].declared_authority_grade,
                coordinates=tuple(sorted(coordinates, key=lambda row: (row.filing_year, row.period))),
            )
            for (modelo, revision), coordinates in sorted(grouped.items(), key=lambda item: item[0])
        )


def compose_temporal_coverage(*, authority: ValidatedRegistryAuthority) -> TemporalCoverageReport:
    """Compose temporal evidence from validated, law-selected registry revisions.

    Every coordinate comes only from the revision's declared selector through
    the registry-supported assessment horizon.  Each is resolved through
    ``inspect_revision`` without a revision-id filter, then admitted through
    ``snapshot`` at the revision's exact grade.  Consequently, an ungraded,
    unselectable, or over-claimed later cell remains visible rather than being
    concealed by an earlier representative coordinate.
    """
    authority.validate_registry()
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    rows: list[TemporalRevisionCoverage] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            rows.extend(
                _compose_revision_temporal_coverage(
                    authority=authority,
                    modelo_id=modelo.id,
                    revision_id=revision.id,
                    filing_year=filing_year,
                    period=period,
                    declared_authority_grade=revision.authority_grade,
                )
                for filing_year, period in revision_selection_coordinates(
                    revision,
                    assessment_horizon=assessment_horizon,
                )
            )
    return TemporalCoverageReport(rows=tuple(rows))


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
    try:
        inspection = authority.inspect_revision(modelo_id, filing_year=filing_year, period=period)
    except (RegistrySnapshotError, RegistryValidationError) as exc:
        return TemporalRevisionCoverage(
            modelo=modelo_id,
            revision=revision_id,
            filing_year=filing_year,
            period=period,
            declared_authority_grade=declared_authority_grade,
            status="refused",
            failure_code="law_selection_refused",
            failure_detail=_failure_detail(exc),
        )
    selected_revision = str(inspection.revision_id)
    if selected_revision != revision_id:
        return TemporalRevisionCoverage(
            modelo=modelo_id,
            revision=revision_id,
            filing_year=filing_year,
            period=period,
            declared_authority_grade=declared_authority_grade,
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
            modelo=modelo_id,
            revision=revision_id,
            filing_year=filing_year,
            period=period,
            declared_authority_grade=declared_authority_grade,
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
            modelo=modelo_id,
            revision=revision_id,
            filing_year=filing_year,
            period=period,
            declared_authority_grade=declared_authority_grade,
            selected_revision=selected_revision,
            status="refused",
            failure_code="declared_grade_snapshot_refused",
            failure_detail=_failure_detail(exc),
        )
    snapshot_revision = str(snapshot.revision.id)
    if snapshot_revision != revision_id:
        return TemporalRevisionCoverage(
            modelo=modelo_id,
            revision=revision_id,
            filing_year=filing_year,
            period=period,
            declared_authority_grade=declared_authority_grade,
            selected_revision=snapshot_revision,
            status="refused",
            failure_code="snapshot_revision_mismatch",
            failure_detail=(
                f"validated snapshot returned revision {snapshot_revision!r} instead of the registered "
                f"revision {revision_id!r}"
            ),
        )
    return TemporalRevisionCoverage(
        modelo=modelo_id,
        revision=revision_id,
        filing_year=filing_year,
        period=period,
        declared_authority_grade=declared_authority_grade,
        selected_revision=snapshot_revision,
        status="validated",
    )


def _failure_detail(error: RegistrySnapshotError | RegistryValidationError) -> str:
    """Keep the first refusal line bounded and stable for report consumers."""
    return str(error).splitlines()[0][:1024]


__all__ = [
    "TemporalCoverageReport",
    "TemporalRevisionCoverage",
    "TemporalRevisionCoverageSummary",
    "compose_temporal_coverage",
]
