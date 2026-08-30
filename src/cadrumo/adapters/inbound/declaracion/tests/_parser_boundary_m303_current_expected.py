"""Expected M303 current-template parser boundary fixture values."""

from __future__ import annotations

from .....core.casilla_id import validated_casilla_id
from ._parser_boundary_support import CasillaId, Decimal, _expected_casilla_values

_M303_CASILLA_C46: CasillaId = validated_casilla_id("c46", surface="declaracion_parser_boundary.casilla")
_M303_CASILLA_C69: CasillaId = validated_casilla_id("c69", surface="declaracion_parser_boundary.casilla")

_M303_2023_2024_EXPECTED: dict[str, dict[CasillaId, Decimal]] = {
    # Per-specimen expected values derived from _MODELO_303_CORPUS_FIXTURES in _generate.py.
    "2023-1T": _expected_casilla_values(
        {
            "27": Decimal("12600.00"),
            "29": Decimal("8100.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8100.00"),
            "c46": Decimal("4500.00"),
            "c69": Decimal("4500.00"),
        }
    ),
    "2023-2T": _expected_casilla_values(
        {
            "27": Decimal("13800.00"),
            "29": Decimal("8700.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8700.00"),
            "c46": Decimal("5100.00"),
            "c69": Decimal("5100.00"),
        }
    ),
    "2023-3T": _expected_casilla_values(
        {
            "27": Decimal("15000.00"),
            "29": Decimal("9300.00"),
            "37": Decimal("0.00"),
            "45": Decimal("9300.00"),
            "c46": Decimal("5700.00"),
            "c69": Decimal("5700.00"),
        }
    ),
    "2023-4T": _expected_casilla_values(
        {
            "27": Decimal("16800.00"),
            "29": Decimal("10500.00"),
            "37": Decimal("0.00"),
            "45": Decimal("10500.00"),
            "c46": Decimal("6300.00"),
            "c69": Decimal("6300.00"),
        }
    ),
    "2024-1T": _expected_casilla_values(
        {
            "27": Decimal("13200.00"),
            "29": Decimal("8400.00"),
            "37": Decimal("0.00"),
            "45": Decimal("8400.00"),
            "c46": Decimal("4800.00"),
            "c69": Decimal("4800.00"),
        }
    ),
    "2024-2T": _expected_casilla_values(
        {
            "27": Decimal("14400.00"),
            "29": Decimal("9000.00"),
            "37": Decimal("0.00"),
            "45": Decimal("9000.00"),
            "c46": Decimal("5400.00"),
            "c69": Decimal("5400.00"),
        }
    ),
    "2024-3T": _expected_casilla_values(
        {
            "27": Decimal("16200.00"),
            "29": Decimal("10200.00"),
            "37": Decimal("0.00"),
            "45": Decimal("10200.00"),
            "c46": Decimal("6000.00"),
            "c69": Decimal("6000.00"),
        }
    ),
    "2024-4T": _expected_casilla_values(
        {
            "27": Decimal("18000.00"),
            "29": Decimal("11400.00"),
            "37": Decimal("0.00"),
            "45": Decimal("11400.00"),
            "c46": Decimal("6600.00"),
            "c69": Decimal("6600.00"),
        }
    ),
}
