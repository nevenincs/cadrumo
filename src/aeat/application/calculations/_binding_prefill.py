"""Binding prefill: resolve `previous_filing` bindings from prior filings.

Sister module to `_relation_prefill`. The runtime distinguishes
`relation` leaves (cross-revision aggregations declared as
`RelationDefinition` records) from `previous_filing` bindings
(declared as `DataBindingDefinition` with `source = "previous_filing"`).
Modelo 390 uses bindings — modelo 200 uses relations — both express
"sum a prior modelo's casilla across periods" but route through
different schema entities.

This module reads observations from the local
`CalculationObservationRepository`, calls the runtime's
`resolve_previous_filing_binding_values`, and returns a mapping
keyed by binding id that callers pass through `binding_values=` to
`calculate_registry_snapshot`. The Sheets engine consumes the same
mapping so binding cells in the workbook get prefilled with the
authoritative value.

Provenance metadata returned alongside lets the apply adapter stamp
each binding's source filing identity so the pull adapter can
detect stale prefills.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from pydantic import BaseModel, ConfigDict

from ...core.resources import resources
from ...domain.calculations.registry._bindings import (
    CasillaObservation,
    RegistryModeloObservation,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ...domain.calculations.registry._schema import RegistrySnapshot
from ._iva_compensation_history import IvaCompensationHistoryRepository, IvaCompensationPeriodState
from ._observations_repository import CalculationObservationRepository


def _selector_year_delta(value: object) -> int:
    """Narrow a binding-selector ``filing_year_delta`` to ``int``.

    Selectors flow through pydantic with a union value type, so static
    analysis loses the per-key shape; an explicit guard restores it and
    rejects unexpected payloads at runtime.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"binding selector 'filing_year_delta' must be int|str, got {type(value).__name__}")


def _selector_periods(value: object) -> tuple[str, ...]:
    """Normalise a binding-selector ``source_periods`` into a tuple of strings."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return tuple(str(item) for item in value)
    raise TypeError(f"binding selector 'source_periods' must be str|tuple[str,...], got {type(value).__name__}")


_LOCAL_FILING_PROVENANCE: Final = "local_filing"
_MODELO_303_IVA_COMPENSATION_BINDING_ID: Final = "modelo-303-compensacion-pendiente-anteriores"

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")


class PrefilledBinding(BaseModel):
    """One binding's resolved value with provenance for downstream stamping."""

    model_config = _STRICT_FROZEN

    binding_id: str
    value: Decimal
    provenance: str = _LOCAL_FILING_PROVENANCE
    source_modelo: str
    source_filing_year: int
    source_periods: tuple[str, ...]
    resolved_at: datetime


class BindingPrefillReport(BaseModel):
    """Outcome of one binding-prefill pass."""

    model_config = _STRICT_FROZEN

    prefilled: tuple[PrefilledBinding, ...]
    binding_values: Mapping[str, Decimal]


class LocalIvaCompensationRecurrence(BaseModel):
    """Local Modelo 303 recurrence extracted for wallet reconciliation only.

    This is comparison evidence. It does not choose the effective casilla `110`
    value; the wallet reconciliation decision remains the only selector.
    """

    model_config = _STRICT_FROZEN

    binding_id: str
    amount: Decimal
    source_modelo: str
    source_filing_year: int
    source_periods: tuple[str, ...]
    resolved_at: datetime


def _gather_observations(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
) -> tuple[RegistryModeloObservation, ...]:
    """Walk every previous_filing binding in the revision and pull
    matching observations from the local store.
    """

    needed: dict[tuple[str, int, str], RegistryModeloObservation] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        payload = repository.load(requirement.modelo, requirement.filing_year, requirement.period)
        if payload is not None:
            obs = payload.observation
        elif requirement.modelo == "303" and iva_history_repository is not None:
            state = iva_history_repository.load_period(requirement.filing_year, requirement.period)
            if state is None:
                continue
            obs = _observation_from_iva_compensation_history(state)
        else:
            continue
        key = (obs.modelo, obs.filing_year, obs.period)
        needed.setdefault(key, obs)
    return tuple(needed.values())


def _observation_from_iva_compensation_history(
    state: IvaCompensationPeriodState,
) -> RegistryModeloObservation:
    """Project secure IVA compensation history into the registry resolver contract."""

    snapshot = resources().modelos.authority.snapshot(
        "303",
        filing_year=state.filing_year,
        period=state.period,
    )
    casillas = {item.id: item for item in snapshot.revision.casillas}
    formulas = {item.target: item for item in snapshot.revision.formulas}

    def observed(casilla_id: str, value: Decimal | None) -> tuple[CasillaObservation, ...]:
        if value is None:
            return ()
        casilla = casillas.get(casilla_id)
        formula = formulas.get(casilla_id)
        operand_refs: tuple[str, ...] = ()
        operand_values: tuple[Decimal, ...] = ()
        if casilla_id == "iva.compensacion-disponible-fin-periodo" and (
            state.pending_for_later_amount is not None and state.period_result_amount is not None
        ):
            operand_refs = ("87", "69")
            operand_values = (state.pending_for_later_amount, state.period_result_amount)
        return (
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                formula_id=formula.id if formula is not None else None,
                operand_refs=operand_refs,
                operand_values=operand_values,
                legal_refs=tuple(casilla.legal_refs) if casilla is not None else (),
                source_refs=tuple(casilla.source_refs) if casilla is not None else (),
            ),
        )

    return RegistryModeloObservation(
        modelo="303",
        filing_year=state.filing_year,
        period=state.period,
        observations=(
            *observed("110", state.prior_pending_amount),
            *observed("78", state.applied_amount),
            *observed("87", state.pending_for_later_amount),
            *observed("69", state.period_result_amount),
            *observed("71", state.final_result_amount),
            *observed("iva.compensacion-disponible-fin-periodo", state.available_end_amount),
        ),
    )


def _requirements_by_binding(
    snapshot: RegistrySnapshot,
) -> dict[str, tuple[str, int, tuple[str, ...]]]:
    grouped: dict[str, tuple[str, int, set[str]]] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        for binding_id in requirement.binding_ids:
            current = grouped.setdefault(binding_id, (requirement.modelo, requirement.filing_year, set()))
            current[2].add(requirement.period)
    return {
        binding_id: (source_modelo, source_year, tuple(sorted(periods)))
        for binding_id, (source_modelo, source_year, periods) in grouped.items()
    }


def resolve_bindings_from_local_store(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
    captured_at: datetime | None = None,
) -> BindingPrefillReport:
    """Resolve every `previous_filing` binding the revision declares
    against observations in the local store.

    Returns a `BindingPrefillReport` carrying the resolved
    `binding_values` mapping (suitable for passing through
    `calculate_registry_snapshot`'s `binding_values=` argument) plus
    a tuple of `PrefilledBinding` records with provenance per entry.

    Bindings the local store cannot satisfy are skipped silently —
    the engine emits blank cells the operator fills by hand. Strict
    enforcement (refusing the export when prior filings are missing)
    is the caller's choice via the prefill report's coverage.
    """

    repo = repository if repository is not None else CalculationObservationRepository()
    iva_repo = iva_history_repository if iva_history_repository is not None else IvaCompensationHistoryRepository()
    when = captured_at if captured_at is not None else datetime.now(UTC)
    observations = _gather_observations(snapshot, repository=repo, iva_history_repository=iva_repo)

    if not observations:
        return BindingPrefillReport(prefilled=(), binding_values={})

    resolved_map = resolve_previous_filing_binding_values(
        snapshot.revision,
        observations,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )

    prefilled: list[PrefilledBinding] = []
    binding_index = {binding.id: binding for binding in snapshot.revision.bindings}
    requirement_index = _requirements_by_binding(snapshot)
    for binding_id, value in resolved_map.items():
        binding = binding_index.get(binding_id)
        if binding is None:
            continue
        selector = binding.selector
        source_modelo, source_filing_year, source_periods = requirement_index.get(
            binding_id,
            (
                str(getattr(selector, "source_modelo", "") or ""),
                snapshot.filing_year + _selector_year_delta(getattr(selector, "filing_year_delta", 0)),
                _selector_periods(getattr(selector, "source_periods", ())),
            ),
        )
        prefilled.append(
            PrefilledBinding(
                binding_id=binding_id,
                value=Decimal(value),
                source_modelo=source_modelo,
                source_filing_year=source_filing_year,
                source_periods=source_periods,
                resolved_at=when,
            )
        )
    return BindingPrefillReport(
        prefilled=tuple(prefilled),
        binding_values=dict(resolved_map),
    )


def extract_modelo_303_local_iva_compensation_recurrence(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository | None = None,
    iva_history_repository: IvaCompensationHistoryRepository | None = None,
    captured_at: datetime | None = None,
) -> tuple[LocalIvaCompensationRecurrence | None, BindingPrefillReport]:
    """Extract the local Modelo 303 compensation recurrence for comparison.

    The returned amount is the locally reconstructed prior compensation balance
    for the target Modelo 303 period. Callers must feed it into
    reconciliation; they must not use it directly as the effective value while
    fresh AEAT wallet evidence exists.
    """

    if str(getattr(snapshot.modelo, "id", snapshot.modelo)) != "303":
        raise ValueError("local IVA compensation recurrence extraction only applies to Modelo 303")
    report = resolve_bindings_from_local_store(
        snapshot,
        repository=repository,
        iva_history_repository=iva_history_repository,
        captured_at=captured_at,
    )
    amount = report.binding_values.get(_MODELO_303_IVA_COMPENSATION_BINDING_ID)
    if amount is None:
        return None, report
    prefilled = next(
        (item for item in report.prefilled if item.binding_id == _MODELO_303_IVA_COMPENSATION_BINDING_ID),
        None,
    )
    if prefilled is None:
        source_modelo, source_year, source_periods = _requirements_by_binding(snapshot)[
            _MODELO_303_IVA_COMPENSATION_BINDING_ID
        ]
        resolved_at = captured_at if captured_at is not None else datetime.now(UTC)
        prefilled = PrefilledBinding(
            binding_id=_MODELO_303_IVA_COMPENSATION_BINDING_ID,
            value=Decimal(amount),
            source_modelo=source_modelo,
            source_filing_year=source_year,
            source_periods=source_periods,
            resolved_at=resolved_at,
        )
    return (
        LocalIvaCompensationRecurrence(
            binding_id=prefilled.binding_id,
            amount=Decimal(amount),
            source_modelo=prefilled.source_modelo,
            source_filing_year=prefilled.source_filing_year,
            source_periods=prefilled.source_periods,
            resolved_at=prefilled.resolved_at,
        ),
        report,
    )


__all__ = [
    "BindingPrefillReport",
    "LocalIvaCompensationRecurrence",
    "PrefilledBinding",
    "extract_modelo_303_local_iva_compensation_recurrence",
    "resolve_bindings_from_local_store",
]
