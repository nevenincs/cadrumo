"""Parser-only declaracion verification-chain coverage for summary modelos."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    CasillaId,
    Decimal,
    _assert_decimal_casilla,
    _casilla_id,
    _casilla_ids,
    _declaracion_case_label,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_M349_SUMMARY_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "decl.numero-operadores",
    "decl.importe-operaciones",
    "decl.numero-rectificaciones",
    "decl.importe-rectificaciones",
)
_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_DECL_PERIODO_CASILLA: CasillaId = _casilla_id("decl.periodo")
_DECL_EVENT_KIND_CASILLA: CasillaId = _casilla_id("decl.event-kind")


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


def test_verification_chain_m369_parser_extracts_declaracion_pdf_casillas() -> None:
    extracted = _parse_extracted_declaracion_values(modelo="369", fixture_stem="2024-1T", year=2024, period="1T")

    _assert_decimal_casilla(extracted, _DECL_EJERCICIO_CASILLA, label="M369/2024-1T")
    assert _DECL_PERIODO_CASILLA in extracted, (
        f"PARSER-GAP [M369/2024-1T]: {_DECL_PERIODO_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )


def test_verification_chain_m036_parser_extracts_event_kind_casilla() -> None:
    extracted = _parse_extracted_declaracion_values(modelo="036", fixture_stem="2025-alta", year=2025, period="alta")

    assert _DECL_EVENT_KIND_CASILLA in extracted, (
        f"PARSER-GAP [M036/2025-alta]: {_DECL_EVENT_KIND_CASILLA!r} not extracted.\n  got: {sorted(extracted)}"
    )
    event_kind = extracted[_DECL_EVENT_KIND_CASILLA]
    assert isinstance(event_kind, str), (
        f"PARSER-GAP [M036/2025-alta]: {_DECL_EVENT_KIND_CASILLA!r} not str: {type(event_kind).__name__!r}"
    )
    assert event_kind == "Alta", f"PARSER-GAP [M036/2025-alta]: expected 'Alta', got {event_kind!r}"
