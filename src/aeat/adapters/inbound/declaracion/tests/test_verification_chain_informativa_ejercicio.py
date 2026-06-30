"""Informativa ejercicio parser-verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    CasillaId,
    _assert_decimal_casilla,
    _casilla_id,
    _declaracion_case_label,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")


@pytest.mark.parametrize(
    ("modelo", "fixture_stem", "period"),
    [
        ("184", "2024-0A", "0A"),
        ("347", "2024-0A", "0A"),
        ("720", "2024-0A", "0A"),
        ("840", "2024-0A", "0A"),
    ],
    ids=("m184", "m347", "m720", "m840"),
)
def test_verification_chain_informativa_parser_extracts_ejercicio_casilla(
    modelo: str,
    fixture_stem: str,
    period: str,
) -> None:
    extracted = _parse_extracted_declaracion_values(modelo=modelo, fixture_stem=fixture_stem, year=2024, period=period)

    _assert_decimal_casilla(
        extracted,
        _DECL_EJERCICIO_CASILLA,
        label=_declaracion_case_label(modelo, fixture_stem),
    )
