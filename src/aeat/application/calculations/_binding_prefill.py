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
    for binding in snapshot.revision.bindings:
        if binding.source != "previous_filing":
            continue
        selector = binding.selector or {}
        source_modelo = str(selector.get("source_modelo", ""))
        if not source_modelo:
            continue
        delta = _selector_year_delta(selector.get("filing_year_delta", 0))
        target_year = snapshot.filing_year + delta
        source_periods = _selector_periods(selector.get("source_periods", ()))
        for payload in repository.iter_modelo(source_modelo):
            obs = payload.observation
            if obs.filing_year != target_year:
                continue
            if source_periods and obs.period not in source_periods:
                continue
            key = (obs.modelo, obs.filing_year, obs.period)
            needed.setdefault(key, obs)
    return tuple(needed.values())


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
    for binding_id, value in resolved_map.items():
        binding = binding_index.get(binding_id)
        if binding is None:
            continue
        selector = binding.selector or {}
        source_periods = _selector_periods(selector.get("source_periods", ()))
        prefilled.append(
            PrefilledBinding(
                binding_id=binding_id,
                value=Decimal(value),
                source_modelo=str(selector.get("source_modelo", "")),
                source_filing_year=snapshot.filing_year + _selector_year_delta(selector.get("filing_year_delta", 0)),
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
