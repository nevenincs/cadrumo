"""Calculate-path advisories around the Modelo 130 prior-payment carry.

Modelo 130 is cumulative from the start of the ejercicio: casilla ``01``
(Ingresos) accumulates year-to-date, so casilla ``04`` (importe del pago
fraccionado) is the cumulative 20 % of the YTD rendimiento. Casilla ``05``
("Pagos fraccionados anteriores") is now a bound previous-filing carry,
``modelo-130-pagos-fraccionados-anteriores``: for each same-ejercicio prior
trimestre it adds the positive part of casilla ``07`` and subtracts casilla
``16``. The result is then consumed unchanged by casilla ``07`` =
``04 - 05 - 06``.

This module does not compute the carry. It emits non-blocking
:class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic` advisories
for the two calculate-path degradation cases around the live carry:

* ``prior_payment_not_deducted`` fires only when a non-first trimestre has
  positive cumulative ingresos, casilla ``05`` still resolved to zero, and a
  real prior-trimestre Modelo 130 filing exists in the local
  :class:`~cadrumo.application.calculations.CalculationObservationRepository`.
  Under the Stage-2 carry, normal readable prior filings populate casilla ``05``
  and this prior over-payment advisory stays silent.
* ``prior_payment_minoracion_not_captured`` fires when a carried prior filing
  includes casilla ``07`` but lacks any casilla ``16`` entry. The registry
  resolver treats that absent minoración as ``Decimal("0")`` so the carry can
  continue, while the advisory names the evidence gap. A filed zero is captured
  evidence and stays silent.

The first-filer safeguard still keys off real stored observations, never a bare
period token: a 1T target or a genuine first-obligation quarter has no prior
trimestre to carry, so casilla ``05`` materialises zero absent-by-design.

See Also:
    :func:`~cadrumo.application.modelo._calculation_diagnostics.collect_bucket_aggregation_advisory_diagnostics`:
        Wires these advisories into the bucket-aggregation calculate path.
    :class:`~cadrumo.application.calculations.CalculationObservationRepository`:
        Supplies the persisted prior-filing observations inspected by both
        advisories.
    :class:`~cadrumo.core.CasillaId`:
        The validated registry casilla key type used for the carry and advisory
        targets.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core.modelo import Modelo
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.period_offset_math import same_ejercicio_prior_quarter_anchors
from ...domain.calculations.registry.schema import ModeloRevision
from ..aggregation import CalculationSourceDiagnostic, casilla_registry_legal_refs
from ..calculations import CalculationObservationRepository

__all__ = [
    "collect_prior_payment_minoracion_not_captured_diagnostics",
    "collect_prior_payment_not_deducted_diagnostics",
]

#: The casilla whose zero value (on a non-first trimestre with a real prior
#: filing) indicates an undeducted prior pago fraccionado.
_PRIOR_PAYMENT_CASILLA: Final[CasillaId] = validated_casilla_id("05", surface="_PRIOR_PAYMENT_CASILLA")

#: The cumulative ingresos casilla whose positivity proves real activity.
_CUMULATIVE_INGRESOS_CASILLA: Final[CasillaId] = validated_casilla_id("01", surface="_CUMULATIVE_INGRESOS_CASILLA")

#: The prior-quarter casilla whose presence proves the prior filing carried a
#: pago fraccionado the casilla-05 carry deducts.
_PRIOR_POSITIVE_PART_CASILLA: Final[CasillaId] = validated_casilla_id("07", surface="_PRIOR_POSITIVE_PART_CASILLA")

#: The prior-quarter minoración casilla (Deducción por inversión en vivienda
#: habitual) the casilla-05 carry subtracts. A prior filing carrying casilla 07
#: but LACKING any casilla-16 entry is "not captured" (distinct from "filed 0");
#: the carry proceeds treating absence as zero, but the gap must surface.
_PRIOR_MINORACION_CASILLA: Final[CasillaId] = validated_casilla_id("16", surface="_PRIOR_MINORACION_CASILLA")


def _prior_trimestre_codes(period_token: str) -> tuple[str, ...]:
    """Return the same-ejercicio trimestre codes that precede ``period_token``.

    For ``2T`` -> ``("1T",)``; for ``3T`` -> ``("1T", "2T")``; for ``4T`` ->
    ``("1T", "2T", "3T")``. A first trimestre (``1T``) or a non-quarterly token
    yields an empty tuple — no prior pago fraccionado is possible.
    """
    try:
        anchors = same_ejercicio_prior_quarter_anchors(period_token)
    except RegistryValidationError:
        return ()
    return tuple(period for _year_delta, period in anchors)


def _prior_m130_filing_exists(
    repository: CalculationObservationRepository,
    *,
    filing_year: int,
    prior_codes: tuple[str, ...],
) -> bool:
    """Return True when a prior-trimestre M130 filing for ``filing_year`` exists.

    Scans the local observation catalogue for any persisted Modelo 130
    observation in the same ejercicio whose period is one of ``prior_codes``.
    This is the first-filer safeguard: a true first-obligation filer has no such
    observation, so the caller must not surface the undeducted-prior-payment
    advisory.
    """
    if not prior_codes:
        return False
    wanted = set(prior_codes)
    for payload in repository.iter_modelo(Modelo.M130.value):
        observation = payload.observation
        if observation.filing_year == filing_year and observation.period in wanted:
            return True
    return False


def collect_prior_payment_not_deducted_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepository,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when a non-first M130 trimestre under-deducts prior payments.

    The advisory (``reason = "prior_payment_not_deducted"``) fires exactly when
    the target period is a non-first trimestre, casilla ``01`` is strictly
    positive, casilla ``05`` still resolved to zero, AND a prior-trimestre
    Modelo 130 filing for the same ejercicio exists in
    ``observation_repository``. In the current registry, the bound casilla-05
    carry normally populates this deduction from readable observations; this
    advisory is the calculate-path degradation signal for a carry that could
    not populate despite a real prior filing. The last gate keeps a true
    first-obligation filer (whose casilla ``05`` is legitimately zero) silent.

    Args:
        revision: The :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
            being calculated, read only for casilla 05's own registry grounding
            -- never for a legal figure.
        casilla_values: The computed casilla values (engine result), keyed by
            :class:`~cadrumo.core.CasillaId`.
        modelo: The modelo identifier of the filing being calculated. Used to
            confirm the modelo is 130 (the cumulative pago-fraccionado form this
            carry applies to) before any catalogue scan.
        period_token: The bare registry period code of the target filing (e.g.
            ``"2T"``).
        filing_year: The ejercicio whose prior trimestres are scanned.
        observation_repository: The local
            :class:`~cadrumo.application.calculations.CalculationObservationRepository`
            scanned for a prior-period filing — the first-filer safeguard.

    Returns:
        A tuple of
        :class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic`
        advisories — empty when no under-deduction is detected, otherwise the
        single advisory.

    See Also:
        :func:`collect_prior_payment_minoracion_not_captured_diagnostics`:
            Covers the companion evidence-gap case where the carry resolves but
            a prior casilla-16 minoración was absent from the stored observation.
        :class:`~cadrumo.application.calculations.CalculationObservationRepository`:
            Provides the first-filer safeguard and prior-filing evidence.
    """
    if modelo != Modelo.M130.value:
        return ()
    prior_codes = _prior_trimestre_codes(period_token)
    if not prior_codes:
        return ()
    cumulative_ingresos = casilla_values.get(_CUMULATIVE_INGRESOS_CASILLA, Decimal(0))
    if cumulative_ingresos <= Decimal(0):
        return ()
    prior_payment = casilla_values.get(_PRIOR_PAYMENT_CASILLA, Decimal(0))
    if prior_payment != Decimal(0):
        return ()
    if not _prior_m130_filing_exists(
        observation_repository,
        filing_year=filing_year,
        prior_codes=prior_codes,
    ):
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="prior_payment_not_deducted",
            source_kind="modelo_130_prior_pago_fraccionado",
            message=(
                f"Modelo 130 {period_token} is cumulative, but casilla 05 ('Pagos fraccionados "
                f"anteriores') is zero while a prior-trimestre {filing_year} filing exists; casilla "
                f"07 = 04 - 05 - 06 does not deduct the pago fraccionado already paid in "
                f"{', '.join(prior_codes)}, so this filing over-declares (RD 439/2007 art. 110). "
                f"The casilla-05 carry could not populate from the prior filing's observation "
                f"(absent or unreadable); re-file the prior trimestre or enter its pago fraccionado "
                f"in casilla 05 before filing"
            ),
            casilla_id=_PRIOR_PAYMENT_CASILLA,
            # Casilla-derived: the advisory's subject IS casilla 05's own carry,
            # so its typed grounding is read off the registry rather than
            # restated from the RD 439/2007 art. 110 citation already in the
            # message.
            legal_refs=casilla_registry_legal_refs(revision, _PRIOR_PAYMENT_CASILLA),
        ),
    )


def collect_prior_payment_minoracion_not_captured_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepository,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when a carried prior M130 filing lacks its casilla-16 minoración.

    The casilla-05 carry (``modelo-130-pagos-fraccionados-anteriores``) computes
    ``Σ max(0, prior 07_q) − Σ prior 16_q``. A prior-trimestre filing that carries
    casilla 07 (a real pago fraccionado the carry deducts) but LACKS any casilla-16
    entry is "not captured" - distinct from a filing that genuinely declared
    casilla 16 = 0. Distinguishing filed-zero from not-captured, the carry
    proceeds (treating the absent minoración as zero) but the gap MUST surface
    as a non-blocking advisory naming it - the minoración is never silently
    dropped (``no-silent-under-declaration``).

    The advisory fires for the SAME ejercicio's prior trimestres of a non-first
    target quarter, only when at least one prior filing carries casilla 07 but no
    casilla-16 entry. A prior filing that declares casilla 16 = 0 explicitly is a
    silent no-op (the value is captured; it just happens to be zero).

    Args:
        revision: The :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
            being calculated, read only for casilla 05's own registry grounding.
        modelo: The modelo identifier of the filing being calculated; the advisory
            applies only to Modelo 130.
        period_token: The bare registry period code of the target filing.
        filing_year: The ejercicio whose prior trimestres are scanned.
        observation_repository: The local
            :class:`~cadrumo.application.calculations.CalculationObservationRepository`
            scanned for prior-period observations.

    Returns:
        A tuple of
        :class:`~cadrumo.application.aggregation.CalculationSourceDiagnostic`
        advisories — empty when every carried prior filing captured its
        casilla-16 minoración, otherwise the single
        ``prior_payment_minoracion_not_captured`` advisory.

    See Also:
        :func:`collect_prior_payment_not_deducted_diagnostics`:
            Covers the degraded carry case where casilla 05 stayed zero despite
            a real prior M130 filing.
        :class:`~cadrumo.application.calculations.CalculationObservationRepository`:
            Supplies the prior-filing observations whose casilla-16 presence
            distinguishes filed zero from not captured.
    """
    if modelo != Modelo.M130.value:
        return ()
    prior_codes = _prior_trimestre_codes(period_token)
    if not prior_codes:
        return ()
    wanted = set(prior_codes)
    uncaptured_periods: list[str] = []
    for payload in observation_repository.iter_modelo(Modelo.M130.value):
        observation = payload.observation
        if observation.filing_year != filing_year or observation.period not in wanted:
            continue
        casilla_values = observation.casilla_values
        has_positive_part = _PRIOR_POSITIVE_PART_CASILLA in casilla_values
        has_minoracion = _PRIOR_MINORACION_CASILLA in casilla_values
        if has_positive_part and not has_minoracion:
            uncaptured_periods.append(observation.period)
    if not uncaptured_periods:
        return ()
    gap = ", ".join(sorted(set(uncaptured_periods)))
    return (
        CalculationSourceDiagnostic(
            reason="prior_payment_minoracion_not_captured",
            source_kind="modelo_130_prior_pago_fraccionado",
            message=(
                f"Modelo 130 {period_token} casilla 05 carries the prior pago fraccionado from {gap}, "
                f"but those prior {filing_year} filings carry no casilla 16 (minoración) entry. The "
                f"carry treats the absent minoración as zero; if those trimestres declared a non-zero "
                f"casilla 16 the deduction is over-stated. Re-file the prior trimestre(s) so casilla 16 "
                f"is captured, or confirm it was genuinely zero (AEAT instr.: casilla 05 minorada en la "
                f"casilla 16)"
            ),
            casilla_id=_PRIOR_PAYMENT_CASILLA,
            legal_refs=casilla_registry_legal_refs(revision, _PRIOR_PAYMENT_CASILLA),
        ),
    )
