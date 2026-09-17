"""Art. 81.2 guardería ceiling scope on the AEAT Renta 2020 worked case (casilla 0613).

Filing year 2020 lies below the published supported-year floor, so the published
generation refuses to answer it. The authored registry still carries the 2020
revision and the governed facts that dated it, and this case inspects that
authored source through the development compiler's validated authority.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.formula_runtime_ops import resolve_parameter
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.contribuyente.descendant import DescendantInfo
from cadrumo.domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from cadrumo.domain.contribuyente.family_profile import RentaFamilyProfile
from cadrumo.domain.contribuyente.family_types import MinimoDescendientesThresholds
from cadrumo.domain.contribuyente.guarderia_mensual import parse_guarderia_mensual
from cadrumo.domain.contribuyente.meses_trabajo import parse_meses_trabajo

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_YEAR = 2020

#: "puede alcanzar hasta 1.000 euros anuales". Supplied by the caller in
#: production from its registry parameter; named here so the expectation below
#: reads as the manual's arithmetic.
_CAP_ANUAL = Decimal("1000")


def _authored_thresholds(filing_year: int) -> MinimoDescendientesThresholds:
    """The Art. 58.1 and Art. 61 norma 2a ceilings the authored M100 revision declares."""
    revision = select_revision(compiled_bundled_authority().modelo("100"), filing_year=filing_year, period="0A")
    by_id = {parameter.id: parameter for parameter in revision.parameters}
    coordinate = {"filing_period": date(filing_year, 12, 31)}
    return MinimoDescendientesThresholds(
        rentas_anuales_limite=resolve_parameter(
            by_id["renta-minimo-descendientes-rentas-anuales-limite"],
            coordinate,
        ),
        declaracion_propia_rentas_limite=resolve_parameter(
            by_id["renta-minimo-descendientes-declaracion-propia-rentas-limite"],
            coordinate,
        ),
    )


def _context(filing_year: int) -> FamilyFactResolutionContext:
    coordinate = date(filing_year, 12, 31)
    return FamilyFactResolutionContext(compiled_bundled_authority(), coordinate, coordinate)


def test_a_child_who_never_turns_three_keeps_months_after_september() -> None:
    """The boundary pin, on AEAT's own 2020 caso — the ceiling is scoped, not general.

    Renta 2020 works a child who is two all year with NON-CONTIGUOUS nursery
    months: January to June, plus OCTOBER and NOVEMBER, to eight months. Both of
    those fall after September, and AEAT counts them. A ceiling applied outside
    the turning-three período would silently drop two months the authority
    grants, so this pins the scope rather than the arithmetic.

    The manual prints 666,64 here, rounding the monthly quota first; the engine
    rounds last and yields 666,67, which is what the 2024 and 2025 manuals do for
    their own case. The discrepancy is AEAT's across editions and is deliberately
    not chased.
    """
    child = DescendantInfo(
        birth_date=date(2018, 1, 31),
        meses_madre_trabajo=parse_meses_trabajo("1-12", field="test"),
        gastos_guarderia_euros=0,
        gastos_guarderia_mensuales=parse_guarderia_mensual("1-6:500;10:500;11:500", field="test"),
        segundo_ciclo_infantil_inicio_mes=None,
    )

    assert child.guarderia_needs_segundo_ciclo_month(_YEAR, context=_context(_YEAR)) is False
    assert RentaFamilyProfile(descendientes=(child,)).incremento_guarderia_0613(
        _YEAR,
        thresholds=_authored_thresholds(_YEAR),
        cap_anual=_CAP_ANUAL,
        context=_context(_YEAR),
    ) == Decimal("666.67")
