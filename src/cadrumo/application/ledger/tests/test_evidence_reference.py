"""Real-behaviour tests for the one evidence-reference id-space definition.

``Transaction.purchase_invoice_evidence_id`` addresses two bucket-scoped id spaces,
and these tests pin the contract every consumer of that field now shares: which
space wins when both could match, which outcomes are acceptable as purchase
evidence, and — the property two readers previously disagreed about — which outcome
can supply document bytes.

The classifier is a pure decision surface, so these tests need no storage: they
build real records and a real catalogue and assert the resolved outcome.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva import InvoiceKind
from ..evidence import MediaKind, PurchaseInvoiceEvidence
from ..evidence_reference import (
    EvidenceReference,
    EvidenceReferenceOutcome,
    classify_evidence_reference,
    find_bytes_bearing_evidence_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "30303030-3030-4030-8030-303030303030"
_OTHER_BUCKET_ID = "31313131-3131-4131-8131-313131313131"
_NOW = datetime(2026, 2, 5, tzinfo=UTC)


def _evidence_record(*, evidence_id: str = "ev-001") -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence.model_validate(
        {
            "evidence_id": evidence_id,
            "bucket_id": _BUCKET_ID,
            "source_path": "factura.pdf",
            "source_sha256": "a" * 64,
            "attachment_id": "a" * 64,
            "media_kind": MediaKind.PDF,
            "created_at": _NOW,
            "updated_at": _NOW,
        },
    )


def _invoice(
    *,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    bucket_id: str | None = _BUCKET_ID,
    invoice_number: str = "INV-001",
) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": kind,
            "bucket_id": bucket_id,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 2, 5),
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": Decimal("100.00"),
            "iva_total": Decimal("21.00"),
            "grand_total": Decimal("121.00"),
            "currency": "EUR",
            "payment_status": PaymentStatus.PAID,
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Material",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100.00"),
                        "subtotal": Decimal("100.00"),
                        "iva_rate": IvaRate.RATE_21,
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )


def _catalogue(*invoices: Invoice) -> InvoiceCatalogue:
    return InvoiceCatalogue.from_invoices(invoices)


def _classify(evidence_id: str, *, records: tuple[PurchaseInvoiceEvidence, ...], invoices: InvoiceCatalogue):
    return classify_evidence_reference(
        evidence_id,
        bucket_id=_BUCKET_ID,
        evidence_records=records,
        invoices=invoices,
    )


def test_registered_evidence_record_resolves_to_the_bytes_bearing_space() -> None:
    record = _evidence_record()

    reference = _classify(record.evidence_id, records=(record,), invoices=_catalogue())

    assert reference.outcome is EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE
    assert reference.record == record
    assert reference.is_acceptable
    assert reference.carries_document_bytes


def test_received_catalogue_invoice_is_acceptable_but_carries_no_bytes() -> None:
    """The distinction the two on-host readers previously got wrong.

    A catalogue-invoice id is a VALID evidence reference — the write gate accepts it —
    yet it holds fiscal totals rather than a document, so a byte reader must not treat
    it as a missing record.
    """
    invoice = _invoice()

    reference = _classify(invoice.invoice_id, records=(), invoices=_catalogue(invoice))

    assert reference.outcome is EvidenceReferenceOutcome.CATALOGUE_INVOICE
    assert reference.invoice == invoice
    assert reference.is_acceptable
    assert not reference.carries_document_bytes


def test_evidence_record_wins_when_an_id_could_match_both_spaces() -> None:
    """The declared consultation order: the evidence store is consulted first.

    This is what makes an id minted by ``evidence add`` usable by ``attach`` in the
    same shell session, so it is pinned rather than left to lookup order.
    """
    invoice = _invoice()
    collided = _evidence_record(evidence_id=invoice.invoice_id)

    reference = _classify(invoice.invoice_id, records=(collided,), invoices=_catalogue(invoice))

    assert reference.outcome is EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE
    assert reference.record == collided
    assert reference.invoice is None


def test_unknown_id_resolves_unresolved_and_is_not_acceptable() -> None:
    reference = _classify("ev-nothing", records=(_evidence_record(),), invoices=_catalogue(_invoice()))

    assert reference.outcome is EvidenceReferenceOutcome.UNRESOLVED
    assert not reference.is_acceptable
    assert not reference.carries_document_bytes
    assert reference.record is None
    assert reference.invoice is None


def test_invoice_from_another_bucket_is_refused_as_a_reference() -> None:
    foreign = _invoice(bucket_id=_OTHER_BUCKET_ID)

    reference = _classify(foreign.invoice_id, records=(), invoices=_catalogue(foreign))

    assert reference.outcome is EvidenceReferenceOutcome.INVOICE_OUTSIDE_BUCKET
    assert not reference.is_acceptable


def test_issued_invoice_is_refused_as_purchase_evidence() -> None:
    issued = _invoice(kind=InvoiceKind.ISSUED)

    reference = _classify(issued.invoice_id, records=(), invoices=_catalogue(issued))

    assert reference.outcome is EvidenceReferenceOutcome.INVOICE_WRONG_KIND
    assert not reference.is_acceptable


def test_find_bytes_bearing_record_declines_a_catalogue_invoice_id() -> None:
    """A byte reader asking the evidence space about an invoice id gets ``None``.

    ``None`` means "not in this space", never "invalid reference": the reader must
    degrade or refuse with that distinction intact.
    """
    invoice = _invoice()
    record = _evidence_record()

    assert find_bytes_bearing_evidence_record(invoice.invoice_id, evidence_records=(record,)) is None
    assert find_bytes_bearing_evidence_record(record.evidence_id, evidence_records=(record,)) == record


def test_resolution_carrying_a_payload_that_contradicts_its_outcome_is_refused() -> None:
    """Anti-tautology guard on the result model itself.

    A resolution claiming the bytes-bearing outcome while carrying an invoice (or no
    record at all) would let a reader believe it can extract bytes from a fiscal
    record, so the model refuses the combination outright.
    """
    with pytest.raises(ValidationError):
        EvidenceReference(
            evidence_id="ev-001",
            outcome=EvidenceReferenceOutcome.PURCHASE_INVOICE_EVIDENCE,
            invoice=_invoice(),
        )
    with pytest.raises(ValidationError):
        EvidenceReference(evidence_id="ev-001", outcome=EvidenceReferenceOutcome.CATALOGUE_INVOICE)
    with pytest.raises(ValidationError):
        EvidenceReference(
            evidence_id="ev-001",
            outcome=EvidenceReferenceOutcome.UNRESOLVED,
            record=_evidence_record(),
        )
