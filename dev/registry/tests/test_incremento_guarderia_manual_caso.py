"""Art. 81.2 guardería ceiling scope on an AEAT Renta worked case (casilla 0613).

The earliest editions that print the case lie below the published supported-year
floor, so the published generation refuses to answer them. The authored registry
still carries those revisions and the governed facts that dated them, and this
case inspects that authored source through the development compiler's validated
authority.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.formula_runtime_ops import resolve_parameter
from cadrumo.domain.calculations.registry.temporal import select_revision
from cadrumo.domain.calculations.registry.tests.authored_editions import manual_editions_printing
from cadrumo.domain.contribuyente.descendant import DescendantInfo
from cadrumo.domain.contribuyente.family_fact_context import FamilyFactResolutionContext
from cadrumo.domain.contribuyente.family_profile import RentaFamilyProfile
from cadrumo.domain.contribuyente.family_types import MinimoDescendientesThresholds
from cadrumo.domain.contribuyente.guarderia_mensual import parse_guarderia_mensual
from cadrumo.domain.contribuyente.meses_trabajo import parse_meses_trabajo

from .profile_schema_support import authored_history_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("authored_history_fact_scope")]

# Every bundled AEAT Renta manual edition that prints this worked caso: its eight
# nursery months (January to June, October and November) and its 666,64 result.
_CASO_EDITIONS = manual_editions_printing("renta", "666,64", "octubre y noviembre")

#: "puede alcanzar hasta 1.000 euros anuales". Supplied by the caller in
#: production from its registry parameter; named here so the expectation below
#: reads as the manual's arithmetic.
_CAP_ANUAL = Decimal("1000")


def _authored_thresholds(filing_year: int) -> MinimoDescendientesThresholds:
    """The Art. 58.1 and Art. 61 norma 2a ceilings the authored M100 revision declares."""
    revision = select_revision(authored_history_authority().modelo("100"), filing_year=filing_year, period="0A")
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
    return FamilyFactResolutionContext(authored_history_authority(), coordinate, coordinate)


@pytest.mark.parametrize("caso_exercise", _CASO_EDITIONS)
def test_a_child_who_never_turns_three_keeps_months_after_september(caso_exercise: int) -> None:
    """The boundary pin, on AEAT's own caso — the ceiling is scoped, not general.

    The Renta manual works a child who is two all year with NON-CONTIGUOUS nursery
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
        birth_date=date(caso_exercise - 2, 1, 31),
        meses_madre_trabajo=parse_meses_trabajo("1-12", field="test"),
        gastos_guarderia_euros=0,
        gastos_guarderia_mensuales=parse_guarderia_mensual("1-6:500;10:500;11:500", field="test"),
        segundo_ciclo_infantil_inicio_mes=None,
    )

    assert child.guarderia_needs_segundo_ciclo_month(caso_exercise, context=_context(caso_exercise)) is False
    assert RentaFamilyProfile(descendientes=(child,)).incremento_guarderia_0613(
        caso_exercise,
        thresholds=_authored_thresholds(caso_exercise),
        cap_anual=_CAP_ANUAL,
        context=_context(caso_exercise),
    ) == Decimal("666.67")
