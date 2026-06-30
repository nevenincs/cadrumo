"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    _casilla_id,
    _casilla_ids,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_DECL_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_DECL_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")
_DECL_SUMMARY_CASILLAS: frozenset[CasillaId] = _casilla_ids(
    "decl.total-perceptores",
    "decl.base-total",
    "decl.retenciones-total",
)
_DECL_SUMMARY_ASSERTION_CASILLAS: tuple[CasillaId, ...] = (
    _DECL_TOTAL_PERCEPTORES_CASILLA,
    _DECL_BASE_TOTAL_CASILLA,
    _DECL_RETENCIONES_TOTAL_CASILLA,
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

def test_verification_chain_m190_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts the 3 M190 summary casillas from the real corpus PDF.

    GROUNDED authority: real AEAT corpus PDF (sanitised) committed at
    src/aeat/tests/fixtures/justificantes/190/2024-0A.pdf.

    The M190 registry has no formulas — retenciones-total is an aggregation of
    perceptor-level withholding records, not a computed formula. Verdict:
    BINDING-GAP for formula verification — no formula to exercise. This test
    verifies the extraction side of the chain.
    """
    pdf_path = FIXTURES_DIR / "justificantes" / "190" / "2024-0A.pdf"

    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="190",
            año_override=2024,
            period_override="0A",
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [M190/2024-0A]: parse_declaracion raised.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}
    assert _DECL_RETENCIONES_TOTAL_CASILLA in extracted, (
        f"PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_RETENCIONES_TOTAL_CASILLA], Decimal), (
        "PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not Decimal"
    )
