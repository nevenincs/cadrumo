"""Application-owned capabilities for invoice confirmation.

Invoice confirmation links the source attachment to the invoice that the
confirmation mints (or reuses).  The application owns that capability's
boundary; an executable composition root supplies the bucket-bound attachment
store implementation.  Attachment manifests and their domain errors remain
domain values, so no persistence adapter DTO or exception crosses inward.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...domain.attachments.protocols import AttachmentStoreProtocol


class InvoiceConfirmationPersistenceError(RuntimeError):
    """Translated failure from the confirmation attachment capability."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"invoice confirmation persistence operation failed: {operation}")


@dataclass(frozen=True, slots=True)
class InvoiceConfirmationPorts:
    """Required authorities for one bucket-scoped invoice confirmation."""

    attachment_store: AttachmentStoreProtocol


class InvoiceConfirmationPortsFactory(Protocol):
    """Construct the complete confirmation capability bundle for one bucket."""

    def __call__(self, *, bucket_id: str) -> InvoiceConfirmationPorts:
        """Return the attachment capability bound to ``bucket_id``."""
        ...


__all__ = [
    "InvoiceConfirmationPersistenceError",
    "InvoiceConfirmationPorts",
    "InvoiceConfirmationPortsFactory",
]
