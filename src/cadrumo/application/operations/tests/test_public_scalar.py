"""Lossless projection of public scalar values."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..public_scalar import PublicDecimal, project_scalar, restore_scalar

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("decimal_text", ["1.2300", "1E+2", "-0.00"])
def test_project_scalar_preserves_decimal_spelling(decimal_text: str) -> None:
    projected = project_scalar(Decimal(decimal_text))

    assert isinstance(projected, PublicDecimal)
    assert projected.decimal == decimal_text
    restored = restore_scalar(projected)
    assert restored == Decimal(decimal_text)
    assert str(restored) == decimal_text


@pytest.mark.parametrize("value", ["same text", 17, True])
def test_project_scalar_preserves_primitive_identity(value: str | int | bool) -> None:
    assert project_scalar(value) is value


@pytest.mark.parametrize("decimal_text", ["NaN", "Infinity", "-Infinity"])
def test_project_scalar_refuses_non_finite_decimal(decimal_text: str) -> None:
    with pytest.raises(ValidationError):
        project_scalar(Decimal(decimal_text))
