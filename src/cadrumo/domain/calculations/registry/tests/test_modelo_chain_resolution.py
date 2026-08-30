"""Period-filter contract tests for ``resolve_relation_values_from_observations``."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from .....tests.registry_observations import registry_grounded_modelo_observation
from ..bindings import RegistryModeloObservation
from ..relations import resolve_relation_values_from_observations
from ..schema import ModeloDefinition, ModeloRevision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M111_RETENCIONES_PERIODO_CASILLA: CasillaId = validated_casilla_id(
    "01",
    surface="test_modelo_chain_resolution M111 retenciones periodo casilla",
)


def _modelo(modelo_id: str) -> ModeloDefinition:
    modelo, _ = _committed_modelo(modelo_id)
    return modelo


def _revision(modelo_id: str, revision_id: str) -> ModeloRevision:
    return _modelo(modelo_id).revisions[revision_id]


def _quarterly_filings(
    modelo_id: str,
    filing_year: int,
    casilla_quarters: dict[CasillaId, dict[str, Decimal]],
) -> tuple[RegistryModeloObservation, ...]:
    """Build one ``RegistryModeloObservation`` per quarter from a per-quarter casilla map."""

    periods = {"1T", "2T", "3T", "4T"}
    by_period: dict[str, dict[CasillaId, Decimal]] = {p: {} for p in periods}
    for casilla_id, quarter_values in casilla_quarters.items():
        for period, value in quarter_values.items():
            by_period[period][casilla_id] = value
    return tuple(
        registry_grounded_modelo_observation(
            modelo=modelo_id,
            filing_year=filing_year,
            period=period,
            casilla_values=values,
        )
        for period, values in by_period.items()
    )


def test_chain_resolution_returns_empty_under_non_aggregating_period() -> None:
    """Calling resolve under a period the receiver does not aggregate yields nothing.

    Modelo 190's relations all target ``0A``. Asking for ``1T`` exercises
    the period-filter path and produces no requirements, so the resolver
    short-circuits to an empty mapping without demanding observations.
    """

    revision = _revision("190", "2025-y-siguientes")
    values = resolve_relation_values_from_observations(revision, (), filing_year=2026, period="1T")
    assert values == {}


def test_chain_resolution_obeys_target_period_under_non_annual_call() -> None:
    """Calling the resolver with a non-annual period must not aggregate the annual relations."""

    revision = _revision("190", "2025-y-siguientes")
    # Even with full quarterly observations, asking for period "1T" must
    # return nothing — the receiver's relations all target "0A".
    casilla_quarters = {
        _M111_RETENCIONES_PERIODO_CASILLA: {
            "1T": Decimal("1"),
            "2T": Decimal("1"),
            "3T": Decimal("1"),
            "4T": Decimal("1"),
        },
    }
    observations = _quarterly_filings("111", 2026, casilla_quarters)

    values = resolve_relation_values_from_observations(revision, observations, filing_year=2026, period="1T")

    assert values == {}
