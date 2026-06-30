"""Post-calculation advisory coordination for bucket aggregation calculations.

The bucket aggregation calculate path first resolves source-backed values,
executes the registry formula engine, and persists the calculated revision. This
module then fans out advisory-only checks over the loaded
:class:`aeat.domain.calculations.registry.ModeloRevision` and the computed
:class:`aeat.domain.calculations.registry.CasillaId` value map, returning
non-blocking
:class:`aeat.application.aggregation.CalculationSourceDiagnostic` rows for the
caller to append to source mesh diagnostics. It does not compute, override, or
persist casilla values.

The prior-payment collectors need persisted filing observations, so the
coordinator shares one
:class:`aeat.application.calculations.CalculationObservationRepository` instance
across them. The official-box and settlement collectors read only the revision
structure and calculated casilla values. Together the collectors extend the
source mesh's no-silent-under-declaration diagnostics with checks whose evidence
only exists after the revision has been calculated.

See Also:
    :func:`aeat.application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
        Calls this coordinator after the calculation revision has been created.
    :func:`aeat.application.modelo._official_box_advisory.collect_official_box_unpopulated_diagnostics`:
        Mirrors registry-authored ADVISORY predicates as calculate diagnostics.
    :mod:`aeat.application.modelo._prior_payment_advisory`:
        Emits Modelo 130 prior-payment carry degradation advisories.
    :func:`aeat.application.modelo._settlement_grade_advisory.collect_settlement_not_computed_diagnostics`:
        Emits structural settlement-completeness advisories for partially modelled revisions.
"""

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
    """Return advisory diagnostics raised after bucket aggregation calculation.

    Runs the calculate-path advisory collectors in tuple order:
    official-box transcription, Modelo 130 prior-payment under-deduction, Modelo
    130 prior-payment minoracion capture, and settlement-not-computed structure.
    These diagnostics are informational and non-blocking; the calculation result
    already exists, and the caller merely appends these rows to the source mesh's
    existing :class:`aeat.application.aggregation.CalculationSourceDiagnostic`
    sequence.

    Args:
        revision: The :class:`aeat.domain.calculations.registry.ModeloRevision`
            whose predicates, casillas, and formulas are inspected.
        casilla_values: Computed engine values keyed by
            :class:`aeat.domain.calculations.registry.CasillaId`.
        modelo: Target modelo identifier used by modelo-specific advisory
            collectors.
        period_token: Bare registry period token for the filing being
            calculated.
        filing_year: Filing year whose same-ejercicio prior observations may be
            inspected.

    Returns:
        Tuple of :class:`aeat.application.aggregation.CalculationSourceDiagnostic`
        advisory rows, or an empty tuple when no post-calculation advisory fires.

    See Also:
        :class:`aeat.application.calculations.CalculationObservationRepository`:
            Supplies the prior-filing observation catalogue used by the Modelo
            130 prior-payment advisory collectors.
        :func:`aeat.application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
            Appends this tuple to the source mesh diagnostics on the returned
            bucket aggregation result.
    """
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
