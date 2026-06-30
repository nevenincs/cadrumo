"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    _casilla_ids,
    parse_declaracion,
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
    pdf_path = FIXTURES_DIR / "justificantes" / modelo / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override=modelo,
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [{case_label}]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert set(extracted.keys()) == _DECL_SUMMARY_CASILLAS, (
        f"PARSER-GAP [{case_label}]: unexpected casilla set.\n  got: {sorted(extracted)}"
    )
    for casilla_id, value in extracted.items():
        assert isinstance(value, Decimal), (
            f"PARSER-GAP [{case_label}]: casilla {casilla_id!r} not Decimal: {type(value).__name__!r}"
        )
