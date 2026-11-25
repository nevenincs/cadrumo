"""Direct-binding registry calculation and observation helpers for single-formula Modelo tests."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from .....domain.calculations.registry.bindings import (
    RegistryModeloObservation,
    resolve_available_bound_inputs_by_casilla_id,
)
from .....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from .published_authority_support import published_authority_operation

__all__ = ["calculate_from_bindings", "registry_observation_of"]


def calculate_from_bindings(
    modelo: str,
    *,
    filing_year: int,
    period: str,
    binding_values: Mapping[str, Decimal],
) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL registry calculation for ``modelo`` from ledger-aggregation binding facts.

    The bound leaves are resolved from ``binding_values`` and the engine computes
    the dependent casillas; returns the result and its produced-value count.
    """
    snapshot = published_authority_operation().snapshot(modelo, filing_year=filing_year, period=period)
    values = dict(binding_values)
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def registry_observation_of(
    modelo: str,
    *,
    filing_year: int,
    period: str,
    result: RegistryCalculationResult,
) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=result.observations,
    )
