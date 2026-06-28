"""Post-calculation advisory coordination for :class:`ModeloRevision` work calculations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...domain.calculations.registry import CasillaId, ModeloRevision
from ..aggregation import CalculationSourceDiagnostic
from ..calculations import CalculationObservationRepository
from ._official_box_advisory import collect_official_box_unpopulated_diagnostics
from ._prior_payment_advisory import (
    collect_prior_payment_minoracion_not_captured_diagnostics,
    collect_prior_payment_not_deducted_diagnostics,
)
from ._settlement_grade_advisory import collect_settlement_not_computed_diagnostics

__all__ = ["collect_bucket_aggregation_advisory_diagnostics"]


def collect_bucket_aggregation_advisory_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
) -> tuple[CalculationSourceDiagnostic, ...]:
    observation_repository = CalculationObservationRepository()
    return (
        collect_official_box_unpopulated_diagnostics(revision, casilla_values)
        + collect_prior_payment_not_deducted_diagnostics(
            casilla_values,
            modelo=modelo,
            period_token=period_token,
            filing_year=filing_year,
            observation_repository=observation_repository,
        )
        + collect_prior_payment_minoracion_not_captured_diagnostics(
            modelo=modelo,
            period_token=period_token,
            filing_year=filing_year,
            observation_repository=observation_repository,
        )
        + collect_settlement_not_computed_diagnostics(revision)
    )
