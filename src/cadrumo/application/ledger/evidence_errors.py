"""Typed refusals for the purchase invoice evidence surface.

These live apart from the evidence records and their CRUD service because the
inference package raises and catches them while holding no repository handle
of its own. ``evidence`` reaches
:class:`~cadrumo.adapters.persistence.storage.attachment.AttachmentStore` and the bucket
event history, so importing a refusal from there pulled the whole persistence
subtree into every consumer that only needed the exception type -- including
the outbound LLM adapter, whose distance from persistence is what the operator's
in-memory inference exemption rests on.

This module therefore imports no persistence, and must keep it that way: its
only dependencies are the shared error base, the served-step mixin, the ledger
precondition mixin and the verdict contract, none of which reaches an adapter.
"""

from __future__ import annotations

from typing import Final

from ...core.errors.hierarchy import CadrumoError
from ..operations.next_step import OperationNextStepErrorMixin
from .preconditions import LedgerPreconditionErrorMixin

__all__ = [
    "EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY",
    "LedgerOffHostConsentRequiredError",
    "PurchaseInvoiceEvidenceInputError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "PurchaseInvoiceEvidenceReaderError",
]

EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY: Final = "errors.refused.refused_ledger_evidence_reader_unavailable"
"""The reader refusal: the reader could not run."""


class PurchaseInvoiceEvidenceInputError(OperationNextStepErrorMixin, LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI-supplied evidence input violates the typed contract.

    It carries the step that puts the refusal right where the producer knows
    one, such as the profile fact a confirm needs before it can classify.
    """


class PurchaseInvoiceEvidenceReaderError(PurchaseInvoiceEvidenceInputError):
    """Raised when the reader, not the document, is why a read did not happen.

    A subclass because every caller that catches an evidence-input refusal must
    keep catching this one, and a distinct class because the two say opposite
    things to an operator: an input refusal asks them to correct what they
    supplied, while this one says the document was fine and the reader was
    absent or answered unusably. It is RETRYABLE for the same reason -- the same
    command run again against a reachable reader is the remedy. A refusal the
    person puts right by choosing a model carries the step that leads there.
    """


class LedgerOffHostConsentRequiredError(OperationNextStepErrorMixin, LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a document read is refused for want of consent to send it off this computer.

    Neither the document nor the reader is at fault: the selected model runs
    off-host and the read carries no consent. It is not an unavailable reader,
    so it is not retried as one; the step it serves names the two remedies, to
    authorise the off-host read or to switch the role to a model on this computer.
    """


class PurchaseInvoiceEvidenceNotFoundError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI lookup targets a missing evidence record."""
