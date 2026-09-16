"""Build invoice catalogues for tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ..models import Invoice, InvoiceCatalogue


def build_invoice_catalogue(invoices: Iterable[Invoice | Mapping[str, object]]) -> InvoiceCatalogue:
    """Validate ``invoices`` into an immutable catalogue."""
    return InvoiceCatalogue.model_validate(tuple(invoices))
