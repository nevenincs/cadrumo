"""Historical-template Modelo 303 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_part2_support import (
    _M303_CASILLA_27,
    _M303_CASILLA_29,
    _M303_CASILLA_45,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
)
from ._parser_boundary_support import (
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    _casilla_id,
    _expected_casilla_values,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_M303_HISTORICAL_PARAMS: tuple[tuple[str, int, str], ...] = (
    ("2021-2T", 2021, "2T"),
    ("2021-3T", 2021, "3T"),
    ("2021-4T", 2021, "4T"),
    ("2022-1T", 2022, "1T"),
    ("2022-2T", 2022, "2T"),
    ("2022-3T", 2022, "3T"),
    ("2022-4T", 2022, "4T"),
)
_M303_HISTORICAL_IDS: tuple[str, ...] = tuple(stem for stem, _year, _period in _M303_HISTORICAL_PARAMS)
_M303_HISTORICAL_PROFILE_CASILLAS: frozenset[str] = frozenset(
    {
        "iva.repercutido.general",
        "iva.repercutido.reducido",
        "iva.repercutido.super-reducido",
        "iva.autorepercutido.intracomunitaria",
        "iva.soportado.interiores",
        "27",
        "29",
        "45",
        "iva.resultado-regimen-general",
    },
)
_M303_C46_ALIAS: CasillaId = _casilla_id("c46")
_M303_HISTORICAL_EXPECTED: dict[str, dict[CasillaId, Decimal]] = {
    "2021-2T": _expected_casilla_values(
        {"27": Decimal("12000.00"), "29": Decimal("7800.00"), "45": Decimal("7800.00"), "c46": Decimal("4200.00")},
    ),
    "2021-3T": _expected_casilla_values(
        {"27": Decimal("13200.00"), "29": Decimal("8400.00"), "45": Decimal("8400.00"), "c46": Decimal("4800.00")},
    ),
    "2021-4T": _expected_casilla_values(
        {"27": Decimal("14400.00"), "29": Decimal("9000.00"), "45": Decimal("9000.00"), "c46": Decimal("5400.00")},
    ),
    "2022-1T": _expected_casilla_values(
        {"27": Decimal("12600.00"), "29": Decimal("8100.00"), "45": Decimal("8100.00"), "c46": Decimal("4500.00")},
    ),
    "2022-2T": _expected_casilla_values(
        {"27": Decimal("15000.00"), "29": Decimal("9600.00"), "45": Decimal("9600.00"), "c46": Decimal("5400.00")},
    ),
    "2022-3T": _expected_casilla_values(
        {"27": Decimal("16200.00"), "29": Decimal("10200.00"), "45": Decimal("10200.00"), "c46": Decimal("6000.00")},
    ),
    "2022-4T": _expected_casilla_values(
        {"27": Decimal("18000.00"), "29": Decimal("11400.00"), "45": Decimal("11400.00"), "c46": Decimal("6600.00")},
    ),
}


@pytest.mark.parametrize("pdf_stem,year,period", _M303_HISTORICAL_PARAMS, ids=_M303_HISTORICAL_IDS)
def test_parser_extracts_modelo_303_historical_template_profile_targets_from_corpus(
    pdf_stem: str,
    year: int,
    period: str,
) -> None:
    """Round-trip all 2021-2022 M303 corpus PDFs from the historical printed template."""
    expected = _M303_HISTORICAL_EXPECTED[pdf_stem]
    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"

    filing = parse_declaracion(
        pdf_path,
        modelo_override="303",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "303"
    assert filing.period == _expected_period(year, period)
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "303"
    assert filing.registry_snapshot_ref.revision_id == "2009-y-siguientes"
    assert filing.registry_snapshot_ref.modelo_year == year

    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == _M303_HISTORICAL_PROFILE_CASILLAS

    expected_values = {
        _M303_CASILLA_27: expected[_M303_CASILLA_27],
        _M303_CASILLA_29: expected[_M303_CASILLA_29],
        _M303_CASILLA_45: expected[_M303_CASILLA_45],
        _M303_RESULTADO_REGIMEN_GENERAL_CASILLA: expected[_M303_C46_ALIAS],
    }
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value, (
            f"{pdf_stem}: casilla {casilla_id!r} expected {expected_value!r}, got {values[casilla_id]!r}"
        )
