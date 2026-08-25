"""Real ledger source helpers for Modelo 130 CLI tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.bucket_pointer import resolve_active_bucket_id
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from ....tests.profile_capsule import open_test_profile_session


def seed_m130_income_transaction(
    *,
    amount: Decimal,
    filing_year: int,
    source_key: str,
    value_date: date | None = None,
) -> None:
    """Seed one real actividad-economica income row for source-bound M130 casilla 01.

    ``value_date`` defaults to 15 February of ``filing_year`` (a Q1 row). Pass an
    explicit date to place the income in a later quarter — useful for exercising
    the cumulative (year-to-date) M130 source window across quarters.
    """

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    if value_date is None:
        value_date = date(filing_year, 2, 15)
    income = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"m130-income-{source_key}-{filing_year}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description=f"M130 oracle income {source_key}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "m130_oracle_income", "source_key": source_key},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": None,
            "taxable_base": amount,
            "iva_rate": None,
            "iva_amount": None,
            "irpf_category": "actividad_economica",
            "purchase_invoice_evidence_id": None,
            "classified_at": datetime(filing_year, 2, 16, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    with open_test_profile_session(bucket_id):
        existing = TransactionCatalogueRepository(bucket_id=bucket_id).load()
        transactions = (*tuple(existing.transactions.values()), income)
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions(transactions),
        )


def seed_m130_expense_transaction(
    *,
    amount: Decimal,
    filing_year: int,
    source_key: str,
    value_date: date | None = None,
) -> None:
    """Seed one real deductible actividad-economica expense (gasto) row for casilla 02.

    The OUTGOING sibling of :func:`seed_m130_income_transaction`. Casilla 02 is a
    source-bound casilla aggregated from the ledger via
    ``ledger_renta_gastos_pago_fraccionado_aggregation``; a deductible gasto is an ACTIVE, EUR,
    OUTGOING, BUSINESS-classified row carrying an IVA-exclusive ``taxable_base``.
    ``amount`` is the (non-negative) magnitude; flow is carried by the direction.
    """

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    if value_date is None:
        value_date = date(filing_year, 2, 15)
    expense = Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=f"m130-expense-{source_key}-{filing_year}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Proveedor SA",
                description=f"M130 oracle expense {source_key}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(filing_year, 2, 16, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "m130_oracle_expense", "source_key": source_key},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": None,
            "taxable_base": amount,
            "iva_rate": None,
            "iva_amount": None,
            "irpf_category": "actividad_economica",
            "purchase_invoice_evidence_id": None,
            "classified_at": datetime(filing_year, 2, 16, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    with open_test_profile_session(bucket_id):
        existing = TransactionCatalogueRepository(bucket_id=bucket_id).load()
        transactions = (*tuple(existing.transactions.values()), expense)
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions(transactions),
        )


__all__ = ["seed_m130_expense_transaction", "seed_m130_income_transaction"]
