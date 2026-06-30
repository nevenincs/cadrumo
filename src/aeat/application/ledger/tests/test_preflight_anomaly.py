"""Preflight anomaly channel + converted-foreign-row currency fix."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    TransactionLifecycleState,
)
from .._preflight import LedgerPreflightIssueReason as R
from .._preflight import _issues_for_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)


def _tx(
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    currency: str = "EUR",
    iva_category: str | None = "domestic_general_21",
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_amount: Decimal | None = Decimal("21.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    value_in_eur: Decimal | None = None,
    fx_rate: Decimal | None = None,
) -> Transaction:
    raw = RawTransaction(
        transaction_id="row-x",
        booked_date=date(2026, 1, 15),
        value_date=date(2026, 1, 15),
        amount=Decimal("121.00"),
        currency=currency,
        counterparty="Proveedor",
        description="row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"k": "v"},
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": direction,
        "business_classification": BusinessClassification.BUSINESS,
        "source_jurisdiction": "ES",
        "group_label": None,
        "category_id": "material_oficina",
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "iva_category": iva_category,
        "fx_rate": fx_rate,
        "value_in_eur": value_in_eur,
        "lifecycle_state": TransactionLifecycleState.ACTIVE,
        "classified_at": _NOW,
        "classified_by": "manual",
    }
    return Transaction.model_validate(payload)


def test_recargo_surfaces_anomaly_not_missing_fact() -> None:
    issues = _issues_for_transaction(_tx(iva_category="recargo_equivalencia", iva_amount=None, iva_rate=None))
    assert [i.reason for i in issues] == [R.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA]
    assert "non-deductible acquisition cost" in issues[0].detail


def test_incoming_recargo_anomaly_points_to_recargo_amount_not_purchase() -> None:
    issues = _issues_for_transaction(
        _tx(
            direction=TransactionDirection.INCOMING,
            iva_category="recargo_equivalencia",
            iva_amount=None,
            iva_rate=None,
        ),
    )

    assert [i.reason for i in issues] == [R.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA]
    assert "recargo_amount" in issues[0].detail
    assert "purchase" not in issues[0].detail


def test_unknown_and_erroneous_categories_surface_anomaly() -> None:
    for cat in ("unknown", "erroneous_invoice"):
        issues = _issues_for_transaction(_tx(iva_category=cat, iva_amount=None, iva_rate=None, taxable_base=None))
        assert [i.reason for i in issues] == [R.ANOMALY_NON_DECLARABLE_IVA_CATEGORY], cat


def test_converted_foreign_row_is_not_flagged_unsupported_currency() -> None:
    # GBP row with a value_in_eur conversion applied at import aggregates fine.
    issues = _issues_for_transaction(_tx(currency="GBP", value_in_eur=Decimal("142.35"), fx_rate=Decimal("1.176")))
    assert all(i.reason is not R.UNSUPPORTED_CURRENCY for i in issues)


def test_unconverted_foreign_row_is_flagged_unsupported_currency() -> None:
    issues = _issues_for_transaction(_tx(currency="GBP", value_in_eur=None, fx_rate=None))
    assert [i.reason for i in issues] == [R.UNSUPPORTED_CURRENCY]
