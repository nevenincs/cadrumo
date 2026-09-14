"""Application-owned read capabilities for invoice and transaction catalogues."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ...core.errors.hierarchy import CadrumoError
from ...domain.invoices.models import InvoiceCatalogue
from ...domain.transactions.models import LedgerDatePartition, TransactionCatalogue


class InvoiceCatalogueReadPersistenceError(CadrumoError):
    """Translated failure while loading a catalogue for link verification."""

    def __init__(self, operation: str) -> None:
        """Carry the application operation without exposing storage details."""
        self.operation = operation
        super().__init__(f"invoice catalogue read operation failed: {operation}")


class InvoiceCatalogueReader(Protocol):
    """Read capability for the application-facing invoice catalogue projection."""

    def load(self) -> InvoiceCatalogue:
        """Return the validated invoice catalogue for the composed bucket."""
        ...


class TransactionCatalogueReader(Protocol):
    """Read capability for the application-facing transaction projection."""

    def load(self) -> TransactionCatalogue:
        """Return the validated transaction catalogue for the composed bucket."""
        ...

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Return the bucket's transactions split at the requested date window."""
        ...


@dataclass(frozen=True, slots=True)
class InvoiceCatalogueReadPorts:
    """Required catalogue capabilities for one composed ledger read path."""

    invoice_reader: InvoiceCatalogueReader
    transaction_reader: TransactionCatalogueReader


__all__ = [
    "InvoiceCatalogueReadPersistenceError",
    "InvoiceCatalogueReadPorts",
    "InvoiceCatalogueReader",
    "TransactionCatalogueReader",
]
