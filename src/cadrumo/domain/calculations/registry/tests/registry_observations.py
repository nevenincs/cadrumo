"""Registry-grounded observation fixtures for registry-aware tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from functools import cache

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId
from ..authority import bundled_authority
from ..bindings import CasillaObservation, RegistryModeloObservation
from ..temporal import select_revision
from .registry_tree import bundled_registry_tree


@cache
def revision_id_for_coordinates(*, modelo: str, filing_year: int, period: str) -> str:
    """Resolve the law-selected revision used by a persisted test observation."""
    modelos, _catalogues = bundled_registry_tree()
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    return str(select_revision(modelo_definition, filing_year=filing_year, period=period).id)


def revision_id_for_observation(observation: RegistryModeloObservation) -> str:
    """Return the canonical revision stamp for an observation's coordinates."""
    return revision_id_for_coordinates(
        modelo=observation.modelo,
        filing_year=observation.filing_year,
        period=observation.period,
    )


def registry_grounded_observations(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> tuple[CasillaObservation, ...]:
    """Return observations grounded in the selected published snapshot."""
    return registry_grounded_observation_rows(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        casilla_values=casilla_values.items(),
        grade=grade,
    )


def registry_grounded_observation_rows(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Iterable[tuple[CasillaId, Decimal]],
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> tuple[CasillaObservation, ...]:
    """Return ordered observations carrying legal and source provenance."""
    snapshot = bundled_authority().snapshot(
        modelo,
        filing_year=filing_year,
        period=period,
        grade=grade,
    )
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
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> RegistryModeloObservation:
    """Return a registry observation grounded in a published snapshot."""
    return RegistryModeloObservation(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        observations=registry_grounded_observations(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            casilla_values=casilla_values,
            grade=grade,
        ),
    )


__all__ = [
    "registry_grounded_modelo_observation",
    "registry_grounded_observation_rows",
    "registry_grounded_observations",
    "revision_id_for_coordinates",
    "revision_id_for_observation",
]
