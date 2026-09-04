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


def _resolve_maternidad_figure(filing_year: int, slug: str) -> int:
    """Read one Art. 81.1 maternidad figure from its dated Modelo 100 parameter.

    The registry is the causal authority: a missing revision or parameter is a
    grounding defect and raises :class:`RegistryValidationError` rather than
    falling back to the module constant, which is a documented default the
    arithmetic must not silently prefer.

    Returns:
        The integer euro figure the registry declares for ``filing_year``.
    """
    from datetime import date

    from ...core.modelo import Modelo
    from ..calculations.registry.formula_runtime_ops import read_parameter

    return int(
        read_parameter(
            Modelo.M100.value,
            str(filing_year),
            f"renta-{filing_year}-maternidad-{slug}",
            date_context={"filing_period": date(filing_year, 12, 31)},
        )
    )


def _resolve_alta_posterior_increment(filing_year: int) -> int | None:
    """Return the post-birth alta increment, or ``None`` where the law grants none.

    The increment reaches only filing years from which the route exists, and the
    registry expresses that by DECLARING the parameter for those revisions and
    omitting it for earlier ones. Absence is therefore the legal answer here, not
    a grounding defect, which is why this one lookup tolerates it.

    Returns:
        The increment for ``filing_year``, or ``None`` when none applies.
    """
    from ..calculations.registry.errors import RegistryValidationError

    try:
        return _resolve_maternidad_figure(filing_year, "alta-posterior-incremento")
    except RegistryValidationError:
        return None


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
    mensual = _resolve_maternidad_figure(filing_year, "mensual")
    cap_anual = _resolve_maternidad_figure(filing_year, "cap-anual")
    increment = _resolve_alta_posterior_increment(filing_year)
    total = 0
    for hijo_id, meses in meses_por_hijo:
        importe = meses * mensual
        cap = cap_anual
        if increment is not None and hijo_id in alta_posterior_hijos:
            importe += increment
            # The raised cap is DERIVED from its two inputs rather than stored,
            # so it cannot drift away from them the way an independent literal
            # would.
            cap = cap_anual + increment
        total += min(importe, cap)
    return total
