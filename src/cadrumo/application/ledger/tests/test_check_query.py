"""The readiness conjunction, and the periods a sweep actually covers.

Readiness draws on two independent sources, and the case that matters is the
one where they disagree: a ledger with no preflight issue but a one-sided
invoice link is NOT ready, because the two catalogues disagree about a fact a
filing would rest on. That conjunction was stated three times in the CLI verb
with three different spellings, so nothing held the branches together.

The year derivation is the other decision covered here. A sweep over years the
ledger does not span would report on nothing; a sweep that misses a year would
declare a ledger ready without looking at part of it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.invoice_link import LinkInconsistencyDirection
from ....domain.invoices.service import LinkInconsistency
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from ..check_query import ledger_check_years, read_ledger_check

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "66666666-6666-4666-8666-666666666666"


def _transaction(
    *,
    provider_id: str,
    booked: date,
    classification: BusinessClassification = BusinessClassification.PERSONAL,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked,
        value_date=None,
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description="office supplies",
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
            # PERSONAL by default: a deductible BUSINESS row without a
            # category legitimately raises preflight issues, which would
            # make "links are the only cause" untestable.
            "business_classification": classification,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            "modified_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
        }
    )


def _no_links(*, bucket_id: str) -> tuple[LinkInconsistency, ...]:
    del bucket_id
    return ()


def _one_link(*, bucket_id: str) -> tuple[LinkInconsistency, ...]:
    del bucket_id
    return (
        LinkInconsistency(
            invoice_id="inv-1",
            transaction_id="a" * 64,
            direction=LinkInconsistencyDirection.INVOICE_ONLY,
        ),
    )


@contextmanager
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogue]:
    """Persist rows through the real repository, then hand back the catalogue."""
    with TemporaryDirectory() as tmp, isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(TransactionCatalogue.from_transactions(transactions))
        yield TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()


def test_the_years_swept_come_from_the_rows_not_the_calendar() -> None:
    """A sweep must cover exactly the years the ledger spans."""
    catalogue = TransactionCatalogue.from_transactions(
        (
            _transaction(provider_id="a", booked=date(2023, 6, 1)),
            _transaction(provider_id="b", booked=date(2025, 2, 3)),
            _transaction(provider_id="c", booked=date(2023, 9, 9)),
        )
    )

    assert ledger_check_years(catalogue) == (2023, 2025)


def test_an_empty_ledger_spans_no_years() -> None:
    """Nothing to check is a real state, distinct from a year with no issues."""
    assert ledger_check_years(TransactionCatalogue()) == ()


def test_a_clean_ledger_with_no_link_problems_is_ready() -> None:
    """The baseline both other cases are measured against."""
    with _stored(_transaction(provider_id="a", booked=date(2024, 4, 10))) as catalogue:
        check = read_ledger_check(bucket_id=_BUCKET, transactions=catalogue, link_reader=_no_links)

    assert check.ready is True
    assert check.link_inconsistencies == ()
    assert check.periods == ("2024",)


def test_a_one_sided_invoice_link_alone_makes_a_ledger_not_ready() -> None:
    """The conjunction's load-bearing half: links can block on their own.

    A branch spelling readiness as preflight-only would pass this ledger, and
    the operator would file against catalogues that disagree.
    """
    with _stored(_transaction(provider_id="a", booked=date(2024, 4, 10))) as catalogue:
        check = read_ledger_check(bucket_id=_BUCKET, transactions=catalogue, link_reader=_one_link)

    assert check.issues == ()
    assert len(check.link_inconsistencies) == 1
    assert check.ready is False


def test_an_empty_ledger_is_ready_only_when_its_links_are_clean() -> None:
    """The empty branch used the same conjunction, not a shortcut."""
    empty = TransactionCatalogue()

    clean = read_ledger_check(bucket_id=_BUCKET, transactions=empty, link_reader=_no_links)
    dirty = read_ledger_check(bucket_id=_BUCKET, transactions=empty, link_reader=_one_link)

    assert clean.ready is True
    assert clean.periods == ()
    assert clean.checked_transaction_count == 0
    assert dirty.ready is False


def test_an_explicit_period_reports_only_that_period() -> None:
    """A named period narrows the report rather than sweeping everything."""
    from ....core.period import Period

    with _stored(
        _transaction(provider_id="a", booked=date(2024, 4, 10)),
        _transaction(provider_id="b", booked=date(2023, 4, 10)),
    ) as catalogue:
        check = read_ledger_check(
            bucket_id=_BUCKET,
            transactions=catalogue,
            period=Period.from_year_and_code(2024, "0A"),
            link_reader=_no_links,
        )

    assert len(check.periods) == 1
    assert "2024" in check.periods[0]
