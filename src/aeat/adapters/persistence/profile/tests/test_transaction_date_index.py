"""Coverage for the plaintext transaction date/period participation index.

:meth:`TransactionCatalogueRepository.load_for_date_range` selects candidate
transaction ids from the plaintext, non-sensitive
:class:`~adapters.persistence.storage.sql.TransactionDateIndexRow` routing
table before decrypting only that subset -- never a full-namespace scan (issue
``#408``). The index is derived and rebuildable
(``ledger-participation-index-is-derived-rebuildable``): correctness never
depends on its presence or freshness, so every correctness assertion here is
mirrored by an anti-tautology proof that the fallback still reproduces the
unfiltered result when the index is missing, incomplete, or stale.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy import inspect as sa_inspect

from .....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
)
from .....tests.secure_sql import isolated_runtime_profile
from ...storage.sql import _orm
from ...storage.sql.session import session_scope
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"

_NON_SENSITIVE_COLUMNS = frozenset({"id", "bucket_id", "transaction_id", "filing_date", "filing_year"})


def _raw(provider_id: str, filing_date: date, amount: Decimal, description: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=filing_date,
        value_date=filing_date,
        amount=amount,
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def _transaction(*, provider_id: str, filing_date: date, amount: Decimal, description: str) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, filing_date, amount, description),
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
        },
    )


def test_date_index_table_carries_only_non_sensitive_routing_columns(
    tmp_path: Path,
) -> None:
    """Schema assertion: the plaintext index has no amount/counterparty/NIF column.

    Per ``sensitive-financial-data-secure-storage-only``: this table is
    plaintext by design, so it must never carry a financial-content column.
    Reflects the live table via SQLAlchemy inspection rather than trusting the
    ORM class docstring, so a future column addition that widens the schema
    fails this test even if the docstring is not updated.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        engine = profile.repository.engine
        # ``MetaData.tables`` is properly typed ``dict[str, Table]``; the ORM
        # class's own ``__table__`` attribute is typed as the more general
        # ``FromClause`` in the SQLAlchemy stubs even though it is always a
        # real ``Table`` at runtime for a mapped class, so looking it up by
        # name avoids that stub-precision gap.
        table = _orm.Base.metadata.tables[_orm.TransactionDateIndexRow.__tablename__]
        _orm.Base.metadata.create_all(engine, tables=[table])
        columns = {column["name"] for column in sa_inspect(engine).get_columns("transaction_date_index")}

    assert columns == _NON_SENSITIVE_COLUMNS


def test_load_for_date_range_returns_exactly_the_in_window_transactions(
    tmp_path: Path,
) -> None:
    """The plaintext index selects the correct candidate subset before decrypt."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        inside_q1 = _transaction(
            provider_id="row-q1", filing_date=date(2024, 2, 10), amount=Decimal("10.00"), description="Q1 expense"
        )
        inside_q1_edge = _transaction(
            provider_id="row-q1-edge",
            filing_date=date(2024, 3, 31),
            amount=Decimal("20.00"),
            description="Q1 last day",
        )
        outside_q2 = _transaction(
            provider_id="row-q2", filing_date=date(2024, 4, 1), amount=Decimal("30.00"), description="Q2 expense"
        )
        catalogue = TransactionCatalogue.from_transactions([inside_q1, inside_q1_edge, outside_q2])
        repo.save(catalogue)

        filtered = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load_for_date_range(
            date(2024, 1, 1), date(2024, 3, 31)
        )

    assert set(filtered.transactions) == {inside_q1.transaction_id, inside_q1_edge.transaction_id}
    assert outside_q2.transaction_id not in filtered.transactions
    assert filtered.transactions[inside_q1.transaction_id] == inside_q1
    assert filtered.transactions[inside_q1_edge.transaction_id] == inside_q1_edge


def test_load_for_date_range_matches_full_load_filtered_in_memory(
    tmp_path: Path,
) -> None:
    """Aggregation-identity proof: index-backed and full-scan filtering agree.

    Builds a catalogue spanning several windows, then asserts the index-backed
    :meth:`load_for_date_range` result equals a full :meth:`load` filtered in
    memory by the identical predicate every ledger aggregator already applies
    (``start <= filing_date <= end``, mirroring :meth:`Period.contains`). This
    is the correctness guarantee the perf optimisation must never break.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        rows = [
            _transaction(
                provider_id=f"row-{i}",
                filing_date=date(2022 + (i % 4), (i % 12) + 1, 15),
                amount=Decimal("5.00") * i,
                description=f"txn {i}",
            )
            for i in range(1, 13)
        ]
        repo.save(TransactionCatalogue.from_transactions(rows))

        start, end = date(2023, 1, 1), date(2024, 12, 31)
        via_index = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load_for_date_range(start, end)
        full = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    expected_ids = {
        transaction_id
        for transaction_id, transaction in full.transactions.items()
        if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
    }
    assert set(via_index.transactions) == expected_ids
    assert dict(via_index.transactions) == {tid: full.transactions[tid] for tid in expected_ids}


def test_date_index_is_co_written_atomically_with_save(
    tmp_path: Path,
) -> None:
    """The index rows exist immediately after ``save``, with no separate sync call."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txn = _transaction(
            provider_id="row-atomic", filing_date=date(2024, 5, 20), amount=Decimal("15.00"), description="expense"
        )
        repo.save(TransactionCatalogue.from_transactions([txn]))

        engine = profile.repository.engine
        with session_scope(engine) as session:
            rows = session.execute(
                select(_orm.TransactionDateIndexRow).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            ).all()

    assert len(rows) == 1
    (row_tuple,) = rows
    row = row_tuple[0]
    assert row.transaction_id == txn.transaction_id
    assert row.filing_date == date(2024, 5, 20)
    assert row.filing_year == 2024


def test_rebuild_date_index_reconstructs_a_dropped_index(
    tmp_path: Path,
) -> None:
    """``rebuild_date_index`` regenerates the index from the encrypted catalogue.

    Per ``ledger-participation-index-is-derived-rebuildable``: dropping every
    index row for this bucket must not lose data -- a full decrypt-scan
    rebuild must restore the exact same index a fresh save would have produced.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        rows = [
            _transaction(
                provider_id=f"row-rebuild-{i}",
                filing_date=date(2024, (i % 12) + 1, 10),
                amount=Decimal("7.00"),
                description=f"txn {i}",
            )
            for i in range(1, 6)
        ]
        repo.save(TransactionCatalogue.from_transactions(rows))

        engine = profile.repository.engine
        with session_scope(engine) as session:
            session.execute(
                delete(_orm.TransactionDateIndexRow).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            )

        with session_scope(engine) as session:
            remaining = session.execute(
                select(_orm.TransactionDateIndexRow.id).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            ).all()
        assert remaining == [], "fixture must actually drop the index for this proof to be meaningful"

        written = repo.rebuild_date_index()

        with session_scope(engine) as session:
            rebuilt = (
                session.execute(
                    select(_orm.TransactionDateIndexRow.transaction_id).where(
                        _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                    ),
                )
                .scalars()
                .all()
            )

    assert written == 5
    assert set(rebuilt) == {row.transaction_id for row in rows}


def test_load_for_date_range_falls_back_to_full_scan_when_index_is_missing(
    tmp_path: Path,
) -> None:
    """Anti-tautology proof: dropping the index does not change the answer.

    If the index rows for this bucket are gone (or drifted relative to the
    encrypted membership index), :meth:`load_for_date_range` must fall back to
    a full decrypt scan filtered in memory and reproduce the identical result
    -- correctness never depends on the index being present, per
    ``ledger-participation-index-is-derived-rebuildable``. This is the proof
    that the perf path is a pure optimisation, not a second source of truth.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        inside = _transaction(
            provider_id="row-fallback-in", filing_date=date(2024, 2, 1), amount=Decimal("9.00"), description="in"
        )
        outside = _transaction(
            provider_id="row-fallback-out", filing_date=date(2024, 6, 1), amount=Decimal("11.00"), description="out"
        )
        repo.save(TransactionCatalogue.from_transactions([inside, outside]))

        engine = profile.repository.engine
        with session_scope(engine) as session:
            session.execute(
                delete(_orm.TransactionDateIndexRow).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            )
        with session_scope(engine) as session:
            remaining = session.execute(
                select(_orm.TransactionDateIndexRow.id).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            ).all()
        assert remaining == [], "fixture must actually drop the index for this proof to be meaningful"

        via_fallback = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load_for_date_range(
            date(2024, 1, 1), date(2024, 3, 31)
        )

    assert set(via_fallback.transactions) == {inside.transaction_id}
    assert via_fallback.transactions[inside.transaction_id] == inside


def test_date_index_unchanged_transaction_row_is_not_rewritten(
    tmp_path: Path,
) -> None:
    """Re-saving an unchanged catalogue leaves the existing index row's surrogate id intact.

    Mirrors the diff-based sync the encrypted rows already use: an unchanged
    filing date must not trigger a delete+insert cycle, only a genuinely new,
    removed, or date-changed transaction should touch the index.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        txn = _transaction(
            provider_id="row-stable", filing_date=date(2024, 3, 3), amount=Decimal("42.00"), description="stable"
        )
        catalogue = TransactionCatalogue.from_transactions([txn])
        repo.save(catalogue)

        engine = profile.repository.engine
        with session_scope(engine) as session:
            (first_id,) = session.execute(
                select(_orm.TransactionDateIndexRow.id).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            ).one()

        # Re-save the identical catalogue (no content change).
        repo.save(catalogue)

        with session_scope(engine) as session:
            (second_id,) = session.execute(
                select(_orm.TransactionDateIndexRow.id).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            ).one()

    assert first_id == second_id


def test_date_index_updates_when_filing_date_changes(
    tmp_path: Path,
) -> None:
    """Changing a transaction's filing date updates its index row, not a stale duplicate."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        original_txn = _transaction(
            provider_id="row-moved", filing_date=date(2024, 1, 5), amount=Decimal("60.00"), description="moved"
        )
        repo.save(TransactionCatalogue.from_transactions([original_txn]))

        moved_raw = original_txn.raw.model_copy(
            update={"booked_date": date(2024, 8, 20), "value_date": date(2024, 8, 20)}
        )
        moved_txn = original_txn.model_copy(update={"raw": moved_raw})
        repo.save(TransactionCatalogue.from_transactions([moved_txn]))

        engine = profile.repository.engine
        with session_scope(engine) as session:
            index_rows = session.execute(
                select(_orm.TransactionDateIndexRow.transaction_id, _orm.TransactionDateIndexRow.filing_date).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            ).all()

    assert len(index_rows) == 1
    (transaction_id, filing_date) = index_rows[0]
    assert transaction_id == moved_txn.transaction_id
    assert filing_date == date(2024, 8, 20)


def test_date_index_removes_row_for_deleted_transaction(
    tmp_path: Path,
) -> None:
    """Removing a transaction from the catalogue removes its index row too."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        keep = _transaction(
            provider_id="row-keep", filing_date=date(2024, 3, 1), amount=Decimal("1.00"), description="keep"
        )
        drop = _transaction(
            provider_id="row-drop", filing_date=date(2024, 3, 2), amount=Decimal("2.00"), description="drop"
        )
        repo.save(TransactionCatalogue.from_transactions([keep, drop]))
        repo.save(TransactionCatalogue.from_transactions([keep]))

        engine = profile.repository.engine
        with session_scope(engine) as session:
            remaining_ids = (
                session.execute(
                    select(_orm.TransactionDateIndexRow.transaction_id).where(
                        _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                    ),
                )
                .scalars()
                .all()
            )

    assert set(remaining_ids) == {keep.transaction_id}
