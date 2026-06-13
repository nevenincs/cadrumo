"""Real ledger source helpers for Modelo 130 CLI tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....application.user_profile._orchestration import profile_storage_session
from ....core import resolve_active_bucket_id
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)


def seed_m130_income_transaction(
    *,
    amount: Decimal,
    filing_year: int,
    source_key: str,
) -> None:
    """Seed one real actividad-economica income row for source-bound M130 casilla 01."""

    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None, "test profile must install an active bucket pointer"
    value_date = date(filing_year, 2, 15)
    income = Transaction.model_validate(
        {
            "raw": RawTransaction(
                transaction_id=f"m130-income-{source_key}-{filing_year}",
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
            "business_classification": BusinessClassification.BUSINESS,
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
    with profile_storage_session(bucket_id):
        existing = TransactionCatalogueRepository(bucket_id=bucket_id).load()
        transactions = (*tuple(existing.transactions.values()), income)
        TransactionCatalogueRepository(bucket_id=bucket_id).save(
            TransactionCatalogue.from_transactions(transactions),
        )


__all__ = ["seed_m130_income_transaction"]
