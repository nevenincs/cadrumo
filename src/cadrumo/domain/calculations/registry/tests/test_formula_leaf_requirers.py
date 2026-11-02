"""A dispatch argument that is not the required leaf kind is refused with the position it occupied."""

from __future__ import annotations

import pytest

from ..errors import RegistryValidationError
from ..formula_runtime_ops import require_casilla_leaf, require_parameter_leaf
from ..schema_formula import FormulaExpression

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LITERAL = FormulaExpression.model_validate({"literal": "1"})
_SUM = FormulaExpression.model_validate({"op": "add", "args": [{"literal": "1"}, {"literal": "2"}]})


def test_a_casilla_leaf_is_returned_as_declared() -> None:
    leaf = FormulaExpression.model_validate({"casilla_id": "0001"})

    assert require_casilla_leaf(leaf, op="m100_x", position=2) == "0001"


def test_a_parameter_leaf_is_returned_as_declared() -> None:
    leaf = FormulaExpression.model_validate({"parameter": "some_rate"})

    assert require_parameter_leaf(leaf, op="m100_x", position=6) == "some_rate"


@pytest.mark.parametrize("argument", [_LITERAL, _SUM], ids=["literal-leaf", "operator-node"])
def test_a_non_casilla_argument_is_refused_with_its_position(argument: FormulaExpression) -> None:
    with pytest.raises(RegistryValidationError) as refused:
        require_casilla_leaf(argument, op="m100_x", position=4)

    assert str(refused.value) == "formula op 'm100_x' requires args[4] to be a casilla leaf"


@pytest.mark.parametrize("argument", [_LITERAL, _SUM], ids=["literal-leaf", "operator-node"])
def test_a_non_parameter_argument_is_refused_with_its_position(argument: FormulaExpression) -> None:
    with pytest.raises(RegistryValidationError) as refused:
        require_parameter_leaf(argument, op="m100_x", position=9)

    assert str(refused.value) == "formula op 'm100_x' requires args[9] to be a parameter leaf"
