"""Application-owned capabilities for the invoice catalogue lifecycle.

This module uses :class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit import WorkUnit
from .catalogue_creation_ports import (
    CatalogueInvoiceAuditCommitPort,
    CatalogueInvoiceEventRepositoryPort,
    CatalogueInvoiceRepositoryPort,
)
from .catalogue_reads_ports import InvoiceCatalogueReadPorts, InvoiceDocumentManifestReader


class SealedRevisionReaderPort(Protocol):
    """Read the sealed revisions of one bucket with the work unit each belongs to."""

    def sealed_revisions(self) -> tuple[tuple[CalculationRevision, WorkUnit], ...]:
        """Return every sealed revision whose work unit is in this bucket."""
        ...


@dataclass(frozen=True, slots=True)
class CatalogueLifecyclePorts:
    """Required read, mutation, and audit capabilities for one bucket."""

    read_ports: InvoiceCatalogueReadPorts
    invoice_repository: CatalogueInvoiceRepositoryPort
    event_repository: CatalogueInvoiceEventRepositoryPort
    audit_commit: CatalogueInvoiceAuditCommitPort
    sealed_revisions: SealedRevisionReaderPort
    #: The profile's document manifests, so a changed or removed invoice is served with its documents.
    documents: InvoiceDocumentManifestReader


class CatalogueLifecyclePortsFactory(Protocol):
    """Construct the complete invoice lifecycle bundle for one bucket."""

    def __call__(
        self, *, bucket_id: str, mutation_writer: Callable[[Callable[[], None]], None] | None = None
    ) -> CatalogueLifecyclePorts:
        """Return all lifecycle capabilities bound to ``bucket_id``.

        ``mutation_writer``, when given, admits every commit those capabilities
        make, so an operation can journal a possible effect only once a write
        is about to begin.
        """
        ...


__all__ = ["CatalogueLifecyclePorts", "CatalogueLifecyclePortsFactory", "SealedRevisionReaderPort"]
