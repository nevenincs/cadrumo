"""Evidence record shared by the evidence mutation suites."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from ....application.ledger.evidence import (
    MediaKind,
    PurchaseInvoiceEvidence,
)

EVIDENCE_MUTATION_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
EVIDENCE_MUTATION_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def evidence_mutation_record() -> PurchaseInvoiceEvidence:
    return PurchaseInvoiceEvidence(
        evidence_id="evidence-target",
        bucket_id=str(EVIDENCE_MUTATION_PROFILE),
        source_path="invoice.pdf",
        source_sha256="a" * 64,
        attachment_id="a" * 64,
        media_kind=MediaKind.PDF,
        supplier="Before SL",
        invoice_number="INV-2026-05",
        invoice_date="2026-05-08",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
        notes="invoice note",
        created_at=EVIDENCE_MUTATION_AT,
        updated_at=EVIDENCE_MUTATION_AT,
    )
