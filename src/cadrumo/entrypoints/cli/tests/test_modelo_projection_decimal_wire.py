"""Exact fixed-point wire checks for Modelo projection decimal payloads."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._modelo_projection_cli import _decimal_wire

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(("value", "expected"), ((Decimal("1E+3"), "1000"), (Decimal("1E-8"), "0.00000001")))
def test_projection_decimal_wire_is_canonical_fixed_point(value: Decimal, expected: str) -> None:
    """Projection output matches the CLI JSON renderer instead of Decimal exponent notation."""
    assert _decimal_wire(value) == expected
