"""Preflight anomaly channel + converted-foreign-row currency fix."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.iva import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..preflight import (
    LedgerPreflightIssue,
    _issues_for_transaction,
)
from ..preflight import (
    LedgerPreflightIssueReason as R,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)


def _tx(
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    currency: str = "EUR",
    iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL,
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_amount: Decimal | None = Decimal("21.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    value_in_eur: Decimal | None = None,
    fx_rate: Decimal | None = None,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="row-x",
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


def _assert_single_issue(
    label: str,
    issues: tuple[LedgerPreflightIssue, ...],
    expected_reason: R,
    *,
    present_detail: tuple[str, ...] = (),
    absent_detail: tuple[str, ...] = (),
) -> None:
    assert [i.reason for i in issues] == [expected_reason], label
    detail = issues[0].detail
    for token in present_detail:
        assert token in detail, label
    for token in absent_detail:
        assert token not in detail, label


def test_preflight_surfaces_non_declarable_iva_anomalies() -> None:
    cases: tuple[tuple[str, Transaction, R, tuple[str, ...], tuple[str, ...]], ...] = (
        (
            "outgoing-recargo",
            _tx(iva_category=IvaCategory.RECARGO_EQUIVALENCIA, iva_amount=None, iva_rate=None),
            R.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA,
            ("non-deductible acquisition cost",),
            (),
        ),
        (
            "incoming-recargo",
            _tx(
                direction=TransactionDirection.INCOMING,
                iva_category=IvaCategory.RECARGO_EQUIVALENCIA,
                iva_amount=None,
                iva_rate=None,
            ),
            R.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA,
            ("recargo_amount",),
            ("purchase",),
        ),
        (
            "unknown",
            _tx(iva_category=IvaCategory.UNKNOWN, iva_amount=None, iva_rate=None, taxable_base=None),
            R.ANOMALY_NON_DECLARABLE_IVA_CATEGORY,
            (),
            (),
        ),
        (
            "erroneous-invoice",
            _tx(iva_category=IvaCategory.ERRONEOUS_INVOICE, iva_amount=None, iva_rate=None, taxable_base=None),
            R.ANOMALY_NON_DECLARABLE_IVA_CATEGORY,
            (),
            (),
        ),
    )

    for label, transaction, expected_reason, present_detail, absent_detail in cases:
        _assert_single_issue(
            label,
            _issues_for_transaction(transaction),
            expected_reason,
            present_detail=present_detail,
            absent_detail=absent_detail,
        )


def test_foreign_currency_preflight_separates_converted_and_unconverted_rows() -> None:
    cases: tuple[tuple[str, Transaction, R, tuple[str, ...]], ...] = (
        (
            "converted",
            _tx(currency="GBP", value_in_eur=Decimal("142.35"), fx_rate=Decimal("1.176")),
            R.MISSING_EUR_TAX_SUBSTRATE,
            ("value_in_eur", "explicit EUR tax substrate", "exclude the row"),
        ),
        (
            "unconverted",
            _tx(currency="GBP", value_in_eur=None, fx_rate=None),
            R.UNSUPPORTED_CURRENCY,
            (),
        ),
    )

    for label, transaction, expected_reason, present_detail in cases:
        _assert_single_issue(
            label,
            _issues_for_transaction(transaction),
            expected_reason,
            present_detail=present_detail,
        )
