"""Pure-function contract tests for the apply adapter's coercion + constraint helpers.

Three load-bearing helpers turn the engine's typed records into
Sheets API request bodies:

  * ``_coerce_cell_value`` — Decimal | str | bool | None → the JSON
    cell value Sheets accepts. Errors here render wrong values on
    the operator's screen.
  * ``_condition_for_constraint`` — SheetCellConstraint → Sheets
    BooleanCondition (NUMBER_BETWEEN / NUMBER_GREATER_THAN_EQ /
    NUMBER_LESS_THAN_EQ). Errors here render the wrong data
    validation rule on the cell.
  * ``_input_message_for_constraint`` — SheetCellConstraint → the
    cell note text the operator sees. Errors here surface
    misleading bounds to the operator.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import pytest

from ....application.storage.calc_sheets import (
    SheetCellAddress,
    SheetCellConstraint,
    TabName,
)
from ._calc_sheets_apply import (
    _coerce_cell_value,
    _condition_for_constraint,
    _input_message_for_constraint,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

_Sign = Literal["any", "non_negative", "non_positive"]


def _make_constraint(
    *,
    sign: _Sign = "any",
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
    casilla: str = "test.casilla",
    legal_refs: tuple[str, ...] = ("ley-x:art-1",),
) -> SheetCellConstraint:
    return SheetCellConstraint(
        address=SheetCellAddress.at(TabName.ENTRADAS, 1, 1),
        sign=sign,
        min_value=min_value,
        max_value=max_value,
        casilla=casilla,
        legal_refs=legal_refs,
    )


# ---------------------------------------------------------------------------
# _coerce_cell_value
# ---------------------------------------------------------------------------


def test_coerce_cell_value_none_becomes_empty_string() -> None:
    assert _coerce_cell_value(None) == ""


def test_coerce_cell_value_preserves_bool() -> None:
    assert _coerce_cell_value(True) is True
    assert _coerce_cell_value(False) is False


def test_coerce_cell_value_decimal_renders_as_fixed_string() -> None:
    """Very large / very small Decimals must not round through float."""
    assert _coerce_cell_value(Decimal("1500.55")) == "1500.55"
    assert _coerce_cell_value(Decimal("0.00000001")) == "0.00000001"
    assert _coerce_cell_value(Decimal("1234567890.99")) == "1234567890.99"


def test_coerce_cell_value_negative_decimal_preserved() -> None:
    assert _coerce_cell_value(Decimal("-500")) == "-500"


def test_coerce_cell_value_passes_string_through() -> None:
    assert _coerce_cell_value("Concepto") == "Concepto"


# ---------------------------------------------------------------------------
# _condition_for_constraint
# ---------------------------------------------------------------------------


def test_condition_non_negative_no_bounds_emits_greater_than_eq_zero() -> None:
    constraint = _make_constraint(sign="non_negative", casilla="iva.compensacion-anteriores")
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_GREATER_THAN_EQ"
    assert condition["values"] == [{"userEnteredValue": "0"}]


def test_condition_min_and_max_emit_number_between() -> None:
    constraint = _make_constraint(
        sign="any",
        min_value=Decimal("10"),
        max_value=Decimal("100"),
        casilla="iva.prorrata-porcentaje",
    )
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_BETWEEN"
    assert condition["values"] == [
        {"userEnteredValue": "10"},
        {"userEnteredValue": "100"},
    ]


def test_condition_non_negative_with_max_emits_number_between_at_zero_lower() -> None:
    """non_negative + max=100 should yield NUMBER_BETWEEN(0, 100), not BETWEEN(None, 100)."""

    constraint = _make_constraint(
        sign="non_negative",
        max_value=Decimal("100"),
        casilla="iva.prorrata-porcentaje",
    )
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_BETWEEN"
    assert condition["values"][0] == {"userEnteredValue": "0"}
    assert condition["values"][1] == {"userEnteredValue": "100"}


def test_condition_non_positive_no_bounds_emits_less_than_eq_zero() -> None:
    constraint = _make_constraint(sign="non_positive", casilla="iva.resultado-negativo")
    condition = _condition_for_constraint(constraint)
    assert condition is not None
    assert condition["type"] == "NUMBER_LESS_THAN_EQ"
    assert condition["values"] == [{"userEnteredValue": "0"}]


def test_condition_unconstrained_returns_none() -> None:
    """sign='any' with no min / max → no data-validation rule needed."""

    constraint = _make_constraint(sign="any", casilla="any.casilla")
    assert _condition_for_constraint(constraint) is None


# ---------------------------------------------------------------------------
# _input_message_for_constraint
# ---------------------------------------------------------------------------


def test_input_message_renders_non_negative_sign() -> None:
    constraint = _make_constraint(
        sign="non_negative",
        casilla="iva.compensacion-anteriores",
        legal_refs=("ley-37-1992:art-99",),
    )
    message = _input_message_for_constraint(constraint)
    assert "iva.compensacion-anteriores" in message
    assert "≥ 0" in message
    assert "ley-37-1992:art-99" in message


def test_input_message_renders_min_and_max_bounds() -> None:
    constraint = _make_constraint(
        sign="any",
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        casilla="iva.prorrata-porcentaje",
        legal_refs=("ley-37-1992:art-104",),
    )
    message = _input_message_for_constraint(constraint)
    assert "iva.prorrata-porcentaje" in message
    assert "≥ 0" in message
    assert "≤ 100" in message


def test_input_message_renders_any_when_no_bounds() -> None:
    constraint = _make_constraint(sign="any", casilla="some.casilla")
    message = _input_message_for_constraint(constraint)
    assert "any" in message
