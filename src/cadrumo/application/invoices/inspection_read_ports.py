"""Narrow explicit-profile invoice inspection capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .catalogue_reads_ports import InvoiceCatalogueReader


class BoundInvoiceCatalogueReader(InvoiceCatalogueReader, Protocol):
    """A canonical catalogue reader whose storage profile is explicit."""

    @property
    def bucket_id(self) -> str | None:
        """Return the storage profile to validate before opening private records."""
        ...


@dataclass(frozen=True, slots=True)
class InvoiceInspectionReadPorts:
    """One read capability bound to one worker profile."""

    bucket_id: str
    invoices: BoundInvoiceCatalogueReader


class InvoiceInspectionReadPortsFactory(Protocol):
    """Compose only invoice reads under the retained operation authority."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> InvoiceInspectionReadPorts:
        """Bind the explicit profile without ambient fallback."""
        ...
