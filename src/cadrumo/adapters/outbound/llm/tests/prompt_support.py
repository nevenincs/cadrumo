"""Test composition for the canonical invoice prompt compiler and renderer."""

from collections.abc import Collection

from .....application.ledger.invoice_extraction_authority import resolve_invoice_extraction_authority_values
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..invoice_extraction_prompt import CompiledInvoiceExtractionPrompt, render_invoice_extraction_prompt


def build_invoice_extraction_prompt(
    *,
    period: Period,
    operation: PinnedAuthorityOperation,
    fields: Collection[str] | None = None,
) -> CompiledInvoiceExtractionPrompt:
    """Compose the prompt with the caller's pinned authority operation."""
    return render_invoice_extraction_prompt(
        values=resolve_invoice_extraction_authority_values(period=period, operation=operation),
        fields=fields,
    )
