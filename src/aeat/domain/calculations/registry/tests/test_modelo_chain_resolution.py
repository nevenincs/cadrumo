"""Period-filter contract tests for ``resolve_relation_values_from_observations``."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.resources import bundled_path
from .._bindings import CasillaObservation, RegistryModeloObservation
from .._loader import load_registry_tree
from .._relations import resolve_relation_values_from_observations
from .._schema import ModeloDefinition, ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _modelo(modelo_id: str) -> ModeloDefinition:
    modelos, _ = load_registry_tree(_REGISTRY_ROOT)
    return next(m for m in modelos if m.id == modelo_id)


def _revision(modelo_id: str, revision_id: str) -> ModeloRevision:
    return _modelo(modelo_id).revisions[revision_id]


def _quarterly_filings(
    modelo_id: str, filing_year: int, casilla_quarters: dict[str, dict[str, Decimal]],
) -> tuple[RegistryModeloObservation, ...]:
    """Build one ``RegistryModeloObservation`` per quarter from a per-quarter casilla map."""

    periods = {"1T", "2T", "3T", "4T"}
    by_period: dict[str, dict[str, Decimal]] = {p: {} for p in periods}
    for casilla_id, quarter_values in casilla_quarters.items():
        for period, value in quarter_values.items():
            by_period[period][casilla_id] = value
    return tuple(
        RegistryModeloObservation(
            modelo=modelo_id,
            filing_year=filing_year,
            period=period,
            observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in values.items()),
        )
        for period, values in by_period.items()
    )


def test_chain_resolution_returns_empty_under_non_aggregating_period() -> None:
    """Calling resolve under a period the receiver does not aggregate yields nothing.

    Modelo 190's relations all target ``0A``. Asking for ``1T`` exercises
    the period-filter path and produces no requirements, so the resolver
    short-circuits to an empty mapping without demanding observations.
    """

    revision = _revision("190", "2024-y-siguientes")
    values = resolve_relation_values_from_observations(revision, (), filing_year=2026, period="1T")
    assert values == {}


def test_chain_resolution_obeys_target_period_under_non_annual_call() -> None:
    """Calling the resolver with a non-annual period must not aggregate the annual relations."""

    revision = _revision("190", "2024-y-siguientes")
    # Even with full quarterly observations, asking for period "1T" must
    # return nothing — the receiver's relations all target "0A".
    casilla_quarters = {
        "01": {"1T": Decimal("1"), "2T": Decimal("1"), "3T": Decimal("1"), "4T": Decimal("1")},
    }
    observations = _quarterly_filings("111", 2026, casilla_quarters)

    values = resolve_relation_values_from_observations(revision, observations, filing_year=2026, period="1T")

    assert values == {}
