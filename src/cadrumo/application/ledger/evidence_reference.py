"""The one definition of what a transaction's evidence reference may name.

:attr:`~cadrumo.domain.transactions.Transaction.purchase_invoice_evidence_id`
addresses TWO bucket-scoped id spaces, and this module is the single place that
says so, in what order they are consulted, and which outcomes are acceptable:

1. A :class:`~cadrumo.application.ledger.evidence.PurchaseInvoiceEvidence` record minted by
   ``aeat app ledger evidence add`` -- a registered PDF/image whose bytes live in
   the encrypted attachment store. This is the only space that can supply document
   BYTES, so it is the only one an on-host reader can extract from.
2. An imported received-invoice id in the rich
   :class:`~cadrumo.domain.invoices.InvoiceCatalogue` -- bucket-matched and
   :attr:`~cadrumo.domain.iva.InvoiceKind.RECEIVED`. This space carries the fiscal
   TOTALS a calculation can fold in, but no bytes.

The PIE space is consulted first, so an id minted by ``evidence add`` is accepted
by ``aeat app ledger attach`` in the same shell session. Ids minted by
``aeat app ledger invoice add`` (slim operator invoice records) are deliberately in
neither space and resolve as :attr:`EvidenceReferenceOutcome.UNRESOLVED`.

Every consumer of the field MUST route its decision through :func:`classify_evidence_reference`
(when it holds both lookups) or :func:`find_bytes_bearing_evidence_record` (when it
only needs the bytes-bearing half), so that no call site re-derives which space an
id belongs to. Re-deriving it is how two readers came to disagree: one resolved only
the invoice catalogue and reported a valid evidence record as "absent", the other
resolved only the evidence store and raised "not found" for a valid invoice id.

This module holds no adapter dependency on purpose: it takes the loaded records and
catalogue as arguments so it stays a pure decision surface, testable without storage.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.invoices.models import Invoice, InvoiceCatalogue
from ...domain.iva.classification import InvoiceKind
from .evidence import PurchaseInvoiceEvidence
from .evidence_errors import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceNotFoundError
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

__all__ = [
    "ACCEPTABLE_EVIDENCE_REFERENCE_OUTCOMES",
    "EvidenceReference",
    "EvidenceReferenceOutcome",
    "classify_evidence_reference",
    "find_bytes_bearing_evidence_record",
    "refuse_reference_without_document_bytes",
    "refuse_unresolved_evidence_reference",
]


class EvidenceReferenceOutcome(StrEnum):
    """Closed taxonomy of what an evidence reference resolved to.

    Attributes:
        PURCHASE_INVOICE_EVIDENCE: A registered evidence record; carries document bytes.
        CATALOGUE_INVOICE: A bucket-matched received catalogue invoice; carries fiscal
            totals but no bytes.
        UNRESOLVED: The id names neither space.
        INVOICE_OUTSIDE_BUCKET: A catalogue invoice exists but belongs to another bucket.
        INVOICE_WRONG_KIND: A catalogue invoice exists but is not ``RECEIVED``, so it
            cannot stand as purchase evidence.
    """

    PURCHASE_INVOICE_EVIDENCE = "purchase_invoice_evidence"
    CATALOGUE_INVOICE = "catalogue_invoice"
    UNRESOLVED = "unresolved"
    INVOICE_OUTSIDE_BUCKET = "invoice_outside_bucket"
    INVOICE_WRONG_KIND = "invoice_wrong_kind"


#: Outcomes that make the reference usable as purchase evidence for the bucket.
ACCEPTABLE_EVIDENCE_REFERENCE_OUTCOMES = frozenset(
    {
        EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE,
        EvidenceReferenceOutcome.CATALOGUE_INVOICE,
    },
)


class EvidenceReference(BaseModel):
    """One resolved evidence reference: the outcome plus whichever record backs it."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: str
    outcome: EvidenceReferenceOutcome
    record: PurchaseInvoiceEvidence | None = None
    invoice: Invoice | None = None

    @model_validator(mode="after")
    def _payload_matches_outcome(self) -> Self:
        """Reject a resolution whose carried payload contradicts its outcome."""
        if self.outcome is EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE:
            if self.record is None or self.invoice is not None:
                raise ValueError("a purchase-invoice-evidence outcome carries exactly its evidence record")
        elif self.outcome is EvidenceReferenceOutcome.UNRESOLVED:
            if self.record is not None or self.invoice is not None:
                raise ValueError("an unresolved outcome carries no record")
        elif self.record is not None or self.invoice is None:
            # The three invoice-space outcomes each carry exactly the invoice found.
            raise ValueError(f"outcome {self.outcome.value!r} carries exactly its catalogue invoice")
        return self

    @property
    def is_acceptable(self) -> bool:
        """Whether the reference is usable as purchase evidence for its bucket."""
        return self.outcome in ACCEPTABLE_EVIDENCE_REFERENCE_OUTCOMES

    @property
    def carries_document_bytes(self) -> bool:
        """Whether the reference can supply document bytes to an on-host reader.

        Only the evidence-record space stores bytes; a catalogue invoice is a fiscal
        record with no document behind it.
        """
        return self.outcome is EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE


def _matching_evidence_record(
    evidence_id: str,
    records: Iterable[PurchaseInvoiceEvidence],
) -> PurchaseInvoiceEvidence | None:
    return next((record for record in records if record.evidence_id == evidence_id), None)


def classify_evidence_reference(
    evidence_id: str,
    *,
    bucket_id: str,
    evidence_records: Iterable[PurchaseInvoiceEvidence],
    invoices: InvoiceCatalogue,
) -> EvidenceReference:
    """Resolve one ``purchase_invoice_evidence_id`` against both id spaces.

    Consults the evidence-record space first, then the invoice catalogue, and
    applies the bucket-ownership and ``RECEIVED``-kind policy to an invoice hit.
    Never raises for an unusable reference: the caller decides how to report the
    outcome, so a write gate can refuse while a read path can degrade.

    Args:
        evidence_id: The reference stored on the transaction.
        bucket_id: Bucket the reference must belong to.
        evidence_records: The bucket's registered evidence records.
        invoices: The bucket's :class:`InvoiceCatalogue`, consulted only after
            the evidence-record space misses.

    Returns:
        :class:`EvidenceReference`: The outcome plus whichever record backs it.
    """
    record = _matching_evidence_record(evidence_id, evidence_records)
    if record is not None:
        return EvidenceReference(
            evidence_id=evidence_id,
            outcome=EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE,
            record=record,
        )
    invoice = invoices.get(evidence_id)
    if invoice is None:
        return EvidenceReference(evidence_id=evidence_id, outcome=EvidenceReferenceOutcome.UNRESOLVED)
    if invoice.bucket_id != bucket_id:
        return EvidenceReference(
            evidence_id=evidence_id,
            outcome=EvidenceReferenceOutcome.INVOICE_OUTSIDE_BUCKET,
            invoice=invoice,
        )
    if invoice.kind is not InvoiceKind.RECEIVED:
        return EvidenceReference(
            evidence_id=evidence_id,
            outcome=EvidenceReferenceOutcome.INVOICE_WRONG_KIND,
            invoice=invoice,
        )
    return EvidenceReference(
        evidence_id=evidence_id,
        outcome=EvidenceReferenceOutcome.CATALOGUE_INVOICE,
        invoice=invoice,
    )


def find_bytes_bearing_evidence_record(
    evidence_id: str,
    *,
    evidence_records: Iterable[PurchaseInvoiceEvidence],
) -> PurchaseInvoiceEvidence | None:
    """Return the evidence record backing ``evidence_id``, or ``None``.

    The bytes-bearing half of :func:`classify_evidence_reference`, for a reader that
    needs document bytes and holds no invoice catalogue. ``None`` does NOT mean the
    reference is invalid -- it may be a legitimate catalogue-invoice id, which simply
    has no document behind it (see this module's docstring). A reader that must refuse
    should use :func:`refuse_reference_without_document_bytes` so the operator is told
    which of the two spaces the id landed in.

    Args:
        evidence_id: The reference stored on the transaction.
        evidence_records: The bucket's registered evidence records.

    Returns:
        The matching :class:`~cadrumo.application.ledger.evidence.PurchaseInvoiceEvidence`, or
        ``None`` when the id is not in the evidence-record space.
    """
    return _matching_evidence_record(evidence_id, evidence_records)


def refuse_reference_without_document_bytes(evidence_id: str) -> PurchaseInvoiceEvidenceInputError:
    """Build the refusal for a reference that resolves outside the bytes-bearing space.

    Worded once, here, so every on-host reader names the same remedy. Use this when
    the reference is (or may be) a legitimate catalogue-invoice id: it is a VALID
    evidence reference that simply holds fiscal totals rather than a document, so the
    operator must not be told their id does not exist. A caller that has established
    the id names nothing at all should raise
    :func:`refuse_unresolved_evidence_reference` instead, which is more specific.

    Args:
        evidence_id: The reference that could not supply bytes.

    Returns:
        The typed error for the caller to raise.
    """
    return PurchaseInvoiceEvidenceInputError(
        f"evidence reference {evidence_id!r} names no registered evidence record, so it carries no "
        "document bytes to read; an imported catalogue-invoice id is a valid evidence reference but "
        "holds fiscal totals rather than a document",
        context={"evidence_id": evidence_id},
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_DOCUMENT_BYTES_AVAILABLE,
            facts={"document_bytes_available": False},
        ),
    )


def refuse_unresolved_evidence_reference(evidence_id: str) -> PurchaseInvoiceEvidenceNotFoundError:
    """Build the refusal for a reference that names nothing in either id space.

    Only for :attr:`EvidenceReferenceOutcome.UNRESOLVED`, which a caller can establish
    only by consulting BOTH spaces. It is the more pointed of the two refusals -- a
    typo'd id gets "no such record" rather than an explanation of the invoice space --
    so a caller that consulted only the evidence-record half must not raise it.

    Args:
        evidence_id: The reference that resolved to neither space.

    Returns:
        The typed error for the caller to raise.
    """
    return PurchaseInvoiceEvidenceNotFoundError(
        f"no purchase invoice evidence record or received catalogue invoice with id {evidence_id!r}",
        context={"evidence_id": evidence_id},
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
            facts={"evidence_reference_resolves": False},
        ),
    )
