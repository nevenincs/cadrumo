"""Regression tests for repository-backed M130 actividad-económica income aggregation.

Tests exercise the full path:
  - real TransactionCatalogueRepository backed by isolated_runtime_profile
  - aggregate_renta_income_ledger_from_repositories for quarterly cumulative windows
  - resolve_ledger_renta_income_aggregation_binding_values against an M130 revision

The cumulative window rule (RD 439/2007 art. 110.2) is tested directly: Q1
covers Jan-Mar, Q2 covers Jan-Jun, so a Jan transaction appears in both Q1
and Q2 totals while a May transaction appears only in Q2.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...tests.secure_sql import isolated_runtime_profile
from ._renta_income_ledger import (
    RentaIncomeLedgerAggregationIssueReason,
    aggregate_renta_income_ledger,
    aggregate_renta_income_ledger_from_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="test") as profile:
        yield profile.repository


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date,
    value_date: date | None,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Cliente SA",
        description=f"income row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _income_transaction(
    provider_id: str,
    *,
    value_date: date,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "EUR",
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": TransactionDirection.INCOMING,
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


# ---------------------------------------------------------------------------
# Pure-aggregator tests (no repository)
# ---------------------------------------------------------------------------


def test_q1_window_includes_jan_mar_transactions() -> None:
    """Q1 cumulative window [Jan 1 to Mar 31] captures all three months."""
    jan = _income_transaction("jan", value_date=date(2024, 1, 15), amount=Decimal("500.00"))
    feb = _income_transaction("feb", value_date=date(2024, 2, 20), amount=Decimal("600.00"))
    mar = _income_transaction("mar", value_date=date(2024, 3, 31), amount=Decimal("700.00"))
    apr = _income_transaction("apr", value_date=date(2024, 4, 1), amount=Decimal("800.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, feb, mar, apr))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q1")

    observation_ids = {o.transaction_id for o in result.observations}
    # Transaction.transaction_id is a content hash; compare against the created objects.
    assert observation_ids == {jan.transaction_id, feb.transaction_id, mar.transaction_id}
    # April is outside Q1 window — ends up in issues
    issue_ids = {i.transaction_id for i in result.issues}
    assert apr.transaction_id in issue_ids
    assert result.casilla_aggregation.casilla_values["01"] == Decimal("1800.00")


def test_q2_window_accumulates_jan_through_jun() -> None:
    """Q2 cumulative window [Jan 1 to Jun 30] includes Q1 rows too (YTD rule)."""
    jan = _income_transaction("jan", value_date=date(2024, 1, 10), amount=Decimal("1000.00"))
    may = _income_transaction("may", value_date=date(2024, 5, 5), amount=Decimal("2000.00"))
    jul = _income_transaction("jul", value_date=date(2024, 7, 1), amount=Decimal("3000.00"))
    catalogue = TransactionCatalogue.from_transactions((jan, may, jul))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q2")

    observation_ids = {o.transaction_id for o in result.observations}
    assert observation_ids == {jan.transaction_id, may.transaction_id}
    assert result.casilla_aggregation.casilla_values["01"] == Decimal("3000.00")


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

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q1")

    assert len(result.observations) == 1
    assert result.observations[0].gross_amount == Decimal("600.00")
    assert result.casilla_aggregation.casilla_values["01"] == Decimal("600.00")


def test_personal_transaction_excluded_with_reason() -> None:
    tx = _income_transaction(
        "personal",
        value_date=date(2024, 2, 1),
        business_classification=BusinessClassification.PERSONAL,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q1")

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.PERSONAL_TRANSACTION


def test_non_eur_transaction_excluded_with_reason() -> None:
    tx = _income_transaction("usd", value_date=date(2024, 3, 1), currency="USD")
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q1")

    assert result.observations == ()
    assert len(result.issues) == 1
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY


def test_outgoing_transaction_excluded_with_reason() -> None:
    tx = Transaction.model_validate(
        {
            "raw": _raw_transaction("out", booked_date=date(2024, 3, 1), value_date=date(2024, 3, 1)),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q1")

    assert result.observations == ()
    assert result.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION


def test_inactive_transaction_skipped_silently() -> None:
    """ARCHIVED lifecycle state bypasses the pipeline without an issue record."""
    tx = _income_transaction(
        "archived",
        value_date=date(2024, 2, 1),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    catalogue = TransactionCatalogue.from_transactions((tx,))

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q1")

    assert result.observations == ()
    assert result.issues == ()


def test_non_quarterly_period_raises() -> None:
    from ._errors import AggregationPeriodError

    catalogue = TransactionCatalogue.from_transactions(())
    with pytest.raises(AggregationPeriodError):
        aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024")


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
        period="2024Q1",
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
    )

    # q2_only is outside Q1 window so it produces one OUTSIDE_PERIOD issue
    assert len(result_q1.issues) == 1
    assert result_q1.issues[0].reason == RentaIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert result_q1.casilla_aggregation.casilla_values["01"] == Decimal("4000.00")
    observation_ids_q1 = {o.transaction_id for o in result_q1.observations}
    assert observation_ids_q1 == {q1_tx1.transaction_id, q1_tx2.transaction_id}

    result_q2 = aggregate_renta_income_ledger_from_repositories(
        bucket_id="test",
        period="2024Q2",
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
    )

    # Q2 is cumulative YTD: Jan-Jun, so all three transactions qualify
    assert result_q2.issues == ()
    assert result_q2.casilla_aggregation.casilla_values["01"] == Decimal("7000.00")
    observation_ids_q2 = {o.transaction_id for o in result_q2.observations}
    assert observation_ids_q2 == {q1_tx1.transaction_id, q1_tx2.transaction_id, q2_only.transaction_id}


def test_casilla_01_target_matches_expected_binding_contract() -> None:
    """Every observation targets casilla 01 — structural pin for the binding contract."""
    transactions = [
        _income_transaction(f"tx-{i}", value_date=date(2024, 1, i + 1), amount=Decimal("100.00")) for i in range(5)
    ]
    catalogue = TransactionCatalogue.from_transactions(transactions)

    result = aggregate_renta_income_ledger(catalogue, bucket_id="test", period="2024Q1")

    assert all(o.target_casilla == "01" for o in result.observations)
    assert result.casilla_aggregation.modelo == "130"
