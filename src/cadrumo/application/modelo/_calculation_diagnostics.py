"""Post-calculation advisory coordination for bucket aggregation calculations.

The bucket aggregation calculate path first resolves source-backed values,
executes the registry formula engine, and persists the calculated revision. This
module then fans out advisory-only checks over the loaded
:class:`ModeloRevision` and the computed :class:`CasillaId` value map, returning
non-blocking
:class:`~application.aggregation.CalculationSourceDiagnostic` rows for the
caller to append to source mesh diagnostics. It does not compute, override, or
persist casilla values.

The prior-payment collectors need persisted filing observations, so the
coordinator shares one
:class:`~application.calculations.CalculationObservationRepository` instance
across them. The official-box and settlement collectors read only the revision
structure and calculated casilla values. Together the collectors extend the
source mesh's no-silent-under-declaration diagnostics with checks whose evidence
only exists after the revision has been calculated.

See Also:
    :func:`~application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
        Calls this coordinator after the calculation revision has been created.
    :func:`~application.modelo._official_box_advisory.collect_official_box_unpopulated_diagnostics`:
        Mirrors registry-authored ADVISORY predicates as calculate diagnostics.
    :mod:`~application.modelo._prior_payment_advisory`:
        Emits Modelo 130 prior-payment carry degradation advisories.
    :func:`~application.modelo._settlement_grade_advisory.collect_settlement_not_computed_diagnostics`:
        Emits structural settlement-completeness advisories for partially modelled revisions.
    :func:`~application.modelo._bienes_inversion_advisory.collect_bienes_inversion_regularizacion_diagnostics`:
        Emits the Modelo 303 capital-goods IVA regularización proposed-casilla-43 advisory.
    :func:`~application.modelo._prorrata_regularizacion_advisory.collect_prorrata_regularizacion_diagnostics`:
        Emits the Modelo 303 annual prorrata-general regularización proposed-casilla-44 advisory.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core import CasillaId
from ...domain.calculations.registry.schema import ModeloRevision
from ..aggregation import CalculationSourceDiagnostic
from ..calculations import CalculationObservationRepository
from ._bienes_inversion_advisory import collect_bienes_inversion_regularizacion_diagnostics
from ._minimo_descendientes_advisory import (
    collect_descendientes_count_desync_diagnostics,
    collect_guarderia_madre_meses_undeclared_diagnostics,
    collect_guarderia_spend_shape_diagnostics,
    collect_minimo_descendientes_dependencia_diagnostics,
    collect_minimo_descendientes_entry_date_missing_diagnostics,
    collect_minimo_descendientes_prorrata_inferred_diagnostics,
    collect_minimo_descendientes_rentas_undeclared_diagnostics,
    collect_minimo_descendientes_undeclared_diagnostics,
)
from ._official_box_advisory import collect_official_box_unpopulated_diagnostics
from ._prior_payment_advisory import (
    collect_prior_payment_minoracion_not_captured_diagnostics,
    collect_prior_payment_not_deducted_diagnostics,
)
from ._prorrata_regularizacion_advisory import collect_prorrata_regularizacion_diagnostics
from ._rate_box_advisory import collect_rate_box_coverage_diagnostics
from ._settlement_grade_advisory import collect_settlement_not_computed_diagnostics

__all__ = ["collect_bucket_aggregation_advisory_diagnostics"]


def collect_bucket_aggregation_advisory_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return advisory diagnostics raised after bucket aggregation calculation.

    Runs the calculate-path advisory collectors in tuple order:
    official-box transcription, Modelo 130 prior-payment under-deduction, Modelo
    130 prior-payment minoracion capture, settlement-not-computed structure, the
    Modelo 100 mínimo-por-descendientes undeclared-facts advisory, the Modelo
    303 capital-goods IVA regularización (LIVA arts. 107-110) proposed-casilla-43
    advisory, and the Modelo 303 annual prorrata-general regularización (LIVA
    arts. 104-105) proposed-casilla-44 advisory. These diagnostics are
    informational and non-blocking; the
    calculation result already exists, and the caller merely appends these rows
    to the source mesh's existing
    :class:`~application.aggregation.CalculationSourceDiagnostic`
    sequence.

    The Modelo 100 mínimo-por-descendientes casillas (0513/0514) are no longer
    advisory-only for the halving/blank-entry checks a prior interim module
    raised: a computed engine (:func:`~application.modelo._profile_binding.inject_derived_minimo_descendientes_facts`)
    that derives the Art. 58/61 LIRPF aggregate — including the custodia-compartida
    halving — directly from the active profile, so those two checks are structurally
    unreachable and were retired. A new, narrower advisory
    (:func:`~application.modelo._minimo_descendientes_advisory.collect_minimo_descendientes_undeclared_diagnostics`)
    replaces them: because a genuinely childless profile and a profile that simply
    never declared its descendientes both resolve 0513 to the same zero, this
    collector flags the ambiguous case (0513 = 0 and no descendiente facts declared
    at all) and points the operator at ``aeat config profile descendiente add``.

    Args:
        revision: The :class:`ModeloRevision` whose predicates, casillas, and
            formulas are inspected.
        casilla_values: Computed engine values keyed by :class:`CasillaId`.
        modelo: Target modelo identifier used by modelo-specific advisory
            collectors.
        period_token: Bare registry period token for the filing being
            calculated.
        filing_year: Filing year whose same-ejercicio prior observations may be
            inspected.
        bucket_id: Bucket identifier used by profile-backed advisory
            collectors.

    Returns:
        Tuple of
        :class:`~application.aggregation.CalculationSourceDiagnostic`
        advisory rows, or an empty tuple when no post-calculation advisory fires.

    See Also:
        :class:`~application.calculations.CalculationObservationRepository`:
            Supplies the prior-filing observation catalogue used by the Modelo
            130 prior-payment advisory collectors.
        :func:`~application.modelo.calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`:
            Appends this tuple to the source mesh diagnostics on the returned
            bucket aggregation result.
    """
    observation_repository = CalculationObservationRepository()
    return (
        collect_official_box_unpopulated_diagnostics(revision, casilla_values)
        + collect_prior_payment_not_deducted_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            period_token=period_token,
            filing_year=filing_year,
            observation_repository=observation_repository,
        )
        + collect_prior_payment_minoracion_not_captured_diagnostics(
            revision,
            modelo=modelo,
            period_token=period_token,
            filing_year=filing_year,
            observation_repository=observation_repository,
        )
        + collect_settlement_not_computed_diagnostics(revision)
        + collect_minimo_descendientes_undeclared_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_minimo_descendientes_prorrata_inferred_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_minimo_descendientes_rentas_undeclared_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_minimo_descendientes_entry_date_missing_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_minimo_descendientes_dependencia_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_guarderia_spend_shape_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_guarderia_madre_meses_undeclared_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_descendientes_count_desync_diagnostics(
            modelo=modelo,
            bucket_id=bucket_id,
        )
        + collect_bienes_inversion_regularizacion_diagnostics(
            revision,
            modelo=modelo,
            period_token=period_token,
            filing_year=filing_year,
            bucket_id=bucket_id,
        )
        + collect_rate_box_coverage_diagnostics(revision, casilla_values)
        + collect_prorrata_regularizacion_diagnostics(
            revision,
            casilla_values,
            modelo=modelo,
            period_token=period_token,
            filing_year=filing_year,
            bucket_id=bucket_id,
            observation_repository=observation_repository,
        )
    )
