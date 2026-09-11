"""Pure captured-catalogue selection for Modelo work units.

The selector owns exact, operator-short, visible, and active-natural matching
over one supplied catalogue. Repository and active-bucket observations remain
at the application addressing boundary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState

_RevisionId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
_OperatorWorkUnitLookupId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        pattern=r"^[0-9a-f]{12}$",
        min_length=12,
        max_length=12,
    ),
]


class ModeloWorkSelectorState(StrEnum):
    """Closed result states for visible natural work lookup."""

    ABSENT = "absent"
    RESOLVED = "resolved"


class ModeloWorkSelectionMode(StrEnum):
    """Closed candidate universes consumed by the one pure selector."""

    VISIBLE_OR_EXACT = "visible_or_exact"
    ACTIVE_NATURAL = "active_natural"


class ModeloWorkUnitCandidate(BaseModel):
    """Stable candidate projection used in ambiguity and assertion refusals."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: BucketId
    modelo: ModeloCode
    filing_year: FilingYear
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
        """Project an existing unit without rereading its catalogue."""
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


class ModeloWorkSelectorRequest(BaseModel):
    """Exact or visible address operands for a captured Modelo work catalogue."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode | None = None
    filing_year: FilingYear | None = None
    period: Period | None = None
    revision_id: _RevisionId | None = None
    bucket_id: BucketId | None = None
    work_unit_id: WorkUnitId | None = None
    operator_work_unit_id: _OperatorWorkUnitLookupId | None = None

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
        """Return whether the complete natural coordinate was supplied."""
        return self.modelo is not None and self.filing_year is not None and self.period is not None

    @property
    def has_exact_target(self) -> bool:
        """Return whether either strict or operator-only exact lookup was supplied."""
        return self.work_unit_id is not None or self.operator_work_unit_id is not None


class ModeloWorkResolution(BaseModel):
    """Immutable result of selecting one supplied work catalogue."""

    model_config = STRICT_FROZEN_CONFIG

    state: ModeloWorkSelectorState
    bucket_id: BucketId
    modelo: ModeloCode | None = None
    filing_year: FilingYear | None = None
    period: Period | None = None
    requested_revision_id: _RevisionId | None = None
    work_unit: WorkUnit | None = None
    candidates: tuple[ModeloWorkUnitCandidate, ...] = ()


def select_modelo_work_resolution(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
    mode: ModeloWorkSelectionMode = ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
) -> ModeloWorkResolution:
    """Purely select all-state exact/visible or active-only natural work from *catalogue*."""
    _validate_modelo_work_selection_request(request, bucket_id=bucket_id, mode=mode)
    if request.work_unit_id is not None:
        return _resolve_exact_work_unit_selection(request, catalogue=catalogue, bucket_id=bucket_id)
    if request.operator_work_unit_id is not None:
        return _resolve_operator_work_unit_selection(request, catalogue=catalogue, bucket_id=bucket_id)
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
        )
    )
    return _select_natural_modelo_work_resolution(request, bucket_id=bucket_id, matches=matches)


def _validate_modelo_work_selection_request(
    request: ModeloWorkSelectorRequest,
    *,
    bucket_id: str,
    mode: ModeloWorkSelectionMode,
) -> None:
    """Reject selector combinations that cannot describe one selection mode."""
    from .work_addressing import ModeloWorkSelectorContradictionError

    if request.bucket_id is not None and request.bucket_id != bucket_id:
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
            context={"request_bucket_id": request.bucket_id, "captured_bucket_id": bucket_id},
        )
    if request.work_unit_id is not None and request.operator_work_unit_id is not None:
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
        )
    if mode is ModeloWorkSelectionMode.ACTIVE_NATURAL and (request.has_exact_target or not request.has_visible_target):
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
        )
    if not request.has_exact_target and not request.has_visible_target:
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
            context={"has_visible_target": False},
        )


def _resolve_exact_work_unit_selection(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Resolve a full work-unit id and assert any supplied coordinates."""
    from .work_addressing import ModeloWorkUnitNotFoundError

    matches = tuple(
        sorted(
            (
                unit
                for unit in catalogue.values()
                if unit.bucket_id == bucket_id and unit.work_unit_id == request.work_unit_id
            ),
            key=lambda unit: unit.work_unit_id,
        )
    )
    if not matches:
        raise ModeloWorkUnitNotFoundError(
            translated_message="errors.error.modelo_work_selector_unit_not_found",
            context={"work_unit_id": request.work_unit_id},
        )
    work_unit = next(iter(matches))
    _assert_exact_coordinates(work_unit, request, bucket_id=bucket_id)
    return _resolved_modelo_work_resolution(work_unit, requested_revision_id=request.revision_id)


def _resolve_operator_work_unit_selection(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Resolve a twelve-character operator id, refusing absent or ambiguous matches."""
    from .work_addressing import (
        ModeloWorkSelectorContradictionError,
        ModeloWorkUnitNotFoundError,
        ModeloWorkVisibleTargetAmbiguousError,
    )

    operator_id = request.operator_work_unit_id
    if operator_id is None or len(operator_id) != 12:
        raise ModeloWorkSelectorContradictionError(
            translated_message="errors.refused.modelo_work_selector_contradiction",
        )
    matches = tuple(
        sorted(
            (
                unit
                for unit in catalogue.values()
                if unit.bucket_id == bucket_id
                and (unit.work_unit_id.startswith(operator_id) or unit.work_unit_id.endswith(operator_id))
            ),
            key=lambda unit: unit.work_unit_id,
        )
    )
    if not matches:
        raise ModeloWorkUnitNotFoundError(
            translated_message="errors.error.modelo_work_selector_unit_not_found",
            context={"work_unit_id": operator_id},
        )
    if len(matches) > 1:
        raise ModeloWorkVisibleTargetAmbiguousError(
            tuple(ModeloWorkUnitCandidate.from_work_unit(unit) for unit in matches),
            selector=operator_id,
        )
    work_unit = next(iter(matches))
    _assert_exact_coordinates(work_unit, request, bucket_id=bucket_id)
    return _resolved_modelo_work_resolution(work_unit, requested_revision_id=request.revision_id)


def _select_natural_modelo_work_resolution(
    request: ModeloWorkSelectorRequest, *, bucket_id: str, matches: tuple[WorkUnit, ...]
) -> ModeloWorkResolution:
    from .work_addressing import ModeloWorkRevisionConflictError, ModeloWorkVisibleTargetAmbiguousError

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
    work_unit = next(iter(matches))
    if request.revision_id is not None and request.revision_id != work_unit.revision_id:
        raise ModeloWorkRevisionConflictError(
            requested_revision_id=request.revision_id,
            existing=ModeloWorkUnitCandidate.from_work_unit(work_unit),
        )
    return _resolved_modelo_work_resolution(work_unit, requested_revision_id=request.revision_id)


def _resolved_modelo_work_resolution(work_unit: WorkUnit, *, requested_revision_id: str | None) -> ModeloWorkResolution:
    return ModeloWorkResolution(
        state=ModeloWorkSelectorState.RESOLVED,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        requested_revision_id=requested_revision_id,
        work_unit=work_unit,
        candidates=(ModeloWorkUnitCandidate.from_work_unit(work_unit),),
    )


def _assert_exact_coordinates(work_unit: WorkUnit, request: ModeloWorkSelectorRequest, *, bucket_id: str) -> None:
    from .work_addressing import ModeloWorkSelectorContradictionError

    for field_name, supplied, actual in (
        ("bucket_id", bucket_id, work_unit.bucket_id),
        ("modelo", request.modelo, work_unit.modelo),
        ("filing_year", request.filing_year, work_unit.filing_year),
        ("period", request.period, work_unit.period),
        ("revision_id", request.revision_id, work_unit.revision_id),
    ):
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


def resolve_modelo_work_bucket(request: ModeloWorkSelectorRequest) -> str:
    """Capture the explicit or active bucket outside the pure selector."""
    from .work_addressing import ModeloWorkNoActiveBucketError

    if request.bucket_id is not None:
        return request.bucket_id
    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        raise ModeloWorkNoActiveBucketError(
            translated_message="errors.refused.modelo_work_selector_no_active_bucket",
            context={"active_bucket_present": False},
        )
    return active_bucket_id


__all__ = [
    "ModeloWorkResolution",
    "ModeloWorkSelectionMode",
    "ModeloWorkSelectorRequest",
    "ModeloWorkSelectorState",
    "ModeloWorkUnitCandidate",
    "resolve_modelo_work_bucket",
    "select_modelo_work_resolution",
]
