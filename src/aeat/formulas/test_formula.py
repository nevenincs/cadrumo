"""Tests for the pydantic formula-node models."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from ._formula import (
    AddFormula,
    Bracket,
    BracketsFormula,
    CasillaRef,
    DivFormula,
    Formula,
    Literal,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
    iter_casilla_refs,
    iter_param_refs,
)


@pytest.mark.unit
def test_literal_coerces_strings_and_ints() -> None:
    """Strings and ints both become :class:`Decimal` values."""
    assert Literal.model_validate({"value": "0.20"}).value == Decimal("0.20")
    assert Literal.model_validate({"value": 3}).value == Decimal("3")


@pytest.mark.unit
def test_literal_rejects_floats() -> None:
    """Float literals are explicitly rejected to prevent precision drift."""
    with pytest.raises(ValidationError):
        Literal.model_validate({"value": 0.2})


@pytest.mark.unit
def test_add_formula_rejects_single_operand() -> None:
    """:class:`AddFormula` requires at least two operands."""
    with pytest.raises(ValidationError):
        AddFormula.model_validate(
            {"op": "add", "operands": [{"op": "literal", "value": "1"}]},
        )


@pytest.mark.unit
def test_sub_formula_requires_exact_two_operands() -> None:
    """:class:`SubFormula` is strictly binary."""
    with pytest.raises(ValidationError):
        SubFormula.model_validate(
            {
                "op": "sub",
                "operands": [
                    {"op": "literal", "value": "1"},
                    {"op": "literal", "value": "2"},
                    {"op": "literal", "value": "3"},
                ],
            },
        )


@pytest.mark.unit
def test_div_formula_default_quantize() -> None:
    """DIV carries a four-decimal quantize by default."""
    div = DivFormula(operands=(Literal(value=Decimal("1")), Literal(value=Decimal("3"))))
    assert div.quantize == Decimal("0.0001")


@pytest.mark.unit
def test_round_formula_rejects_nested_round() -> None:
    """Single-rounding invariant: nested ROUND nodes are rejected."""
    inner = RoundFormula(operands=(Literal(value=Decimal("1")),))
    with pytest.raises(ValidationError):
        RoundFormula(operands=(inner,))  # type: ignore[arg-type]


@pytest.mark.unit
def test_brackets_formula_requires_terminal_none() -> None:
    """The final bracket must be the default tier with no upper bound."""
    with pytest.raises(ValidationError):
        BracketsFormula(
            operands=(Literal(value=Decimal("1")),),  # type: ignore[arg-type]
            brackets=(
                Bracket(upper_inclusive=Decimal("9000"), value=Decimal("100")),
                Bracket(upper_inclusive=Decimal("10000"), value=Decimal("75")),
            ),
        )


@pytest.mark.unit
def test_brackets_formula_rejects_non_ascending() -> None:
    """Non-ascending upper_inclusive sequences are rejected."""
    with pytest.raises(ValidationError):
        BracketsFormula(
            operands=(Literal(value=Decimal("1")),),  # type: ignore[arg-type]
            brackets=(
                Bracket(upper_inclusive=Decimal("10000"), value=Decimal("75")),
                Bracket(upper_inclusive=Decimal("9000"), value=Decimal("100")),
                Bracket(upper_inclusive=None, value=Decimal("0")),
            ),
        )


@pytest.mark.unit
def test_iter_casilla_refs_collects_all_refs() -> None:
    """Nested formulas yield their casilla references in traversal order."""
    formula = SubFormula(
        operands=(  # type: ignore[arg-type]
            CasillaRef(casilla_id="01"),
            AddFormula(
                operands=(  # type: ignore[arg-type]
                    CasillaRef(casilla_id="02"),
                    CasillaRef(casilla_id="03"),
                )
            ),
        )
    )
    assert iter_casilla_refs(formula) == ["01", "02", "03"]


@pytest.mark.unit
def test_iter_param_refs_collects_all_refs() -> None:
    """Nested formulas yield their parameter references in traversal order."""
    formula = PercentFormula(
        operands=(  # type: ignore[arg-type]
            ParamRef(param_id="irpf.rate"),
            CasillaRef(casilla_id="03"),
        )
    )
    assert iter_param_refs(formula) == ["irpf.rate"]


@pytest.mark.unit
def test_formula_round_trips_through_json() -> None:
    """Discriminated-union formulas survive JSON serialisation."""
    original = SubFormula(
        operands=(  # type: ignore[arg-type]
            CasillaRef(casilla_id="01"),
            CasillaRef(casilla_id="02"),
        )
    )
    adapter: TypeAdapter[Formula] = TypeAdapter(Formula)
    payload = adapter.dump_json(original)
    replay = adapter.validate_json(payload)
    assert replay == original
