"""Application contract for atomic catalogue-invoice audit persistence."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....domain.buckets.event import BucketEventType
from ....domain.iva.classification import InvoiceKind
from ...exchange_rate_provider import exchange_rate_provider
from ..catalogue_creation import build_catalogue_invoice, create_catalogue_invoice
from ._catalogue_creation_fakes import in_memory_catalogue_creation_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "74747474-7474-4747-8474-747474747474"
_OCCURRED_AT = datetime(2026, 9, 22, 10, 30, tzinfo=UTC)


def test_create_commits_the_catalogue_invoice_and_its_audit_entry_together() -> None:
    """The application service uses its one atomic persistence port."""
    ports = in_memory_catalogue_creation_ports()
    invoice = _invoice()

    result = create_catalogue_invoice(
        invoice=invoice,
        ports=ports,
        occurred_at=_OCCURRED_AT,
        actor="operator",
    )

    assert result.catalogue.get(invoice.invoice_id) == invoice
    assert len(result.bucket_event_ids) == 1
    event = ports.event_repository.load().events[result.bucket_event_ids[0]]
    assert event.event_type is BucketEventType.PAYABLE_INVOICE_CREATED
    assert event.object_id == invoice.invoice_id
    assert event.actor == "operator"


def _invoice():
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.RECEIVED,
        counterparty_name="Papeleria Sol SL",
        counterparty_tax_id="A58818501",
        counterparty_country="ES",
        invoice_number="ATOMIC-2026-001",
        issued_at=date(2026, 9, 22),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        currency="EUR",
        rate_provider=exchange_rate_provider(),
    )
