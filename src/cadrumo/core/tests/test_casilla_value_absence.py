"""Reading an omitted casilla as zero only on a named ground."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..casilla_id import CasillaId, validated_casilla_id
from ..casilla_value_absence import AbsentCasillaReading

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_STATED: CasillaId = validated_casilla_id("01", surface="test_casilla_value_absence")
_OMITTED: CasillaId = validated_casilla_id("02", surface="test_casilla_value_absence")


@pytest.mark.parametrize("reading", list(AbsentCasillaReading))
@pytest.mark.parametrize("stated", [Decimal("0.00"), Decimal("-12.50"), Decimal("1E+2"), Decimal("0")])
def test_a_stated_value_is_returned_exactly_whatever_the_ground(reading: AbsentCasillaReading, stated: Decimal) -> None:
    value = reading.read({_STATED: stated}, _STATED)

    assert value == stated
    assert value.as_tuple() == stated.as_tuple()


@pytest.mark.parametrize("reading", list(AbsentCasillaReading))
def test_an_omitted_casilla_reads_as_zero_on_every_ground(reading: AbsentCasillaReading) -> None:
    assert reading.read({_STATED: Decimal("5")}, _OMITTED) == Decimal("0")
    assert reading.read({}, _OMITTED) == Decimal("0")
