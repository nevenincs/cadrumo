"""Moving a rate between its two scales keeps every digit."""

from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from ..percentage import fraction_of_percentage

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("points", "fraction"),
    [("15", "0.15"), ("1", "0.01"), ("0.5", "0.005"), ("12.3456", "0.123456"), ("100", "1.00"), ("0", "0.00")],
)
def test_the_decimal_point_moves_two_places(points: str, fraction: str) -> None:
    assert str(fraction_of_percentage(Decimal(points))) == fraction


def test_the_active_context_does_not_round_it() -> None:
    with localcontext() as context:
        context.prec = 2
        assert str(fraction_of_percentage(Decimal("12.3456"))) == "0.123456"


def test_what_is_not_a_number_names_no_fraction() -> None:
    with pytest.raises(ValueError, match="finite"):
        fraction_of_percentage(Decimal("NaN"))
