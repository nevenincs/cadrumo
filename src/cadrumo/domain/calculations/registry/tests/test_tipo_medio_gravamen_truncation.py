"""The tipo medio de gravamen general is truncated to two decimals, never half-up.

LIRPF art. 63.2 (estatal) and 74.2 (autonómico) direct that the tipo medio de
gravamen general "se expresará con dos decimales sin redondeo", and the AEAT Manual
práctico de Renta restates it. The independent oracle is the manual's worked case
(Parte 1, capítulo de casos prácticos): a cuota of 2.475 over a base of 26.800 is
printed as 9,23 % (the exact quotient is 9,23507..., which half-up would print as
9,24) and a cuota of 2.240,90 over a base of 26.850 is printed as 8,34 % (exact
8,34600..., half-up 8,35).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..formula_expression import evaluate_expression
from ..formula_runtime_ops import apply_rounding
from ..schema import FormulaDefinition, RegistrySnapshot
from ..schema_rounding import RegistryRoundingCode
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE_LIQUIDABLE_GENERAL = validated_casilla_id("0505", surface="test_tipo_medio_base_general")
_CUOTA_ESTATAL = validated_casilla_id("0532", surface="test_tipo_medio_cuota_estatal")
_CUOTA_AUTONOMICA = validated_casilla_id("0533", surface="test_tipo_medio_cuota_autonomica")
_TIPO_MEDIO_ESTATAL = "renta-tipo-medio-gravamen-estatal-base-liquidable-general"
_TIPO_MEDIO_AUTONOMICO = "renta-tipo-medio-gravamen-autonomico-base-liquidable-general"

_YEARS = filing_year_envelope().years

# (formula id, cuota casilla, cuota, base, tipo medio printed by the manual)
_MANUAL_CASES = (
    (_TIPO_MEDIO_AUTONOMICO, _CUOTA_AUTONOMICA, Decimal("2475"), Decimal("26800"), Decimal("9.23")),
    (_TIPO_MEDIO_ESTATAL, _CUOTA_ESTATAL, Decimal("2240.90"), Decimal("26850"), Decimal("8.34")),
)


def _formula(snapshot: RegistrySnapshot, formula_id: str) -> FormulaDefinition:
    matches = [formula for formula in snapshot.revision.formulas if formula.id == formula_id]
    assert len(matches) == 1
    return matches[0]


def _evaluate(snapshot: RegistrySnapshot, formula: FormulaDefinition, values: dict[CasillaId, Decimal]) -> Decimal:
    value = evaluate_expression(
        formula.expression,
        values=values,
        binding_values={},
        parameters={},
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        filing_year=snapshot.filing_year,
    )
    return apply_rounding(value, formula.rounding)


@pytest.mark.parametrize("filing_year", _YEARS)
@pytest.mark.parametrize(("formula_id", "cuota_casilla", "cuota", "base", "printed"), _MANUAL_CASES)
def test_tipo_medio_general_matches_the_manual_worked_case(
    registry_snapshot: Callable[..., RegistrySnapshot],
    filing_year: int,
    formula_id: str,
    cuota_casilla: CasillaId,
    cuota: Decimal,
    base: Decimal,
    printed: Decimal,
) -> None:
    snapshot = registry_snapshot("100", filing_year, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    formula = _formula(snapshot, formula_id)

    assert formula.rounding is RegistryRoundingCode.DECIMAL_2_TRUNCATED
    result = _evaluate(snapshot, formula, {_BASE_LIQUIDABLE_GENERAL: base, cuota_casilla: cuota})
    assert result == printed


@pytest.mark.parametrize("filing_year", _YEARS)
@pytest.mark.parametrize("formula_id", (_TIPO_MEDIO_ESTATAL, _TIPO_MEDIO_AUTONOMICO))
def test_tipo_medio_general_is_zero_without_a_positive_base(
    registry_snapshot: Callable[..., RegistrySnapshot], filing_year: int, formula_id: str
) -> None:
    snapshot = registry_snapshot("100", filing_year, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    formula = _formula(snapshot, formula_id)

    result = _evaluate(
        snapshot,
        formula,
        {_BASE_LIQUIDABLE_GENERAL: Decimal("0"), _CUOTA_ESTATAL: Decimal("0"), _CUOTA_AUTONOMICA: Decimal("0")},
    )
    assert result == Decimal("0")


@pytest.mark.parametrize(
    ("exact", "expected"),
    (
        (Decimal("9.2399"), Decimal("9.23")),
        (Decimal("9.2350"), Decimal("9.23")),
        (Decimal("9.23507"), Decimal("9.23")),
        (Decimal("8.3460"), Decimal("8.34")),
        (Decimal("9.23"), Decimal("9.23")),
        (Decimal("0"), Decimal("0")),
    ),
)
def test_decimal_2_truncated_never_carries_the_dropped_digits(exact: Decimal, expected: Decimal) -> None:
    assert apply_rounding(exact, RegistryRoundingCode.DECIMAL_2_TRUNCATED) == expected
