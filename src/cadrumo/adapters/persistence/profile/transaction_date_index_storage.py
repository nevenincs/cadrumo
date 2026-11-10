"""Encrypted SQL repository with atomic per-bucket transaction reads and writes."""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import delete, insert, select, update

from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....domain.transactions.models import (
    Transaction,
    TransactionCatalogue,
)
from ..storage.errors import SecureObjectRevisionConflictError
from ..storage.sql.tables import transaction_date_index_table
from .transaction_date_projection import (
    IndexedTransactionDates,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from sqlalchemy import Connection

    from ..storage.sql.secure_objects import SecureObjectRepository


def date_index_revision(rows: dict[str, tuple[int, IndexedTransactionDates]]) -> str:
    """Identify a prepared routing baseline without persisting financial data."""
    values = [
        (key, row_id, dates.filing_date.isoformat(), dates.eligible_from.isoformat(), dates.eligible_to.isoformat())
        for key, (row_id, dates) in sorted(rows.items())
    ]
    return sha256_hex(json.dumps(values, separators=(",", ":")).encode(UTF_8_ENCODING))


def read_date_index_rows(bucket_id: str, session: Connection) -> dict[str, tuple[int, IndexedTransactionDates]]:
    """Read the exact bucket baseline used by the canonical routing diff."""
    existing_rows = session.execute(
        select(
            transaction_date_index_table.c.id,
            transaction_date_index_table.c.transaction_id,
            transaction_date_index_table.c.filing_date,
            transaction_date_index_table.c.eligible_from,
            transaction_date_index_table.c.eligible_to,
        ).where(transaction_date_index_table.c.bucket_id == bucket_id),
    ).all()
    return {
        transaction_id: (
            row_id,
            IndexedTransactionDates(
                filing_date=filing_date,
                eligible_from=eligible_from,
                eligible_to=eligible_to,
            ),
        )
        for row_id, transaction_id, filing_date, eligible_from, eligible_to in existing_rows
    }


def write_date_index_rows(
    bucket_id: str,
    session: Connection,
    *,
    incoming: dict[str, IndexedTransactionDates],
    existing: dict[str, tuple[int, IndexedTransactionDates]],
) -> None:
    """Apply the canonical routing diff after its complete baseline assertion."""
    stale_ids = set(existing) - set(incoming)
    if stale_ids:
        session.execute(
            delete(transaction_date_index_table).where(
                transaction_date_index_table.c.bucket_id == bucket_id,
                transaction_date_index_table.c.transaction_id.in_(stale_ids),
            ),
        )

    new_rows: list[dict[str, object]] = []
    for transaction_id, dates in incoming.items():
        current = existing.get(transaction_id)
        if current is not None and current[1] == dates:
            continue  # unchanged: leave the existing row untouched
        if current is not None:
            session.execute(
                update(transaction_date_index_table)
                .where(transaction_date_index_table.c.id == current[0])
                .values(
                    filing_date=dates.filing_date,
                    filing_year=dates.filing_date.year,
                    eligible_from=dates.eligible_from,
                    eligible_to=dates.eligible_to,
                ),
            )
            continue
        new_rows.append(
            {
                "bucket_id": bucket_id,
                "transaction_id": transaction_id,
                "filing_date": dates.filing_date,
                "filing_year": dates.filing_date.year,
                "eligible_from": dates.eligible_from,
                "eligible_to": dates.eligible_to,
            },
        )
    if new_rows:
        session.execute(insert(transaction_date_index_table), new_rows)


def date_routing_unchanged(current: Transaction, replacement: Transaction) -> bool:
    """Determine whether an edit leaves the routing projection intact."""
    return current.transaction_id == replacement.transaction_id and IndexedTransactionDates.for_transaction(
        current
    ) == IndexedTransactionDates.for_transaction(replacement)


def sync_date_index_rows(objects: SecureObjectRepository, bucket_id: str, catalogue: TransactionCatalogue) -> None:
    """Bring ``bucket_id``'s routing rows to ``catalogue``, retrying a conflicting baseline up to three times.

    Each attempt reads the bucket baseline, returns when it already matches,
    and otherwise writes the diff in a transaction that first asserts the
    baseline is unchanged; a third conflict propagates.
    """
    incoming: dict[str, IndexedTransactionDates] = {
        transaction_id: IndexedTransactionDates.for_transaction(transaction)
        for transaction_id, transaction in catalogue.transactions.items()
    }

    for attempt in range(3):
        with objects.guarded_session_scope() as session:
            baseline = read_date_index_rows(bucket_id, session)
        if {key: value[1] for key, value in baseline.items()} == incoming:
            return

        def commit(session: Connection, baseline: dict[str, tuple[int, IndexedTransactionDates]] = baseline) -> None:
            current = read_date_index_rows(bucket_id, session)
            if current != baseline:
                # No DML has occurred: the whole transaction is a proven
                # prewrite conflict, including convergence by another writer.
                raise SecureObjectRevisionConflictError(
                    translated_message="errors.fail.fail_storage_secure_object_revision_conflict",
                    context={
                        "namespace": "transaction-date-index",
                        "expected_revision_id": date_index_revision(baseline),
                        "current_revision_id": date_index_revision(current),
                    },
                )
            write_date_index_rows(bucket_id, session, incoming=incoming, existing=current)

        try:
            objects.write_transaction(commit)
        except SecureObjectRevisionConflictError:
            if attempt == 2:
                raise
        else:
            return


def date_index_ids_and_count(objects: SecureObjectRepository, bucket_id: str) -> tuple[set[str], int]:
    """Return date-index ids and physical row count for the completeness gate.

    The partition path only needs identity for the gate; loading all four
    routing columns into Python is deferred to the targeted window query.
    Keeping the row count alongside the id set also refuses duplicate index
    rows instead of allowing set projection to hide them.
    """
    with objects.guarded_session_scope() as session:
        rows = (
            session.execute(
                select(transaction_date_index_table.c.transaction_id).where(
                    transaction_date_index_table.c.bucket_id == bucket_id,
                ),
            )
            .scalars()
            .all()
        )
    return set(rows), len(rows)


def date_index_candidate_ids(
    objects: SecureObjectRepository, bucket_id: str, start: date, end: date
) -> set[str] | None:
    """Return the candidate transaction ids in ``[start, end]`` per the plaintext index.

    Returns ``None`` when this bucket has no rows in the index at all
    (distinguishing "index absent" from "index present but window empty",
    so a date-range load can tell a genuinely stale/missing index apart
    from a real empty result).
    """
    with objects.guarded_session_scope() as session:
        any_row = session.execute(
            select(transaction_date_index_table.c.id)
            .where(transaction_date_index_table.c.bucket_id == bucket_id)
            .limit(1),
        ).first()
        if any_row is None:
            return None
        rows = session.execute(
            select(transaction_date_index_table.c.transaction_id).where(
                transaction_date_index_table.c.bucket_id == bucket_id,
                transaction_date_index_table.c.filing_date >= start,
                transaction_date_index_table.c.filing_date <= end,
            ),
        ).scalars()
        return set(rows)
