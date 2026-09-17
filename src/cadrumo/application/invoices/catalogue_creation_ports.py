"""Application-owned capabilities for catalogue-invoice creation.

The creation service needs three distinct authorities: a guarded invoice
catalogue mutation, a guarded bucket-event append, and an exchange-rate source.
This module owns the narrow contracts and the bucket-scoped bundle.  Concrete
encrypted repositories and outbound rate providers are composed outside the
application layer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from ...core.errors.hierarchy import CadrumoError
from ...domain.buckets.event import BucketEventHistoryCatalogue
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.invoices.models import InvoiceCatalogue


class CatalogueInvoicePersistenceError(CadrumoError):
    """Translated failure from the invoice or event persistence capability."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"catalogue invoice persistence operation failed: {operation}")


class CatalogueInvoiceRateError(CadrumoError):
    """Translated failure from the catalogue invoice rate capability."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never outbound details."""
        self.operation = operation
        super().__init__(f"catalogue invoice rate operation failed: {operation}")


class CatalogueInvoiceRepositoryPort(Protocol):
    """Guarded invoice-catalogue mutation capability for one bucket."""

    def load(self) -> InvoiceCatalogue:
        """Return the bucket's current invoice catalogue."""
        ...

    def mutate(self, mutation: Callable[[InvoiceCatalogue], InvoiceCatalogue]) -> InvoiceCatalogue:
        """Apply ``mutation`` as one revision-guarded catalogue write.

        Core types:
        :class:`~cadrumo.domain.invoices.models.InvoiceCatalogue`.
        """
        ...


class CatalogueInvoiceEventRepositoryPort(BucketEventHistoryRepositoryProtocol, Protocol):
    """Guarded event-history capability for one bucket."""

    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        """Append through the event catalogue's revision guard."""
        ...


class CatalogueInvoiceRateProviderPort(Protocol):
    """Exchange-rate capability used while constructing a catalogue invoice."""

    @property
    def rate_source_id(self) -> str:
        """Return the authority identifier stamped on converted invoices."""
        ...

    def get_eur_rate(self, currency: str, rate_date: date) -> Decimal | None:
        """Return the currency-to-EUR rate, or no rate for that date."""
        ...


@dataclass(frozen=True, slots=True)
class CatalogueCreationPorts:
    """Required authorities for one bucket-scoped catalogue creation."""

    invoice_repository: CatalogueInvoiceRepositoryPort
    event_repository: CatalogueInvoiceEventRepositoryPort
    rate_provider: CatalogueInvoiceRateProviderPort


class CatalogueCreationPortsFactory(Protocol):
    """Construct the complete creation bundle for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> CatalogueCreationPorts:
        """Return all creation authorities bound to ``bucket_id``."""
        ...


__all__ = [
    "CatalogueCreationPorts",
    "CatalogueCreationPortsFactory",
    "CatalogueInvoiceEventRepositoryPort",
    "CatalogueInvoicePersistenceError",
    "CatalogueInvoiceRateError",
    "CatalogueInvoiceRateProviderPort",
    "CatalogueInvoiceRepositoryPort",
]
