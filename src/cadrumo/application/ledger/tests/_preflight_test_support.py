"""Shared support for ledger preflight tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.categories.spending_category import SpendingCategory
from ....domain.iva.schema import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_Q2_2026 = _period(2026, "2T")
_AD_HOC_2026 = _period(2026, "AD-HOC")


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency=currency,
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


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    amount: Decimal = Decimal("121.00"),
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    category_id: str | None = SpendingCategory.MATERIAL_OFICINA.value,
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
    iva_category: IvaCategory | None = None,
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
    irpf_category: str | None = None,
    usage_ratio_id: str | None = None,
    booked_date: date = date(2026, 4, 5),
    currency: str = "EUR",
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, booked_date=booked_date, amount=amount, currency=currency),
            "direction": direction,
            "group_label": None,
            "business_classification": business_classification,
            "source_jurisdiction": "ES",
            "business_pct": business_pct,
            "category_id": category_id,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "counterparty_country": counterparty_country,
            "counterparty_identification_state": counterparty_identification_state,
            "irpf_category": irpf_category,
            "usage_ratio_id": usage_ratio_id,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
