"""Canonical captured-catalogue selector for Modelo work units.

The selector is deliberately pure: it resolves exact, visible, and
create-or-reuse active-only targets from one supplied :class:`WorkUnitCatalogue`.
Repository and active-bucket observations remain thin capture boundaries.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG, Period
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.identity import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...domain.calculations.registry import RevisionId
from ...domain.modelos import ModeloCode, ModeloError, ModeloValidationError, WorkUnit, WorkUnitCatalogue, WorkUnitState
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol

_BucketId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_RevisionId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
_WorkUnitLookupId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        pattern=r"^(?:[0-9a-f]{12}|[0-9a-f]{64})$",
        min_length=12,
        max_length=64,
    ),
]


class ModeloWorkSelectorState(StrEnum):
    """Resolution state for a visible modelo filing target."""

    ABSENT = "absent"
    RESOLVED = "resolved"


class ModeloWorkSelectionMode(StrEnum):
    """Closed candidate sets accepted by the captured-catalogue selector."""

    VISIBLE_OR_EXACT = "visible_or_exact"
    ACTIVE_NATURAL = "active_natural"


class ModeloWorkSelectorError(ModeloError):
    """Base error for modelo work selector refusals."""


class ModeloWorkNoActiveBucketError(ModeloWorkSelectorError):
    """Raised when a selector requires the active bucket but none is selected."""


class ModeloWorkUnitNotFoundError(ModeloWorkSelectorError, KeyError):
    """Raised when an explicit work-unit id does not exist."""


class ModeloWorkSelectorContradictionError(ModeloWorkSelectorError, ValueError):
    """Raised when exact id and natural-key flags address different work."""


class ModeloWorkUnitCandidate(BaseModel):
    """Human-readable candidate metadata for selector guidance."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: _BucketId
    modelo: ModeloCode
    filing_year: Annotated[int, Field(ge=2000, le=2099)]
    period: Period
    revision_id: _RevisionId
    state: WorkUnitState
    current_calculation_revision_id: CalculationRevisionId | None = None
    filed_calculation_revision_id: CalculationRevisionId | None = None
    current_filing_record_id: FilingRecordId | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_work_unit(cls, unit: WorkUnit) -> ModeloWorkUnitCandidate:
        """Project a work unit into selector-guidance metadata."""
        return cls(
            work_unit_id=unit.work_unit_id,
            short_work_unit_id=unit.work_unit_id[-12:],
            bucket_id=unit.bucket_id,
            modelo=unit.modelo,
            filing_year=unit.filing_year,
            period=unit.period,
            revision_id=unit.revision_id,
            state=unit.state,
            current_calculation_revision_id=unit.current_calculation_revision_id,
            filed_calculation_revision_id=unit.filed_calculation_revision_id,
            current_filing_record_id=unit.current_filing_record_id,
            created_at=unit.created_at.isoformat(),
            updated_at=unit.updated_at.isoformat(),
        )


class ModeloWorkVisibleTargetAmbiguousError(ModeloWorkSelectorError):
    """Raised when a visible target matches multiple work units."""

    def __init__(self, candidates: tuple[ModeloWorkUnitCandidate, ...], *, selector: str | None = None) -> None:
        """Retain candidates and distinguish exact-token ambiguity in the message."""
        self.candidates = candidates
        self.selector = selector
        if selector is None:
            message = "modelo work target is ambiguous; choose a registry revision or exact work_unit_id"
        else:
            message = f"modelo work id selector {selector!r} is ambiguous; use the full 64-character work_unit_id"
        super().__init__(message)


class ModeloWorkRevisionConflictError(ModeloWorkSelectorError):
    """Raised when the requested registry revision conflicts with existing work."""

    def __init__(
        self,
        *,
        requested_revision_id: RevisionId,
        existing: ModeloWorkUnitCandidate,
    ) -> None:
        """Retain the requested assertion and conflicting stored candidate."""
        self.requested_revision_id = requested_revision_id
        self.existing = existing
        super().__init__("modelo work target already has a work unit for a different registry revision")


class ModeloWorkSelectorRequest(BaseModel):
    """Operator-facing modelo work selector."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode | None = None
    filing_year: Annotated[int, Field(ge=2000, le=2099)] | None = None
    period: Period | None = None
    revision_id: _RevisionId | None = None
    bucket_id: _BucketId | None = None
    work_unit_id: _WorkUnitLookupId | None = None

    @field_validator("modelo", mode="before")
    @classmethod
    def _coerce_modelo(cls, value: object) -> ModeloCode | None:
        if value is None or isinstance(value, ModeloCode):
            return value
        if isinstance(value, str):
            return ModeloCode(value)
        raise ModeloValidationError(f"expected ModeloCode or str, got {type(value).__name__}")

    @field_validator("revision_id", "bucket_id")
    @classmethod
    def _normalise_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @property
    def has_visible_target(self) -> bool:
        """Return whether modelo/year/period were all supplied."""
        return self.modelo is not None and self.filing_year is not None and self.period is not None


class ModeloWorkResolution(BaseModel):
    """Resolved selector outcome for a visible modelo filing target."""

    model_config = STRICT_FROZEN_CONFIG

    state: ModeloWorkSelectorState
    bucket_id: _BucketId
    modelo: ModeloCode | None = None
    filing_year: Annotated[int, Field(ge=2000, le=2099)] | None = None
    period: Period | None = None
    requested_revision_id: _RevisionId | None = None
    work_unit: WorkUnit | None = None
    candidates: tuple[ModeloWorkUnitCandidate, ...] = ()


def resolve_modelo_work_bucket(request: ModeloWorkSelectorRequest) -> str:
    """Resolve the selector bucket from an explicit id or the active profile."""
    if request.bucket_id is not None:
        return request.bucket_id
    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        raise ModeloWorkNoActiveBucketError(
            translated_message="errors.refused.modelo_work_selector_no_active_bucket",
            context={"active_bucket_present": False},
        )
    return active_bucket_id


def select_modelo_work_resolution(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
    mode: ModeloWorkSelectionMode = ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
) -> ModeloWorkResolution:
    """Purely resolve exact, visible, or active-only work from one captured catalogue."""
    if request.bucket_id is not None and request.bucket_id != bucket_id:
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
            context={"request_bucket_id": request.bucket_id, "captured_bucket_id": bucket_id},
        )
    if mode is ModeloWorkSelectionMode.ACTIVE_NATURAL and (
        request.work_unit_id is not None or not request.has_visible_target
    ):
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
        )
    if request.work_unit_id is not None:
        return _exact_resolution(request, catalogue=catalogue, bucket_id=bucket_id)
    if not request.has_visible_target:
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
            context={"has_visible_target": False},
        )
    matches = tuple(
        sorted(
            (
                unit
                for unit in catalogue.values()
                if unit.bucket_id == bucket_id
                and unit.modelo == request.modelo
                and unit.filing_year == request.filing_year
                and unit.period == request.period
                and (mode is not ModeloWorkSelectionMode.ACTIVE_NATURAL or unit.state is WorkUnitState.BORRADOR)
            ),
            key=lambda unit: (unit.revision_id, unit.created_at, unit.work_unit_id),
        ),
    )
    return _natural_resolution(request, bucket_id=bucket_id, matches=matches)


def _exact_resolution(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    assert request.work_unit_id is not None
    matches = tuple(
        sorted(
            (
                unit
                for unit in catalogue.values()
                if unit.bucket_id == bucket_id
                and (
                    unit.work_unit_id.startswith(request.work_unit_id)
                    or unit.work_unit_id.endswith(request.work_unit_id)
                )
            ),
            key=lambda unit: unit.work_unit_id,
        ),
    )
    if not matches:
        raise ModeloWorkUnitNotFoundError(
            translated_message="errors.error.modelo_work_selector_unit_not_found",
            context={"work_unit_id": request.work_unit_id},
        )
    if len(matches) > 1:
        raise ModeloWorkVisibleTargetAmbiguousError(
            tuple(ModeloWorkUnitCandidate.from_work_unit(unit) for unit in matches),
            selector=request.work_unit_id,
        )
    work_unit = matches[0]
    _validate_explicit_work_unit_matches_request(work_unit, request, resolved_bucket_id=bucket_id)
    return ModeloWorkResolution(
        state=ModeloWorkSelectorState.RESOLVED,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        requested_revision_id=request.revision_id,
        work_unit=work_unit,
        candidates=(ModeloWorkUnitCandidate.from_work_unit(work_unit),),
    )


def _natural_resolution(
    request: ModeloWorkSelectorRequest,
    *,
    bucket_id: str,
    matches: tuple[WorkUnit, ...],
) -> ModeloWorkResolution:
    if not matches:
        return ModeloWorkResolution(
            state=ModeloWorkSelectorState.ABSENT,
            bucket_id=bucket_id,
            modelo=request.modelo,
            filing_year=request.filing_year,
            period=request.period,
            requested_revision_id=request.revision_id,
        )
    if len(matches) > 1:
        raise ModeloWorkVisibleTargetAmbiguousError(
            tuple(ModeloWorkUnitCandidate.from_work_unit(unit) for unit in matches),
        )
    work_unit = matches[0]
    if request.revision_id is not None and request.revision_id != work_unit.revision_id:
        raise ModeloWorkRevisionConflictError(
            requested_revision_id=request.revision_id,
            existing=ModeloWorkUnitCandidate.from_work_unit(work_unit),
        )
    return ModeloWorkResolution(
        state=ModeloWorkSelectorState.RESOLVED,
        bucket_id=bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        requested_revision_id=request.revision_id,
        work_unit=work_unit,
        candidates=(ModeloWorkUnitCandidate.from_work_unit(work_unit),),
    )


def _validate_explicit_work_unit_matches_request(
    work_unit: WorkUnit,
    request: ModeloWorkSelectorRequest,
    *,
    resolved_bucket_id: str,
) -> None:
    expected: tuple[tuple[str, object | None, object], ...] = (
        ("bucket_id", resolved_bucket_id, work_unit.bucket_id),
        ("modelo", request.modelo, work_unit.modelo),
        ("filing_year", request.filing_year, work_unit.filing_year),
        ("period", request.period, work_unit.period),
        ("revision_id", request.revision_id, work_unit.revision_id),
    )
    for field_name, supplied, actual in expected:
        if supplied is not None and supplied != actual:
            raise ModeloWorkSelectorContradictionError(
                translated_message="errors.refused.modelo_work_selector_contradiction",
                context={
                    "work_unit_id": work_unit.work_unit_id,
                    "field_name": field_name,
                    "work_unit_value": str(actual),
                    "selector_value": str(supplied),
                },
            )


def resolve_active_natural_modelo_work_unit(
    request: ModeloWorkSelectorRequest,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> ModeloWorkResolution:
    """Capture and resolve an active natural target for create-or-reuse operations."""
    bucket_id = resolve_modelo_work_bucket(request)
    repo = repository or WorkUnitCatalogueRepository(bucket_id=bucket_id)
    return select_modelo_work_resolution(
        request,
        catalogue=repo.load(),
        bucket_id=bucket_id,
        mode=ModeloWorkSelectionMode.ACTIVE_NATURAL,
    )


def resolve_modelo_work_unit(
    request: ModeloWorkSelectorRequest,
    *,
    repository: WorkUnitCatalogueRepositoryProtocol | None = None,
) -> ModeloWorkResolution:
    """Capture and resolve one work unit by exact id or visible target."""
    bucket_id = resolve_modelo_work_bucket(request)
    repo = repository or WorkUnitCatalogueRepository(bucket_id=bucket_id)
    return select_modelo_work_resolution(request, catalogue=repo.load(), bucket_id=bucket_id)


__all__ = [
    "ModeloWorkNoActiveBucketError",
    "ModeloWorkResolution",
    "ModeloWorkRevisionConflictError",
    "ModeloWorkSelectionMode",
    "ModeloWorkSelectorContradictionError",
    "ModeloWorkSelectorError",
    "ModeloWorkSelectorRequest",
    "ModeloWorkSelectorState",
    "ModeloWorkUnitCandidate",
    "ModeloWorkUnitNotFoundError",
    "ModeloWorkVisibleTargetAmbiguousError",
    "resolve_active_natural_modelo_work_unit",
    "resolve_modelo_work_bucket",
    "resolve_modelo_work_unit",
    "select_modelo_work_resolution",
]
