"""Application-owned capabilities for invoice source resolution.

The invoice source-mesh resolver needs only a read projection of the invoice
catalogue.  The application owns that narrow capability and its translated
persistence failure; an outer composition root binds the encrypted repository
adapter for each bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.invoices.models import InvoiceCatalogue


class InvoiceSourcePersistenceError(RuntimeError):
    """Translated failure while reading the invoice source catalogue."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"invoice source persistence operation failed: {operation}")


class InvoiceSourceCatalogueReader(Protocol):
    """Read the bucket-bound invoice catalogue used by source resolution."""

    def load(self) -> InvoiceCatalogue:
        """Return the validated invoice catalogue for the composed bucket."""
        ...


@dataclass(frozen=True, slots=True)
class InvoiceSourceResolverPorts:
    """Required capabilities for one invoice source-mesh resolver."""

    catalogue_reader: InvoiceSourceCatalogueReader


__all__ = [
    "InvoiceSourceCatalogueReader",
    "InvoiceSourcePersistenceError",
    "InvoiceSourceResolverPorts",
]
