"""A period-filtered Ledger listing over real encrypted storage, index fresh or stale.

A period page reads only the date partition of the bucket. That is only safe if
the page is the one a full scan would select, and if a stale plaintext date
index costs a slower read rather than a missing row. These tests seed a real
bucket through the production read composition, then compare the page served
from a complete index with the page served after the index is made incomplete,
where the repository's completeness gate must fall back to a full scan.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, select

from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.sql import orm
from ...adapters.persistence.storage.sql.session import session_scope
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.list_query import (
    LedgerTransactionListPageV1,
    LedgerTransactionListQuery,
    query_ledger_transaction_list,
)
from ...application.review.filter import LedgerReviewFilterSpec
from ...core.ledger_sort import LedgerSortField, LedgerSortOrder
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..ledger_action_composition import compose_ledger_read_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "55555555-5555-4555-8555-555555555555"


@dataclass(frozen=True)
class _Row:
    """One synthetic ledger row and the facts the listing filters and orders on."""

    provider_id: str
    booked: date
    value: date | None = None
    amount: Decimal = Decimal("10.00")
    group_label: str | None = None
    classification: BusinessClassification = BusinessClassification.BUSINESS
    accrued: date | None = None


#: Boundary rows around the fourth quarter of 2030. The listing keys on the
#: value date when present, else the booked date; the accrued rows are
#: criterio-de-caja rows whose devengo date sits apart from that filing date.
_ROWS: tuple[_Row, ...] = (
    _Row("q3-last-day", booked=date(2030, 9, 30)),
    _Row("q4-first-day", booked=date(2030, 10, 1), amount=Decimal("40.00"), group_label="office"),
    _Row("booked-q3-valued-q4", booked=date(2030, 9, 30), value=date(2030, 10, 1), amount=Decimal("5.00")),
    _Row(
        "q4-mid-travel",
        booked=date(2030, 11, 15),
        amount=Decimal("30.00"),
        group_label="travel",
        classification=BusinessClassification.NOT_YET_PROCESSED,
    ),
    _Row("q4-mid-office", booked=date(2030, 11, 15), amount=Decimal("20.00"), group_label="office"),
    _Row(
        "q4-last-day",
        booked=date(2030, 12, 31),
        amount=Decimal("15.00"),
        classification=BusinessClassification.NOT_YET_PROCESSED,
    ),
    _Row("booked-q4-valued-next-year", booked=date(2030, 12, 31), value=date(2031, 1, 1)),
    _Row("next-year-first-day", booked=date(2031, 1, 1)),
    _Row("same-quarter-prior-year", booked=date(2029, 11, 15)),
    _Row("filed-next-year-accrued-q4", booked=date(2031, 1, 15), amount=Decimal("1210.00"), accrued=date(2030, 11, 2)),
    _Row("filed-q4-accrued-q3", booked=date(2030, 12, 1), amount=Decimal("1210.00"), accrued=date(2030, 8, 3)),
)

#: Independently stated: the rows whose filing date falls in 2030-Q4.
_Q4_2030: frozenset[str] = frozenset(
    {
        "q4-first-day",
        "booked-q3-valued-q4",
        "q4-mid-travel",
        "q4-mid-office",
        "q4-last-day",
        "filed-q4-accrued-q3",
    }
)
_Q1_2031: frozenset[str] = frozenset(
    {"booked-q4-valued-next-year", "next-year-first-day", "filed-next-year-accrued-q4"}
)


def _transaction(row: _Row) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=row.provider_id,
        booked_date=row.booked,
        value_date=row.value,
        amount=row.amount,
        currency="EUR",
        counterparty="Proveedor Sintetico SL",
        description=f"row {row.provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2031, 2, 1, 9, 0, tzinfo=UTC),
            provider_name="synthetic provider",
        ),
        raw_fields={"Concepto": row.provider_id},
    )
    fields: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "business_classification": row.classification,
        "source_jurisdiction": "ES",
        "group_label": row.group_label,
        "created_at": datetime(2031, 2, 1, 9, 0, tzinfo=UTC),
        "modified_at": datetime(2031, 2, 1, 9, 0, tzinfo=UTC),
    }
    if row.accrued is not None:
        fields |= {
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory("domestic_general"),
            "cash_accounting_treatment": IvaCashAccountingTreatment("supplier_regime"),
            "operation_date": row.accrued,
            "cash_accounting_payment_evidence": (
                IvaCashAccountingPaymentEvidence(
                    payment_date=row.value or row.booked,
                    taxable_base=Decimal("1000.00"),
                    iva_amount=Decimal("210.00"),
                    recargo_amount=Decimal("0.00"),
                ),
            ),
            "classified_at": datetime(2031, 2, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    return Transaction.model_validate(fields)


def _query(filters: tuple[str, ...], **options: object) -> LedgerTransactionListQuery:
    return LedgerTransactionListQuery.model_validate(
        {"spec": LedgerReviewFilterSpec.from_strings(filters), **options},
    )


_Q4 = ("period=4T", "year=2030")

_Q4_BY_DATE = _query(_Q4, sort_by=LedgerSortField.DATE)
_Q4_PAGES = (
    _query(_Q4, sort_by=LedgerSortField.DATE, limit=2),
    _query(_Q4, sort_by=LedgerSortField.DATE, limit=2, offset=2),
    _query(_Q4, sort_by=LedgerSortField.DATE, limit=2, offset=4),
)
_Q4_OFFICE = _query(_Q4, group="office", sort_by=LedgerSortField.DATE)
_Q4_PENDING = _query((*_Q4, "status=pending"))
_Q1_2031_BY_DATE = _query(("period=1T", "year=2031"), sort_by=LedgerSortField.DATE)
_EMPTY_PERIOD = _query(("period=2T", "year=2030"))

#: The listing shapes whose pages must not depend on which read path served them.
_QUERIES: tuple[LedgerTransactionListQuery, ...] = (
    _query(_Q4),
    _Q4_BY_DATE,
    *_Q4_PAGES,
    _query(_Q4, sort_by=LedgerSortField.AMOUNT, sort_order=LedgerSortOrder.DESC),
    _query(_Q4, by_group=True),
    _Q4_OFFICE,
    _Q4_PENDING,
    _query(("period=12", "year=2030"), sort_by=LedgerSortField.DATE),
    _query(("period=01", "year=2031"), sort_by=LedgerSortField.DATE),
    _Q1_2031_BY_DATE,
    _EMPTY_PERIOD,
    _query(("period=0A", "year=2030"), sort_by=LedgerSortField.DATE, limit=3, offset=1),
)


@pytest.fixture
def transactions(authority_operation: PinnedAuthorityOperation) -> dict[str, Transaction]:
    """Build the boundary rows under the pinned authority their IVA vocabulary needs."""
    del authority_operation
    return {row.provider_id: _transaction(row) for row in _ROWS}


@pytest.fixture
def seeded_profile(tmp_path: Path, transactions: dict[str, Transaction]) -> Iterator[TestRuntimeProfile]:
    """Yield a real bucket holding the boundary rows with a complete date index."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        TransactionCatalogueRepository(bucket_id=_BUCKET).save(
            TransactionCatalogue.from_transactions(transactions.values())
        )
        yield profile


def _pages(operation: PinnedAuthorityOperation) -> tuple[LedgerTransactionListPageV1, ...]:
    ports = compose_ledger_read_ports(bucket_id=_BUCKET, operation=operation)
    return tuple(query_ledger_transaction_list(query, bucket_id=_BUCKET, ports=ports) for query in _QUERIES)


def _index_is_complete(window: tuple[date, date]) -> bool:
    return TransactionCatalogueRepository(bucket_id=_BUCKET).partition_by_date_range(*window).index_complete


def _drop_index_rows(profile: TestRuntimeProfile, transaction_ids: frozenset[str]) -> None:
    """Remove date-index rows as a crash between the encrypted commit and the index sync would."""
    condition = (orm.TransactionDateIndexRow.bucket_id == _BUCKET) & orm.TransactionDateIndexRow.transaction_id.in_(
        sorted(transaction_ids)
    )
    with session_scope(profile.repository.engine) as session:
        session.execute(delete(orm.TransactionDateIndexRow).where(condition))


def _indexed_ids(profile: TestRuntimeProfile) -> frozenset[str]:
    with session_scope(profile.repository.engine) as session:
        return frozenset(
            session.execute(
                select(orm.TransactionDateIndexRow.transaction_id).where(
                    orm.TransactionDateIndexRow.bucket_id == _BUCKET,
                ),
            ).scalars()
        )


def _provider_ids(page: LedgerTransactionListPageV1) -> list[str]:
    return [item.transaction.raw.provider_transaction_id for item in page.results]


def test_a_period_page_from_the_date_index_selects_exactly_the_filing_date_window(
    seeded_profile: TestRuntimeProfile,
    authority_operation: PinnedAuthorityOperation,
    transactions: dict[str, Transaction],
) -> None:
    """Boundary dates, the value-date key and devengo-only candidates resolve as stated."""
    assert _index_is_complete((date(2030, 10, 1), date(2030, 12, 31)))

    pages = dict(zip(_QUERIES, _pages(authority_operation), strict=True))

    q4 = pages[_Q4_BY_DATE]
    assert set(_provider_ids(q4)) == _Q4_2030
    assert q4.total == len(_Q4_2030)
    assert q4.truncated is False
    filing_dates = [item.transaction.raw.value_date or item.transaction.raw.booked_date for item in q4.results]
    assert filing_dates == sorted(filing_dates)
    assert [item.transaction for item in q4.results] == [transactions[provider_id] for provider_id in _provider_ids(q4)]

    paged = [pages[query] for query in _Q4_PAGES]
    assert [provider_id for page in paged for provider_id in _provider_ids(page)] == _provider_ids(q4)
    assert [page.total for page in paged] == [len(_Q4_2030)] * 3
    assert all(page.truncated for page in paged)

    assert set(_provider_ids(pages[_Q1_2031_BY_DATE])) == _Q1_2031
    assert _provider_ids(pages[_Q4_PENDING]) == ["q4-mid-travel", "q4-last-day"]
    assert _provider_ids(pages[_Q4_OFFICE]) == ["q4-first-day", "q4-mid-office"]

    empty = pages[_EMPTY_PERIOD]
    assert empty.results == ()
    assert empty.total == 0
    assert empty.truncated is False


@pytest.mark.parametrize(
    "dropped",
    [
        pytest.param(("q4-mid-office",), id="an-in-window-row-lost-its-index-entry"),
        pytest.param(("next-year-first-day", "same-quarter-prior-year"), id="out-of-window-rows-lost-their-entries"),
        pytest.param(None, id="the-whole-index-is-missing"),
    ],
)
def test_a_stale_date_index_falls_back_to_the_full_scan_page(
    seeded_profile: TestRuntimeProfile,
    authority_operation: PinnedAuthorityOperation,
    transactions: dict[str, Transaction],
    dropped: tuple[str, ...] | None,
) -> None:
    """An incomplete index costs a full scan, never a row: every page matches the complete-index page.

    Losing an in-window row's entry is the dangerous case. A read that trusted
    the index would select ids from it, find that row absent, and drop it from
    the page with nothing to say it was missing.
    """
    complete_pages = _pages(authority_operation)
    assert _index_is_complete((date(2030, 10, 1), date(2030, 12, 31)))

    missing = frozenset(
        transactions[provider_id].transaction_id for provider_id in (dropped if dropped is not None else transactions)
    )
    _drop_index_rows(seeded_profile, missing)
    assert _indexed_ids(seeded_profile).isdisjoint(missing), (
        "fixture must leave the index without the dropped rows for this proof to mean anything"
    )
    assert not _index_is_complete((date(2030, 10, 1), date(2030, 12, 31)))

    stale_pages = _pages(authority_operation)

    for query, complete, stale in zip(_QUERIES, complete_pages, stale_pages, strict=True):
        assert stale == complete, f"stale-index page differs from the complete-index page for {query!r}"
    assert set(_provider_ids(stale_pages[_QUERIES.index(_Q4_BY_DATE)])) == _Q4_2030
