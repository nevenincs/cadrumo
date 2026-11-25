"""Shared row and statistics helpers for the 30,000-transaction ledger benchmarks."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from cadrumo.domain.transactions.enums import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from cadrumo.domain.transactions.models import Transaction
from cadrumo.domain.transactions.raw_transaction import RawTransaction


def dates_across_year(year: int, count: int) -> Iterator[date]:
    """Yield ``count`` booked dates spread evenly across ``year``."""
    start = date(year, 1, 1)
    span_days = (date(year, 12, 31) - start).days
    for i in range(count):
        yield start + timedelta(days=(i * span_days) // max(count - 1, 1))


def p95(samples: Sequence[float]) -> float:
    """Return the 95th percentile of ``samples`` (nearest-rank, no interpolation)."""
    ordered = sorted(samples)
    rank = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return ordered[rank]


def classified_business_transaction(
    raw: RawTransaction,
    *,
    direction: TransactionDirection,
    taxable_base: Decimal = Decimal("100.00"),
    iva_amount: Decimal = Decimal("21.00"),
) -> Transaction:
    """Wrap ``raw`` as a manually classified, deductible business expense with 21 % IVA."""
    booked = raw.booked_date
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": "material_oficina",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(booked.year, booked.month, booked.day, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
