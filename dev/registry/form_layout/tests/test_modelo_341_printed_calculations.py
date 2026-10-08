"""The printed three-row compensation arithmetic preserves unknown inputs."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression

from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _evaluate(revision_id: str, target: str, values: dict[str, Decimal]) -> Decimal:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/341")).revisions[revision_id]
    formula = next(formula for formula in revision.formulas if formula.target_casilla_id == target)
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


@pytest.mark.parametrize("revision_id", ["2005-2015", "2016-y-siguientes"])
@pytest.mark.parametrize("row", [1, 2, 3])
@pytest.mark.parametrize("base,rate,expected", [("1000", "8", "80"), ("1500", "12", "180"), ("0", "10.5", "0")])
def test_each_row_uses_its_own_base_and_explicit_percentage(
    revision_id: str, row: int, base: str, rate: str, expected: str
) -> None:
    values = {f"{row:02}": Decimal(base), f"{row + 3:02}": Decimal(rate)}
    assert _evaluate(revision_id, f"{row + 6:02}", values) == Decimal(expected)


@pytest.mark.parametrize("revision_id", ["2005-2015", "2016-y-siguientes"])
def test_total_uses_all_three_compensations(revision_id: str) -> None:
    assert _evaluate(revision_id, "10", {"07": Decimal("180"), "08": Decimal("52.5"), "09": Decimal("0")}) == Decimal(
        "232.5"
    )


@pytest.mark.parametrize("revision_id", ["2005-2015", "2016-y-siguientes"])
@pytest.mark.parametrize(
    "target,values", [("07", {"01": Decimal("1000")}), ("10", {"07": Decimal("80"), "08": Decimal("0")})]
)
def test_missing_rate_or_compensation_does_not_become_zero(
    revision_id: str, target: str, values: dict[str, Decimal]
) -> None:
    with pytest.raises(RegistryValidationError):
        _evaluate(revision_id, target, values)
