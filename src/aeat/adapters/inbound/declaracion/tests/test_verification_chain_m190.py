"""Modelo 190 parser-verification-chain tests."""

from __future__ import annotations

import pytest

from ._verification_chain_support import (
    CasillaId,
    Decimal,
    _casilla_id,
    _parse_extracted_declaracion_values,
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
    extracted = _parse_extracted_declaracion_values(modelo="190", fixture_stem="2024-0A", year=2024, period="0A")
    assert _DECL_RETENCIONES_TOTAL_CASILLA in extracted, (
        f"PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not extracted.\n  got: {sorted(extracted)}"
    )
    assert isinstance(extracted[_DECL_RETENCIONES_TOTAL_CASILLA], Decimal), (
        "PARSER-GAP [M190/2024-0A]: 'decl.retenciones-total' not Decimal"
    )
