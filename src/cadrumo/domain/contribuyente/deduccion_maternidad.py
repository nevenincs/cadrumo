"""Art. 81 LIRPF deducción maternidad computation helpers.

Pure-domain arithmetic; no entrypoint or CLI dependencies.
:func:`compute_deduccion_maternidad_0611` reads the dated Art. 81 figures
from the Modelo 100 parameter registry and derives the raised post-birth
alta cap from the ordinary cap plus the applicable increment.
"""

from __future__ import annotations

from collections.abc import Container


def _resolve_maternidad_figure(filing_year: int, slug: str) -> int:
    """Read one Art. 81.1 maternidad figure from its dated Modelo 100 parameter.

    The registry is the causal authority: a missing revision or parameter is a
    grounding defect and raises :class:`RegistryValidationError`; the
    arithmetic has no undated fallback authority.

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

    The ordinary formula multiplies each child's eligible months by the dated
    monthly parameter and caps it at the dated annual parameter.

    A ``hijo_id`` named in *alta_posterior_hijos* additionally receives the Art.
    81.1 post-birth alta increment for the one calendar month completing the
    30-day minimum contribution period, ONLY for *filing_year* from
    a revision that declares the increment: its total adds that increment on top of the ordinary
    monthly accrual (the completion month is counted once at the ordinary rate,
    already inside ``meses``, and once again here), and its cap is raised to
    derived annual cap. Every other pair, and
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
