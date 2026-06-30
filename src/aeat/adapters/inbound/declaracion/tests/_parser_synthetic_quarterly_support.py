"""Shared quarterly synthetic fixture expectations."""

from __future__ import annotations

from ._parser_boundary_support import CasillaId, Decimal, _casilla_id

_M115_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    _casilla_id("01"): Decimal("3"),
    _casilla_id("02"): Decimal("12000.00"),
    _casilla_id("03"): Decimal("2280.00"),
    _casilla_id("04"): Decimal("0.00"),
    _casilla_id("05"): Decimal("2280.00"),
}
_M131_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    _casilla_id("01"): Decimal("5000.00"),
    _casilla_id("02"): Decimal("100.00"),
    _casilla_id("03"): Decimal("0.00"),
    _casilla_id("04"): Decimal("0.00"),
    _casilla_id("05"): Decimal("0.00"),
    _casilla_id("06"): Decimal("0.00"),
    _casilla_id("07"): Decimal("100.00"),
    _casilla_id("08"): Decimal("0.00"),
    _casilla_id("09"): Decimal("0.00"),
    _casilla_id("10"): Decimal("100.00"),
    _casilla_id("11"): Decimal("0.00"),
    _casilla_id("12"): Decimal("0.00"),
    _casilla_id("13"): Decimal("100.00"),
    _casilla_id("14"): Decimal("0.00"),
    _casilla_id("15"): Decimal("100.00"),
}
