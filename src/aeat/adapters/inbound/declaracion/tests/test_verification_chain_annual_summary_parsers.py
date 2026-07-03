"""Annual summary parser-verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    CasillaId,
    _assert_all_extracted_values_decimal,
    _casilla_ids,
    _parse_extracted_declaracion_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_DECL_SUMMARY_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "decl.total-perceptores",
    "decl.base-total",
    "decl.retenciones-total",
)


_ANNUAL_SUMMARY_PARSER_CASES: tuple[tuple[str, str], ...] = (
    ("180", "M180/2024-0A"),
    ("193", "M193/2024-0A"),
)


@pytest.mark.parametrize(
    ("modelo", "case_label"),
    _ANNUAL_SUMMARY_PARSER_CASES,
    ids=("m180", "m193"),
)
def test_verification_chain_annual_summary_parser_extracts_declaracion_pdf_casillas(
    modelo: str,
    case_label: str,
) -> None:
    extracted = _parse_extracted_declaracion_values(modelo=modelo, fixture_stem="2024-0A", year=2024, period="0A")
    assert set(extracted.keys()) == _DECL_SUMMARY_CASILLAS, (
        f"PARSER-GAP [{case_label}]: unexpected casilla set.\n  got: {sorted(extracted)}"
    )
    _assert_all_extracted_values_decimal(extracted, label=case_label)
