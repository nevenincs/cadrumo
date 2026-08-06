"""Shared Modelo 123 parser boundary corpus expectations."""

from __future__ import annotations

from ._parser_boundary_support import (
    _MODELO_123_2023_SYNTHETIC_FIXTURE,
    _MODELO_123_2024_SYNTHETIC_FIXTURE,
    _MODELO_123_CURRENT_EXPECTED_TARGETS,
    _MODELO_123_HISTORICAL_EXPECTED_TARGETS,
    CasillaId,
    Decimal,
    Path,
    _expected_casilla_values,
)

_M123_PROFILE_TARGET_CASES: tuple[tuple[str, int, str, str, tuple[CasillaId, ...]], ...] = (
    ("current", 2026, "1T", "modelo-123-declaracion-pdf", _MODELO_123_CURRENT_EXPECTED_TARGETS),
    ("historical", 2023, "4T", "modelo-123-2019-declaracion-pdf", _MODELO_123_HISTORICAL_EXPECTED_TARGETS),
)
_M123_PROFILE_TARGET_CASE_IDS: tuple[str, ...] = tuple(
    case_id for case_id, _year, _period, _profile_id, _targets in _M123_PROFILE_TARGET_CASES
)

_M123_CORPUS_CASES: tuple[
    tuple[str, Path, int, str, str, tuple[CasillaId, ...], dict[CasillaId, Decimal]],
    ...,
] = (
    (
        "2024-y-siguientes",
        _MODELO_123_2024_SYNTHETIC_FIXTURE,
        2024,
        "1T",
        "2024-y-siguientes",
        _MODELO_123_CURRENT_EXPECTED_TARGETS,
        _expected_casilla_values(
            {
                "01": Decimal("5.00"),
                "02": Decimal("3.00"),
                "03": Decimal("8.00"),
                "04": Decimal("10000.00"),
                "05": Decimal("5000.00"),
                "06": Decimal("15000.00"),
                "07": Decimal("1900.00"),
                "08": Decimal("950.00"),
                "09": Decimal("2850.00"),
                "10": Decimal("0.00"),
                "11": Decimal("0.00"),
                "12": Decimal("2850.00"),
                "13": Decimal("0.00"),
                "14": Decimal("2850.00"),
            },
        ),
    ),
    (
        "2019-2023",
        _MODELO_123_2023_SYNTHETIC_FIXTURE,
        2023,
        "1T",
        "2019-2023",
        _MODELO_123_HISTORICAL_EXPECTED_TARGETS,
        _expected_casilla_values(
            {
                "01": Decimal("4.00"),
                "02": Decimal("8000.00"),
                "03": Decimal("1520.00"),
                "04": Decimal("0.00"),
                "05": Decimal("0.00"),
                "06": Decimal("1520.00"),
                "07": Decimal("0.00"),
                "08": Decimal("1520.00"),
            },
        ),
    ),
)
_M123_CORPUS_CASE_IDS: tuple[str, ...] = tuple(
    case_id for case_id, _fixture, _year, _period, _revision, _targets, _values in _M123_CORPUS_CASES
)
