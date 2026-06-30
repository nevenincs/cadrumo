"""Regression tests for repository-backed M130 actividad income aggregation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from .._renta_income_ledger import (
    RentaIncomeLedgerAggregationIssueReason,
    RentaIncomeObservation,
    aggregate_renta_income_ledger,
    aggregate_renta_income_ledger_from_repositories,
)
from ._renta_income_aggregation_support import (
    _ANNUAL_2024,
    _M130_INGRESOS_CASILLA,
    _Q1_2024,
    _Q2_2024,
    _income_transaction,
    _raw_transaction,
    isolated_renta_income_objects,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_renta_income_objects(tmp_path) as objects:
        yield objects


# Pure-aggregator tests (no repository)
# ---------------------------------------------------------------------------


def test_q1_window_includes_jan_mar_transactions() -> None:
    """Q1 cumulative window [Jan 1 to Mar 31] captures all three months."""
    jan = _income_transaction("jan", value_date=date(2024, 1, 15), amount=Decimal("500.00"))
    feb = _income_transaction("feb", value_date=date(2024, 2, 20), amount=Decimal("600.00"))
    mar = _income_transaction("mar", value_date=date(2024, 3, 31), amount=Decimal("700.00"))
    apr = _income_transaction("apr", value_date=date(2024, 4, 1), amount=Decimal("800.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, feb, mar, apr))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    observation_ids = {o.transaction_id for o in result.observations}
    # Transaction.transaction_id is a content hash; compare against the created objects.
    assert observation_ids == {jan.transaction_id, feb.transaction_id, mar.transaction_id}
    # April is outside Q1 window — ends up in issues
    issue_ids = {i.transaction_id for i in result.issues}
    assert apr.transaction_id in issue_ids
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == sum(
        (tx.raw.amount for tx in (jan, feb, mar)),
        Decimal("0"),
    )


def test_q2_window_accumulates_jan_through_jun() -> None:
    """Q2 cumulative window [Jan 1 to Jun 30] includes Q1 rows too (YTD rule)."""
    jan = _income_transaction("jan", value_date=date(2024, 1, 10), amount=Decimal("1000.00"))
    may = _income_transaction("may", value_date=date(2024, 5, 5), amount=Decimal("2000.00"))
    jul = _income_transaction("jul", value_date=date(2024, 7, 1), amount=Decimal("3000.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, may, jul))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q2_2024)

    observation_ids = {o.transaction_id for o in result.observations}
    assert observation_ids == {jan.transaction_id, may.transaction_id}
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == sum(
        (tx.raw.amount for tx in (jan, may)),
        Decimal("0"),
    )


def test_mixed_classification_applies_business_pct() -> None:
    """MIXED transaction contributes only its business fraction to casilla 01."""
    tx = _income_transaction(
        "mixed",
        value_date=date(2024, 3, 1),
        amount=Decimal("1000.00"),
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.60"),
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert len(result.observations) == 1
    assert result.observations[0].gross_amount == Decimal("600.00")
    assert result.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == Decimal("600.00")


def test_personal_transaction_excluded_with_reason() -> None:
    tx = _income_transaction(
        "personal",
        value_date=date(2024, 2, 1),
        business_classification=BusinessClassification.PERSONAL,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.PERSONAL_TRANSACTION


def test_non_eur_transaction_excluded_with_reason() -> None:
    tx = _income_transaction("usd", value_date=date(2024, 3, 1), currency="USD")
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY


def test_outgoing_business_expense_is_skipped_silently_by_income_pipeline() -> None:
    """A business OUTGOING row is the gasto pipeline's concern, not income's.

    Deductible OUTGOING expenses are aggregated into M130 casilla 02 by the
    companion ``ledger_renta_gasto_aggregation`` pipeline. The income pass no
    longer claims the expense was "dropped" — it skips OUTGOING rows silently so
    no spurious advisory surfaces. The deductible-expense aggregation itself is
    proven in ``test_renta_gasto_aggregation.py``.
    """
    tx = Transaction.model_validate(
        {
            "raw": _raw_transaction(
                "out",
                booked_date=date(2024, 3, 1),
                value_date=date(2024, 3, 1),
                amount=Decimal("121"),
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": "material_oficina",
            "taxable_base": Decimal("100"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    # No income observation and — critically — no issue/advisory: the income
    # pipeline does not own deductible expenses.
    assert result.observations == ()
    assert result.issues == ()


def test_outgoing_personal_transaction_is_skipped_silently_by_income_pipeline() -> None:
    """A personal OUTGOING row is neither income nor a deducible gasto."""
    tx = Transaction.model_validate(
        {
            "raw": _raw_transaction("out", booked_date=date(2024, 3, 1), value_date=date(2024, 3, 1)),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.PERSONAL,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert result.issues == ()


def test_inactive_transaction_skipped_silently() -> None:
    """ARCHIVED lifecycle state bypasses the pipeline without an issue record."""
    tx = _income_transaction(
        "archived",
        value_date=date(2024, 2, 1),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert result.observations == ()
    assert result.issues == ()


def test_non_quarterly_period_raises() -> None:
    from .._errors import AggregationPeriodError

    catalogue = TransactionCatalogue.from_transactions(())
    with pytest.raises(AggregationPeriodError):
        aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_ANNUAL_2024)


# ---------------------------------------------------------------------------
# Repository-backed integration test
# ---------------------------------------------------------------------------


def test_repository_backed_aggregation_emits_casilla_01_sum(
    secure_objects: SecureObjectRepository,
) -> None:
    """Full path: persist -> load from repo -> aggregate -> correct casilla 01 value."""
    q1_tx1 = _income_transaction("q1-a", value_date=date(2024, 2, 1), amount=Decimal("2500.00"))
    q1_tx2 = _income_transaction("q1-b", value_date=date(2024, 3, 15), amount=Decimal("1500.00"))
    # Q2-only transaction: excluded from Q1 window (outside_period issue), included in Q2 window
    q2_only = _income_transaction("q2-only", value_date=date(2024, 5, 10), amount=Decimal("3000.00"))

    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((q1_tx1, q1_tx2, q2_only)))

    result_q1 = aggregate_renta_income_ledger_from_repositories(
        bucket_id="test",
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
    )

    # q2_only is outside Q1 window so it produces one OUTSIDE_PERIOD issue
    assert len(result_q1.issues) == 1
    assert result_q1.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert result_q1.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == sum(
        (tx.raw.amount for tx in (q1_tx1, q1_tx2)),
        Decimal("0"),
    )
    observation_ids_q1 = {o.transaction_id for o in result_q1.observations}
    assert observation_ids_q1 == {q1_tx1.transaction_id, q1_tx2.transaction_id}

    result_q2 = aggregate_renta_income_ledger_from_repositories(
        bucket_id="test",
        period=_Q2_2024,
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
    )

    # Q2 is cumulative YTD: Jan-Jun, so all three transactions qualify
    assert result_q2.issues == ()
    assert result_q2.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == sum(
        (tx.raw.amount for tx in (q1_tx1, q1_tx2, q2_only)),
        Decimal("0"),
    )
    observation_ids_q2 = {o.transaction_id for o in result_q2.observations}
    assert observation_ids_q2 == {q1_tx1.transaction_id, q1_tx2.transaction_id, q2_only.transaction_id}


def test_casilla_01_target_matches_expected_binding_contract() -> None:
    """Every observation targets casilla 01 — structural pin for the binding contract."""
    transactions = [
        _income_transaction(f"tx-{i}", value_date=date(2024, 1, i + 1), amount=Decimal("100.00")) for i in range(5)
    ]
    catalogue = TransactionCatalogue.from_transactions(transactions)

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period=_Q1_2024)

    assert all(o.target_casilla_id == _M130_INGRESOS_CASILLA for o in result.observations)
    assert result.casilla_aggregation.modelo == "130"


def test_income_observation_rejects_legacy_target_casilla_key() -> None:
    transactions = [
        _income_transaction("tx-legacy-key", value_date=date(2024, 1, 1), amount=Decimal("100.00")),
    ]
    result = aggregate_renta_income_ledger(
        TransactionCatalogue.from_transactions(transactions),
        bucket_id="test",
        period=_Q1_2024,
    )
    payload = result.observations[0].model_dump()
    payload["target_casilla"] = payload.pop("target_casilla_id")

    with pytest.raises(ValidationError) as exc_info:
        RentaIncomeObservation.model_validate(payload)

    detail = str(exc_info.value)
    assert "target_casilla_id" in detail
    assert "target_casilla" in detail


# ---------------------------------------------------------------------------
