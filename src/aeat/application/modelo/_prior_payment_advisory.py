"""Calculate-path advisory for an undeducted Modelo 130 prior pago fraccionado.

Modelo 130 is cumulative from the start of the ejercicio: casilla ``01``
(Ingresos) accumulates year-to-date, so casilla ``04`` (importe del pago
fraccionado) is the cumulative 20 % of the YTD rendimiento. To avoid the
operator paying the same euros twice, casilla ``05`` ("Pagos fraccionados
anteriores") carries the pagos fraccionados already declared in the prior
trimestres of the same ejercicio, and the resultado parcial formula
``modelo-130-resultado-apartado-i`` subtracts it: casilla ``07`` =
``04 - 05 - 06`` (AEAT instr. casilla 07, "restar el importe de la casilla 05
y 06 al importe de la casilla 04"; RD 439/2007 art. 110).

Casilla ``05`` is an ``input_kind = "manual"`` cell with no binding, so a
cumulative 2T/3T/4T calculate never auto-deducts the prior trimestres' pago
fraccionado. A filer who files 1T (paying, say, 100) and then runs a cumulative
2T calculate gets casilla ``05`` = 0, so casilla ``07`` does NOT subtract the
100 already paid — the operator over-pays. No finding surfaces because the
return is internally consistent; the over-declaration is silent
(``no-silent-under-declaration``).

This module surfaces that contradiction on the calculate path as a non-blocking
:class:`~aeat.application.aggregation.CalculationSourceDiagnostic` with
``reason = "prior_payment_not_deducted"``. The advisory fires ONLY when:

* the target period is a non-first trimestre (``2T`` / ``3T`` / ``4T``) — a
  true first-obligation filer (``1T``, or an alta-quarter first filing) has no
  prior pago fraccionado, so casilla ``05`` is legitimately null and the
  advisory must not fire; and
* casilla ``01`` (cumulative ingresos) is strictly positive; and
* casilla ``05`` is zero / unpopulated; and
* a prior-trimestre Modelo 130 filing for the SAME ejercicio actually exists in
  the local observation catalogue.

The last gate is the first-filer safeguard: the advisory keys off a real prior
filing, never off a bare period token. An operator whose first M130 obligation
falls in 2T (a mid-year alta) has no prior-trimestre filing in the catalogue,
so the advisory stays silent — null casilla ``05`` is correct, not an error.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Final

from ...core import Modelo
from ..aggregation import CalculationSourceDiagnostic
from ..calculations import CalculationObservationRepository

__all__ = [
    "collect_prior_payment_minoracion_not_captured_diagnostics",
    "collect_prior_payment_not_deducted_diagnostics",
]

#: Quarterly ordinal for the within-ejercicio cumulative model. ``1T`` is the
#: first-obligation period (no prior pago fraccionado); ``2T``/``3T``/``4T`` are
#: the non-first trimestres whose casilla 05 carries prior payments.
_QUARTERLY_ORDINAL: Final[dict[str, int]] = {"1T": 1, "2T": 2, "3T": 3, "4T": 4}

#: The casilla whose zero value (on a non-first trimestre with a real prior
#: filing) indicates an undeducted prior pago fraccionado.
_PRIOR_PAYMENT_CASILLA: Final[str] = "05"

#: The cumulative ingresos casilla whose positivity proves real activity.
_CUMULATIVE_INGRESOS_CASILLA: Final[str] = "01"

#: The prior-quarter casilla whose presence proves the prior filing carried a
#: pago fraccionado the casilla-05 carry deducts.
_PRIOR_POSITIVE_PART_CASILLA: Final[str] = "07"

#: The prior-quarter minoración casilla (Deducción por inversión en vivienda
#: habitual) the casilla-05 carry subtracts. A prior filing carrying casilla 07
#: but LACKING any casilla-16 entry is "not captured" (distinct from "filed 0");
#: the carry proceeds treating absence as zero, but the gap must surface.
_PRIOR_MINORACION_CASILLA: Final[str] = "16"


def _prior_trimestre_codes(period_token: str) -> tuple[str, ...]:
    """Return the same-ejercicio trimestre codes that precede ``period_token``.

    For ``2T`` -> ``("1T",)``; for ``3T`` -> ``("1T", "2T")``; for ``4T`` ->
    ``("1T", "2T", "3T")``. A first trimestre (``1T``) or a non-quarterly token
    yields an empty tuple — no prior pago fraccionado is possible.
    """
    ordinal = _QUARTERLY_ORDINAL.get(period_token)
    if ordinal is None or ordinal <= 1:
        return ()
    return tuple(code for code, value in _QUARTERLY_ORDINAL.items() if value < ordinal)


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
    casilla_values: Mapping[str, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepository,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return an advisory when a non-first M130 trimestre under-deducts prior payments.

    The advisory (``reason = "prior_payment_not_deducted"``) fires exactly when
    the target period is a non-first trimestre, casilla ``01`` is strictly
    positive, casilla ``05`` is zero, AND a prior-trimestre Modelo 130 filing for
    the same ejercicio exists in ``observation_repository``. The last gate keeps
    a true first-obligation filer (whose casilla ``05`` is legitimately null)
    silent.

    Args:
        casilla_values: The computed casilla values (engine result), keyed by
            casilla id.
        modelo: The modelo identifier of the filing being calculated. Used to
            confirm the modelo is 130 (the cumulative pago-fraccionado form this
            carry applies to) before any catalogue scan.
        period_token: The bare registry period code of the target filing (e.g.
            ``"2T"``).
        filing_year: The ejercicio whose prior trimestres are scanned.
        observation_repository: The local
            :class:`CalculationObservationRepository` scanned for a prior-period
            filing — the first-filer safeguard.

    Returns:
        A tuple of :class:`CalculationSourceDiagnostic` advisories — empty when
        no under-deduction is detected, otherwise the single advisory.
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
                f"Modelo 130 {period_token} is cumulative from the start of the ejercicio, but "
                f"casilla 05 ('Pagos fraccionados anteriores') is zero while a prior-trimestre "
                f"{filing_year} filing exists; casilla 07 = 04 - 05 - 06 therefore does not deduct "
                f"the pago fraccionado already paid in {', '.join(prior_codes)}, so this filing "
                f"over-declares (RD 439/2007 art. 110). The casilla-05 carry could not populate the "
                f"deduction from the prior filing's observation (it is absent or unreadable); re-file "
                f"the prior trimestre through the app so the carry resolves, or enter the prior pago "
                f"fraccionado in casilla 05 before filing"
            ),
            casilla_id=_PRIOR_PAYMENT_CASILLA,
        ),
    )


def collect_prior_payment_minoracion_not_captured_diagnostics(
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
    casilla 16 = 0. Per the ratified ADR
    ``2026-06-13-modelo-130-pagos-fraccionados-carry`` casilla-16
    filed-zero-vs-not-captured distinction, the carry proceeds (treating the absent
    minoración as zero) but the gap MUST surface as a non-blocking advisory naming
    it - the minoración is never silently dropped (``no-silent-under-declaration``).

    The advisory fires for the SAME ejercicio's prior trimestres of a non-first
    target quarter, only when at least one prior filing carries casilla 07 but no
    casilla-16 entry. A prior filing that declares casilla 16 = 0 explicitly is a
    silent no-op (the value is captured; it just happens to be zero).

    Args:
        modelo: The modelo identifier of the filing being calculated; the advisory
            applies only to Modelo 130.
        period_token: The bare registry period code of the target filing.
        filing_year: The ejercicio whose prior trimestres are scanned.
        observation_repository: The local
            :class:`CalculationObservationRepository` scanned for prior-period
            observations.

    Returns:
        A tuple of :class:`CalculationSourceDiagnostic` advisories — empty when
        every carried prior filing captured its casilla-16 minoración.

    Returns:
        A tuple with a single ``prior_payment_minoracion_not_captured`` advisory
        when a prior filing carries casilla 07 but no casilla-16 entry, otherwise
        empty.
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
        ),
    )
