"""Shared Modelo 130 parser boundary corpus expectations."""

from __future__ import annotations

from ._parser_boundary_support import CasillaId, Decimal, _expected_casilla_values

_M130_CORPUS_PARAMS: tuple[tuple[str, int, str], ...] = (
    ("2021-2T", 2021, "2T"),
    ("2021-3T", 2021, "3T"),
    ("2021-4T", 2021, "4T"),
    ("2022-1T", 2022, "1T"),
    ("2022-2T", 2022, "2T"),
    ("2022-3T", 2022, "3T"),
    ("2022-4T", 2022, "4T"),
    ("2023-1T", 2023, "1T"),
    ("2023-2T", 2023, "2T"),
    ("2023-3T", 2023, "3T"),
    ("2023-4T", 2023, "4T"),
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
)
_M130_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in _M130_CORPUS_PARAMS)
_M130_CORPUS_GROUND_TRUTH: dict[str, dict[CasillaId, Decimal]] = {
    "2021-2T": _expected_casilla_values({"03": Decimal("5000.00"), "19": Decimal("900.00")}),
    "2021-3T": _expected_casilla_values({"03": Decimal("7500.00"), "19": Decimal("1400.00")}),
    "2021-4T": _expected_casilla_values({"03": Decimal("10000.00"), "19": Decimal("1900.00")}),
    "2022-1T": _expected_casilla_values({"03": Decimal("5200.00"), "19": Decimal("940.00")}),
    "2022-2T": _expected_casilla_values({"03": Decimal("7800.00"), "19": Decimal("1460.00")}),
    "2022-3T": _expected_casilla_values({"03": Decimal("9100.00"), "19": Decimal("1720.00")}),
    "2022-4T": _expected_casilla_values({"03": Decimal("11000.00"), "19": Decimal("2100.00")}),
    "2023-1T": _expected_casilla_values({"03": Decimal("5400.00"), "19": Decimal("980.00")}),
    "2023-2T": _expected_casilla_values({"03": Decimal("8100.00"), "19": Decimal("1520.00")}),
    "2023-3T": _expected_casilla_values({"03": Decimal("10500.00"), "19": Decimal("2000.00")}),
    "2023-4T": _expected_casilla_values({"03": Decimal("13000.00"), "19": Decimal("2500.00")}),
    "2024-1T": _expected_casilla_values({"03": Decimal("5600.00"), "19": Decimal("1020.00")}),
    "2024-2T": _expected_casilla_values({"03": Decimal("8400.00"), "19": Decimal("1580.00")}),
    "2024-3T": _expected_casilla_values({"03": Decimal("11200.00"), "19": Decimal("2140.00")}),
    "2024-4T": _expected_casilla_values({"03": Decimal("14000.00"), "19": Decimal("2700.00")}),
}
