"""Domain exceptions for the invoice catalogue.

Defines the typed error hierarchy raised by :mod:`cadrumo.domain.invoices`.
Every failure path inherits from :class:`InvoiceError` so callers can
catch the whole domain, while :class:`InvoiceCatalogueError` and its
subclasses narrow to catalogue-level faults (persistence, missing
records, broken cross-catalogue links).
"""

from __future__ import annotations

from pathlib import Path

from ...core.errors import CadrumoError, CoreValidationError

__all__ = [
    "InvoiceCatalogueError",
    "InvoiceError",
    "InvoiceLinkError",
    "InvoiceLinkInconsistencyError",
    "InvoiceNotFoundError",
    "InvoicePersistenceError",
    "InvoiceValidationError",
]


class InvoiceError(CadrumoError):
    """Base error for every invoice-catalogue failure."""


class InvoiceCatalogueError(InvoiceError):
    """Raised when an invoice catalogue is invalid or inconsistent."""


class InvoicePersistenceError(InvoiceCatalogueError):
    """Raised when invoice catalogue persistence cannot be completed."""


class InvoiceNotFoundError(InvoiceCatalogueError):
    """Raised when a catalogue lookup targets a missing invoice."""


class InvoiceLinkError(InvoiceCatalogueError):
    """Raised when a bidirectional invoice/transaction link cannot proceed."""


class InvoiceLinkInconsistencyError(InvoiceLinkError):
    """Raised when a bidirectional link leaves the two catalogues out of sync.

    Carries both filesystem paths and both identifiers so an operator can
    manually reconcile the invoice and transaction catalogues.

    Attributes:
        invoice_path: Path to the invoice catalogue file.
        transactions_path: Path to the transaction catalogue file.
        invoice_id: Invoice identifier involved in the failed link.
        transaction_id: Transaction identifier involved in the failed link.
    """

    def __init__(
        self,
        *,
        invoice_path: Path,
        transactions_path: Path,
        invoice_id: str,
        transaction_id: str,
        message: str,
    ) -> None:
        """Construct a link-inconsistency error carrying both sides of the failure.

        Args:
            invoice_path: Path to the invoice catalogue file.
            transactions_path: Path to the transaction catalogue file.
            invoice_id: Invoice identifier involved in the failed link.
            transaction_id: Transaction identifier involved in the failed link.
            message: Human-readable explanation.
        """
        super().__init__(message)
        self.invoice_path: Path = invoice_path
        self.transactions_path: Path = transactions_path
        self.invoice_id: str = invoice_id
        self.transaction_id: str = transaction_id


class InvoiceValidationError(InvoiceError, CoreValidationError):
    """Raised when invoice records violate state or shape invariants.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic validators.
    """
