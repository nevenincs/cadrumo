"""Shared Modelo 303 parser boundary corpus expectations.

See Also:
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m303`
        Single-fixture parser boundary check for the current Modelo 303
        declaration profile.
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m303_corpus_printed_template`
        Current-template corpus sweep that consumes the 2023-2024 parameters
        and expected profile casilla set.
    :mod:`~adapters.inbound.declaracion.tests.test_parser_boundary_m303_historical`
        Historical-template corpus sweep that consumes the 2021-2022
        parameters and expected values.
    :class:`~domain.calculations.registry.CasillaId`
        Typed casilla key used for historical expected extracted values.
"""

from __future__ import annotations

from decimal import Decimal

from .....core.casilla_id import CasillaId, validated_casilla_id
from .parser_boundary_m100_support import corpus_specimens
from .parser_boundary_support import expected_casilla_values, split_by_supported_filing_year

_M303_HISTORICAL_EXPECTED_OLDEST_FIRST: tuple[dict[CasillaId, Decimal], ...] = (
    expected_casilla_values(
        {"27": Decimal("12000.00"), "29": Decimal("7800.00"), "45": Decimal("7800.00"), "c46": Decimal("4200.00")},
    ),
    expected_casilla_values(
        {"27": Decimal("13200.00"), "29": Decimal("8400.00"), "45": Decimal("8400.00"), "c46": Decimal("4800.00")},
    ),
    expected_casilla_values(
        {"27": Decimal("14400.00"), "29": Decimal("9000.00"), "45": Decimal("9000.00"), "c46": Decimal("5400.00")},
    ),
    expected_casilla_values(
        {"27": Decimal("12600.00"), "29": Decimal("8100.00"), "45": Decimal("8100.00"), "c46": Decimal("4500.00")},
    ),
    expected_casilla_values(
        {"27": Decimal("15000.00"), "29": Decimal("9600.00"), "45": Decimal("9600.00"), "c46": Decimal("5400.00")},
    ),
    expected_casilla_values(
        {"27": Decimal("16200.00"), "29": Decimal("10200.00"), "45": Decimal("10200.00"), "c46": Decimal("6000.00")},
    ),
    expected_casilla_values(
        {"27": Decimal("18000.00"), "29": Decimal("11400.00"), "45": Decimal("11400.00"), "c46": Decimal("6600.00")},
    ),
)
_M303_CORPUS_CASES: tuple[tuple[str, int, str], ...] = corpus_specimens("303")
# The specimens the historical-template expectations describe are the oldest ones; the
# rest of the directory is the current printed template.
_M303_HISTORICAL_CASES: tuple[tuple[str, int, str], ...] = _M303_CORPUS_CASES[
    : len(_M303_HISTORICAL_EXPECTED_OLDEST_FIRST)
]
M303_HISTORICAL_PARAMS, M303_HISTORICAL_UNSUPPORTED_PARAMS = split_by_supported_filing_year(
    _M303_HISTORICAL_CASES, year_index=1
)
M303_HISTORICAL_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in M303_HISTORICAL_PARAMS)
M303_HISTORICAL_UNSUPPORTED_IDS: tuple[str, ...] = tuple(
    stem for stem, _year, _period in M303_HISTORICAL_UNSUPPORTED_PARAMS
)

M303_2023_2024_PARAMS: tuple[tuple[str, int, str], ...] = _M303_CORPUS_CASES[
    len(_M303_HISTORICAL_EXPECTED_OLDEST_FIRST) :
]
M303_2023_2024_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in M303_2023_2024_PARAMS)

_M303_CORPUS_STEMS: tuple[str, ...] = tuple(
    stem for stem, _year, _period in (*_M303_HISTORICAL_CASES, *M303_2023_2024_PARAMS)
)

M303_CURRENT_PROFILE_CASILLAS: frozenset[str] = frozenset(
    {
        "27",
        "29",
        "37",
        "45",
        "iva.resultado-regimen-general",
        "64",
        "66",
        "iva.compensacion-pendiente-periodos-anteriores",
        "iva.compensacion-aplicada-periodo",
        "iva.compensacion-pendiente-periodos-posteriores",
        "iva.resultado",
        "71",
    },
)
M303_HISTORICAL_PROFILE_CASILLAS: frozenset[str] = frozenset(
    {
        "27",
        "29",
        "45",
        "iva.resultado-regimen-general",
    },
)

M303_C46_ALIAS: CasillaId = validated_casilla_id("c46", surface="declaracion_parser_boundary.casilla")
M303_HISTORICAL_EXPECTED: dict[str, dict[CasillaId, Decimal]] = dict(
    zip(
        (stem for stem, _year, _period in _M303_HISTORICAL_CASES),
        _M303_HISTORICAL_EXPECTED_OLDEST_FIRST,
        strict=True,
    )
)
