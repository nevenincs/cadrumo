"""The February 2026 form deducts fuel advances without changing January."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.schema import FormulaDefinition
from cadrumo.domain.calculations.registry.temporal import select_revision

from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _formula(period: str) -> FormulaDefinition:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353"))
    revision = select_revision(modelo, filing_year=2026, period=period)
    return next(formula for formula in revision.formulas if formula.target_casilla_id == "05")


def _evaluate(formula: FormulaDefinition, values: dict[str, Decimal]) -> Decimal:
    return evaluate_expression(
        formula.expression,
        values=values,
        binding_values={},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
    )


@pytest.mark.parametrize("period", ["01", "02", "12"])
@pytest.mark.parametrize(
    "result,previous,advance,january,later",
    [
        ("1800", "100", "150", "1700", "1550"),
        ("-200", "0", "50", "-200", "-250"),
        ("100", "25", "75", "75", "0"),
        ("0", "0", "0", "0", "0"),
        ("1.23", "0.13", "0.10", "1.10", "1.00"),
    ],
)
def test_result_follows_the_formula_printed_for_the_selected_month(
    period: str, result: str, previous: str, advance: str, january: str, later: str
) -> None:
    values = {"03": Decimal(result), "04": Decimal(previous), "10": Decimal(advance)}
    assert _evaluate(_formula(period), values) == Decimal(january if period == "01" else later)


@pytest.mark.parametrize("period", ["02", "12"])
@pytest.mark.parametrize("missing", ["03", "04", "10"])
def test_an_unknown_operand_is_not_silently_treated_as_zero(period: str, missing: str) -> None:
    values = {"03": Decimal("1800"), "04": Decimal("100"), "10": Decimal("150")}
    del values[missing]
    with pytest.raises(RegistryValidationError, match="referenced before evaluation"):
        _evaluate(_formula(period), values)


def test_january_does_not_require_the_later_advance_box() -> None:
    assert _evaluate(_formula("01"), {"03": Decimal("1800"), "04": Decimal("100")}) == Decimal("1700")


def test_advance_is_in_the_calculation_closure_only_after_the_official_transition() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353"))
    for period in ("01", "02"):
        revision = select_revision(modelo, filing_year=2026, period=period)
        assert revision.completeness_manifest is not None
        closure = {entry.casilla_id for entry in revision.completeness_manifest.casillas}
        assert ("10" in closure) == (period == "02")
    assert "boe-modelo-390-2026-form" in _formula("02").source_refs
    assert "orden-hac-27-2026:disposicion-final-unica" in _formula("02").legal_refs
