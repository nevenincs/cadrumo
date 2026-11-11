"""Impatriado income ledger rows shared by the aggregation and profile suites."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_YEAR = filing_year_envelope().horizon


def impatriado_transaction(
    provider_id: str,
    *,
    amount: Decimal,
    source_jurisdiction: str | None,
    irpf_category: str | None = "trabajo",
    direction: TransactionDirection = TransactionDirection.INCOMING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    taxable_base: Decimal | None = None,
    iva_amount: Decimal | None = None,
    value_date: date = date(_YEAR, 3, 1),
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Empleador SA",
                description=f"impatriado income {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(1980, 4, 6, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": provider_id},
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": source_jurisdiction,
            "business_classification": business_classification,
            "business_pct": business_pct,
            "taxable_base": taxable_base,
            "iva_amount": iva_amount,
            "irpf_category": irpf_category,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(1980, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
