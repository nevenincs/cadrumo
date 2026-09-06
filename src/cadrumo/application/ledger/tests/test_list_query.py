"""Selection semantics for one Ledger transaction listing.

These assertions were unreachable while the logic lived in the CLI adapter: the
only coverage ran through a rendered projection over real encrypted storage, so
the ordering and paging rules could only be observed indirectly and at the cost
of a key derivation. Reading them here, against an injected catalogue, is what
makes the contract cheap enough to assert exhaustively -- and what lets a second
frontend rely on it rather than reimplementing it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.ledger_sort import LedgerSortField, LedgerSortOrder
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from ...review.filter import LedgerReviewFilterSpec
from ..list_query import LedgerTransactionListQuery, query_ledger_transaction_list, sort_ledger_results

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "11111111-1111-4111-8111-111111111111"


def _transaction(*, provider_id: str, amount: Decimal, group_label: str | None = None) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=f"row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": group_label,
            "created_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            "modified_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
        }
    )


def _query(**overrides: object) -> LedgerTransactionListQuery:
    return LedgerTransactionListQuery(spec=LedgerReviewFilterSpec(clauses=()), **overrides)


@contextmanager
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogueRepository]:
    """Persist rows through the real encrypted repository the query requires.

    The manual-ledger resolver refuses a protocol stand-in on purpose -- the
    write path uses methods the Protocol does not declare -- so a double here
    would be testing the refusal, not the query.
    """
    with TemporaryDirectory() as tmp, isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(TransactionCatalogue.from_transactions(transactions))
        yield TransactionCatalogueRepository(bucket_id=profile.bucket_id)


def _page(repository: TransactionCatalogueRepository, query: LedgerTransactionListQuery):
    return query_ledger_transaction_list(query, bucket_id=_BUCKET, transaction_repository=repository)


def test_an_unfiltered_listing_returns_every_row_and_is_not_truncated() -> None:
    """The baseline every other case is measured against."""
    with _stored(
        _transaction(provider_id="a", amount=Decimal("10.00")),
        _transaction(provider_id="b", amount=Decimal("20.00")),
    ) as repository:
        page = _page(repository, _query())

    assert page.total == 2
    assert len(page.results) == 2
    assert page.truncated is False
    assert page.bucket_id == _BUCKET


def test_total_counts_the_filtered_set_not_the_returned_window() -> None:
    """A window that hides rows must still say how many there were.

    Reporting the window length as the total is the failure this guards: an
    operator paging through work would be told the queue is as short as the
    page they can see.
    """
    with _stored(*(_transaction(provider_id=str(index), amount=Decimal("10.00")) for index in range(5))) as repository:
        page = _page(repository, _query(limit=2))

    assert page.total == 5
    assert len(page.results) == 2
    assert page.truncated is True


def test_a_window_that_starts_past_the_first_row_is_truncated() -> None:
    """Truncation covers an offset window, not only a short one."""
    with _stored(*(_transaction(provider_id=str(index), amount=Decimal("10.00")) for index in range(3))) as repository:
        page = _page(repository, _query(offset=1))

    assert len(page.results) == 2
    assert page.truncated is True


def test_a_group_selection_keeps_only_that_group() -> None:
    """Group is a filter over stored labels, applied before paging."""
    with _stored(
        _transaction(provider_id="a", amount=Decimal("10.00"), group_label="travel"),
        _transaction(provider_id="b", amount=Decimal("20.00"), group_label="office"),
    ) as repository:
        page = _page(repository, _query(group="travel"))

    assert page.total == 1
    assert page.results[0].transaction.group_label == "travel"


def test_descending_amount_reverses_the_ascending_order() -> None:
    """Sort direction is honoured on the axis, not just the tie-break."""
    with _stored(
        _transaction(provider_id="a", amount=Decimal("10.00")),
        _transaction(provider_id="b", amount=Decimal("30.00")),
        _transaction(provider_id="c", amount=Decimal("20.00")),
    ) as repository:
        ascending = _page(repository, _query(sort_by=LedgerSortField.AMOUNT))
        descending = _page(
            repository,
            _query(sort_by=LedgerSortField.AMOUNT, sort_order=LedgerSortOrder.DESC),
        )

    amounts = [result.transaction.raw.amount for result in ascending.results]
    assert amounts == sorted(amounts)
    assert [result.transaction.raw.amount for result in descending.results] == list(reversed(amounts))


def test_sorting_happens_before_paging() -> None:
    """A page must be the top of the sorted set, not the top of the stored one.

    Paging first and sorting the page would still return sorted rows, so the
    defect is invisible unless the first page is checked against the global
    ordering.
    """
    with _stored(
        _transaction(provider_id="a", amount=Decimal("30.00")),
        _transaction(provider_id="b", amount=Decimal("10.00")),
        _transaction(provider_id="c", amount=Decimal("20.00")),
    ) as repository:
        page = _page(repository, _query(sort_by=LedgerSortField.AMOUNT, limit=1))

    assert [result.transaction.raw.amount for result in page.results] == [Decimal("10.00")]


def test_ungrouped_rows_trail_named_groups_when_partitioning() -> None:
    """Rows with no group are last, so a named block is never split by them."""
    with _stored(
        _transaction(provider_id="a", amount=Decimal("10.00")),
        _transaction(provider_id="b", amount=Decimal("20.00"), group_label="office"),
    ) as repository:
        page = _page(repository, _query(by_group=True))

    assert [result.transaction.group_label for result in page.results] == ["office", None]


def test_excluding_model_rejected_rows_without_an_event_repository_refuses() -> None:
    """A missing dependency must refuse, never silently return unfiltered rows."""
    with (
        _stored(_transaction(provider_id="a", amount=Decimal("10.00"))) as repository,
        pytest.raises(ValueError, match="event history"),
    ):
        _page(repository, _query(exclude_llm_rejected=True))


def test_the_sort_is_stable_and_tie_broken_by_transaction_id() -> None:
    """Equal keys must order deterministically, or paging drifts between calls."""
    with _stored(
        _transaction(provider_id="a", amount=Decimal("10.00")),
        _transaction(provider_id="b", amount=Decimal("10.00")),
    ) as repository:
        page = _page(repository, _query(sort_by=LedgerSortField.AMOUNT))

    ordered = [result.transaction.transaction_id for result in page.results]
    assert ordered == sorted(ordered)


def test_sort_ledger_results_is_reusable_on_its_own() -> None:
    """The sort is public because a second frontend needs it without the query."""
    with _stored(
        _transaction(provider_id="a", amount=Decimal("30.00")),
        _transaction(provider_id="b", amount=Decimal("10.00")),
    ) as repository:
        results = _page(repository, _query()).results

    ordered = sort_ledger_results(results, sort_by=LedgerSortField.AMOUNT, sort_order=LedgerSortOrder.ASC)

    assert [item.transaction.raw.amount for item in ordered] == [Decimal("10.00"), Decimal("30.00")]
