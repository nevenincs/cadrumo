"""Typed refusals for the purchase invoice evidence surface.

These live apart from the evidence records and their CRUD service because the
inference package raises and catches them while holding no repository handle
of its own. ``evidence`` reaches
:class:`~cadrumo.adapters.persistence.storage.AttachmentStore` and the bucket
event history, so importing a refusal from there pulled the whole persistence
subtree into every consumer that only needed the exception type -- including
``cadrumo.llm``, whose distance from persistence is what the operator's
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
]


class PurchaseInvoiceEvidenceInputError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI-supplied evidence input violates the typed contract."""


class PurchaseInvoiceEvidenceNotFoundError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI lookup targets a missing evidence record."""
