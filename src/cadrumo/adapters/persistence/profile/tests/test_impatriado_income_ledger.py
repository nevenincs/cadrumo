"""Persistence-backed impatriado ledger aggregation tests.

These cases exercise the bucket-bound transaction catalogue and its
period-partitioned repository read. Pure source-scope policy remains covered
in the inward application aggregation tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.impatriado_income_ledger import (
    ImpatriadoIncomeLedgerAggregation,
    ImpatriadoIncomeLedgerAggregationIssueReason,
    aggregate_impatriado_income_ledger,
    aggregate_impatriado_income_ledger_from_repositories,
)
from cadrumo.core.period import Period
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_ANNUAL_2024 = Period.from_year_and_code(2024, "0A")
_BASE_CASILLA = "impatriado.base-liquidable-general"
_BUCKET_ID = "16161616-1616-4616-8616-161616161616"


def _impatriado_transaction(
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
    value_date: date = date(2024, 3, 1),
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
                    ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
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
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _base_total(aggregation: ImpatriadoIncomeLedgerAggregation) -> Decimal:
    values = aggregation.casilla_aggregation.casilla_values
    return next((v for c, v in values.items() if str(c) == _BASE_CASILLA), Decimal("0"))


def test_repository_backed_aggregation_reports_out_of_period_catalogue_transactions(
    tmp_path: Path,
) -> None:
    """A catalogue transaction outside the requested ejercicio must surface as a summary.

    Regression test: the repository-backed entry point must NOT
    silently drop out-of-window rows. The compact summary keeps the operator
    visibility signal without allocating one issue per plaintext index entry.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        in_period = _impatriado_transaction(
            "row-in-period",
            amount=Decimal("30000.00"),
            source_jurisdiction="ES",
            value_date=date(2024, 6, 1),
        )
        out_of_period = _impatriado_transaction(
            "row-out-of-period",
            amount=Decimal("45000.00"),
            source_jurisdiction="ES",
            value_date=date(2025, 1, 15),
        )
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((in_period, out_of_period)))

        result = aggregate_impatriado_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_ANNUAL_2024,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
        )

    assert {o.transaction_id for o in result.observations} == {in_period.transaction_id}
    assert _base_total(result) == Decimal("30000.00")
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2025, 1, 15)
    assert result.out_of_window_summary.max_filing_date == date(2025, 1, 15)


def test_repository_backed_aggregation_summarizes_previously_silent_out_of_window_rows(
    tmp_path: Path,
) -> None:
    """Out-of-window rows surface as one compact period-exclusion summary.

    A wrong-direction outgoing row is ignored by the in-window classifier
    because this aggregation owns incoming rows. When that same row falls
    outside the requested ejercicio, the repository-backed partition reports
    its count and date span instead of dropping it before aggregation.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        in_year = _impatriado_transaction(
            "row-in-year",
            amount=Decimal("20000.00"),
            source_jurisdiction="ES",
            value_date=date(2024, 3, 1),
        )
        wrong_direction_out_of_year = _impatriado_transaction(
            "row-wrong-direction-out-of-year",
            amount=Decimal("15000.00"),
            source_jurisdiction="ES",
            value_date=date(2025, 2, 1),
            direction=TransactionDirection.OUTGOING,
        )
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((in_year, wrong_direction_out_of_year)))

        result = aggregate_impatriado_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_ANNUAL_2024,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
        )

    assert {o.transaction_id for o in result.observations} == {in_year.transaction_id}
    assert result.issues == ()
    assert result.out_of_window_summary is not None
    assert result.out_of_window_summary.count == 1
    assert result.out_of_window_summary.min_filing_date == date(2025, 2, 1)
    assert result.out_of_window_summary.max_filing_date == date(2025, 2, 1)


def test_repository_backed_aggregation_partition_matches_full_scan(
    tmp_path: Path,
) -> None:
    """The partitioned result matches the full-scan result for declared values.

    The same multi-year catalogue is aggregated once through the
    repository-backed partition and once through the pure full-scan aggregator.
    In-window observations and casilla totals/provenance must match; only the
    out-of-window diagnostic shape can differ. The full-scan path keeps row
    reasons, while the partition reports a compact count and date span.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        in_year = _impatriado_transaction(
            "row-parity-in-year",
            amount=Decimal("20000.00"),
            source_jurisdiction="ES",
            value_date=date(2024, 3, 1),
        )
        out_of_year = _impatriado_transaction(
            "row-parity-out-of-year",
            amount=Decimal("10000.00"),
            source_jurisdiction="ES",
            value_date=date(2025, 1, 15),
        )
        foreign_out_of_year = _impatriado_transaction(
            "row-parity-foreign-out-of-year",
            amount=Decimal("5000.00"),
            source_jurisdiction="FR",
            value_date=date(2023, 6, 1),
        )
        catalogue = TransactionCatalogue.from_transactions((in_year, out_of_year, foreign_out_of_year))
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(catalogue)

        partitioned = aggregate_impatriado_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_ANNUAL_2024,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository),
        )
        full_scan = aggregate_impatriado_income_ledger(catalogue, bucket_id=_BUCKET_ID, period=_ANNUAL_2024)

    assert set(partitioned.observations) == set(full_scan.observations)
    assert partitioned.casilla_aggregation.casilla_values == full_scan.casilla_aggregation.casilla_values
    assert set(partitioned.casilla_aggregation.provenance) == set(full_scan.casilla_aggregation.provenance)
    assert {o.transaction_id for o in partitioned.observations} == {in_year.transaction_id}

    assert partitioned.issues == ()
    assert partitioned.out_of_window_summary is not None
    assert partitioned.out_of_window_summary.count == 2
    assert partitioned.out_of_window_summary.min_filing_date == date(2023, 6, 1)
    assert partitioned.out_of_window_summary.max_filing_date == date(2025, 1, 15)

    full_scan_issue_ids = {i.transaction_id for i in full_scan.issues}
    assert full_scan_issue_ids == {out_of_year.transaction_id, foreign_out_of_year.transaction_id}
    full_scan_by_id = {i.transaction_id: i for i in full_scan.issues}
    assert (
        full_scan_by_id[out_of_year.transaction_id].reason
        is ImpatriadoIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD
    )
    assert (
        full_scan_by_id[foreign_out_of_year.transaction_id].reason
        is ImpatriadoIncomeLedgerAggregationIssueReason.BECKHAM_FOREIGN_SOURCE_SEGREGATED
    )
