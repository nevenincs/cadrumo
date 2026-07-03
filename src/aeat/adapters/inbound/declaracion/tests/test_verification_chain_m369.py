"""Modelo 369 parser-verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    CasillaId,
    _assert_decimal_casilla,
    _casilla_id,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_DECL_PERIODO_CASILLA: CasillaId = _casilla_id("decl.periodo")


def test_verification_chain_m369_parser_extracts_declaracion_pdf_casillas() -> None:
    extracted = _parse_extracted_declaracion_values(modelo="369", fixture_stem="2024-1T", year=2024, period="1T")

    _assert_decimal_casilla(extracted, _DECL_EJERCICIO_CASILLA, label="M369/2024-1T")
    assert _DECL_PERIODO_CASILLA in extracted, (
        f"PARSER-GAP [M369/2024-1T]: {_DECL_PERIODO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
