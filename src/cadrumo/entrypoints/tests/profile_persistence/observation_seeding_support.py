"""Persist revision-stamped registry observations through their repository."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.application.calculations.observations_repository import APP_FILING_SOURCE_KIND, ResultDispositionProjection
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.bindings_previous_filing import (
    PreviousFilingProvider,
    previous_filing_binding_source_casilla_ids,
)
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)
from cadrumo.domain.modelos.filing_kind_evidence import ObservedFilingKind

_M200_TURNOVER: CasillaId = validated_casilla_id("DP200007:00255", surface="_M200_TURNOVER")


def save_stamped_observation(
    repository: CalculationObservationRepository,
    observation: RegistryModeloObservation,
    *,
    source_kind: str,
    captured_at: datetime | None = None,
    result_disposition: ResultDispositionProjection | None = None,
    filing_kind: ObservedFilingKind | None = None,
) -> None:
    """Save ``observation`` stamped with the canonical revision of its own coordinates."""
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=source_kind,
            captured_at=captured_at,
            result_disposition=result_disposition,
            filing_kind=filing_kind,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def save_local_m303_compensacion_filings(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
    casillas_by_period: Mapping[str, Mapping[CasillaId, Decimal]],
    captured_at: datetime,
    dispositions_by_period: Mapping[str, ResultDisposition] | None = None,
) -> None:
    """Persist one local ``app_filing`` M303 compensacion observation per period.

    A period is filed as a compensación unless ``dispositions_by_period`` names another
    disposition for it, such as the ingreso of a period that applies carried credit.
    """
    for period, casillas in casillas_by_period.items():
        save_stamped_observation(
            repository,
            RegistryModeloObservation(
                modelo="303",
                filing_year=filing_year,
                period=period,
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=filing_year,
                    period=period,
                    casilla_values=casillas,
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=captured_at,
            result_disposition=ResultDispositionProjection(
                disposition=(dispositions_by_period or {}).get(period, ResultDisposition.COMPENSACION),
                provenance_kind="app_filing",
                provenance_locator=f"test-local-filing:{filing_year}:{period}",
            ),
        )


def save_preceding_m200_turnover(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
    turnover: Decimal,
    captured_at: datetime,
) -> None:
    """Hold the preceding Modelo 200 locally, showing the net turnover (casilla 00255) the rate reads.

    LIS art. 29.1 keys the rate to the turnover of the immediately preceding tax
    period, a fact of that period's own return. An edition whose rate reads no
    preceding turnover gets nothing held, since its earlier year may lie outside
    the support envelope.
    """
    if not _reads_preceding_m200_turnover(filing_year):
        return
    save_stamped_observation(
        repository,
        RegistryModeloObservation(
            modelo="200",
            filing_year=filing_year - 1,
            period="0A",
            observations=registry_grounded_observations(
                modelo="200",
                filing_year=filing_year - 1,
                period="0A",
                casilla_values={_M200_TURNOVER: turnover},
                grade=RegistryAuthorityGrade.CALCULATION,
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=captured_at,
    )


def _reads_preceding_m200_turnover(filing_year: int) -> bool:
    with bundled_indexed_authority().operation() as authority:
        snapshot = authority.snapshot(
            "200", filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
        )
    return any(
        isinstance(binding.provider, PreviousFilingProvider)
        and binding.provider.source_modelo == "200"
        and _M200_TURNOVER in previous_filing_binding_source_casilla_ids(binding)
        for binding in snapshot.revision.bindings
    )
