"""Invoice linking application service tests."""

from __future__ import annotations

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....domain.invoices.enums import PaymentStatus
from ....domain.invoices.errors import InvoiceLinkError
from ....domain.invoices.tests.catalogue_support import consulting_invoice
from ....domain.transactions.models import TransactionCatalogue
from ..transaction_linking import link_invoice_transaction_catalogues
from .bank_row_support import incoming_bank_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_link_invoice_transaction_catalogues_roundtrips_bidirectional_link() -> None:
    invoice = consulting_invoice(payment_status=PaymentStatus.PAID)
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
    invoice = consulting_invoice(payment_status=PaymentStatus.PAID)

    with pytest.raises(InvoiceLinkError) as exc_info:
        link_invoice_transaction_catalogues(
            build_invoice_catalogue([invoice]),
            TransactionCatalogue(),
            invoice_id=invoice.invoice_id,
            transaction_id="missing-transaction",
        )

    assert exc_info.value.translated_message == "application.invoices.linking.errors.transaction_not_found"
    assert exc_info.value.context == {"transaction_id": "missing-transaction"}
