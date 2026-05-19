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

from ...domain.calculations.registry._bindings import (
    RegistryFilingObservation,
    previous_filing_observation_requirements,
    resolve_previous_filing_binding_values,
)
from ...domain.calculations.registry._schema import RegistrySnapshot
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


def _gather_observations(
    snapshot: RegistrySnapshot,
    *,
    repository: CalculationObservationRepository,
) -> tuple[RegistryFilingObservation, ...]:
    """Walk every previous_filing binding in the revision and pull
    matching observations from the local store.
    """

    needed: dict[tuple[str, int, str], RegistryFilingObservation] = {}
    for requirement in previous_filing_observation_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    ):
        payload = repository.load(requirement.modelo, requirement.filing_year, requirement.period)
        if payload is None:
            continue
        obs = payload.observation
        key = (obs.modelo, obs.filing_year, obs.period)
        needed.setdefault(key, obs)
    return tuple(needed.values())


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
    when = captured_at if captured_at is not None else datetime.now(UTC)
    observations = _gather_observations(snapshot, repository=repo)

    if not observations:
        return BindingPrefillReport(prefilled=(), binding_values={})

    try:
        resolved_map = resolve_previous_filing_binding_values(
            snapshot.revision,
            observations,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
    except Exception:
        # Defensive downgrade — partial coverage of source filings
        # can leave a binding unresolvable. Returning an empty
        # report mirrors the relation-prefill behaviour: caller
        # decides whether to refuse or proceed with blanks.
        return BindingPrefillReport(prefilled=(), binding_values={})

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


__all__ = [
    "BindingPrefillReport",
    "PrefilledBinding",
    "resolve_bindings_from_local_store",
]
