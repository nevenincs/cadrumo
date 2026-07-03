from __future__ import annotations

import pytest

from ._verification_chain_support import (
    _M303_2023_ONWARDS_PARAMS,
    CasillaId,
    _assert_all_extracted_values_decimal,
    _casilla_ids,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M303_2023_PROFILE_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "iva.repercutido.general",
    "iva.repercutido.reducido",
    "iva.repercutido.super-reducido",
    "iva.autorepercutido.intracomunitaria",
    "iva.soportado.interiores",
    "iva.autoconsumo.promotor.base",
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
)


@pytest.mark.parametrize("pdf_stem,year,period", _M303_2023_ONWARDS_PARAMS)
def test_verification_chain_m303_parser_extracts_all_profile_casillas(pdf_stem: str, year: int, period: str) -> None:
    """Parser extracts all M303 2023+ profile casillas from corpus PDFs."""
    extracted = _parse_extracted_declaracion_values(modelo="303", fixture_stem=pdf_stem, year=year, period=period)

    assert set(extracted.keys()) == _M303_2023_PROFILE_CASILLAS, (
        f"PARSER-GAP [{pdf_stem}]: M303 2023+ profile extraction did not produce "
        f"the expected 18 casilla IDs (6 primitives + 12 form-page totals).\n"
        f"  got: {sorted(extracted)}"
    )
    _assert_all_extracted_values_decimal(extracted, label=pdf_stem)
