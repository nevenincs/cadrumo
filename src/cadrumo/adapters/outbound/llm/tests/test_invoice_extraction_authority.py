"""The outbound invoice readers consume the application authority they receive.

These tests belong beside the prompt and text-reader adapters because they
exercise concrete rendering and reader-entry-point behavior.  Authority
resolution itself remains covered by the inward application test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from cadrumo.core.period import Period
from cadrumo.domain.iva.schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_2026 = Period.from_year_and_code(2026, "0A")
_FABRICATED_PCT = Decimal("37.25")
_FABRICATED_RETENCION_PCT = Decimal("41.75")


def _fabricated_values() -> InvoiceExtractionAuthorityValues:
    """Return values that share no figure with the real registry."""
    return InvoiceExtractionAuthorityValues(
        period=_ANNUAL_2026,
        iva_rate_pcts=(_FABRICATED_PCT,),
        retencion_rate_pcts=(_FABRICATED_RETENCION_PCT,),
        no_printed_tax_categories=(IvaCategory("domestic_exempt"),),
        regime_legend_phrases=("regimen inventado a efectos de prueba",),
    )


class TestTheRendererCannotReachAroundItsArgument:
    """The prompt renderer has exactly the authority values it is handed."""

    def test_fabricated_values_reach_the_text_and_the_real_ones_do_not(self) -> None:
        """The renderer cannot reacquire the registry behind its argument."""
        from cadrumo.adapters.outbound.llm.invoice_extraction_prompt import render_invoice_extraction_prompt
        from cadrumo.application.ledger.invoice_extraction_authority import (
            resolve_invoice_extraction_authority_values,
        )

        real = resolve_invoice_extraction_authority_values(period=_ANNUAL_2026)
        rendered = render_invoice_extraction_prompt(values=_fabricated_values())

        assert "37.25" in rendered.text
        assert "41.75" in rendered.text
        assert "regimen inventado a efectos de prueba" in rendered.text
        for pct in real.iva_rate_pcts:
            assert f"{pct.normalize():f}%" not in rendered.text
        for phrase in real.regime_legend_phrases:
            assert phrase not in rendered.text

    def test_the_compiled_artefact_reports_the_values_it_rendered(self) -> None:
        """The compiled stamp describes the supplied read, not a re-resolution."""
        from cadrumo.adapters.outbound.llm.invoice_extraction_prompt import render_invoice_extraction_prompt

        rendered = render_invoice_extraction_prompt(values=_fabricated_values())

        assert rendered.iva_rate_pcts == (_FABRICATED_PCT,)
        assert rendered.period == _ANNUAL_2026


class TestTheReaderEntryPointUsesTheAuthority:
    """The concrete text-reader entry point forwards authority to its prompt."""

    def test_values_passed_to_the_reader_entry_point_reach_the_dispatched_prompt(self) -> None:
        """Reader prompt bytes carry the exact application-owned values supplied."""
        from cadrumo.adapters.outbound.llm.evidence_draft_text import build_text_field_extraction_prompt

        prompt = build_text_field_extraction_prompt("Factura 1", values=_fabricated_values())

        assert "37.25" in prompt
        assert "Factura 1" in prompt
