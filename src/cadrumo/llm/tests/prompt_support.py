"""Test composition for the canonical invoice prompt compiler and renderer."""

from collections.abc import Collection

from ...application.ledger.invoice_extraction_authority import resolve_invoice_extraction_authority_values
from ...core.period import Period
from ..invoice_extraction_prompt import CompiledInvoiceExtractionPrompt, render_invoice_extraction_prompt


def build_invoice_extraction_prompt(
    *,
    period: Period,
    fields: Collection[str] | None = None,
) -> CompiledInvoiceExtractionPrompt:
    """Compose the two production owners without shipping a test convenience."""
    return render_invoice_extraction_prompt(
        values=resolve_invoice_extraction_authority_values(period=period),
        fields=fields,
    )
