"""Art. 81 LIRPF deducción maternidad computation helpers.

Pure-domain arithmetic; no entrypoint or CLI dependencies.
:func:`compute_deduccion_maternidad_0611` reads the dated Art. 81 figures
from the Modelo 100 parameter registry and derives the raised post-birth
alta cap from the ordinary cap plus the applicable increment.
"""

from __future__ import annotations

from collections.abc import Container


def _resolve_maternidad_figure(filing_year: int, slug: str) -> int:
    """Read one Art. 81.1 figure from the published authority.

    The three 2025 Modelo 100 parameters are also projected into the typed
    governed-fact catalogue. Consume that projection when its exact
    year/parameter coordinate is published; earlier years retain the existing
    exact-year Modelo 100 parameter lookup because no generated projection is
    declared for them. Neither path has an undated or numeric fallback.

    Returns:
        The integer euro figure the registry declares for ``filing_year``.
    """
    from datetime import date
    from typing import cast

    from ...core.modelo import Modelo
    from ..calculations.registry.authority import bundled_authority
    from ..calculations.registry.facts.modelo_parameter_fact import ModeloParameterFact
    from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
    from ..calculations.registry.facts.schema import FactSelector
    from ..calculations.registry.formula_runtime_ops import read_parameter
    from ..calculations.registry.schema_base import DateAxis

    projection_fact_ids = {
        "mensual": ModeloParameterFact.MATERNITY_MONTHLY_DEDUCTION,
        "cap-anual": ModeloParameterFact.MATERNITY_ANNUAL_CAP,
        "alta-posterior-incremento": ModeloParameterFact.MATERNITY_POST_ENROLLMENT_INCREMENT,
    }
    authority = bundled_authority()
    fact_id = projection_fact_ids.get(slug)
    parameter_id = f"renta-{filing_year}-maternidad-{slug}"
    effective_date = date(filing_year, 12, 31)
    fact = authority.catalogues.facts.facts.get(fact_id) if fact_id is not None else None
    expected_selectors = frozenset({("modelo", "100"), ("parameter_id", parameter_id)})
    if (
        fact_id is not None
        and fact is not None
        and any(
            variant.valid_from <= effective_date
            and (variant.valid_to is None or effective_date <= variant.valid_to)
            and frozenset((selector.name, selector.value) for selector in variant.selectors) == expected_selectors
            for variant in fact.variants
        )
    ):
        resolved = authority.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=fact_id,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
                selectors=(
                    FactSelector(name="modelo", value="100"),
                    FactSelector(name="parameter_id", value=parameter_id),
                ),
            ),
        )
        return int(cast(ResolvedScalarFact, resolved).payload.value)

    return int(
        read_parameter(
            Modelo("100").value,
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
