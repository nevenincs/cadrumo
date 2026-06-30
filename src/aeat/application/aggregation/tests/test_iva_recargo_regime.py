"""Engine-level recargo-equivalencia regime: non-declarable IVA categories.

A recargo-equivalencia purchase carries IVA + RE that the retailer cannot deduct
(it is acquisition cost, settled via the supplier). The IVA aggregation engine
must therefore never emit a declarable observation for it — even when the row
carries IVA facts — and likewise for the unknown / erroneous_invoice sentinels.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from .. import IvaLedgerAggregationIssueReason, aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_Q2_2026 = _period(2026, "2T")


def _tx(provider_id: str, *, iva_category: IvaCategory) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 5),
        value_date=date(2026, 4, 5),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Mayorista",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"k": "v"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            # Deliberately carries IVA facts: the engine must STILL refuse to emit
            # a declarable observation for these categories.
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "iva_category": iva_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


@pytest.mark.parametrize(
    "category",
    [IvaCategory.RECARGO_EQUIVALENCIA, IvaCategory.UNKNOWN, IvaCategory.ERRONEOUS_INVOICE],
)
def test_non_declarable_category_is_gated_not_emitted(category: IvaCategory) -> None:
    tx = _tx("re-1", iva_category=category)
    result = aggregate_iva_ledger_observations(TransactionCatalogue.from_transactions((tx,)), period=_Q2_2026)
    # No declarable observation, and the gate reason names the unsupported category.
    assert result.observations == ()
    assert [i.reason for i in result.issues] == [IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY]


def test_normal_domestic_category_still_emits() -> None:
    tx = _tx("ok-1", iva_category=IvaCategory.DOMESTIC_GENERAL_21)
    result = aggregate_iva_ledger_observations(TransactionCatalogue.from_transactions((tx,)), period=_Q2_2026)
    assert len(result.observations) == 1
    assert result.observations[0].category is IvaCategory.DOMESTIC_GENERAL_21
