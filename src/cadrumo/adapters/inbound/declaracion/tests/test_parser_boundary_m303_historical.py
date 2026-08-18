"""Historical-template Modelo 303 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_casillas import (
    _M303_CASILLA_27,
    _M303_CASILLA_29,
    _M303_CASILLA_45,
    _M303_RESULTADO_REGIMEN_GENERAL_CASILLA,
)
from ._parser_boundary_m303_support import (
    _M303_C46_ALIAS,
    _M303_HISTORICAL_EXPECTED,
    _M303_HISTORICAL_IDS,
    _M303_HISTORICAL_PARAMS,
    _M303_HISTORICAL_PROFILE_CASILLAS,
)
from ._parser_boundary_support import (
    FIXTURES_DIR,
    _expected_period,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


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
    assert filing.registry_snapshot_ref.revision_id == "2022"
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
