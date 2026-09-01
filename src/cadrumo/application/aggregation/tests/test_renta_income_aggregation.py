"""Regression tests for repository-backed M130 actividad income aggregation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ._secure_objects_fixtures import SECURE_OBJECTS_BUCKET_ID, secure_objects

__all__ = ["secure_objects"]
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from .._renta_income_ledger import (
    RentaIncomeLedgerAggregationIssueReason,
    RentaIncomeObservation,
    aggregate_renta_income_ledger,
    aggregate_renta_income_ledger_from_repositories,
)
from .renta_income_aggregation_support import (
    _ANNUAL_2024,
    _M130_INGRESOS_CASILLA,
    _Q1_2024,
    _Q2_2024,
    _income_transaction,
    _raw_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# Pure-aggregator tests (no repository)
# ---------------------------------------------------------------------------


def test_q1_window_includes_jan_mar_transactions() -> None:
    """Q1 cumulative window [Jan 1 to Mar 31] captures all three months."""
    jan = _income_transaction("jan", value_date=date(2024, 1, 15), amount=Decimal("500.00"))
    feb = _income_transaction("feb", value_date=date(2024, 2, 20), amount=Decimal("600.00"))
    mar = _income_transaction("mar", value_date=date(2024, 3, 31), amount=Decimal("700.00"))
    apr = _income_transaction("apr", value_date=date(2024, 4, 1), amount=Decimal("800.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, feb, mar, apr))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

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

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q2_2024)

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

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

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

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.PERSONAL_TRANSACTION


def test_non_eur_transaction_excluded_with_reason() -> None:
    tx = _income_transaction("usd", value_date=date(2024, 3, 1), currency="USD")
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY


def test_outgoing_business_expense_is_skipped_silently_by_income_pipeline() -> None:
    """A business OUTGOING row is the gasto pipeline's concern, not income's.

    Deductible OUTGOING expenses are aggregated into M130 casilla 02 by the
    companion ``ledger_renta_gastos_pago_fraccionado_aggregation`` pipeline. The income pass no
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

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

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

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

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

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert result.observations == ()
    assert result.issues == ()


def test_non_quarterly_period_raises() -> None:
    from ..errors import AggregationPeriodError

    catalogue = TransactionCatalogue.from_transactions(())
    with pytest.raises(AggregationPeriodError):
        aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_ANNUAL_2024)


# ---------------------------------------------------------------------------
# Repository-backed integration test
# ---------------------------------------------------------------------------


def test_repository_backed_aggregation_emits_casilla_01_sum(
    secure_objects: SecureObjectRepository,
) -> None:
    """Full path: persist -> load from repo -> aggregate -> correct casilla 01 value."""
    q1_tx1 = _income_transaction("q1-a", value_date=date(2024, 2, 1), amount=Decimal("2500.00"))
    q1_tx2 = _income_transaction("q1-b", value_date=date(2024, 3, 15), amount=Decimal("1500.00"))
    # Q2-only transaction: excluded from Q1 window summary, included in Q2 window
    q2_only = _income_transaction("q2-only", value_date=date(2024, 5, 10), amount=Decimal("3000.00"))

    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((q1_tx1, q1_tx2, q2_only)))

    result_q1 = aggregate_renta_income_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    )

    # q2_only is outside Q1 window so it produces one compact summary entry.
    assert result_q1.issues == ()
    assert result_q1.out_of_window_summary is not None
    assert result_q1.out_of_window_summary.count == 1
    assert result_q1.out_of_window_summary.min_filing_date == date(2024, 5, 10)
    assert result_q1.out_of_window_summary.max_filing_date == date(2024, 5, 10)
    assert result_q1.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == sum(
        (tx.raw.amount for tx in (q1_tx1, q1_tx2)),
        Decimal("0"),
    )
    observation_ids_q1 = {o.transaction_id for o in result_q1.observations}
    assert observation_ids_q1 == {q1_tx1.transaction_id, q1_tx2.transaction_id}

    result_q2 = aggregate_renta_income_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q2_2024,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    )

    # Q2 is cumulative YTD: Jan-Jun, so all three transactions qualify
    assert result_q2.issues == ()
    assert result_q2.out_of_window_summary is None
    assert result_q2.casilla_aggregation.casilla_values[_M130_INGRESOS_CASILLA] == sum(
        (tx.raw.amount for tx in (q1_tx1, q1_tx2, q2_only)),
        Decimal("0"),
    )
    observation_ids_q2 = {o.transaction_id for o in result_q2.observations}
    assert observation_ids_q2 == {q1_tx1.transaction_id, q1_tx2.transaction_id, q2_only.transaction_id}


def test_repository_backed_aggregation_summarizes_previously_silent_out_of_window_rows(
    secure_objects: SecureObjectRepository,
) -> None:
    """Out-of-window rows surface as one compact period-exclusion summary.

    An archived row is ignored before the in-window income classifier runs.
    When that row falls outside the requested cumulative window, the
    repository-backed partition reports its count and date span instead of
    dropping it before aggregation.
    """
    in_window = _income_transaction("row-in-window", value_date=date(2024, 2, 1), amount=Decimal("500.00"))
    archived_out_of_window = _income_transaction(
        "row-archived-out-of-window",
        value_date=date(2024, 5, 10),
        amount=Decimal("900.00"),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((in_window, archived_out_of_window)))

    result = aggregate_renta_income_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    )

    assert {o.transaction_id for o in result.observations} == {in_window.transaction_id}
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2024, 5, 10)
    assert result.out_of_window_summary.max_filing_date == date(2024, 5, 10)


def test_repository_backed_aggregation_partition_matches_full_scan(
    secure_objects: SecureObjectRepository,
) -> None:
    """The partitioned result matches the full-scan result for declared values.

    The same multi-period catalogue is aggregated once through the
    repository-backed partition and once through the pure full-scan aggregator.
    In-window observations and casilla totals/provenance must match; only the
    out-of-window issue taxonomy can differ.
    """
    q1_row = _income_transaction("row-q1", value_date=date(2024, 2, 1), amount=Decimal("500.00"))
    q3_row = _income_transaction("row-q3", value_date=date(2024, 8, 1), amount=Decimal("700.00"))
    archived_q3_row = _income_transaction(
        "row-q3-archived",
        value_date=date(2024, 9, 1),
        amount=Decimal("300.00"),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    catalogue = TransactionCatalogue.from_transactions((q1_row, q3_row, archived_q3_row))
    tx_repo = TransactionCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects)
    tx_repo.save(catalogue)

    partitioned = aggregate_renta_income_ledger_from_repositories(
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_Q1_2024,
        transaction_repository=TransactionCatalogueRepository(
            bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects
        ),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=SECURE_OBJECTS_BUCKET_ID, objects=secure_objects),
    )
    full_scan = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    # Declared-value invariance: observations and casilla aggregation identical
    # (as sets: full-scan iterates catalogue insertion order, partitioned
    # iterates sorted ids).
    assert set(partitioned.observations) == set(full_scan.observations)
    assert partitioned.casilla_aggregation.casilla_values == full_scan.casilla_aggregation.casilla_values
    assert set(partitioned.casilla_aggregation.provenance) == set(full_scan.casilla_aggregation.provenance)
    assert {o.transaction_id for o in partitioned.observations} == {q1_row.transaction_id}

    # Permitted delta: repository-backed partitioning reports one compact
    # out-of-window summary, while full-scan refines by row after decryption.
    assert partitioned.issues == ()
    assert partitioned.out_of_window_summary is not None
    assert partitioned.out_of_window_summary.count == 2
    assert partitioned.out_of_window_summary.min_filing_date == date(2024, 8, 1)
    assert partitioned.out_of_window_summary.max_filing_date == date(2024, 9, 1)

    full_scan_issue_ids = {i.transaction_id for i in full_scan.issues}
    assert full_scan_issue_ids == {q3_row.transaction_id}
    assert archived_q3_row.transaction_id not in full_scan_issue_ids


def test_casilla_01_target_matches_expected_binding_contract() -> None:
    """Every observation targets casilla 01 — structural pin for the binding contract."""
    transactions = [
        _income_transaction(f"tx-{i}", value_date=date(2024, 1, i + 1), amount=Decimal("100.00")) for i in range(5)
    ]
    catalogue = TransactionCatalogue.from_transactions(transactions)

    result = aggregate_renta_income_ledger(catalogue, bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_Q1_2024)

    assert all(o.target_casilla_id == _M130_INGRESOS_CASILLA for o in result.observations)
    assert result.casilla_aggregation.modelo == "130"


def test_income_observation_rejects_legacy_target_casilla_key() -> None:
    transactions = [
        _income_transaction("tx-legacy-key", value_date=date(2024, 1, 1), amount=Decimal("100.00")),
    ]
    result = aggregate_renta_income_ledger(
        TransactionCatalogue.from_transactions(transactions),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
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
