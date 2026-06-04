"""Application-level addressing for modelo work CLI consumers."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.resources import resources
from ...domain.calculations.registry._temporal import select_revision
from ...domain.contribuyente import CCAA
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos._errors import ModeloError
from ...domain.modelos._work_unit import WorkUnit
from ._actions import create_work_unit, get_calculation_revision, rename_work_unit
from ._selectors import (
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloWorkResolution,
    ModeloWorkSelectorRequest,
    ModeloWorkSelectorState,
    resolve_modelo_work_unit,
    select_current_draft_revision,
    select_current_verified_revision,
    select_exportable_revision,
    select_modelo_calculation_revision,
)


@dataclass(frozen=True, slots=True)
class ModeloWorkAddress:
    """Operator-facing or exact modelo work address."""

    work_unit_id: str | None = None
    modelo: str | None = None
    filing_year: int | None = None
    period: str | None = None
    registry_revision_id: str | None = None
    bucket_id: str | None = None


class ModeloWorkAddressNotFoundError(ModeloError, LookupError):
    """Raised when a natural modelo work address resolves no active work unit."""


class ModeloWorkRegistryYearMismatchError(ModeloError, ValueError):
    """Raised when a registry revision does not cover the filing year."""


@dataclass(frozen=True, slots=True)
class ModeloWorkEnsureResult:
    """Result of resolving or creating a visible-target work unit."""

    work_unit: WorkUnit
    reused: bool
    name_applied: str | None = None


def _revision_covers_year(*, modelo: str, revision_id: str, filing_year: int) -> bool:
    definition = resources().modelos.authority.modelo(modelo.strip())
    revision = definition.revisions[revision_id]
    selector = revision.period_selector
    if selector.years:
        return filing_year in selector.years
    if selector.year_from is None:
        return True
    if selector.year_to is None:
        return filing_year >= selector.year_from
    return selector.year_from <= filing_year <= selector.year_to


def resolve_registry_revision_for_work_target(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    registry_revision_id: str | None,
) -> str:
    """Resolve and validate the registry revision for a visible filing target."""
    if registry_revision_id is None:
        definition = resources().modelos.authority.modelo(modelo.strip())
        return select_revision(definition, filing_year=filing_year, period=period).id
    revision_id = registry_revision_id.strip()
    if not _revision_covers_year(modelo=modelo, revision_id=revision_id, filing_year=filing_year):
        raise ModeloWorkRegistryYearMismatchError(
            f"registry revision {revision_id!r} does not cover filing year {filing_year}"
        )
    return revision_id


def ensure_modelo_work_unit_for_visible_target(
    *,
    bucket_id: str,
    modelo: str,
    filing_year: int,
    period: str,
    registry_revision_id: str | None,
    name: str | None = None,
    actor: str = "operator",
    causante_ccaa: CCAA | None = None,
) -> ModeloWorkEnsureResult:
    """Resume or create the active work unit for one visible filing target."""
    requested_revision = registry_revision_id.strip() if registry_revision_id is not None else None
    resolution = resolve_optional_modelo_work_address(
        ModeloWorkAddress(
            bucket_id=bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            registry_revision_id=requested_revision,
        )
    )
    if resolution.work_unit is not None:
        unit = resolution.work_unit
        name_applied: str | None = None
        if name is not None and name.strip() and name.strip() != unit.name:
            unit = rename_work_unit(unit.work_unit_id, name, actor=actor)
            name_applied = unit.name
        return ModeloWorkEnsureResult(work_unit=unit, reused=True, name_applied=name_applied)

    revision_id = resolve_registry_revision_for_work_target(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        registry_revision_id=requested_revision,
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
    )
    return ModeloWorkEnsureResult(work_unit=unit, reused=False)


def resolve_modelo_work_address(address: ModeloWorkAddress) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address."""
    resolution = resolve_optional_modelo_work_address(address)
    if resolution.state is ModeloWorkSelectorState.ABSENT or resolution.work_unit is None:
        raise ModeloWorkAddressNotFoundError("no active modelo work unit matches the supplied address")
    return resolution


def resolve_optional_modelo_work_address(address: ModeloWorkAddress) -> ModeloWorkResolution:
    """Resolve an operator-facing modelo work address, allowing absence."""
    resolution = resolve_modelo_work_unit(
        ModeloWorkSelectorRequest(
            work_unit_id=address.work_unit_id,
            modelo=address.modelo,
            filing_year=address.filing_year,
            period=address.period,
            revision_id=address.registry_revision_id,
            bucket_id=address.bucket_id,
        )
    )
    return resolution


def resolve_modelo_work_address_unit(address: ModeloWorkAddress) -> WorkUnit:
    """Resolve an operator-facing modelo work address to one work unit."""
    resolution = resolve_modelo_work_address(address)
    assert resolution.work_unit is not None
    return resolution.work_unit


def resolve_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
    default_for: str | None = None,
) -> CalculationRevision:
    """Resolve a calculation revision by exact id or under a modelo work address."""
    if calculation_revision_id is not None and address == ModeloWorkAddress():
        return get_calculation_revision(calculation_revision_id)

    work_unit = resolve_modelo_work_address_unit(address)
    if calculation_revision_id is not None:
        return select_modelo_calculation_revision(
            work_unit,
            selector=ModeloCalculationRevisionSelector.EXPLICIT,
            calculation_revision_id=calculation_revision_id,
        ).revision
    if default_for == "verify" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_current_draft_revision(work_unit).revision
    if default_for == "file" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_current_verified_revision(work_unit).revision
    if default_for == "export" and selector is ModeloCalculationRevisionSelector.CURRENT:
        return select_exportable_revision(work_unit).revision
    return select_modelo_calculation_revision(work_unit, selector=selector).revision


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
            f"{revision.state.value!r}; {purpose} requires {allowed_values}"
        )
    return revision


def resolve_verifiable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the calculation revision that ``work verify`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="verify",
    )
    return _require_revision_state(
        revision,
        allowed=(CalculationRevisionState.BORRADOR,),
        purpose="verification",
    )


def resolve_fileable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the calculation revision that ``work file`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="file",
    )
    return _require_revision_state(
        revision,
        allowed=(CalculationRevisionState.VERIFICADO_COMPLETO,),
        purpose="filing",
    )


def resolve_exportable_modelo_calculation_revision_address(
    *,
    address: ModeloWorkAddress,
    calculation_revision_id: str | None = None,
    selector: ModeloCalculationRevisionSelector = ModeloCalculationRevisionSelector.CURRENT,
) -> CalculationRevision:
    """Resolve the calculation revision that ``modelo export`` may consume."""
    revision = resolve_modelo_calculation_revision_address(
        address=address,
        calculation_revision_id=calculation_revision_id,
        selector=selector,
        default_for="export",
    )
    return _require_revision_state(
        revision,
        allowed=(
            CalculationRevisionState.VERIFICADO_COMPLETO,
            CalculationRevisionState.PRESENTADO,
        ),
        purpose="export",
    )


__all__ = [
    "ModeloCalculationRevisionSelector",
    "ModeloCalculationRevisionSelectorAmbiguousError",
    "ModeloCalculationRevisionSelectorNotFoundError",
    "ModeloCalculationRevisionSelectorStateError",
    "ModeloWorkAddress",
    "ModeloWorkAddressNotFoundError",
    "ModeloWorkEnsureResult",
    "ModeloWorkRegistryYearMismatchError",
    "ensure_modelo_work_unit_for_visible_target",
    "resolve_exportable_modelo_calculation_revision_address",
    "resolve_fileable_modelo_calculation_revision_address",
    "resolve_modelo_calculation_revision_address",
    "resolve_modelo_work_address",
    "resolve_modelo_work_address_unit",
    "resolve_optional_modelo_work_address",
    "resolve_registry_revision_for_work_target",
    "resolve_verifiable_modelo_calculation_revision_address",
]
