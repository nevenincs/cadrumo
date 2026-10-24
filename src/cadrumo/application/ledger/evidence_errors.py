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
only dependencies are the shared error base, the ledger precondition mixin and
the verdict and setup-action contracts, none of which reaches an adapter.
"""

from __future__ import annotations

from typing import Final

from ...core.errors.hierarchy import CadrumoError
from ..operator_actions.models import PreconditionVerdict
from ..provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID
from .preconditions import LedgerPreconditionErrorMixin

__all__ = [
    "EVIDENCE_LOCAL_AI_NOT_READY_KEY",
    "EVIDENCE_READER_UNAVAILABLE_KEY",
    "PurchaseInvoiceEvidenceInputError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "PurchaseInvoiceEvidenceReaderError",
    "evidence_reader_refusal_key",
]

EVIDENCE_READER_UNAVAILABLE_KEY: Final = "errors.refused.refused_ledger_evidence_reader_unavailable"
"""The reader refusal that offers no setup: the reader could not run, for a reason setup cannot repair."""

EVIDENCE_LOCAL_AI_NOT_READY_KEY: Final = "errors.refused.refused_ledger_evidence_local_ai_not_ready"
"""The reader refusal that names the local AI and its setup."""


def evidence_reader_refusal_key(verdict: PreconditionVerdict | None) -> str:
    """Return the message key of a reader refusal carrying ``verdict``.

    The sentence follows the verdict, so the person is told to set the local AI
    up only when its setup is the action the verdict names.
    """
    if verdict is not None and verdict.action is not None and verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID:
        return EVIDENCE_LOCAL_AI_NOT_READY_KEY
    return EVIDENCE_READER_UNAVAILABLE_KEY


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
