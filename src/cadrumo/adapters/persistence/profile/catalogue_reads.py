"""Persistence adapters for the invoice link-consistency read port."""

from __future__ import annotations

from datetime import date

from ....application.invoices.catalogue_reads_ports import (
    InvoiceCatalogueReadPersistenceError,
    InvoiceCatalogueReadPorts,
    InvoiceCatalogueReader,
    TransactionCatalogueReader,
)
from ....domain.invoices.errors import InvoicePersistenceError
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.transactions.errors import TransactionPersistenceError
from ....domain.transactions.models import LedgerDatePartition, TransactionCatalogue
from ..storage.errors import StorageError
from ..storage.runtime_repository import secure_object_repository_for_bucket
from .invoices import InvoiceCatalogueRepository
from .transactions import TransactionCatalogueRepository


class InvoiceCatalogueReadAdapter(InvoiceCatalogueReader):
    """Translate the encrypted invoice repository to the application read port."""

    def __init__(self, *, repository: InvoiceCatalogueRepository) -> None:
        """Bind an already-composed invoice repository."""
        self._repository = repository

    def load(self) -> InvoiceCatalogue:
        """Load the catalogue while hiding persistence implementation errors."""
        try:
            return self._repository.load()
        except (InvoicePersistenceError, StorageError, OSError) as exc:
            raise InvoiceCatalogueReadPersistenceError("invoice_catalogue_load") from exc


class TransactionCatalogueReadAdapter(TransactionCatalogueReader):
    """Translate the encrypted transaction repository to the application read port."""

    def __init__(self, *, repository: TransactionCatalogueRepository) -> None:
        """Bind an already-composed transaction repository."""
        self._repository = repository

    def load(self) -> TransactionCatalogue:
        """Load the catalogue while hiding persistence implementation errors."""
        try:
            return self._repository.load()
        except (TransactionPersistenceError, StorageError, OSError) as exc:
            raise InvoiceCatalogueReadPersistenceError("transaction_catalogue_load") from exc

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Partition the catalogue while hiding persistence implementation errors."""
        try:
            return self._repository.partition_by_date_range(start, end)
        except (TransactionPersistenceError, StorageError, OSError) as exc:
            raise InvoiceCatalogueReadPersistenceError("transaction_catalogue_partition") from exc


def build_invoice_catalogue_read_ports(*, bucket_id: str) -> InvoiceCatalogueReadPorts:
    """Bind both encrypted catalogue repositories to one profile bucket."""
    normalized_bucket_id = bucket_id.strip()
    objects = secure_object_repository_for_bucket(normalized_bucket_id)
    return InvoiceCatalogueReadPorts(
        invoice_reader=InvoiceCatalogueReadAdapter(
            repository=InvoiceCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        ),
        transaction_reader=TransactionCatalogueReadAdapter(
            repository=TransactionCatalogueRepository(bucket_id=normalized_bucket_id, objects=objects),
        ),
    )


__all__ = [
    "InvoiceCatalogueReadAdapter",
    "TransactionCatalogueReadAdapter",
    "build_invoice_catalogue_read_ports",
]
