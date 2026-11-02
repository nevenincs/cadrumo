"""Relation values resolved from synthetic quarterly observations of a source modelo."""

from __future__ import annotations

from decimal import Decimal

from .....core.casilla_id import CasillaId
from ..ids import BindingId
from ..relations import relation_source_requirements
from ..schema import RegistrySnapshot
from .registry_observations import registry_grounded_modelo_observation
from .relation_fixture import resolve_relation_values_from_observations


def _value_for(data_type: str, period_index: int) -> Decimal:
    quarter = Decimal(period_index + 1)
    if data_type == "integer":
        return quarter
    return Decimal("10") * quarter


def relation_values_from_synthetic_quarters(
    snapshot: RegistrySnapshot,
    source_snapshot: RegistrySnapshot,
    *,
    source_modelo: str,
    filing_year: int,
) -> dict[BindingId, Decimal]:
    """Resolve the annual relations from one distinct synthetic observation per required source period."""
    source_casilla_ids = {casilla.id: casilla for casilla in source_snapshot.revision.casillas}
    requirements = relation_source_requirements(snapshot.revision, filing_year=filing_year, period="0A")
    observed_by_period: dict[str, dict[CasillaId, Decimal]] = {}
    for requirement in requirements:
        source_casilla_id = requirement.source_casilla_ids[0]
        source_casilla = source_casilla_ids[source_casilla_id]
        for index, period in enumerate(requirement.periods):
            value = _value_for(source_casilla.data_type, index)
            observed_by_period.setdefault(period, {})[source_casilla_id] = value
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo=source_modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
        )
        for period, casilla_values in sorted(observed_by_period.items())
    )
    return resolve_relation_values_from_observations(
        snapshot.revision,
        observations,
        filing_year=filing_year,
        period="0A",
    )
