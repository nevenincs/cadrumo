"""Shared Modelo 130 parser boundary corpus expectations.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m130_corpus`
        Parser round-trip coverage that consumes this corpus parameter and
        ground-truth table.
    :mod:`~adapters.inbound.declaracion.tests.test_verification_chain_m130`
        Verification-chain coverage that reuses the same corpus specimens after
        parsing.
    :class:`~domain.calculations.registry.CasillaId`
        Typed casilla key used for the expected extracted values.
"""

from __future__ import annotations

from decimal import Decimal

from .....core.casilla_id import CasillaId
from .parser_boundary_m100_support import corpus_specimens
from .parser_boundary_support import expected_casilla_values, split_by_supported_filing_year

_M130_CORPUS_CASES: tuple[tuple[str, int, str], ...] = corpus_specimens("130")
M130_CORPUS_PARAMS, M130_UNSUPPORTED_CORPUS_PARAMS = split_by_supported_filing_year(_M130_CORPUS_CASES, year_index=1)
M130_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in M130_CORPUS_PARAMS)
M130_UNSUPPORTED_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in M130_UNSUPPORTED_CORPUS_PARAMS)
_M130_GROUND_TRUTH_OLDEST_FIRST: tuple[dict[CasillaId, Decimal], ...] = (
    expected_casilla_values({"03": Decimal("5000.00"), "19": Decimal("900.00")}),
    expected_casilla_values({"03": Decimal("7500.00"), "19": Decimal("1400.00")}),
    expected_casilla_values({"03": Decimal("10000.00"), "19": Decimal("1900.00")}),
    expected_casilla_values({"03": Decimal("5200.00"), "19": Decimal("940.00")}),
    expected_casilla_values({"03": Decimal("7800.00"), "19": Decimal("1460.00")}),
    expected_casilla_values({"03": Decimal("9100.00"), "19": Decimal("1720.00")}),
    expected_casilla_values({"03": Decimal("11000.00"), "19": Decimal("2100.00")}),
    expected_casilla_values({"03": Decimal("5400.00"), "19": Decimal("980.00")}),
    expected_casilla_values({"03": Decimal("8100.00"), "19": Decimal("1520.00")}),
    expected_casilla_values({"03": Decimal("10500.00"), "19": Decimal("2000.00")}),
    expected_casilla_values({"03": Decimal("13000.00"), "19": Decimal("2500.00")}),
    expected_casilla_values({"03": Decimal("5600.00"), "19": Decimal("1020.00")}),
    expected_casilla_values({"03": Decimal("8400.00"), "19": Decimal("1580.00")}),
    expected_casilla_values({"03": Decimal("11200.00"), "19": Decimal("2140.00")}),
    expected_casilla_values({"03": Decimal("14000.00"), "19": Decimal("2700.00")}),
)
M130_CORPUS_GROUND_TRUTH: dict[str, dict[CasillaId, Decimal]] = dict(
    zip((stem for stem, _year, _period in _M130_CORPUS_CASES), _M130_GROUND_TRUTH_OLDEST_FIRST, strict=True)
)
