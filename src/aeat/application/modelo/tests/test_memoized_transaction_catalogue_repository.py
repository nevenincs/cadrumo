"""Unit coverage for :class:`_MemoizedTransactionCatalogueRepository`.

Isolates the read-through cache's bookkeeping from the encrypted storage
boundary with a lightweight counting fake that satisfies
:class:`~domain.transactions.TransactionCatalogueRepositoryProtocol` (no I/O,
pure call-count logic) — the pure-logic isolation case the project's testing
mandate carves out for unit tests. Real-storage behaviour of ``load`` and
``load_for_date_range`` is covered separately at the persistence boundary
(``test_transactions_repository_roundtrip.py``,
``test_transaction_date_index.py``).
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.transactions import TransactionCatalogue
from .._calculation_actions import _MemoizedTransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _CountingTransactionCatalogueRepository:
    """Fake satisfying ``TransactionCatalogueRepositoryProtocol`` that counts calls."""

    def __init__(self, *, bucket_id: str = "counting-bucket") -> None:
        self._bucket_id = bucket_id
        self.load_calls = 0
        self.load_for_date_range_calls: list[tuple[date, date]] = []
        self.save_calls = 0

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self) -> bool:
        return True

    def load(self) -> TransactionCatalogue:
        self.load_calls += 1
        return TransactionCatalogue.from_transactions([])

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        self.load_for_date_range_calls.append((start, end))
        return TransactionCatalogue.from_transactions([])

    def save(self, catalogue: TransactionCatalogue) -> None:
        self.save_calls += 1


def test_load_is_memoized_across_repeated_calls() -> None:
    """A second ``load()`` call must not re-hit the wrapped repository."""

    counting = _CountingTransactionCatalogueRepository()
    memoized = _MemoizedTransactionCatalogueRepository(counting)

    first = memoized.load()
    second = memoized.load()
    third = memoized.load()

    assert counting.load_calls == 1
    assert first is second is third


def test_load_for_date_range_is_memoized_for_the_identical_window() -> None:
    """Repeated calls with the SAME window must hit the wrapped repository once.

    Guards against a future resolver pair that requests the identical window
    in one calculate invocation (issue #408) re-scanning independently
    instead of sharing one targeted decrypt.
    """

    counting = _CountingTransactionCatalogueRepository()
    memoized = _MemoizedTransactionCatalogueRepository(counting)
    window = (date(2024, 1, 1), date(2024, 3, 31))

    first = memoized.load_for_date_range(*window)
    second = memoized.load_for_date_range(*window)

    assert counting.load_for_date_range_calls == [window]
    assert first is second


def test_load_for_date_range_caches_distinct_windows_independently() -> None:
    """A different window must not collide with a previously cached one."""

    counting = _CountingTransactionCatalogueRepository()
    memoized = _MemoizedTransactionCatalogueRepository(counting)
    quarterly_window = (date(2024, 1, 1), date(2024, 3, 31))
    annual_window = (date(2024, 1, 1), date(2024, 12, 31))

    memoized.load_for_date_range(*quarterly_window)
    memoized.load_for_date_range(*annual_window)
    memoized.load_for_date_range(*quarterly_window)

    assert counting.load_for_date_range_calls == [quarterly_window, annual_window]


def test_load_and_load_for_date_range_caches_are_independent() -> None:
    """The full-scan cache and the windowed cache must not share state."""

    counting = _CountingTransactionCatalogueRepository()
    memoized = _MemoizedTransactionCatalogueRepository(counting)

    memoized.load()
    memoized.load_for_date_range(date(2024, 1, 1), date(2024, 3, 31))

    assert counting.load_calls == 1
    assert counting.load_for_date_range_calls == [(date(2024, 1, 1), date(2024, 3, 31))]


def test_save_and_exists_are_never_memoized() -> None:
    """``save`` and ``exists`` delegate straight through on every call."""

    counting = _CountingTransactionCatalogueRepository()
    memoized = _MemoizedTransactionCatalogueRepository(counting)

    memoized.exists()
    memoized.exists()
    memoized.save(TransactionCatalogue.from_transactions([]))
    memoized.save(TransactionCatalogue.from_transactions([]))

    assert counting.save_calls == 2


def test_bucket_id_delegates_to_wrapped_repository() -> None:
    """The wrapper exposes the wrapped repository's bound bucket id."""

    counting = _CountingTransactionCatalogueRepository(bucket_id="a-real-bucket-id")
    memoized = _MemoizedTransactionCatalogueRepository(counting)

    assert memoized.bucket_id == "a-real-bucket-id"
