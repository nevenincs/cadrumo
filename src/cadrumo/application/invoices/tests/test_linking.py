"""Invoice linking application service tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.errors import InvoiceLinkError
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import TransactionCatalogue
from ..transaction_linking import link_invoice_transaction_catalogues
from .bank_row_support import incoming_bank_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_link_invoice_transaction_catalogues_roundtrips_bidirectional_link() -> None:
    invoice = _invoice()
    transaction = incoming_bank_transaction()

    result = link_invoice_transaction_catalogues(
        build_invoice_catalogue([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
        invoice_id=invoice.invoice_id,
        transaction_id=transaction.transaction_id.upper(),
    )

    linked_invoice = result.invoices.get(invoice.invoice_id)
    linked_transaction = result.transactions.get(transaction.transaction_id)
    assert result.invoice == linked_invoice
    assert result.transaction_id == transaction.transaction_id
    assert linked_invoice is not None
    assert linked_invoice.linked_transaction_ids == (transaction.transaction_id,)
    assert linked_transaction is not None
    assert linked_transaction.invoice_id == invoice.invoice_id


def test_link_invoice_transaction_catalogues_reports_missing_transaction_context() -> None:
    invoice = _invoice()

    with pytest.raises(InvoiceLinkError) as exc_info:
        link_invoice_transaction_catalogues(
            build_invoice_catalogue([invoice]),
            TransactionCatalogue(),
            invoice_id=invoice.invoice_id,
            transaction_id="missing-transaction",
        )

    assert exc_info.value.translated_message == "application.invoices.linking.errors.transaction_not_found"
    assert exc_info.value.context == {"transaction_id": "missing-transaction"}


def _invoice() -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "INV-001",
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
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
                        "description": "Servicios",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("100.00"),
                        "subtotal": Decimal("100.00"),
                        "iva_rate": IvaRate.from_registry("RATE_21"),
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )
