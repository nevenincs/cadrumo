"""Modelo 349 parser-verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    CasillaId,
    Decimal,
    _casilla_ids,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M349_SUMMARY_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "decl.numero-operadores",
    "decl.importe-operaciones",
    "decl.numero-rectificaciones",
    "decl.importe-rectificaciones",
)


def test_verification_chain_m349_parser_extracts_declaracion_pdf_casillas() -> None:
    extracted = _parse_extracted_declaracion_values(modelo="349", fixture_stem="2024-1T", year=2024, period="1T")

    assert set(extracted.keys()) == _M349_SUMMARY_CASILLAS, (
        f"PARSER-GAP [M349/2024-1T]: unexpected casilla set.\n  got: {sorted(extracted)}"
    )
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [M349/2024-1T]: casilla {casilla_id!r} not Decimal: "
            f"{type(value).__name__!r} = {value!r}"
        )
