"""Shared Modelo 111 parser boundary corpus expectations."""

from __future__ import annotations

from ._parser_boundary_support import CasillaId, Decimal, _casilla_id

_M111_CASILLA_07: CasillaId = _casilla_id("07")
_M111_CASILLA_08: CasillaId = _casilla_id("08")
_M111_CASILLA_09: CasillaId = _casilla_id("09")
_M111_CASILLA_28: CasillaId = _casilla_id("28")
_M111_CASILLA_30: CasillaId = _casilla_id("30")
_M111_CORPUS_PARAMS: tuple[tuple[str, int, str], ...] = (
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
)
_M111_CORPUS_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in _M111_CORPUS_PARAMS)
_M111_POSITIVE_EXPECTED_VALUES: dict[CasillaId, Decimal] = {
    _M111_CASILLA_07: Decimal("1"),
    _M111_CASILLA_08: Decimal("1000.00"),
    _M111_CASILLA_09: Decimal("1000.00"),
    _M111_CASILLA_28: Decimal("1000.00"),
}
