"""Coverage for the plaintext transaction date/period participation index.

:meth:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository.load_for_date_range`
selects candidate transaction ids from the plaintext, non-sensitive
:class:`~adapters.persistence.storage.sql.TransactionDateIndexRow` routing
table before decrypting only that subset -- never a full-namespace scan (issue
``#408``). The index is derived and rebuildable
(``aeat-ledger-contract``): correctness never
depends on its presence or freshness, so every correctness assertion here is
mirrored by an anti-tautology proof that the fallback still reproduces the
unfiltered result when the index is missing, incomplete, or stale.

See Also:
    :meth:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository.partition_by_date_range`:
        Completeness-gated split that returns in-window transactions and
        plaintext out-of-window projections.
    :class:`~domain.transactions.LedgerDatePartition`:
        Partition result contract that records whether the date index was
        complete.
    :meth:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository.rebuild_date_index`:
        Maintenance path that regenerates the derived routing index from the
        encrypted catalogue.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy import inspect as sa_inspect

from .....domain.iva.schema import IvaCashAccountingPaymentEvidence, IvaCashAccountingTreatment, IvaCategory
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .....tests.secure_sql import isolated_runtime_profile
from ...storage.sql import orm as _orm
from ...storage.sql.session import session_scope
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"

_NON_SENSITIVE_COLUMNS = frozenset(
    {
        "id",
        "bucket_id",
        "transaction_id",
        "filing_date",
        "filing_year",
        # Routing dates only, same non-sensitive class as ``filing_date``: the
        # inclusive span of every date the row can file an observation under,
        # so a period partition selects on overlap rather than on the filing
        # date alone. Carries no amount, counterparty, or other financial fact.
        "eligible_from",
        "eligible_to",
    },
)


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


def _cash_accounting_transaction(
    *,
    provider_id: str,
    filing_date: date,
    operation_date: date,
    payment_date: date,
) -> Transaction:
    """Build a real criterio-de-caja row whose devengo date differs from its filing date."""
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, filing_date, Decimal("1210.00"), "criterio de caja"),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            "taxable_base": Decimal("1000.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("210.00"),
            "iva_category": IvaCategory.DOMESTIC_GENERAL,
            "cash_accounting_treatment": IvaCashAccountingTreatment.TAXPAYER_REGIME,
            "operation_date": operation_date,
            "cash_accounting_payment_evidence": (
                IvaCashAccountingPaymentEvidence(
                    payment_date=payment_date,
                    taxable_base=Decimal("1000.00"),
                    iva_amount=Decimal("210.00"),
                    recargo_amount=Decimal("0.00"),
                ),
            ),
            "classified_at": datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _normalise_sql(statement: str) -> str:
    return " ".join(statement.lower().split())


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
        # ``FromClause`` in SQLAlchemy's type hints even though it is always a
        # real ``Table`` at runtime for a mapped class, so looking it up by
        # name avoids that type-precision gap.
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
    (``start <= filing_date <= end``, mirroring :meth:`~core.Period.contains`).
    This
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


def test_load_by_ids_matches_exact_full_catalogue_subset_and_omits_missing(
    tmp_path: Path,
) -> None:
    """Targeted secure reads preserve full-load row validation and identity."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        rows = [
            _transaction(
                provider_id=f"targeted-{index}",
                filing_date=date(2024, index + 1, 15),
                amount=Decimal(index + 1),
                description=f"targeted row {index}",
            )
            for index in range(3)
        ]
        repo.save(TransactionCatalogue.from_transactions(rows))

        requested = (rows[2].transaction_id, "f" * 64, rows[0].transaction_id, rows[0].transaction_id)
        targeted = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load_by_ids(requested)
        full = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    expected_ids = {rows[0].transaction_id, rows[2].transaction_id}
    assert set(targeted.transactions) == expected_ids
    assert dict(targeted.transactions) == {
        transaction_id: full.transactions[transaction_id] for transaction_id in expected_ids
    }


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

    Per ``aeat-ledger-contract``: dropping every
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
    ``aeat-ledger-contract``. This is the proof
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
        moved_payload = original_txn.model_dump(mode="python")
        moved_payload["raw"] = moved_raw
        moved_payload.pop("transaction_id")
        moved_txn = Transaction.model_validate(moved_payload)
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


def test_partition_by_date_range_splits_in_window_and_out_of_window(
    tmp_path: Path,
) -> None:
    """The completeness-gated partition returns exactly the right in/out-of-window split.

    In-window rows are real, decrypted :class:`Transaction` records;
    out-of-window rows are plaintext index projections (id + filing date only)
    reconstructed from the index without decryption.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        inside_q1 = _transaction(
            provider_id="row-q1", filing_date=date(2024, 2, 10), amount=Decimal("10.00"), description="Q1 expense"
        )
        outside_q2 = _transaction(
            provider_id="row-q2", filing_date=date(2024, 4, 1), amount=Decimal("30.00"), description="Q2 expense"
        )
        repo.save(TransactionCatalogue.from_transactions([inside_q1, outside_q2]))

        partition = TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(
            date(2024, 1, 1), date(2024, 3, 31)
        )

    assert partition.index_complete is True
    assert set(partition.in_window.transactions) == {inside_q1.transaction_id}
    assert partition.in_window.transactions[inside_q1.transaction_id] == inside_q1
    assert len(partition.out_of_window) == 1
    out_of_window_projection = partition.out_of_window[0]
    assert out_of_window_projection.transaction_id == outside_q2.transaction_id
    assert out_of_window_projection.filing_date == date(2024, 4, 1)
    assert partition.out_of_window_summary is not None
    assert partition.out_of_window_summary.count == 1
    assert partition.out_of_window_summary.min_filing_date == date(2024, 4, 1)
    assert partition.out_of_window_summary.max_filing_date == date(2024, 4, 1)


def test_partition_by_date_range_uses_one_targeted_secure_object_batch(
    tmp_path: Path,
) -> None:
    """The complete-index partition uses one batch read for in-window secure rows."""

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        inside_jan = _transaction(
            provider_id="row-batch-jan",
            filing_date=date(2024, 1, 10),
            amount=Decimal("10.00"),
            description="batch jan",
        )
        inside_mar = _transaction(
            provider_id="row-batch-mar",
            filing_date=date(2024, 3, 31),
            amount=Decimal("20.00"),
            description="batch mar",
        )
        outside_apr = _transaction(
            provider_id="row-batch-apr",
            filing_date=date(2024, 4, 1),
            amount=Decimal("30.00"),
            description="batch apr",
        )
        outside_dec = _transaction(
            provider_id="row-batch-dec",
            filing_date=date(2024, 12, 20),
            amount=Decimal("40.00"),
            description="batch dec",
        )
        repo.save(TransactionCatalogue.from_transactions([inside_jan, inside_mar, outside_apr, outside_dec]))

        statements: list[str] = []

        def collect_statement(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
            statements.append(_normalise_sql(statement))

        engine = profile.repository.engine
        event.listen(engine, "before_cursor_execute", collect_statement)
        try:
            partition = TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(
                date(2024, 1, 1), date(2024, 3, 31)
            )
        finally:
            event.remove(engine, "before_cursor_execute", collect_statement)

    expected_in_window = {inside_jan.transaction_id, inside_mar.transaction_id}
    expected_out_of_window = {outside_apr.transaction_id, outside_dec.transaction_id}
    assert partition.index_complete is True
    assert set(partition.in_window.transactions) == expected_in_window
    assert partition.in_window.transactions[inside_jan.transaction_id] == inside_jan
    assert partition.in_window.transactions[inside_mar.transaction_id] == inside_mar
    assert {row.transaction_id for row in partition.out_of_window} == expected_out_of_window
    assert {row.filing_date for row in partition.out_of_window} == {date(2024, 4, 1), date(2024, 12, 20)}
    assert partition.out_of_window_summary is not None
    assert partition.out_of_window_summary.count == 2
    assert partition.out_of_window_summary.min_filing_date == date(2024, 4, 1)
    assert partition.out_of_window_summary.max_filing_date == date(2024, 12, 20)

    secure_object_selects = [
        statement for statement in statements if "from secure_objects" in statement and statement.startswith("select")
    ]
    batch_selects = [statement for statement in secure_object_selects if "object_key in" in statement]
    point_key_selects = [statement for statement in secure_object_selects if "object_key =" in statement]

    assert len(batch_selects) == 1, "schema cutover and payload integrity must share one addressed snapshot"
    assert len(point_key_selects) == 1, "only the membership-index lookup should use a point secure-object read"
    assert not any(
        "from secure_objects" in statement and "object_key in" not in statement and "object_key =" not in statement
        for statement in secure_object_selects
    ), "targeted partition reads must never scan the secure-object namespace"


def test_partition_by_date_range_matches_full_load_filtered_in_memory(
    tmp_path: Path,
) -> None:
    """Aggregation-identity proof: the partition's two halves cover every row exactly once."""

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
        partition = TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(start, end)
        full = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    expected_in_window = {
        transaction_id
        for transaction_id, transaction in full.transactions.items()
        if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
    }
    expected_out_of_window = set(full.transactions) - expected_in_window

    assert set(partition.in_window.transactions) == expected_in_window
    assert {projection.transaction_id for projection in partition.out_of_window} == expected_out_of_window
    out_of_window_dates = tuple(projection.filing_date for projection in partition.out_of_window)
    assert partition.out_of_window_summary is not None
    assert partition.out_of_window_summary.count == len(expected_out_of_window)
    assert partition.out_of_window_summary.min_filing_date == min(out_of_window_dates)
    assert partition.out_of_window_summary.max_filing_date == max(out_of_window_dates)
    # Every out-of-window projection's filing date matches the real decrypted date.
    for out_of_window_projection in partition.out_of_window:
        real_transaction = full.transactions[out_of_window_projection.transaction_id]
        real_filing_date = real_transaction.raw.value_date or real_transaction.raw.booked_date
        assert out_of_window_projection.filing_date == real_filing_date


def test_partition_by_date_range_falls_back_to_full_scan_on_stale_index(
    tmp_path: Path,
) -> None:
    """Anti-staleness proof (mandatory): a mismatched index forces a full-scan fallback, never a silent drop.

    Deletes one index row (simulating a crash between the encrypted commit and
    the separate index-sync transaction, or a partially-rebuilt index) and
    asserts the completeness gate detects the count/id mismatch and falls back
    to a full decrypt scan -- reproducing the identical partition a complete
    index would have produced, with ``index_complete=False`` recording which
    path served the read. This is the guard against reopening the
    stale-index silent-drop class: a stale index must cost latency, never
    correctness.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        inside = _transaction(
            provider_id="row-stale-in", filing_date=date(2024, 2, 1), amount=Decimal("9.00"), description="in"
        )
        outside = _transaction(
            provider_id="row-stale-out", filing_date=date(2024, 6, 1), amount=Decimal("11.00"), description="out"
        )
        repo.save(TransactionCatalogue.from_transactions([inside, outside]))

        engine = profile.repository.engine
        # Delete only the OUT-of-window row's index entry: the membership
        # index still lists both transaction ids, but the date index is now
        # incomplete for this bucket -- a genuine staleness signal, not an
        # empty-index case already covered by the full-fallback test above.
        with session_scope(engine) as session:
            session.execute(
                delete(_orm.TransactionDateIndexRow).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                    _orm.TransactionDateIndexRow.transaction_id == outside.transaction_id,
                ),
            )
        with session_scope(engine) as session:
            remaining = (
                session.execute(
                    select(_orm.TransactionDateIndexRow.transaction_id).where(
                        _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                    ),
                )
                .scalars()
                .all()
            )
        assert remaining == [inside.transaction_id], (
            "fixture must leave the index with exactly one stale (missing) row for this proof to be meaningful"
        )

        partition = TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(
            date(2024, 1, 1), date(2024, 3, 31)
        )

    assert partition.index_complete is False
    assert set(partition.in_window.transactions) == {inside.transaction_id}
    assert partition.in_window.transactions[inside.transaction_id] == inside
    assert len(partition.out_of_window) == 1
    assert partition.out_of_window[0].transaction_id == outside.transaction_id
    assert partition.out_of_window[0].filing_date == date(2024, 6, 1)
    assert partition.out_of_window_summary is not None
    assert partition.out_of_window_summary.count == 1
    assert partition.out_of_window_summary.min_filing_date == date(2024, 6, 1)
    assert partition.out_of_window_summary.max_filing_date == date(2024, 6, 1)


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


def test_eligible_span_equals_filing_date_for_a_row_without_a_timing_override(
    tmp_path: Path,
) -> None:
    """A plain ledger row's indexed span collapses to its filing date.

    Guards the fast path: widening the partition to span overlap must not
    widen the candidate set for the overwhelming majority of rows, which
    carry no tax-timing override.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        plain = _transaction(
            provider_id="row-plain",
            filing_date=date(2026, 4, 15),
            amount=Decimal("100.00"),
            description="plain expense",
        )
        repo.save(TransactionCatalogue.from_transactions([plain]))

        engine = profile.repository.engine
        with session_scope(engine) as session:
            row = session.execute(
                select(
                    _orm.TransactionDateIndexRow.filing_date,
                    _orm.TransactionDateIndexRow.eligible_from,
                    _orm.TransactionDateIndexRow.eligible_to,
                ).where(_orm.TransactionDateIndexRow.bucket_id == profile.bucket_id),
            ).one()

    filing_date, eligible_from, eligible_to = row
    assert filing_date == date(2026, 4, 15)
    assert eligible_from == date(2026, 4, 15)
    assert eligible_to == date(2026, 4, 15)


def test_partition_keeps_a_cash_accounting_row_whose_devengo_precedes_its_filing_date(
    tmp_path: Path,
) -> None:
    """A Q2-booked criterio-de-caja row with a Q1 devengo stays a Q1 candidate.

    Under LIVA art. 163 *decies* the art. 75 devengo date is independent of
    the ledger filing date, so partitioning on the filing date alone reports
    the row out-of-window undecrypted and silently drops its Q1 cuota
    devengada. The partition must select on the eligible-date span instead.
    Asserts BOTH partition paths -- the plaintext-index fast path and the
    full-scan fallback -- because the fallback carried the identical defect.
    """

    q1_start, q1_end = date(2026, 1, 1), date(2026, 3, 31)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        cash_sale = _cash_accounting_transaction(
            provider_id="row-cash",
            filing_date=date(2026, 4, 15),
            operation_date=date(2026, 3, 20),
            payment_date=date(2026, 4, 15),
        )
        repo.save(TransactionCatalogue.from_transactions([cash_sale]))

        indexed = TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(q1_start, q1_end)

        engine = profile.repository.engine
        with session_scope(engine) as session:
            session.execute(
                delete(_orm.TransactionDateIndexRow).where(
                    _orm.TransactionDateIndexRow.bucket_id == profile.bucket_id,
                ),
            )
        fallback = TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(q1_start, q1_end)

    assert indexed.index_complete is True
    assert set(indexed.in_window.transactions) == {cash_sale.transaction_id}
    assert indexed.out_of_window == ()

    assert fallback.index_complete is False
    assert set(fallback.in_window.transactions) == {cash_sale.transaction_id}
    assert fallback.out_of_window == ()


def test_partition_excludes_a_cash_accounting_row_with_no_date_in_the_window(
    tmp_path: Path,
) -> None:
    """Anti-tautology: the widened span still excludes a genuinely absent row.

    Proves the cash-accounting selection above is not simply "always
    in-window": a criterio-de-caja row whose devengo, collection, and
    statutory fallback dates all fall after the window is still reported
    out-of-window without decryption.
    """

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repo = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        cash_sale = _cash_accounting_transaction(
            provider_id="row-cash-late",
            filing_date=date(2026, 4, 15),
            operation_date=date(2026, 3, 20),
            payment_date=date(2026, 4, 15),
        )
        repo.save(TransactionCatalogue.from_transactions([cash_sale]))

        partition = TransactionCatalogueRepository(bucket_id=profile.bucket_id).partition_by_date_range(
            date(2025, 1, 1), date(2025, 12, 31)
        )

    assert partition.index_complete is True
    assert partition.in_window.transactions == {}
    assert {projection.transaction_id for projection in partition.out_of_window} == {cash_sale.transaction_id}
