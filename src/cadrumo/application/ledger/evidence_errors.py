"""Typed refusals for the purchase invoice evidence surface.

These live apart from the evidence records and their CRUD service because the
inference package raises and catches them while holding no repository handle
of its own. ``evidence`` reaches
:class:`~cadrumo.adapters.persistence.storage.AttachmentStore` and the bucket
event history, so importing a refusal from there pulled the whole persistence
subtree into every consumer that only needed the exception type -- including
the outbound LLM adapter, whose distance from persistence is what the operator's
in-memory inference exemption rests on.

This module therefore imports no persistence, and must keep it that way: its
only dependencies are the shared error base and the ledger precondition mixin,
neither of which reaches an adapter.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError
from .preconditions import LedgerPreconditionErrorMixin

__all__ = [
    "PurchaseInvoiceEvidenceInputError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "PurchaseInvoiceEvidenceReaderError",
]


class PurchaseInvoiceEvidenceInputError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI-supplied evidence input violates the typed contract."""


class PurchaseInvoiceEvidenceReaderError(PurchaseInvoiceEvidenceInputError):
    """Raised when the reader, not the document, is why a read did not happen.

    A subclass because every caller that catches an evidence-input refusal must
    keep catching this one, and a distinct class because the two say opposite
    things to an operator: an input refusal asks them to correct what they
    supplied, while this one says the document was fine and the reader was
    absent or answered unusably. It is RETRYABLE for the same reason -- the same
    command run again against a reachable reader is the remedy.
    """


class PurchaseInvoiceEvidenceNotFoundError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI lookup targets a missing evidence record."""
