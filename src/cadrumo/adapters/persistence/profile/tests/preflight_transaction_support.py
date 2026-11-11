"""Classified ledger transaction builder shared by the readiness preflight tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat


def preflight_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    amount: Decimal = Decimal("121.00"),
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    category_id: str | None = SpendingCategory.from_registry("material_oficina").value,
    usage_ratio_id: str | None = None,
) -> Transaction:
    """Return one classified April 2026 ledger row for the readiness preflight tests."""
    booked_date = date(2026, 4, 5)
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": BindingSourceKind.LEDGER_TRANSACTION.value},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": direction,
            "group_label": None,
            "business_classification": business_classification,
            "source_jurisdiction": "ES",
            "business_pct": business_pct,
            "category_id": category_id,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "iva_category": None,
            "counterparty_country": None,
            "counterparty_identification_state": None,
            "irpf_category": None,
            "usage_ratio_id": usage_ratio_id,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
