"""Application-owned capabilities for the invoice catalogue lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .catalogue_creation_ports import (
    CatalogueInvoiceAuditCommitPort,
    CatalogueInvoiceEventRepositoryPort,
    CatalogueInvoiceRepositoryPort,
)
from .catalogue_reads_ports import InvoiceCatalogueReadPorts


@dataclass(frozen=True, slots=True)
class CatalogueLifecyclePorts:
    """Required read, mutation, and audit capabilities for one bucket."""

    read_ports: InvoiceCatalogueReadPorts
    invoice_repository: CatalogueInvoiceRepositoryPort
    event_repository: CatalogueInvoiceEventRepositoryPort
    audit_commit: CatalogueInvoiceAuditCommitPort


class CatalogueLifecyclePortsFactory(Protocol):
    """Construct the complete invoice lifecycle bundle for one bucket."""

    def __call__(self, *, bucket_id: str) -> CatalogueLifecyclePorts:
        """Return all lifecycle capabilities bound to ``bucket_id``."""
        ...


__all__ = ["CatalogueLifecyclePorts", "CatalogueLifecyclePortsFactory"]
