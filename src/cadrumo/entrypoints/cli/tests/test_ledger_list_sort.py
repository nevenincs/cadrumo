"""Real-behaviour sort-stability suite for ``aeat app ledger list`` (D5).

Exercises the ledger-interface-contract D5 sort directly against the pure
``_sort_results`` projection helper and end-to-end through
``project_ledger_list`` over a real encrypted ``TransactionCatalogueRepository``
(no CLI runner, no mocks). The load-bearing contract under test is: the sort is
stable, an optional missing key always sorts last under both orders, and
equal-key rows fall back to the content-addressed ``transaction_id`` so the
order is fixed across runs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....application.ledger.models import ManualLedgerTransactionResult
from ....application.review.filter import LedgerReviewFilterSpec
from ....core import LedgerSortField, LedgerSortOrder
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import BucketTransactionRef, Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from .._ledger_list import _sort_results, project_ledger_list

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _transaction(
    *,
    provider_id: str,
    amount: Decimal,
    description: str,
    created_at: datetime,
    value_date: date | None = date(2024, 4, 10),
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 4, 10),
        value_date=value_date,
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={"Concepto": description},
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        "source_jurisdiction": "ES",
        "group_label": None,
    }
    payload["created_at"] = created_at
    payload["modified_at"] = created_at
    return Transaction.model_validate(payload)


def _result(transaction: Transaction) -> ManualLedgerTransactionResult:
    return ManualLedgerTransactionResult(
        ref=BucketTransactionRef(bucket_id="b", transaction_id=transaction.transaction_id),
        transaction=transaction,
    )


def test_sort_by_equal_key_falls_back_to_transaction_id_ascending() -> None:
    """Rows sharing an equal sort key keep a fixed transaction_id tie-break order.

    Three rows share an identical ``description`` sort key. Under both ascending
    and descending order the primary key is equal for all three, so the
    deterministic final tie-break on the content-addressed ``transaction_id``
    must fix their order — and that tie-break is ALWAYS ascending, independent
    of the primary sort order.
    """
    rows = tuple(
        _result(
            _transaction(
                provider_id=f"row-{n}",
                amount=Decimal("10.00"),
                description="same description",
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            ),
        )
        for n in range(3)
    )
    ascending_tids = sorted(r.transaction.transaction_id for r in rows)

    asc = _sort_results(rows, sort_by=LedgerSortField.DESCRIPTION, sort_order=LedgerSortOrder.ASC)
    desc = _sort_results(rows, sort_by=LedgerSortField.DESCRIPTION, sort_order=LedgerSortOrder.DESC)

    # Equal primary key -> identical tie-break order under both directions.
    assert [r.transaction.transaction_id for r in asc] == ascending_tids
    assert [r.transaction.transaction_id for r in desc] == ascending_tids


def test_sort_is_stable_and_orders_distinct_keys() -> None:
    """Distinct keys order correctly and the sort is stable on the chosen axis."""
    high = _result(
        _transaction(
            provider_id="high",
            amount=Decimal("300.00"),
            description="charlie",
            created_at=datetime(2024, 3, 1, tzinfo=UTC),
        ),
    )
    mid = _result(
        _transaction(
            provider_id="mid",
            amount=Decimal("200.00"),
            description="bravo",
            created_at=datetime(2024, 2, 1, tzinfo=UTC),
        ),
    )
    low = _result(
        _transaction(
            provider_id="low",
            amount=Decimal("100.00"),
            description="alpha",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        ),
    )
    rows = (high, mid, low)

    by_amount_asc = _sort_results(rows, sort_by=LedgerSortField.AMOUNT, sort_order=LedgerSortOrder.ASC)
    assert [r.transaction.raw.amount for r in by_amount_asc] == [
        Decimal("100.00"),
        Decimal("200.00"),
        Decimal("300.00"),
    ]
    by_amount_desc = _sort_results(rows, sort_by=LedgerSortField.AMOUNT, sort_order=LedgerSortOrder.DESC)
    assert [r.transaction.raw.amount for r in by_amount_desc] == [
        Decimal("300.00"),
        Decimal("200.00"),
        Decimal("100.00"),
    ]
    by_created_asc = _sort_results(rows, sort_by=LedgerSortField.CREATED_AT, sort_order=LedgerSortOrder.ASC)
    assert [r.transaction.created_at for r in by_created_asc] == [
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 2, 1, tzinfo=UTC),
        datetime(2024, 3, 1, tzinfo=UTC),
    ]


def test_optional_sort_key_sorts_last_under_both_orders() -> None:
    """A row with a missing optional value_date sorts last in both orders."""
    with_key_early = _result(
        _transaction(
            provider_id="early",
            amount=Decimal("10.00"),
            description="x",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            value_date=date(2024, 1, 1),
        ),
    )
    with_key_late = _result(
        _transaction(
            provider_id="late",
            amount=Decimal("10.00"),
            description="x",
            created_at=datetime(2024, 6, 1, tzinfo=UTC),
            value_date=date(2024, 6, 1),
        ),
    )
    missing = _result(
        _transaction(
            provider_id="missing",
            amount=Decimal("10.00"),
            description="x",
            created_at=datetime(2024, 3, 1, tzinfo=UTC),
            value_date=None,
        ),
    )
    rows = (missing, with_key_late, with_key_early)

    asc = _sort_results(rows, sort_by=LedgerSortField.VALUE_DATE, sort_order=LedgerSortOrder.ASC)
    desc = _sort_results(rows, sort_by=LedgerSortField.VALUE_DATE, sort_order=LedgerSortOrder.DESC)

    # Missing key trails in BOTH orders.
    assert asc[-1].transaction.raw.value_date is None
    assert desc[-1].transaction.raw.value_date is None
    # Present keys order correctly within their block.
    assert [r.transaction.raw.value_date for r in asc[:2]] == [date(2024, 1, 1), date(2024, 6, 1)]
    assert [r.transaction.raw.value_date for r in desc[:2]] == [date(2024, 6, 1), date(2024, 1, 1)]


def test_project_ledger_list_applies_sort_over_real_repository(tmp_path: Path) -> None:
    """End-to-end: project_ledger_list sorts a real encrypted catalogue by amount.

    Persists three transactions through the real
    :class:`TransactionCatalogueRepository`, then lists them through
    ``project_ledger_list`` with ``sort_by=amount``. The rendered rows must
    appear in ascending magnitude order — proving the sort is wired into the
    projection path, not only the helper.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="65853d4f-9e30-443f-9f91-b048ef4d292e") as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txns = [
            _transaction(
                provider_id=f"row-{label}",
                amount=amount,
                description=label,
                created_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
            for label, amount in (("b", Decimal("200.00")), ("c", Decimal("300.00")), ("a", Decimal("100.00")))
        ]
        repo.save(TransactionCatalogue.from_transactions(txns))

        projection = project_ledger_list(
            transaction_repository=TransactionCatalogueRepository(bucket_id=profile.bucket_id),
            spec=LedgerReviewFilterSpec.from_strings([]),
            group=None,
            by_group=False,
            limit=None,
            offset=0,
            sort_by=LedgerSortField.AMOUNT,
            sort_order=LedgerSortOrder.ASC,
        )

    # D2: projection.rows are typed LedgerListRowPayload objects, not bare dicts.
    # The display projection normalises the magnitude (no forced trailing cents),
    # so the assertion checks the ascending ORDER of the rendered amounts.
    amounts = [row.amount for row in projection.rows]
    assert amounts == ["100", "200", "300"]
