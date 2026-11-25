"""Transaction rows and catalogues shared by the memoized catalogue suites."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


def memoized_raw_transaction(provider_id: str, booked_on: date, amount: Decimal, description: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_on,
        value_date=booked_on,
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=7,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def memoized_transaction(
    provider_id: str,
    booked_on: date,
    *,
    amount: Decimal = Decimal("100.00"),
    description: str = "Software subscription",
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": memoized_raw_transaction(provider_id, booked_on, amount, description),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
        },
    )


def memoized_catalogue(*transactions: Transaction) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(transactions)


def memoized_transaction_ids(catalogue: TransactionCatalogue) -> set[str]:
    return set(catalogue.transactions)
