"""Registry-grounded observation fixtures for tests.

These helpers build :class:`CasillaObservation` values from the production
registry authority so tests do not invent legal/source provenance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from ..core.resources import resources
from ..domain.calculations.registry import CasillaId, CasillaObservation, RegistryModeloObservation


def registry_grounded_observations(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CasillaObservation, ...]:
    """Return observations grounded in the selected registry snapshot."""

    return registry_grounded_observation_rows(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        casilla_values=casilla_values.items(),
    )


def registry_grounded_observation_rows(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Iterable[tuple[CasillaId, Decimal]],
) -> tuple[CasillaObservation, ...]:
    """Return ordered observations grounded in the selected registry snapshot."""

    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)
    casillas_by_id = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    observations: list[CasillaObservation] = []
    for casilla_id, value in casilla_values:
        casilla = casillas_by_id.get(casilla_id)
        if casilla is None:
            raise AssertionError(
                f"fixture casilla {casilla_id!r} is absent from "
                f"registry snapshot {modelo}/{snapshot.revision.id}/{filing_year}/{period}",
            )
        observations.append(
            CasillaObservation(
                casilla_id=casilla_id,
                value=value,
                legal_refs=casilla.legal_refs,
                source_refs=casilla.source_refs,
            ),
        )
    return tuple(observations)


def registry_grounded_modelo_observation(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
) -> RegistryModeloObservation:
    """Return a RegistryModeloObservation grounded in the selected snapshot."""

    return RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=registry_grounded_observations(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
        ),
    )
