"""Selection semantics for one Ledger transaction listing.

These assertions were unreachable while the logic lived in the CLI adapter: the
only coverage ran through a rendered projection over real encrypted storage, so
the ordering and paging rules could only be observed indirectly and at the cost
of a key derivation. Reading them here, against an injected catalogue, is what
makes the contract cheap enough to assert exhaustively -- and what lets a second
frontend rely on it rather than reimplementing it.
"""

from __future__ import annotations

from collections.abc import Generator, Iterable
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypedDict, Unpack, cast, override

import pytest
from pydantic import ValidationError

from ....core.ledger_sort import LedgerSortField, LedgerSortOrder
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from ....domain.transactions.date_partition import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
)
from ....domain.transactions.dates import transaction_eligible_date_span
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios.model import UsageRatioProfile
from ...review.filter import LedgerReviewFilterSpec
from ..action_ports import LedgerActionPorts
from ..list_operation import ledger_list_row
from ..list_query import LedgerTransactionListQuery, query_ledger_transaction_list, sort_ledger_results
from ..transaction_projection import LedgerTransactionReviewProjection

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "11111111-1111-4111-8111-111111111111"


def _transaction(
    *,
    provider_id: str,
    amount: Decimal,
    group_label: str | None = None,
    own_account_id: str | None = None,
    filing_date: date = date(2024, 4, 10),
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=filing_date,
        value_date=filing_date,
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
            "own_account_id": own_account_id,
            "created_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            "modified_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
        }
    )


class _QueryOverrides(TypedDict, total=False):
    """The fields a test may vary on a list query.

    Typed rather than ``object`` because the per-field types have to survive
    ``**`` unpacking into the model: a bare ``object`` widens every value and
    the model's own bool, int, and enum fields can no longer be checked.
    """

    group: str | None
    by_group: bool
    limit: int | None
    offset: int
    sort_by: LedgerSortField | None
    sort_order: LedgerSortOrder
    exclude_llm_rejected: bool


def _query(**overrides: Unpack[_QueryOverrides]) -> LedgerTransactionListQuery:
    return LedgerTransactionListQuery(spec=LedgerReviewFilterSpec(clauses=()), **overrides)


@contextmanager
def _stored(*transactions: Transaction) -> Generator[TransactionCatalogueRepositoryProtocol]:
    """Build a deterministic transaction catalogue through the read protocol."""
    yield _InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
    )


class _InMemoryTransactionRepository(TransactionCatalogueRepositoryProtocol):
    """Deterministic inward fake for the application transaction read port."""

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        self._bucket_id = bucket_id
        self._catalogue = catalogue

    @property
    @override
    def bucket_id(self) -> str:
        return self._bucket_id

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    @override
    def load(self) -> TransactionCatalogue:
        return self._catalogue

    @override
    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    @override
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    ),
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    @override
    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue


class _MissingEventHistoryRepository:
    """Preserve the refusal contract when rejection filtering lacks events."""

    @staticmethod
    def load() -> object:
        raise ValueError("event history repository is required")


def _page(repository: TransactionCatalogueRepositoryProtocol, query: LedgerTransactionListQuery):
    with bundled_indexed_authority().operation() as operation:
        ports = LedgerActionPorts(
            operation=operation,
            transaction_repository=cast(Any, repository),
            bucket_event_repository=cast(Any, _MissingEventHistoryRepository()),
            invoice_repository=cast(Any, None),
            attachment_store=cast(Any, None),
            usage_ratio_profile=UsageRatioProfile(),
            usage_ratio_profile_loader=cast(Any, None),
            work_unit_repository=cast(Any, None),
            calculation_repository=cast(Any, None),
            purchase_invoice_evidence_records=(),
        )
        return query_ledger_transaction_list(query, bucket_id=_BUCKET, ports=ports)


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


def test_an_account_filter_keeps_only_rows_bound_to_that_own_account() -> None:
    """``account=`` selects one own account; unbound rows and other accounts drop out."""
    with _stored(
        _transaction(provider_id="a", amount=Decimal("10.00"), own_account_id="acc-01"),
        _transaction(provider_id="b", amount=Decimal("20.00"), own_account_id="acc-02"),
        _transaction(provider_id="c", amount=Decimal("30.00")),
    ) as repository:
        page = _page(
            repository,
            LedgerTransactionListQuery(spec=LedgerReviewFilterSpec.from_strings(["account=acc-01"])),
        )

    assert [item.transaction.raw.provider_transaction_id for item in page.results] == ["a"]
    assert page.total == 1


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


def _cash_accounting_transaction(*, provider_id: str, filing_date: date, operation_date: date) -> Transaction:
    """A criterio-de-caja row whose devengo date sits apart from its ledger filing date."""
    base = _transaction(provider_id=provider_id, amount=Decimal("1210.00"), filing_date=filing_date)
    return Transaction.model_validate(
        {
            **base.model_dump(),
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("domestic_general"),
            "cash_accounting_treatment": IvaCashAccountingTreatment("supplier_regime"),
            "operation_date": operation_date,
            "cash_accounting_payment_evidence": (
                IvaCashAccountingPaymentEvidence(
                    payment_date=filing_date,
                    taxable_base=Decimal("1000.00"),
                    iva_amount=Decimal("210.00"),
                    recargo_amount=Decimal("0.00"),
                ),
            ),
            "classified_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


class _PartitionOnlyRepository(_InMemoryTransactionRepository):
    """A read port that serves a period read from its date partition alone.

    The in-window half is chosen by overlap with each row's eligible date span,
    the same candidate superset the stored partition returns, so it can hold a
    row whose filing date lies outside the window. A whole-catalogue read
    refuses, which is what makes reaching for it observable.
    """

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        super().__init__(bucket_id=bucket_id, catalogue=catalogue)
        self.windows: list[tuple[date, date]] = []

    @override
    def load(self) -> TransactionCatalogue:
        raise AssertionError("a period listing read the whole catalogue")

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        self.windows.append((start, end))
        in_window: list[Transaction] = []
        for transaction in self._catalogue:
            earliest, latest = transaction_eligible_date_span(transaction)
            if earliest <= end and latest >= start:
                in_window.append(transaction)
        return LedgerDatePartition(in_window=TransactionCatalogue.from_transactions(in_window), index_complete=True)


def _period_query(period: str, year: int, **overrides: Unpack[_QueryOverrides]) -> LedgerTransactionListQuery:
    return LedgerTransactionListQuery(
        spec=LedgerReviewFilterSpec.from_strings([f"period={period}", f"year={year}"]), **overrides
    )


def test_a_period_listing_reads_only_that_periods_date_partition() -> None:
    """A period filter asks for its own window and never decrypts the whole bucket."""
    repository = _PartitionOnlyRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(
            (
                _transaction(provider_id="before", amount=Decimal("1.00"), filing_date=date(2024, 3, 31)),
                _transaction(provider_id="first", amount=Decimal("2.00"), filing_date=date(2024, 4, 1)),
                _transaction(provider_id="last", amount=Decimal("3.00"), filing_date=date(2024, 6, 30)),
                _transaction(provider_id="after", amount=Decimal("4.00"), filing_date=date(2024, 7, 1)),
            )
        ),
    )

    page = _page(repository, _period_query("2T", 2024, sort_by=LedgerSortField.DATE))

    assert repository.windows == [(date(2024, 4, 1), date(2024, 6, 30))]
    assert [item.transaction.raw.provider_transaction_id for item in page.results] == ["first", "last"]
    assert page.total == 2
    assert page.truncated is False


def test_a_period_listing_narrows_the_partition_superset_to_the_filing_date() -> None:
    """A row the partition offers only for its devengo date stays off the period page.

    The partition selects candidates by eligible date span, so a criterio-de-caja
    row filed in July but accrued in May is in its in-window half. The listing
    filters on the ledger filing date; showing that row would make the period
    page disagree with the full-scan page.
    """
    accrued_in_window = _cash_accounting_transaction(
        provider_id="accrued-in-window", filing_date=date(2024, 7, 15), operation_date=date(2024, 5, 2)
    )
    filed_in_window = _cash_accounting_transaction(
        provider_id="filed-in-window", filing_date=date(2024, 5, 20), operation_date=date(2024, 3, 2)
    )
    repository = _PartitionOnlyRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(
            (
                accrued_in_window,
                filed_in_window,
                _transaction(provider_id="plain", amount=Decimal("5.00"), filing_date=date(2024, 6, 1)),
            )
        ),
    )
    offered = repository.partition_by_date_range(date(2024, 4, 1), date(2024, 6, 30)).in_window
    assert accrued_in_window.transaction_id in offered.transactions, (
        "fixture must place the devengo-only row inside the partition superset for this proof to mean anything"
    )

    page = _page(repository, _period_query("2T", 2024, sort_by=LedgerSortField.DATE))

    assert [item.transaction.raw.provider_transaction_id for item in page.results] == ["filed-in-window", "plain"]
    assert page.total == 2


def test_a_listing_without_a_period_reads_the_whole_catalogue() -> None:
    """Only a period filter can bound the read; other clauses still see every row."""
    repository = _PartitionOnlyRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions((_transaction(provider_id="a", amount=Decimal("1.00")),)),
    )

    with pytest.raises(AssertionError, match="whole catalogue"):
        _page(repository, _query())
    assert repository.windows == []


def test_a_listed_row_names_the_own_account_it_is_bound_to_and_never_its_number() -> None:
    bound = ledger_list_row(_transaction(provider_id="a", amount=Decimal("10.00"), own_account_id="acc-01"))
    unbound = ledger_list_row(_transaction(provider_id="b", amount=Decimal("20.00")))

    assert bound.own_account_id == "acc-01"
    assert unbound.own_account_id is None
    assert "acc-01" not in bound.transaction.model_dump_json()
    with pytest.raises(ValidationError):
        LedgerTransactionReviewProjection(
            transaction=bound.transaction,
            review_status=bound.review_status,
            group_label=None,
            own_account_id="ES9121000418450200051332",
        )
