"""Art. 81 LIRPF deducción maternidad computation helpers.

Pure-domain arithmetic; no entrypoint or CLI dependencies.
:func:`compute_deduccion_maternidad_0611` applies the central
:data:`core.external_constants.DEDUCCION_MATERNIDAD_MENSUAL_EUR` and
:data:`core.external_constants.DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR`
limits used by :class:`RentaFamilyProfile`, plus the Art. 81.1 post-birth
alta increment (:data:`core.external_constants.DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR`,
:data:`core.external_constants.DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR`) for
filing years from :data:`core.external_constants.DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR`.
"""

from __future__ import annotations

from collections.abc import Container

from ...core.external_constants import (
    DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR,
    DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR,
    DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR,
    DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
    DEDUCCION_MATERNIDAD_MENSUAL_EUR,
)


def compute_deduccion_maternidad_0611(
    meses_por_hijo: list[tuple[str, int]],
    *,
    filing_year: int,
    alta_posterior_hijos: Container[str] = frozenset(),
) -> int:
    """Compute Art. 81 LIRPF deducción maternidad from per-hijo meses pairs.

    Ordinary formula: ``sum(min(meses × DEDUCCION_MATERNIDAD_MENSUAL_EUR,
    DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR))`` for each ``(hijo_id, meses)`` pair.

    A ``hijo_id`` named in *alta_posterior_hijos* additionally receives the Art.
    81.1 post-birth alta increment for the one calendar month completing the
    30-day minimum contribution period, ONLY for *filing_year* from
    DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR: its total adds
    DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR on top of the ordinary
    monthly accrual (the completion month is counted once at the ordinary rate,
    already inside ``meses``, and once again here), and its cap is raised to
    DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR. Every other pair, and
    every pair for an earlier filing year, keeps the ordinary rate and cap
    untouched — the increment can only ever ADD to a hijo's total, never
    substitute for it.

    Returns an integer euros amount.
    """
    increment_applies = filing_year >= DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_FIRST_FILING_YEAR
    total = 0
    for hijo_id, meses in meses_por_hijo:
        importe = meses * DEDUCCION_MATERNIDAD_MENSUAL_EUR
        cap = DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR
        if increment_applies and hijo_id in alta_posterior_hijos:
            importe += DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_INCREMENTO_EUR
            cap = DEDUCCION_MATERNIDAD_ALTA_POSTERIOR_ANUAL_CAP_EUR
        total += min(importe, cap)
    return total
