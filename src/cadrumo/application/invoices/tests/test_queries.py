"""Invoice query projection service tests."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.invoice_link import LinkInconsistencyDirection
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import PaymentStatus
from ....domain.invoices.service import verify_link_consistency
from ....domain.invoices.tests.catalogue_support import consulting_invoice
from ....domain.transactions.date_partition import (
    LedgerDatePartition,
)
from ....domain.transactions.models import TransactionCatalogue
from ....domain.transactions.service import link_invoice
from ...tests.ledger_partition_support import partition_by_filing_date
from ..catalogue_reads import verify_invoice_repository_links
from ..catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..transaction_linking import link_invoice_transaction_catalogues
from .bank_row_support import incoming_bank_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_consistency_query_reports_one_sided_transaction_link() -> None:
    invoice = consulting_invoice(payment_status=PaymentStatus.PAID)
    transaction = incoming_bank_transaction()
    drifted_transactions = link_invoice(
        TransactionCatalogue.from_transactions([transaction]),
        transaction.transaction_id,
        invoice.invoice_id,
    )

    inconsistencies = verify_link_consistency(build_invoice_catalogue([invoice]), drifted_transactions)

    assert len(inconsistencies) == 1
    assert inconsistencies[0].invoice_id == invoice.invoice_id
    assert inconsistencies[0].transaction_id == transaction.transaction_id
    assert inconsistencies[0].direction is LinkInconsistencyDirection.TRANSACTION_ONLY


def test_repository_consistency_query_reads_both_required_catalogue_ports() -> None:
    invoice = consulting_invoice(payment_status=PaymentStatus.PAID)
    transaction = incoming_bank_transaction()
    linked = link_invoice_transaction_catalogues(
        build_invoice_catalogue([invoice]),
        TransactionCatalogue.from_transactions([transaction]),
        invoice_id=invoice.invoice_id,
        transaction_id=transaction.transaction_id,
    )
    ports = InvoiceCatalogueReadPorts(
        invoice_reader=_InvoiceCatalogueReader(linked.invoices),
        transaction_reader=_TransactionCatalogueReader(linked.transactions),
    )

    assert verify_invoice_repository_links(ports=ports) == ()


class _InvoiceCatalogueReader:
    """Inward test fake for the application invoice projection capability."""

    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class _TransactionCatalogueReader:
    """Inward test fake for the application transaction projection capability."""

    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return partition_by_filing_date(self._catalogue.values(), start, end)
