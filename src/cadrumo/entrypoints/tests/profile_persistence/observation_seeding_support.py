"""Persist revision-stamped registry observations through their repository."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.application.calculations.observations_repository import APP_FILING_SOURCE_KIND, ResultDispositionProjection
from cadrumo.core.casilla_id import CasillaId
from cadrumo.core.result_disposition import ResultDisposition
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
    revision_id_for_observation,
)


def save_stamped_observation(
    repository: CalculationObservationRepository,
    observation: RegistryModeloObservation,
    *,
    source_kind: str,
    captured_at: datetime | None = None,
    result_disposition: ResultDispositionProjection | None = None,
) -> None:
    """Save ``observation`` stamped with the canonical revision of its own coordinates."""
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind=source_kind,
            captured_at=captured_at,
            result_disposition=result_disposition,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def save_local_m303_compensacion_filings(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
    casillas_by_period: Mapping[str, Mapping[CasillaId, Decimal]],
    captured_at: datetime,
) -> None:
    """Persist one local ``app_filing`` M303 compensacion observation per period."""
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
                disposition=ResultDisposition.COMPENSACION,
                provenance_kind="app_filing",
                provenance_locator=f"test-local-filing:{filing_year}:{period}",
            ),
        )
