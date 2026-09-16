"""Reconciliation matches the cash an invoice settles for, not its printed total.

A retención is withheld at source: an issued invoice of 1815.00 carrying a
225.00 IRPF retención is paid with a 1590.00 transfer, and nothing of 1815.00
ever reaches the bank.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...calculations.registry.authority import bundled_indexed_authority
from ...iva.classification import InvoiceKind
from ...transactions.enums import BusinessClassification, TransactionDirection
from ...transactions.models import Transaction, TransactionCatalogue
from ...transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..enums import IvaRate, PaymentStatus
from ..models import Invoice, InvoiceCatalogue, InvoiceLine
from ..service import suggest_reconciliations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ISSUED_ON = date(2026, 2, 3)


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _issued_invoice(*, retention_amount: Decimal | None) -> Invoice:
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-2026-001",
            "issued_at": _ISSUED_ON,
            "counterparty_name": "Beta Logistica Mediterranea SL",
            "counterparty_tax_id": "B92000025",
            "counterparty_country": "ES",
            "base_total": Decimal("1500.00"),
            "iva_total": Decimal("315.00"),
            "grand_total": Decimal("1815.00"),
            "currency": "EUR",
            "lines": (
                InvoiceLine.model_validate(
                    {
                        "description": "Servicios de consultoria",
                        "quantity": Decimal("1"),
                        "unit_price": Decimal("1500.00"),
                        "subtotal": Decimal("1500.00"),
                        "iva_rate": IvaRate.from_registry("RATE_21"),
                        "iva_amount": Decimal("315.00"),
                    },
                ),
            ),
            "payment_status": PaymentStatus.PAID,
            "retention_rate": None if retention_amount is None else Decimal("0.15"),
            "retention_amount": retention_amount,
        },
    )


def _incoming_transfer(amount: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"bank-{amount}",
                booked_date=date(2026, 2, 10),
                value_date=date(2026, 2, 11),
                amount=Decimal(amount),
                currency="EUR",
                counterparty="Beta Logistica Mediterranea SL",
                description="TRANSFERENCIA RECIBIDA BETA LOGISTICA",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=7,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2026, 2, 12, 9, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": "TRANSFERENCIA RECIBIDA BETA LOGISTICA"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        },
    )


def _suggested_amounts(invoice: Invoice, *amounts: str) -> set[Decimal]:
    transactions = {_incoming_transfer(amount).transaction_id: amount for amount in amounts}
    suggestions = suggest_reconciliations(
        InvoiceCatalogue.model_validate({"invoices": {invoice.invoice_id: invoice}}),
        TransactionCatalogue.from_transactions([_incoming_transfer(amount) for amount in amounts]),
    )
    return {Decimal(transactions[suggestion.transaction_id]) for suggestion in suggestions}


def test_a_retencion_invoice_matches_the_net_transfer_only() -> None:
    invoice = _issued_invoice(retention_amount=Decimal("225.00"))

    assert _suggested_amounts(invoice, "1590.00", "1815.00") == {Decimal("1590.00")}


def test_an_invoice_without_retencion_still_matches_its_total() -> None:
    invoice = _issued_invoice(retention_amount=None)

    assert _suggested_amounts(invoice, "1590.00", "1815.00") == {Decimal("1815.00")}
