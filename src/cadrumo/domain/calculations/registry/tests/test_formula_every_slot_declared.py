"""A módulo formula missing a trailing slot refuses instead of dropping that módulo's amount."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId
from ..errors import RegistryValidationError
from ..formula_expression import evaluate_expression
from ..schema_formula import FormulaExpression, ParameterDefinition
from .authored_editions import filing_year_envelope
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_YEARS = filing_year_envelope().years


def _published_formula(
    modelo: str, period: str, op: str, filing_year: int
) -> tuple[FormulaExpression, dict[str, ParameterDefinition]]:
    revision = published_snapshot(modelo, filing_year=filing_year, period=period).revision
    [expression] = [formula.expression for formula in revision.formulas if formula.expression.op == op]
    parameters: dict[str, ParameterDefinition] = {str(parameter.id): parameter for parameter in revision.parameters}
    return expression, parameters


def _run(expression: FormulaExpression, *, parameters: dict[str, ParameterDefinition], filing_year: int) -> Decimal:
    """Evaluate with every casilla the formula reads at zero, so only the shape of the formula is at stake."""
    values: dict[CasillaId, Decimal] = {
        arg.casilla_id: Decimal(0) for arg in expression.args if arg.casilla_id is not None and arg.casilla_id != ""
    }
    return evaluate_expression(
        expression,
        values=values,
        binding_values={},
        parameters=parameters,
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        filing_year=filing_year,
    )


def _modulos_previo(filing_year: int) -> tuple[FormulaExpression, dict[str, ParameterDefinition]]:
    return _published_formula("131", "1T", "m131_resolve_modulos_previo", filing_year)


@pytest.mark.parametrize("filing_year", _YEARS)
def test_the_published_modulos_formula_declares_every_slot_its_table_prices(filing_year: int) -> None:
    expression, parameters = _modulos_previo(filing_year)

    assert _run(expression, parameters=parameters, filing_year=filing_year) == Decimal(0)


@pytest.mark.parametrize("filing_year", _YEARS)
def test_a_modulos_formula_with_its_last_slot_dropped_refuses_even_with_no_epigrafe(filing_year: int) -> None:
    expression, parameters = _modulos_previo(filing_year)
    *slots, last_modulo, table = expression.args
    assert last_modulo.casilla_id is not None
    dropped = expression.model_copy(update={"args": (*slots, table)})

    with pytest.raises(RegistryValidationError, match="módulo slots"):
        _run(dropped, parameters=parameters, filing_year=filing_year)
