"""Application-level addressing for modelo work commands.

The address facade converts visible modelo/year/period filing targets and exact
work-unit ids into :class:`ModeloWorkAddress` values, resolves them through the
central selector contract, and returns the matching
:class:`~WorkUnit` or :class:`CalculationRevision`.

This module is the application facade over the accepted addressing policy:
operators address the active bucket/profile plus modelo, filing year, and period;
raw ids remain advanced exact-addressing escape hatches. Ambiguous visible
targets, contradictory exact-id plus natural-key flags, and discarded natural-key
matches are handled by the captured-catalogue operation in this defining module
rather than by CLI-local string logic.

Creation flows validate the law-determined registry revision before delegating
to :func:`~cadrumo.application.modelo.create_work_unit`; an explicit
``--revision`` is an assertion of the selected legal revision, not a free
override. Revision flows apply
:class:`~cadrumo.application.modelo.ModeloCalculationRevisionSelector`
defaults so verify, file, and export commands consume only the lifecycle states
they are allowed to handle.

See Also:
    :func:`select_modelo_work_resolution`:
        The authoritative pure work selector over one captured catalogue.
    :mod:`~cadrumo.entrypoints.cli._modelo`:
        CLI commands that project operator flags into this facade.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from secrets import token_bytes
from threading import RLock
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.authority import RegistryAuthorityCapture, bundled_authority
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.contribuyente.ccaa import CCAA
from ...domain.modelos.calculation_revision import (
    CURRENT_SEALED_REVISION_STATES,
    CalculationRevision,
    CalculationRevisionState,
)
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.errors import ModeloError, ModeloValidationError
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from .action_errors import CalculationRevisionNotFoundError, CalculationRevisionStateError, ModeloPreconditionErrorMixin
from .calculation_actions import get_calculation_revision
from .preconditions import (
    build_modelo_precondition_failure_for_scenario,
    build_modelo_work_file_unverified_revision_failure,
)
from .registry_discovery import declared_modelo_period_tokens
from .selectors import (
    ModeloCalculationRevisionDefault,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    resolve_modelo_calculation_revision_pick,
)
from .work_lifecycle import RevisionParentOperation, create_work_unit, rename_work_unit, require_revision_parent_active

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


class ModeloWorkSelectorError(ModeloError):
    """Base error for Modelo work-selection refusals."""


class ModeloWorkNoActiveBucketError(ModeloWorkSelectorError):
    """Raised when an implicit selector cannot capture an active bucket."""


class ModeloWorkUnitNotFoundError(ModeloWorkSelectorError, KeyError):
    """Raised when an exact work identifier resolves no all-state unit."""


class ModeloWorkSelectorContradictionError(ModeloWorkSelectorError, ValueError):
    """Raised when an exact selector contradicts supplied coordinates."""


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


class ModeloWorkVisibleTargetAmbiguousError(ModeloWorkSelectorError):
    """Raised after the deterministic complete candidate set has cardinality > 1."""

    def __init__(self, candidates: tuple[ModeloWorkUnitCandidate, ...], *, selector: str | None = None) -> None:
        """Retain the full candidate set and optional exact-id token."""
        self.candidates = candidates
        self.selector = selector
        message = (
            "modelo work target is ambiguous; choose a registry revision or exact work_unit_id"
            if selector is None
            else f"modelo work id selector {selector!r} is ambiguous; use the full 64-character work_unit_id"
        )
        super().__init__(message)


class ModeloWorkRevisionConflictError(ModeloWorkSelectorError):
    """Raised only after a singleton natural candidate fails its revision assertion."""

    def __init__(self, *, requested_revision_id: RevisionId, existing: ModeloWorkUnitCandidate) -> None:
        """Retain the failed revision assertion and existing work candidate."""
        self.requested_revision_id = requested_revision_id
        self.existing = existing
        super().__init__("modelo work target already has a work unit for a different registry revision")


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
    if request.work_unit_id is not None:
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
    if request.operator_work_unit_id is not None:
        if len(request.operator_work_unit_id) != 12:
            raise ModeloWorkSelectorContradictionError(
                translated_message="errors.refused.modelo_work_selector_contradiction",
            )
        matches = tuple(
            sorted(
                (
                    unit
                    for unit in catalogue.values()
                    if unit.bucket_id == bucket_id
                    and (
                        unit.work_unit_id.startswith(request.operator_work_unit_id)
                        or unit.work_unit_id.endswith(request.operator_work_unit_id)
                    )
                ),
                key=lambda unit: unit.work_unit_id,
            )
        )
        if not matches:
            raise ModeloWorkUnitNotFoundError(
                translated_message="errors.error.modelo_work_selector_unit_not_found",
                context={"work_unit_id": request.operator_work_unit_id},
            )
        if len(matches) > 1:
            raise ModeloWorkVisibleTargetAmbiguousError(
                tuple(ModeloWorkUnitCandidate.from_work_unit(unit) for unit in matches),
                selector=request.operator_work_unit_id,
            )
        work_unit = next(iter(matches))
        _assert_exact_coordinates(work_unit, request, bucket_id=bucket_id)
        return _resolved_modelo_work_resolution(work_unit, requested_revision_id=request.revision_id)
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
        )
    )
    return _select_natural_modelo_work_resolution(request, bucket_id=bucket_id, matches=matches)


def _select_natural_modelo_work_resolution(
    request: ModeloWorkSelectorRequest, *, bucket_id: str, matches: tuple[WorkUnit, ...]
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
    if request.bucket_id is not None:
        return request.bucket_id
    active_bucket_id = resolve_active_bucket_id()
    if active_bucket_id is None:
        raise ModeloWorkNoActiveBucketError(
            translated_message="errors.refused.modelo_work_selector_no_active_bucket",
            context={"active_bucket_present": False},
        )
    return active_bucket_id


class ModeloRevisionPickError(ModeloError, ValueError):
    """Raised when a calculation-revision selector is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class ModeloVisibleFilingTarget:
    """Operator-visible modelo filing target under one bucket/profile.

    This is the normal user-facing address: bucket/profile plus modelo, filing
    year, and period, with an optional registry-revision assertion for
    disambiguation.
    """

    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: RevisionId | None = None
    bucket_id: str | None = None

    def to_work_address(self) -> ModeloWorkAddress:
        """Project the visible target into the shared :class:`ModeloWorkAddress` shape."""
        return ModeloWorkAddress(
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period,
            registry_revision_id=self.registry_revision_id,
            bucket_id=self.bucket_id,
        )


@dataclass(frozen=True, slots=True)
class ModeloExactWorkUnitTarget:
    """Advanced exact-addressing target for one content-addressed work unit.

    Use this only when the caller already has an authoritative ``WorkUnitId``;
    visible filing targets remain the default operator path.
    """

    work_unit_id: WorkUnitId
    bucket_id: str | None = None

    def to_work_address(self) -> ModeloWorkAddress:
        """Project the exact target into the shared :class:`ModeloWorkAddress` shape."""
        return ModeloWorkAddress(work_unit_id=self.work_unit_id, bucket_id=self.bucket_id)


@dataclass(frozen=True, slots=True)
class ModeloRevisionPick:
    """Command-specific calculation-revision pick under a resolved work target.

    ``default_for`` applies the command policy owned by
    :mod:`~cadrumo.application.modelo._selectors`: verify selects a draft, file
    selects a verified-complete revision, and export prefers the current filed
    revision before falling back to an unambiguous verified revision.
    """

    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT
    calculation_revision_id: CalculationRevisionId | None = None
    default_for: ModeloCalculationRevisionDefault | None = None

    def __post_init__(self) -> None:
        """Reject incompatible default and explicit calculation revision choices."""
        if self.selector is ModeloCalculationRevisionSelector.EXPLICIT:
            if self.calculation_revision_id is None:
                raise ModeloRevisionPickError(
                    "explicit revision picks require calculation_revision_id",
                    translated_message="application.modelo.errors.revision_pick_explicit_id_required",
                )
            return
        if self.calculation_revision_id is not None:
            raise ModeloRevisionPickError(
                "calculation_revision_id is only valid with the explicit revision selector",
                translated_message="application.modelo.errors.revision_pick_id_requires_explicit_selector",
            )

    @classmethod
    def explicit(cls, calculation_revision_id: CalculationRevisionId) -> ModeloRevisionPick:
        """Create an exact calculation-revision :class:`ModeloRevisionPick`."""
        return cls(
            selector=ModeloCalculationRevisionSelector.EXPLICIT,
            calculation_revision_id=calculation_revision_id,
        )


@dataclass(frozen=True, slots=True)
class ModeloResolvedWorkProjection:
    """Support-safe projection of a resolved modelo work target.

    The projection exposes the visible filing coordinates plus short ids for
    support guidance without making raw ids the normal operator workflow.
    """

    work_unit_id: WorkUnitId
    short_work_unit_id: str
    bucket_id: str
    modelo: str
    filing_year: int
    period: Period
    registry_revision_id: RevisionId
    state: str
    current_calculation_revision_id: CalculationRevisionId | None
    filed_calculation_revision_id: CalculationRevisionId | None
    current_filing_record_id: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_work_unit(cls, work_unit: WorkUnit) -> ModeloResolvedWorkProjection:
        """Project a Cadrumo work unit into a resolved-work projection.

        Converts :class:`~WorkUnit` into
        :class:`ModeloResolvedWorkProjection`.
        """
        return cls(
            work_unit_id=work_unit.work_unit_id,
            short_work_unit_id=work_unit.work_unit_id[-12:],
            bucket_id=work_unit.bucket_id,
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            registry_revision_id=work_unit.revision_id,
            state=work_unit.state.value,
            current_calculation_revision_id=work_unit.current_calculation_revision_id,
            filed_calculation_revision_id=work_unit.filed_calculation_revision_id,
            current_filing_record_id=work_unit.current_filing_record_id,
            created_at=work_unit.created_at.isoformat(),
            updated_at=work_unit.updated_at.isoformat(),
        )


@dataclass(frozen=True, slots=True)
class ModeloResolvedRevisionProjection:
    """Support-safe projection of a resolved calculation revision.

    Carries the selected revision, selector policy, lifecycle state, and short
    ids used by CLI guidance after a work target has been resolved.
    """

    calculation_revision_id: CalculationRevisionId
    short_calculation_revision_id: str
    work_unit_id: WorkUnitId
    short_work_unit_id: str
    selector: ModeloCalculationRevisionSelector
    state: str
    created_at: str
    updated_at: str
    verified_at: str | None = None
    filed_at: str | None = None

    @classmethod
    def from_revision(
        cls,
        revision: CalculationRevision,
        *,
        selector: ModeloCalculationRevisionSelector,
    ) -> ModeloResolvedRevisionProjection:
        """Project a :class:`CalculationRevision` into a :class:`ModeloResolvedRevisionProjection`."""
        return cls(
            calculation_revision_id=revision.calculation_revision_id,
            short_calculation_revision_id=revision.calculation_revision_id[-12:],
            work_unit_id=revision.work_unit_id,
            short_work_unit_id=revision.work_unit_id[-12:],
            selector=selector,
            state=revision.state.value,
            created_at=revision.created_at.isoformat(),
            updated_at=revision.updated_at.isoformat(),
            verified_at=revision.verified_at.isoformat() if revision.verified_at is not None else None,
            filed_at=revision.filed_at.isoformat() if revision.filed_at is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ModeloWorkAddress:
    """Operator-facing or exact modelo work address.

    This is the shared transport shape consumed at the application facade
    boundary. Prefer ``ModeloVisibleFilingTarget`` for model/year/period
    addressing or ``ModeloExactWorkUnitTarget`` for the advanced exact-id
    escape hatch, then project into this shape before selector resolution.
    """

    work_unit_id: WorkUnitId | None = None
    operator_work_unit_id: str | None = None
    modelo: str | None = None
    filing_year: int | None = None
    period: Period | None = None
    registry_revision_id: RevisionId | None = None
    bucket_id: str | None = None

    @classmethod
    def from_visible_target(cls, target: ModeloVisibleFilingTarget) -> ModeloWorkAddress:
        """Create a :class:`ModeloWorkAddress` from a natural modelo filing target."""
        return target.to_work_address()

    @classmethod
    def from_exact_target(cls, target: ModeloExactWorkUnitTarget) -> ModeloWorkAddress:
        """Create a :class:`ModeloWorkAddress` from an exact work-unit target."""
        return target.to_work_address()


type ModeloWorkTarget = ModeloVisibleFilingTarget | ModeloExactWorkUnitTarget | ModeloWorkAddress
"""Supported work-target shapes for centralized modelo addressing."""


class ModeloWorkAddressNotFoundError(ModeloPreconditionErrorMixin, ModeloError, LookupError):
    """Raised when a natural modelo work address resolves no work unit."""


class ModeloWorkRegistryYearMismatchError(ModeloError, ValueError):
    """Raised when an explicit revision diverges from the law-determined one."""


class ModeloWorkPeriodTokenError(ModeloError, ValueError):
    """Raised when an operator-facing period token cannot be normalized."""

    def __init__(
        self,
        *,
        year: int,
        token: str,
        modelo: str | None,
        declared_tokens: tuple[str, ...],
        fallback: str | None = None,
    ) -> None:
        """Record the rejected token and the declared alternatives for its target."""
        context = {
            "year": year,
            "token": token,
            "modelo": modelo or "",
            "tokens": ", ".join(declared_tokens),
        }
        if declared_tokens:
            super().__init__(
                context=context,
                translated_message="application.modelo.errors.work_period_token_invalid",
            )
            return
        del fallback
        super().__init__(
            context=context,
            translated_message="application.modelo.errors.work_period_token_unrecognised",
        )


@dataclass(frozen=True, slots=True)
class ModeloWorkEnsureResult:
    """Result of resolving or creating a visible-target work unit."""

    work_unit: WorkUnit
    reused: bool
    name_applied: str | None = None


def work_address_for_modelo_target(target: ModeloWorkTarget) -> ModeloWorkAddress:
    """Coerce a typed modelo work target into a :class:`ModeloWorkAddress` selector shape."""
    if isinstance(target, ModeloWorkAddress):
        return target
    if isinstance(target, ModeloVisibleFilingTarget):
        return target.to_work_address()
    return target.to_work_address()


def _modelo_work_period_from_core(year: int, period: Period, *, modelo: str | None = None) -> Period:
    """Resolve a modelo work period through the core ``Period`` value object only."""
    declared = declared_modelo_period_tokens(modelo)
    if period.filing_year != year:
        raise ModeloWorkPeriodTokenError(
            year=year,
            token=str(period),
            modelo=modelo,
            declared_tokens=declared,
        )
    return period


def modelo_work_address_from_operator_target(
    *,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None = None,
) -> ModeloWorkAddress:
    """Build a :class:`ModeloWorkAddress` from exact or visible operator input.

    A complete visible target is ``modelo`` + ``year`` + typed ``Period``. If no
    visible target is supplied, an exact ``work_unit_id`` is required. Period year
    mismatches fail here before the selector sees the request.
    """
    if modelo is not None and year is not None and period is not None:
        period = _modelo_work_period_from_core(year, period, modelo=modelo)
        year = period.filing_year
    elif work_unit_id is None:
        raise ModeloWorkAddressNotFoundError(
            "pass an exact work-unit id, or address the filing with modelo, year, and period",
        )
    normalized_work_unit_id = work_unit_id.strip().lower() if work_unit_id is not None else None
    operator_work_unit_id = (
        normalized_work_unit_id if normalized_work_unit_id is not None and len(normalized_work_unit_id) == 12 else None
    )
    return ModeloWorkAddress(
        work_unit_id=None if operator_work_unit_id is not None else normalized_work_unit_id,
        operator_work_unit_id=operator_work_unit_id,
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )


def resolve_modelo_work_unit_for_operator_target(
    *,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: Period | None = None,
    registry_revision_id: RevisionId | None = None,
    bucket_id: str | None = None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> WorkUnit:
    """Resolve exact or visible operator input to one active :class:`~WorkUnit`.

    The result comes from the shared selector boundary, so ambiguity and
    exact-id/natural-key contradictions surface as typed selector errors.
    """
    return resolve_modelo_work_address_unit(
        modelo_work_address_from_operator_target(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            registry_revision_id=registry_revision_id,
            bucket_id=bucket_id,
        ),
        catalogue=catalogue,
        bucket_id=resolved_bucket_id,
    )


def resolve_modelo_revision_for_operator_target(
    *,
    calculation_revision_id: CalculationRevisionId | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    default_for: ModeloCalculationRevisionDefault | None = None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    """Resolve one :class:`CalculationRevision` from exact or visible operator input.

    An explicit calculation-revision id can stand alone as the exact escape hatch.
    Otherwise the work target is resolved first and the selector/default policy is
    applied under that work unit.
    """
    address = _revision_target_address(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )
    return _resolve_revision_with_precondition_translation(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for=default_for,
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )


def _revision_target_address(
    *,
    calculation_revision_id: CalculationRevisionId | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: Period | None,
    registry_revision_id: RevisionId | None,
    bucket_id: str | None,
) -> ModeloWorkAddress:
    if (
        calculation_revision_id is not None
        and work_unit_id is None
        and modelo is None
        and year is None
        and period is None
        and registry_revision_id is None
        and bucket_id is None
    ):
        return ModeloWorkAddress()
    return modelo_work_address_from_operator_target(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision_id=registry_revision_id,
        bucket_id=bucket_id,
    )


def _resolve_revision_with_precondition_translation(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None,
    selector: ModeloCalculationRevisionSelector,
    default_for: ModeloCalculationRevisionDefault | None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    try:
        return _resolve_revision_for_default(
            address=address,
            calculation_revision_id=calculation_revision_id,
            selector=selector,
            default_for=default_for,
            catalogue=catalogue,
            resolved_bucket_id=resolved_bucket_id,
        )
    except CalculationRevisionNotFoundError as error:
        recovery_error = _calculation_revision_work_unit_target_error(
            error=error,
            calculation_revision_id=calculation_revision_id,
            address=address,
            default_for=default_for,
            catalogue=catalogue,
            resolved_bucket_id=resolved_bucket_id,
        )
        if recovery_error is error:
            raise
        raise recovery_error from error
    except ModeloWorkAddressNotFoundError as error:
        precondition_error = _natural_target_absent_precondition_error(
            error=error,
            address=address,
            default_for=default_for,
        )
        if precondition_error is error:
            raise
        raise precondition_error from error
    except ModeloWorkUnitNotFoundError as error:
        precondition_error = _exact_work_unit_absent_precondition_error(
            error=error,
            address=address,
            default_for=default_for,
        )
        if precondition_error is error:
            raise
        raise precondition_error from error


def _resolve_revision_for_default(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None,
    selector: ModeloCalculationRevisionSelector,
    default_for: ModeloCalculationRevisionDefault | None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    resolver = (
        {
            "verify": resolve_verifiable_modelo_calculation_revision_address,
            "file": resolve_fileable_modelo_calculation_revision_address,
            "export": resolve_exportable_modelo_calculation_revision_address,
        }.get(default_for)
        if default_for is not None
        else None
    )
    if resolver is None:
        resolver = resolve_modelo_calculation_revision_address
    return resolver(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )


def _calculation_revision_work_unit_target_error(
    *,
    error: CalculationRevisionNotFoundError,
    calculation_revision_id: CalculationRevisionId | None,
    address: ModeloWorkAddress,
    default_for: ModeloCalculationRevisionDefault | None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevisionNotFoundError:
    """Attach the declared calculate recovery when an exact work unit was supplied."""
    if default_for == "verify":
        subject_leaf_key = "modelo.work.verify"
    elif default_for == "file":
        subject_leaf_key = "modelo.work.file"
    else:
        return error
    if calculation_revision_id is None or address != ModeloWorkAddress():
        return error
    try:
        work_unit = resolve_modelo_work_unit_for_operator_target(
            work_unit_id=calculation_revision_id,
            catalogue=catalogue,
            resolved_bucket_id=resolved_bucket_id,
        )
    except ModeloWorkUnitNotFoundError:
        return error
    is_active = work_unit.state is WorkUnitState.BORRADOR
    scenario_id = (
        f"{subject_leaf_key}.calculation_revision.work_unit_target"
        if is_active
        else f"{subject_leaf_key}.calculation_revision.work_unit_target_discarded"
    )
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=subject_leaf_key,
        scenario_id=scenario_id,
        evidence_id=f"{subject_leaf_key}.calculation_revision.addressing",
        evidence_values={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": work_unit.work_unit_id,
            "work_unit_state": work_unit.state.value,
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={"work_unit_id": work_unit.work_unit_id} if is_active else None,
    )
    return CalculationRevisionNotFoundError(
        translated_message=(
            "application.modelo.errors.calculation_revision_id_is_work_unit"
            if is_active
            else "application.modelo.errors.calculation_revision_id_is_discarded_work_unit"
        ),
        context={
            "calculation_revision_id": calculation_revision_id,
            "work_unit_id": work_unit.work_unit_id,
            "work_unit_state": work_unit.state.value,
        },
        precondition_failure=failure,
    )


def _natural_target_absent_precondition_error(
    *,
    error: ModeloWorkAddressNotFoundError,
    address: ModeloWorkAddress,
    default_for: ModeloCalculationRevisionDefault | None,
) -> ModeloWorkAddressNotFoundError:
    """Attach the declared no-action verdict to an absent natural verify/file target."""
    subject_leaf_key = _natural_target_subject_leaf_key(default_for)
    if subject_leaf_key is None or not _natural_target_is_addressed(address):
        return error
    addressed_modelo, addressed_filing_year, addressed_period = _addressed_obligation(address)
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=subject_leaf_key,
        scenario_id=f"{subject_leaf_key}.work_address.natural_target_absent",
        evidence_id=f"{subject_leaf_key}.work_address.addressing",
        evidence_values={
            "modelo": addressed_modelo,
            "filing_year": addressed_filing_year,
            "period": addressed_period.registry_token,
            "registry_revision_id": address.registry_revision_id or "",
            "bucket_id": address.bucket_id or "",
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )
    return ModeloWorkAddressNotFoundError(
        str(error),
        translated_message="errors.error.modelo_work_address_not_found",
        context={
            "modelo": addressed_modelo,
            "filing_year": addressed_filing_year,
            "period": addressed_period.registry_token,
            "registry_revision_id": address.registry_revision_id or "",
            "bucket_id": address.bucket_id or "",
        },
        precondition_failure=failure,
    )


def _natural_target_subject_leaf_key(default_for: ModeloCalculationRevisionDefault | None) -> str | None:
    if default_for == "verify":
        return "modelo.work.verify"
    if default_for == "file":
        return "modelo.work.file"
    return None


def _addressed_obligation(address: ModeloWorkAddress) -> tuple[ModeloCode, FilingYear, Period]:
    """Return the obligation a natural address names, refusing a partial one.

    ``ModeloWorkAddress`` leaves the three coordinates optional because a
    work-unit-id address carries none of them. Callers here have already passed
    :func:`_natural_target_is_addressed`, so absence is a contradiction -- and
    it is refused rather than asserted, because an ``assert`` is stripped under
    ``python -O`` and would let a partial address reach the precondition build.
    """
    if address.modelo is None or address.filing_year is None or address.period is None:
        raise ModeloWorkSelectorContradictionError(
            "natural work address passed the addressed screen without a complete "
            "modelo/ejercicio/period coordinate set",
        )
    return ModeloCode(address.modelo), address.filing_year, address.period


def _selected_work_unit(resolution: ModeloWorkResolution) -> WorkUnit:
    """Return the work unit a resolved selection carries, refusing an unresolved one.

    Refused rather than asserted for the same reason: under ``python -O`` the
    assert disappears and an unresolved selection reaches the caller as ``None``.
    """
    if resolution.work_unit is None:
        raise ModeloWorkSelectorContradictionError(
            "work selection resolved without naming a work unit",
        )
    return resolution.work_unit


def _natural_target_is_addressed(address: ModeloWorkAddress) -> bool:
    return (
        address.work_unit_id is None
        and address.modelo is not None
        and address.filing_year is not None
        and address.period is not None
    )


def _exact_work_unit_absent_precondition_error(
    *,
    error: ModeloWorkUnitNotFoundError,
    address: ModeloWorkAddress,
    default_for: ModeloCalculationRevisionDefault | None,
) -> ModeloWorkAddressNotFoundError | ModeloWorkUnitNotFoundError:
    """Attach the declared no-action verdict to an absent exact verify/file work-unit target."""
    if default_for == "verify":
        subject_leaf_key = "modelo.work.verify"
    elif default_for == "file":
        subject_leaf_key = "modelo.work.file"
    else:
        return error
    if address.work_unit_id is None:
        return error
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=subject_leaf_key,
        scenario_id=f"{subject_leaf_key}.work_address.exact_work_unit_absent",
        evidence_id=f"{subject_leaf_key}.work_address.addressing",
        evidence_values={
            "work_unit_id": address.work_unit_id,
            "bucket_id": address.bucket_id or "",
            "selector_kind": "work_unit_id",
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
    )
    return ModeloWorkAddressNotFoundError(
        str(error),
        translated_message="errors.error.modelo_work_address_not_found",
        context={
            "work_unit_id": address.work_unit_id,
            "bucket_id": address.bucket_id or "",
            "selector_kind": "work_unit_id",
        },
        precondition_failure=failure,
    )


def resolve_modelo_work_target(
    target: ModeloWorkTarget,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Resolve any supported modelo target through the shared selector boundary.

    Returns a :class:`ModeloWorkResolution` containing the resolved work unit or
    typed absence/ambiguity metadata from this defining module's pure selector.
    """
    return resolve_modelo_work_address(
        work_address_for_modelo_target(target),
        catalogue=catalogue,
        bucket_id=bucket_id,
    )


def resolve_modelo_work_unit_id(
    target: ModeloWorkTarget,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> WorkUnitId:
    """Resolve a visible or exact modelo target to the authoritative work-unit id."""
    resolution = resolve_modelo_work_target(target, catalogue=catalogue, bucket_id=bucket_id)
    return _selected_work_unit(resolution).work_unit_id


def project_modelo_work_unit(work_unit: WorkUnit) -> ModeloResolvedWorkProjection:
    """Project an internal work unit into the visible :class:`ModeloResolvedWorkProjection` addressing contract."""
    return ModeloResolvedWorkProjection.from_work_unit(work_unit)


def project_modelo_work_target(
    target: ModeloWorkTarget,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloResolvedWorkProjection:
    """Resolve a target and project it back to a :class:`ModeloResolvedWorkProjection`."""
    resolution = resolve_modelo_work_target(target, catalogue=catalogue, bucket_id=bucket_id)
    return project_modelo_work_unit(_selected_work_unit(resolution))


def diverging_work_target_revision_axes(
    *,
    law_revision_id: RevisionId,
    requested_revision_id: RevisionId | None,
    stored_revision_id: RevisionId | None,
) -> frozenset[str]:
    """Return the axis names whose asserted revision is not the law-determined one.

    The one comparison behind both revision-assertion surfaces. An axis that
    supplies no value asserts nothing and can never diverge; a supplied value
    is normalised and judged against the law-determined revision ALONE, never
    against the other axis, so a stored value can never select the revision a
    request is judged by.

    Extracted because the rule was written twice, in two dispositions -- this
    module raising on divergence and the Workspace projection recording it as
    typed data. The dispositions differ legitimately: an exception escaping a
    read projection would destroy the information its typed refusal exists to
    carry. The COMPARISON differing would not be legitimate, and two copies of
    one normalisation drift silently: a change to what counts as equal lands at
    one site, the other goes on answering the old question, and the two
    surfaces disagree about whether a taxpayer's stored revision matches the
    law.

    Returns:
        The diverging axis names, empty when every supplied axis matches.
    """
    return frozenset(
        axis
        for axis, candidate in (("requested", requested_revision_id), ("stored", stored_revision_id))
        if candidate is not None and candidate.strip() != law_revision_id
    )


def assert_work_target_revision(
    capture: RegistryAuthorityCapture,
    *,
    requested_revision_id: RevisionId | None,
    stored_revision_id: RevisionId | None,
) -> RevisionId:
    """Assert both work-target revision axes against one law-selected capture.

    ``capture`` carries the single law-determined projection for the visible
    filing target.  The ``requested`` axis is an operator ``--revision``
    assertion; the ``stored`` axis is the revision already recorded on a work
    unit.  The axes are independent: either may be absent, and each is checked
    against the same captured law-determined revision rather than against the
    other, so a stored value can never select the revision a request is judged
    by.

    Returns:
        The law-determined revision id carried by ``capture``.

    Raises:
        ModeloWorkRegistryYearMismatchError: An supplied axis diverges from the
            law-determined revision.
    """
    projection = capture.projection
    law_revision_id = (
        projection.revision_id if isinstance(projection, RegistryRevisionInspection) else projection.revision.id
    )
    diverging = diverging_work_target_revision_axes(
        law_revision_id=law_revision_id,
        requested_revision_id=requested_revision_id,
        stored_revision_id=stored_revision_id,
    )
    for axis, candidate in (
        ("requested", requested_revision_id),
        ("stored", stored_revision_id),
    ):
        if axis not in diverging or candidate is None:
            continue
        asserted = candidate.strip()
        raise ModeloWorkRegistryYearMismatchError(
            f"{axis} registry revision {asserted!r} is not the law-determined revision "
            f"for this filing target. The law-determined revision is {law_revision_id!r}. "
            f"The period-to-revision binding is fixed by law (AEAT orden ministerial); "
            f"you cannot override it. Re-create the work unit without --revision to use "
            f"the correct revision, or omit --revision to accept the law-determined default.",
        )
    return law_revision_id


def law_selected_revision_for_work_target(
    *,
    modelo: str,
    filing_year: int,
    period: Period,
    requested_revision_id: RevisionId | None = None,
    stored_revision_id: RevisionId | None = None,
) -> RevisionId:
    """Capture the law-selected revision once and assert every supplied axis.

    Exactly one :class:`RegistryAuthorityCapture` is taken for
    ``(modelo, filing_year, period)``, so the work path performs one registry
    read and both axes are judged against the same atomic projection.
    """
    capture = bundled_authority().capture_law_selected_projection(
        modelo.strip(),
        filing_year=filing_year,
        period=period.registry_token,
    )
    return assert_work_target_revision(
        capture,
        requested_revision_id=requested_revision_id,
        stored_revision_id=stored_revision_id,
    )


_WORK_CAPTURE_MAX_ATTEMPTS = 8
_work_capture_process_pid = os.getpid()
_work_capture_process_nonce = token_bytes(32)
_work_capture_domains: set[str] = set()
_work_capture_lock = RLock()
_work_capture_generations: dict[str, tuple[tuple[str, ...], int]] = {}
_work_capture_generation = 0


class ModeloWorkCaptureError(ModeloWorkSelectorError, RuntimeError):
    """Raised when a work capture cannot reach one uncontended observation."""


@dataclass(frozen=True, slots=True)
class ModeloWorkCapture:
    """One isolated work resolution and its currentness coordinate.

    The capture carries the strict frozen :class:`ModeloWorkResolution` selected
    over exactly one catalogue read, plus an opaque comparison domain and a
    generation. The physical storage root, bucket, namespace and object key that
    produced it are folded into the domain digest and are never exposed.
    """

    resolution: ModeloWorkResolution
    comparison_domain: str
    generation: int

    def require_current(self, current: ModeloWorkCurrentCoordinate) -> ModeloWorkCapture:
        """Refuse a currentness comparison outside this physical process domain."""
        _require_work_capture_process_domain(self.comparison_domain)
        current.require_current(self)
        return self


@dataclass(frozen=True, slots=True)
class ModeloWorkCurrentCoordinate:
    """Opaque same-process coordinate for one work catalogue owner scope."""

    comparison_domain: str
    generation: int

    def require_current(self, captured: ModeloWorkCapture) -> ModeloWorkCurrentCoordinate:
        """Require a capture from this exact scope and process incarnation."""
        _require_work_capture_process_domain(self.comparison_domain)
        _require_work_capture_process_domain(captured.comparison_domain)
        if self.comparison_domain != captured.comparison_domain:
            raise ModeloWorkCaptureError(
                translated_message="errors.refused.modelo_work_capture_not_current",
                context={"reason": "distinct_owner_scope"},
            )
        if self.generation != captured.generation:
            raise ModeloWorkCaptureError(
                translated_message="errors.refused.modelo_work_capture_not_current",
                context={"reason": "capture_superseded"},
            )
        return self


def _require_work_capture_process_domain(domain: str) -> None:
    """Refuse a coordinate domain not minted in this process incarnation."""
    if _work_capture_process_pid != os.getpid():
        raise ModeloWorkCaptureError(
            translated_message="errors.refused.modelo_work_capture_not_current",
            context={"reason": "forked_process"},
        )
    with _work_capture_lock:
        known = domain in _work_capture_domains
    if not known:
        raise ModeloWorkCaptureError(
            translated_message="errors.refused.modelo_work_capture_not_current",
            context={"reason": "foreign_process_incarnation"},
        )


def _work_capture_comparison_domain(*, bucket_id: str, implicit: bool) -> str:
    """Mint the non-persisted coordinate domain for one owner scope."""
    from ...core.config import load_settings

    domain = content_hash_hex(
        {
            "owner": "application.modelo.work_addressing",
            "storage_root": str(load_settings().cadrumo_local_storage_root),
            "namespace": "modelo.work_unit_catalogue",
            "bucket_id": bucket_id,
            "implicit_pointer_limb": implicit,
            "process_incarnation": _work_capture_process_nonce.hex(),
        }
    )
    with _work_capture_lock:
        _work_capture_domains.add(domain)
    return domain


def _work_pointer_limb() -> str:
    """Return the implicit pointer limb coordinate for the active storage root."""
    from ...core.bucket_pointer import pointer_path
    from ...core.config import load_settings
    from ...core.paths import path_stat_fingerprint

    target = pointer_path(load_settings().cadrumo_local_storage_root)
    try:
        return content_hash_hex(path_stat_fingerprint(target))
    except OSError:
        return "absent"


def _work_capture_generation_for(domain: str, observation: tuple[str, ...]) -> int:
    """Assign one injective, order-preserving generation per distinct observation."""
    global _work_capture_generation
    with _work_capture_lock:
        recorded = _work_capture_generations.get(domain)
        if recorded is not None and recorded[0] == observation:
            return recorded[1]
        _work_capture_generation += 1
        _work_capture_generations[domain] = (observation, _work_capture_generation)
        return _work_capture_generation


def _work_capture_observation(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
) -> tuple[str, WorkUnitCatalogue, tuple[str, ...], bool]:
    """Read the pointer and one catalogue record until the two limbs agree."""
    implicit = request.bucket_id is None
    for _attempt in range(_WORK_CAPTURE_MAX_ATTEMPTS):
        limb_before = _work_pointer_limb() if implicit else None
        bucket_id = resolve_modelo_work_bucket(request)
        catalogue, revision_id = catalogue_repository.load_revisioned()
        if implicit and _work_pointer_limb() != limb_before:
            continue
        observation: tuple[str, ...]
        if implicit:
            if limb_before is None:
                raise ModeloWorkSelectorContradictionError(
                    "implicit pointer observation requires the limb the pointer held before",
                )
            observation = (limb_before, revision_id)
        else:
            observation = (revision_id,)
        return bucket_id, catalogue, observation, implicit
    raise ModeloWorkCaptureError(
        translated_message="errors.refused.modelo_work_capture_not_current",
        context={"attempts": _WORK_CAPTURE_MAX_ATTEMPTS},
    )


def capture_modelo_work_resolution(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
    mode: ModeloWorkSelectionMode = ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
) -> ModeloWorkCapture:
    """Atomically capture one work resolution over a single catalogue read.

    The implicit pointer limb and the one-record catalogue coordinate are read
    so that a pointer replacement interleaved with the catalogue read is retried
    rather than composed, which is what defeats a pointer/catalogue ABA. An
    explicit ``bucket_id`` excludes the pointer limb entirely while still
    carrying the catalogue generation. No registry is consulted and the
    catalogue is read exactly once per successful attempt.
    """
    bucket_id, catalogue, observation, implicit = _work_capture_observation(
        request,
        catalogue_repository=catalogue_repository,
    )
    resolution = select_modelo_work_resolution(
        request,
        catalogue=catalogue,
        bucket_id=bucket_id,
        mode=mode,
    )
    domain = _work_capture_comparison_domain(bucket_id=bucket_id, implicit=implicit)
    return ModeloWorkCapture(
        resolution=resolution,
        comparison_domain=domain,
        generation=_work_capture_generation_for(domain, observation),
    )


def read_modelo_work_current_coordinate(
    request: ModeloWorkSelectorRequest,
    *,
    catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
) -> ModeloWorkCurrentCoordinate:
    """Return the typed current coordinate for same-domain capture validation."""
    bucket_id, _catalogue, observation, implicit = _work_capture_observation(
        request,
        catalogue_repository=catalogue_repository,
    )
    domain = _work_capture_comparison_domain(bucket_id=bucket_id, implicit=implicit)
    return ModeloWorkCurrentCoordinate(
        comparison_domain=domain,
        generation=_work_capture_generation_for(domain, observation),
    )


def ensure_modelo_work_unit_for_active_target(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: Period,
    registry_revision_id: RevisionId | None,
    name: str | None = None,
    actor: str = "operator",
    causante_ccaa: CCAA | None = None,
    enforce_applicability: bool = True,
    catalogue: WorkUnitCatalogue,
) -> ModeloWorkEnsureResult:
    """Resume or create the active work unit for one visible filing target.

    The visible target is resolved first. If one active unit exists, it is reused
    after profile-readiness validation and optional rename. If none exists, the
    law-determined registry revision is selected and a work unit is created.

    Returns:
        A :class:`ModeloWorkEnsureResult` marking whether the unit was reused or
        newly created.
    """
    requested_revision = registry_revision_id.strip() if registry_revision_id is not None else None
    resolution = select_modelo_work_resolution(
        ModeloWorkSelectorRequest(
            bucket_id=bucket_id,
            modelo=ModeloCode(modelo),
            filing_year=filing_year,
            period=period,
            revision_id=requested_revision,
        ),
        catalogue=catalogue,
        bucket_id=bucket_id,
        mode=ModeloWorkSelectionMode.ACTIVE_NATURAL,
    )
    if resolution.work_unit is not None:
        unit = resolution.work_unit
        from .profile_readiness_gate import require_profile_ready_for_work_unit

        require_profile_ready_for_work_unit(unit, enforce_applicability=enforce_applicability)
        name_applied: str | None = None
        if name is not None and name.strip() and name.strip() != unit.name:
            unit = rename_work_unit(unit.work_unit_id, name, actor=actor)
            name_applied = unit.name
        return ModeloWorkEnsureResult(work_unit=unit, reused=True, name_applied=name_applied)

    revision_id = law_selected_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        requested_revision_id=requested_revision,
    )
    unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=name,
        actor=actor,
        causante_ccaa=causante_ccaa,
        enforce_applicability=enforce_applicability,
    )
    return ModeloWorkEnsureResult(work_unit=unit, reused=False)


def resolve_modelo_work_address(
    address: ModeloWorkAddress,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address to a required :class:`ModeloWorkResolution`."""
    resolution = resolve_optional_modelo_work_address(address, catalogue=catalogue, bucket_id=bucket_id)
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise ModeloWorkAddressNotFoundError(
            translated_message="errors.error.modelo_work_address_not_found",
            context={"work_unit_present": False},
        )
    return resolution


def resolve_optional_modelo_work_address(
    address: ModeloWorkAddress,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address to a :class:`ModeloWorkResolution`."""
    request = ModeloWorkSelectorRequest(
        work_unit_id=address.work_unit_id,
        operator_work_unit_id=address.operator_work_unit_id,
        modelo=ModeloCode(address.modelo) if address.modelo is not None else None,
        filing_year=address.filing_year,
        period=address.period,
        revision_id=address.registry_revision_id,
        bucket_id=address.bucket_id,
    )
    return select_modelo_work_resolution(request, catalogue=catalogue, bucket_id=bucket_id)


def resolve_modelo_work_address_unit(
    address: ModeloWorkAddress,
    *,
    catalogue: WorkUnitCatalogue,
    bucket_id: str,
) -> WorkUnit:
    """Resolve an operator-facing modelo work address to one :class:`~WorkUnit`."""
    resolution = resolve_modelo_work_address(address, catalogue=catalogue, bucket_id=bucket_id)
    return _selected_work_unit(resolution)


def resolve_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    default_for: ModeloCalculationRevisionDefault | None = None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    """Resolve a :class:`CalculationRevision` by exact id or under a modelo work address.

    ``default_for`` applies the command-specific selector default after the work
    unit is resolved. A bare exact calculation-revision id bypasses work-address
    resolution and loads the revision directly.  For verify and file only, a
    positional exact token that names a persisted work unit is reconciled through
    that unit's current-revision pointer.  This is not an alternate CLI grammar:
    it closes the application-owned recovery edge where the exact persisted
    identity initially has no calculation revision, calculation creates the
    current revision, and the unchanged original invocation must then address it.
    """
    if calculation_revision_id is not None and address == ModeloWorkAddress():
        revision = _resolve_exact_calculation_revision_or_current_work_unit_revision(
            calculation_revision_id=calculation_revision_id,
            default_for=default_for,
            catalogue=catalogue,
            resolved_bucket_id=resolved_bucket_id,
        )
        return _require_revision_parent_admitted_for_operation(
            revision,
            default_for=default_for,
            catalogue=catalogue,
            resolved_bucket_id=resolved_bucket_id,
        )

    work_unit = resolve_modelo_work_address_unit(
        address,
        catalogue=catalogue,
        bucket_id=resolved_bucket_id,
    )
    revision = resolve_modelo_calculation_revision_pick(
        work_unit,
        selector=selector,
        calculation_revision_id=calculation_revision_id,
        default_for=default_for,
    ).revision
    return _require_revision_parent_admitted_for_operation(
        revision,
        default_for=default_for,
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )


def _resolve_exact_calculation_revision_or_current_work_unit_revision(
    *,
    calculation_revision_id: CalculationRevisionId,
    default_for: ModeloCalculationRevisionDefault | None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    """Resolve an exact revision, or a current revision reached through its work unit.

    ``work verify`` and ``work file`` have an existing, declared recovery for a
    positional identifier which proves to be a work-unit id: calculate that unit.
    Before calculation the unit has no current revision and the original lookup
    must keep that verdict.  Afterwards, resolving the current pointer here makes
    the exact same operator invocation executable.  A discarded parent remains
    deliberately unresolved so the existing terminal profile is projected by the
    caller's typed error path.
    """
    try:
        return get_calculation_revision(calculation_revision_id)
    except CalculationRevisionNotFoundError as revision_error:
        if default_for not in {"verify", "file"}:
            raise
        try:
            work_unit = resolve_modelo_work_unit_for_operator_target(
                work_unit_id=calculation_revision_id,
                catalogue=catalogue,
                resolved_bucket_id=resolved_bucket_id,
            )
        except ModeloWorkUnitNotFoundError:
            raise revision_error from None
        if work_unit.state is not WorkUnitState.BORRADOR or work_unit.current_calculation_revision_id is None:
            raise revision_error from None
        return get_calculation_revision(work_unit.current_calculation_revision_id)


def _require_revision_parent_admitted_for_operation(
    revision: CalculationRevision,
    *,
    default_for: ModeloCalculationRevisionDefault | None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    """Refuse verify/file when a resolved revision belongs to a discarded work unit."""
    if default_for == "verify":
        operation = RevisionParentOperation.VERIFY
    elif default_for == "file":
        operation = RevisionParentOperation.FILE
    else:
        return revision
    work_unit = resolve_modelo_work_unit_for_operator_target(
        work_unit_id=revision.work_unit_id,
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )
    require_revision_parent_active(
        work_unit=work_unit,
        calculation_revision_id=revision.calculation_revision_id,
        operation=operation,
    )
    return revision


def resolve_modelo_revision_pick(
    *,
    target: ModeloWorkTarget,
    pick: ModeloRevisionPick | None = None,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> ModeloResolvedRevisionProjection:
    """Resolve and project a revision selection as :class:`ModeloResolvedRevisionProjection`."""
    if pick is None:
        pick = ModeloRevisionPick()
    work_unit = resolve_modelo_work_address_unit(
        work_address_for_modelo_target(target),
        catalogue=catalogue,
        bucket_id=resolved_bucket_id,
    )
    selection = resolve_modelo_calculation_revision_pick(
        work_unit,
        selector=pick.selector,
        calculation_revision_id=pick.calculation_revision_id,
        default_for=pick.default_for,
    )
    return ModeloResolvedRevisionProjection.from_revision(selection.revision, selector=selection.selector)


def _require_revision_state(
    revision: CalculationRevision,
    *,
    allowed: tuple[CalculationRevisionState, ...],
    purpose: str,
) -> CalculationRevision:
    if revision.state not in allowed:
        allowed_values = ", ".join(state.value for state in allowed)
        raise ModeloCalculationRevisionSelectorStateError(
            f"selected revision {revision.calculation_revision_id!r} is in state "
            f"{revision.state.value!r}; {purpose} requires {allowed_values}",
        )
    return revision


def resolve_verifiable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    """Resolve the :class:`CalculationRevision` that ``work verify`` addresses.

    Returns the resolved revision in ANY lifecycle state; no draft gate is
    applied here. Verification-state policy is owned by
    :func:`~cadrumo.application.modelo.verify_modelo_revision` under
    ``aeat-cli-contract``: a revision already out of
    ``BORRADOR`` that carries a granting :class:`VerificationReport` collapses to
    that existing report as an idempotent no-op, and the hard refusal is reserved
    for the inconsistent non-draft/no-granting-report state. Gating ``BORRADOR``
    here would refuse the idempotent retry before the collapse could fire.
    """
    return resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="verify",
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )


def resolve_fileable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    """Resolve the verified-complete :class:`CalculationRevision` that ``work file`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="file",
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )
    if revision.state is CalculationRevisionState.VERIFICADO_COMPLETO:
        return revision
    work_unit = resolve_modelo_work_unit_for_operator_target(
        work_unit_id=revision.work_unit_id,
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )
    raise CalculationRevisionStateError(
        translated_message="errors.error.error_modelo_calculation_revision_state",
        context={"calculation_revision_id": revision.calculation_revision_id, "state": revision.state.value},
        precondition_failure=build_modelo_work_file_unverified_revision_failure(
            calculation_revision_id=revision.calculation_revision_id,
            state=revision.state.value,
            work_unit=work_unit,
        ),
    )


def resolve_exportable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: CalculationRevisionId | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    catalogue: WorkUnitCatalogue,
    resolved_bucket_id: str,
) -> CalculationRevision:
    """Resolve the filed or verified-complete :class:`CalculationRevision` that ``modelo export`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="export",
        catalogue=catalogue,
        resolved_bucket_id=resolved_bucket_id,
    )
    return _require_revision_state(
        revision,
        # Sorted, not `tuple(frozenset)`: `allowed` is joined into the operator-facing
        # refusal, and a frozenset's iteration order would vary the message run to run.
        allowed=tuple(sorted(CURRENT_SEALED_REVISION_STATES, key=lambda state: state.value)),
        purpose="export",
    )


__all__ = [
    "ModeloCalculationRevisionSelector",
    "ModeloCalculationRevisionSelectorAmbiguousError",
    "ModeloCalculationRevisionSelectorNotFoundError",
    "ModeloCalculationRevisionSelectorStateError",
    "ModeloExactWorkUnitTarget",
    "ModeloResolvedRevisionProjection",
    "ModeloResolvedWorkProjection",
    "ModeloRevisionPick",
    "ModeloRevisionPickError",
    "ModeloVisibleFilingTarget",
    "ModeloWorkAddress",
    "ModeloWorkAddressNotFoundError",
    "ModeloWorkCapture",
    "ModeloWorkCaptureError",
    "ModeloWorkCurrentCoordinate",
    "ModeloWorkEnsureResult",
    "ModeloWorkNoActiveBucketError",
    "ModeloWorkPeriodTokenError",
    "ModeloWorkRegistryYearMismatchError",
    "ModeloWorkResolution",
    "ModeloWorkRevisionConflictError",
    "ModeloWorkSelectionMode",
    "ModeloWorkSelectorContradictionError",
    "ModeloWorkSelectorError",
    "ModeloWorkSelectorRequest",
    "ModeloWorkSelectorState",
    "ModeloWorkTarget",
    "ModeloWorkUnitCandidate",
    "ModeloWorkUnitNotFoundError",
    "ModeloWorkVisibleTargetAmbiguousError",
    "assert_work_target_revision",
    "capture_modelo_work_resolution",
    "ensure_modelo_work_unit_for_active_target",
    "law_selected_revision_for_work_target",
    "modelo_work_address_from_operator_target",
    "project_modelo_work_target",
    "project_modelo_work_unit",
    "read_modelo_work_current_coordinate",
    "resolve_exportable_modelo_calculation_revision_address",
    "resolve_fileable_modelo_calculation_revision_address",
    "resolve_modelo_calculation_revision_address",
    "resolve_modelo_revision_for_operator_target",
    "resolve_modelo_revision_pick",
    "resolve_modelo_work_address",
    "resolve_modelo_work_address_unit",
    "resolve_modelo_work_bucket",
    "resolve_modelo_work_target",
    "resolve_modelo_work_unit_for_operator_target",
    "resolve_modelo_work_unit_id",
    "resolve_optional_modelo_work_address",
    "resolve_verifiable_modelo_calculation_revision_address",
    "select_modelo_work_resolution",
    "work_address_for_modelo_target",
]
