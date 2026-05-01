"""Tests for the :mod:`aeat.formulas._codes` enums."""

from __future__ import annotations

import pytest

from ._codes import FormulaOp, Quarter

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@pytest.mark.unit
def test_formula_op_has_13_members() -> None:
    """The operator set is locked to 13 members; expansion requires an ADR."""
    assert len(FormulaOp) == 13


@pytest.mark.unit
def test_formula_op_values_match_lowercased_names() -> None:
    """Every enum value should be the lowercased member name."""
    for member in FormulaOp:
        assert member.value == member.name.lower()


@pytest.mark.unit
def test_formula_op_values_are_unique() -> None:
    """No two operators share a value."""
    values = {member.value for member in FormulaOp}
    assert len(values) == len(FormulaOp)


@pytest.mark.unit
def test_quarter_has_four_members() -> None:
    """Fiscal quarters cover the calendar year exactly."""
    assert {member.value for member in Quarter} == {"Q1", "Q2", "Q3", "Q4"}
