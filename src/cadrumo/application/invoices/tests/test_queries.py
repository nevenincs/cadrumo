"""Invoice query projection service tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.invoices.enums import resolve_iva_rate_token

from ....core.invoice_link import LinkInconsistencyDirection
from ....domain.invoices.enums import PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.invoices.service import verify_link_consistency
from ....domain.iva.classification import InvoiceKind
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ..catalogue_reads import verify_invoice_repository_links
from ..catalogue_reads_ports import InvoiceCatalogueReadPorts
from ..transaction_linking import link_invoice_transaction_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_consistency_query_reports_one_sided_transaction_link() -> None:
    invoice = _invoice()
    transaction = _transaction()
    drifted_transactions = link_invoice(
        TransactionCatalogue.from_transactions([transaction]),
        transaction.transaction_id,
        invoice.invoice_id,
    )

    inconsistencies = verify_link_consistency(InvoiceCatalogue.from_invoices([invoice]), drifted_transactions)

    assert len(inconsistencies) == 1
    assert inconsistencies[0].invoice_id == invoice.invoice_id
    assert inconsistencies[0].transaction_id == transaction.transaction_id
    assert inconsistencies[0].direction is LinkInconsistencyDirection.TRANSACTION_ONLY


def test_repository_consistency_query_reads_both_required_catalogue_ports() -> None:
    invoice = _invoice()
    transaction = _transaction()
    linked = link_invoice_transaction_catalogues(
        InvoiceCatalogue.from_invoices([invoice]),
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
        """Mirror the public date-partition contract over the in-memory catalogue."""
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue.values():
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    ),
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )


def _invoice(
    *,
    invoice_number: str = "INV-001",
    issued_at: date = date(2026, 4, 1),
    kind: InvoiceKind = InvoiceKind.ISSUED,
) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": invoice_number,
            "issued_at": issued_at,
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
                        "iva_rate": resolve_iva_rate_token("rate_21", date.today()),
                        "iva_amount": Decimal("21.00"),
                    },
                ),
            ),
        },
    )


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="bank-row-1",
        booked_date=date(2026, 4, 2),
        value_date=date(2026, 4, 2),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Cliente SL",
        description="Cliente SL",
        provenance=RawProvenance(
            source_path=Path("statement.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 2, tzinfo=UTC),
            provider_name="csv",
        ),
        raw_fields={"amount": "121.00"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.INCOMING, "group_label": None, "source_jurisdiction": "ES"},
    )
