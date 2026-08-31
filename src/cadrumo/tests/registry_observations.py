"""Registry-grounded observation fixtures for tests.

These helpers build :class:`CasillaObservation` values from the production
registry authority so tests do not invent legal/source provenance.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from ..core.authority_grade import RegistryAuthorityGrade
from ..core.casilla_id import CasillaId
from ..core.resources import bundled_path
from ..domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ..domain.calculations.registry.snapshot import build_snapshot
from ..tests.registry_tree import bundled_registry_tree


def registry_grounded_observations(
    *,
    modelo: str,
    filing_year: int,
    period: str,
    casilla_values: Mapping[CasillaId, Decimal],
    grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
) -> tuple[CasillaObservation, ...]:
    """Return observations grounded in the selected registry snapshot."""

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
    """Return ordered observations grounded in the selected registry snapshot.

    Built from the compile-only registry tree, scoped to ``modelo`` alone,
    rather than through ``bundled_authority()`` -- the authority
    validates every modelo in the bundled tree before it returns anything, so
    one unrelated modelo missing filing capability broke this fixture for
    every caller, on any modelo, anywhere it was imported. ``grade`` defaults
    to :attr:`RegistryAuthorityGrade.FILING`, preserving the prior strict
    contract for callers that need it; a caller asking a narrower question
    (a formula-runtime calculation, an applicability/scheduling fact) should
    pass a lower grade explicitly.
    """

    modelos, catalogues = bundled_registry_tree()
    modelo_definition = next(item for item in modelos if item.id == modelo)
    snapshot = build_snapshot(
        modelo_definition,
        catalogues,
        source_root=bundled_path(),
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
            grade=grade,
        ),
    )
