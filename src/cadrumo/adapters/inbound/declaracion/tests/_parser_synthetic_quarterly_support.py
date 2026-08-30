"""Shared quarterly synthetic fixture expectations."""

from __future__ import annotations

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import CasillaId, Decimal

_M115_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    validated_casilla_id("01", surface="declaracion_parser_boundary.casilla"): Decimal("3"),
    validated_casilla_id("02", surface="declaracion_parser_boundary.casilla"): Decimal("12000.00"),
    validated_casilla_id("03", surface="declaracion_parser_boundary.casilla"): Decimal("2280.00"),
    validated_casilla_id("04", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("05", surface="declaracion_parser_boundary.casilla"): Decimal("2280.00"),
}
_M131_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    validated_casilla_id("01", surface="declaracion_parser_boundary.casilla"): Decimal("5000.00"),
    validated_casilla_id("02", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("03", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("04", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("05", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("06", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("07", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("08", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("09", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("10", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("11", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("12", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("13", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
    validated_casilla_id("14", surface="declaracion_parser_boundary.casilla"): Decimal("0.00"),
    validated_casilla_id("15", surface="declaracion_parser_boundary.casilla"): Decimal("100.00"),
}
