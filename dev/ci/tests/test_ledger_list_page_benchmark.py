"""Scale benchmark: one period-filtered ``ledger.list`` page at 30k-transaction scale.

The Records workspace lists entries one page at a time through the registered
``ledger.list`` read. This module seeds a REAL bucket (encrypted SQLite via
:class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
and :func:`isolated_runtime_profile`, no mocks) with 30,000 synthetic
transactions across ten filing years, the same volume and shape the ledger
scale benchmark seeds, and measures the work the list executor does for one
page: the canonical selection query over the exact-profile read ports, then
the projection the operation publishes.

The budgeted gate is one quarter's page of at most 200 rows, asserted in
PROCESS CPU-time against the 3.0 CPU-second period-operation budget the ledger
scale benchmark derives; wall-clock rides alongside as a non-failing advisory
for the reasons that module gives. The unfiltered first page stays a printed
diagnostic: a whole-ledger read is outside the period-operation budget.
"""

from __future__ import annotations

import statistics
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.actions_manual import ledger_transaction_payload
from cadrumo.application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from cadrumo.application.ledger.list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from cadrumo.application.ledger.read_ports import LedgerReadPorts
from cadrumo.application.ledger.review_projection import ledger_transaction_review_status
from cadrumo.application.ledger.transaction_projection import (
    LedgerTransactionProjection,
    LedgerTransactionReviewProjection,
)
from cadrumo.core.ledger_sort import LedgerSortField
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.transactions.enums import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

from ..perf_measurement import wall_advisory_message

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "41414141-4141-4141-8141-414141414141"
_TOTAL_TRANSACTIONS = 30_000
_FILING_YEARS = 10
_TRANSACTIONS_PER_YEAR = _TOTAL_TRANSACTIONS // _FILING_YEARS
_FIRST_YEAR = 2021
_LAST_YEAR = _FIRST_YEAR + _FILING_YEARS - 1

#: The period-operation budget the ledger scale benchmark derives and binds.
_P95_BUDGET_CPU_SECONDS = 3.0
_P95_WALL_ADVISORY_SECONDS = 3.0
_P95_WEDGE_WALL_TO_CPU_RATIO = 4.0

#: The largest page a Records list screen may hold.
_PAGE_SIZE = 200
_BUDGET_SAMPLE_COUNT = 10
_DIAGNOSTIC_SAMPLE_COUNT = 2


@pytest.fixture(scope="module")
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Pin one registry generation for every measured page."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _synthetic_transaction(idx: int, *, booked: date) -> Transaction:
    """One classified business row; direction alternates so the ledger is not degenerate."""
    direction = TransactionDirection.OUTGOING if idx % 3 else TransactionDirection.INCOMING
    raw = RawTransaction(
        provider_transaction_id=f"list-bench-row-{idx:06d}",
        booked_date=booked,
        value_date=booked,
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor Escala SL",
        description=f"list benchmark row {idx}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=idx + 1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(booked.year, booked.month, booked.day, 12, 0, tzinfo=UTC),
            provider_name="list benchmark provider",
        ),
        raw_fields={"Concepto": f"row {idx}"},
    )
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
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(booked.year, booked.month, booked.day, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _dates_across_year(year: int, count: int) -> Iterator[date]:
    start = date(year, 1, 1)
    span_days = (date(year, 12, 31) - start).days
    for i in range(count):
        yield start + timedelta(days=(i * span_days) // max(count - 1, 1))


@pytest.fixture(scope="module")
def scale_bucket(authority_operation: PinnedAuthorityOperation) -> Iterator[SecureObjectRepository]:
    """Yield a real bucket holding the 30k-transaction, ten-year ledger; seeding is untimed setup."""
    with (
        tempfile.TemporaryDirectory(prefix="cadrumo-list-bench-") as tmp_dir,
        isolated_runtime_profile(tmp_path=Path(tmp_dir), bucket_id=_BUCKET_ID) as profile,
    ):
        transactions: list[Transaction] = []
        idx = 0
        for year in range(_FIRST_YEAR, _FIRST_YEAR + _FILING_YEARS):
            for booked in _dates_across_year(year, _TRANSACTIONS_PER_YEAR):
                transactions.append(_synthetic_transaction(idx, booked=booked))
                idx += 1
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).save(
            TransactionCatalogue.from_transactions(transactions)
        )
        yield profile.repository


def _read_page(
    request: LedgerListRequest, objects: SecureObjectRepository, operation: PinnedAuthorityOperation
) -> LedgerListProjection:
    """Do what the list executor does for one request: select the page, then project it."""
    ports = LedgerReadPorts(
        operation=operation,
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )
    page = query_ledger_transaction_list(
        LedgerTransactionListQuery(
            spec=request.filter_spec(),
            group=request.group,
            by_group=request.by_group,
            limit=request.limit,
            offset=request.offset,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            exclude_llm_rejected=request.exclude_llm_rejected,
        ),
        bucket_id=_BUCKET_ID,
        ports=ports,
    )
    return LedgerListProjection(
        profile_id=request.profile_id,
        rows=tuple(
            LedgerTransactionReviewProjection(
                transaction=LedgerTransactionProjection.from_payload(ledger_transaction_payload(item.transaction)),
                review_status=ledger_transaction_review_status(item.transaction),
                group_label=item.transaction.group_label,
            )
            for item in page.results
        ),
        total=page.total,
        truncated=page.truncated,
        offset=request.offset,
        limit=request.limit,
        by_group=request.by_group,
    )


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    rank = max(0, min(len(ordered) - 1, round(0.95 * (len(ordered) - 1))))
    return ordered[rank]


@pytest.mark.perf
@pytest.mark.serial
def test_period_filtered_list_page_p95_cpu_within_budget(
    scale_bucket: SecureObjectRepository, authority_operation: PinnedAuthorityOperation
) -> None:
    """One quarter's first page of at most 200 rows stays inside the period-operation CPU budget."""
    request = LedgerListRequest(
        profile_id=UUID(_BUCKET_ID),
        filters=("period=4T", f"year={_LAST_YEAR}"),
        limit=_PAGE_SIZE,
        sort_by=LedgerSortField.DATE,
    )
    cpu: list[float] = []
    wall: list[float] = []
    for _ in range(_BUDGET_SAMPLE_COUNT):
        wall_started = time.perf_counter()
        cpu_started = time.process_time()
        page = _read_page(request, scale_bucket, authority_operation)
        cpu.append(time.process_time() - cpu_started)
        wall.append(time.perf_counter() - wall_started)
        # One quarter of one year: roughly a quarter of that year's rows, and one page of them.
        assert 0 < page.total < _TRANSACTIONS_PER_YEAR
        assert len(page.rows) == _PAGE_SIZE
        assert page.truncated
        assert all(row.transaction.date.startswith(str(_LAST_YEAR)) for row in page.rows)

    cpu_p95 = _p95(cpu)
    wall_p95 = _p95(wall)
    print(
        f"\n[bench] ledger_list_period_page: n={_BUDGET_SAMPLE_COUNT} cpu_p95={cpu_p95:.3f}s "
        f"cpu_mean={statistics.mean(cpu):.3f}s gate=cpu<{_P95_BUDGET_CPU_SECONDS:.1f}s "
        f"wall_p95={wall_p95:.3f}s (wall advisory)"
    )
    wall_advisory_message(
        "ledger_list_period_page p95",
        wall_seconds=wall_p95,
        cpu_seconds=cpu_p95,
        wall_advisory_seconds=_P95_WALL_ADVISORY_SECONDS,
        hang_wall_to_cpu_ratio=_P95_WEDGE_WALL_TO_CPU_RATIO,
    )
    assert cpu_p95 < _P95_BUDGET_CPU_SECONDS, (
        f"period-filtered ledger.list page P95 {cpu_p95:.3f} CPU-s at {_TOTAL_TRANSACTIONS}-row scale exceeds "
        f"the {_P95_BUDGET_CPU_SECONDS:.1f} CPU-s budget (cpu samples={cpu!r})"
    )


def test_unfiltered_list_page_reports_full_ledger_latency(
    scale_bucket: SecureObjectRepository, authority_operation: PinnedAuthorityOperation
) -> None:
    """Report the unfiltered first page's cost; a whole-ledger read is a diagnostic, not a gate."""
    request = LedgerListRequest(profile_id=UUID(_BUCKET_ID), limit=_PAGE_SIZE)
    cpu: list[float] = []
    for _ in range(_DIAGNOSTIC_SAMPLE_COUNT):
        started = time.process_time()
        page = _read_page(request, scale_bucket, authority_operation)
        cpu.append(time.process_time() - started)
        assert page.total == _TOTAL_TRANSACTIONS
        assert len(page.rows) == _PAGE_SIZE
    print(
        f"\n[bench] ledger_list_unfiltered_page_diagnostic: n={_DIAGNOSTIC_SAMPLE_COUNT} "
        f"cpu_p95={_p95(cpu):.3f}s cpu_mean={statistics.mean(cpu):.3f}s (outside the period budget)"
    )
