"""Modelo 036 parser-verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    CasillaId,
    _casilla_id,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_DECL_EVENT_KIND_CASILLA: CasillaId = _casilla_id("decl.event-kind")


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
