"""Modelo 190 parser-verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    FIXTURES_DIR,
    CasillaId,
    Decimal,
    DeclaracionParseError,
    _casilla_id,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")


def test_verification_chain_m190_parser_extracts_declaracion_pdf_casillas() -> None:
    """Parser extracts M190 summary retenciones from the real corpus PDF.

    GROUNDED authority: real AEAT corpus PDF (sanitised) committed at
    src/aeat/tests/fixtures/justificantes/190/2024-0A.pdf.

    The M190 registry has no formulas; retenciones-total is an aggregation of
    perceptor-level withholding records, not a computed formula. Verdict:
    BINDING-GAP for formula verification; no formula to exercise. This test
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
