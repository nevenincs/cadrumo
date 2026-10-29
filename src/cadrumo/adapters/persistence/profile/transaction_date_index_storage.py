"""Encrypted SQL repository with atomic per-bucket transaction reads and writes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update

from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....domain.transactions.models import (
    Transaction,
)
from ..storage.sql.orm import TransactionDateIndexRow
from .transaction_date_projection import (
    IndexedTransactionDates,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from sqlalchemy.orm import Session


_log = get_logger(__name__)


def date_index_revision(rows: dict[str, tuple[int, IndexedTransactionDates]]) -> str:
    """Identify a prepared routing baseline without persisting financial data."""
    values = [
        (key, row_id, dates.filing_date.isoformat(), dates.eligible_from.isoformat(), dates.eligible_to.isoformat())
        for key, (row_id, dates) in sorted(rows.items())
    ]
    return sha256_hex(json.dumps(values, separators=(",", ":")).encode(UTF_8_ENCODING))


def read_date_index_rows(bucket_id: str, session: Session) -> dict[str, tuple[int, IndexedTransactionDates]]:
    """Read the exact bucket baseline used by the canonical routing diff."""
    existing_rows = session.execute(
        select(
            TransactionDateIndexRow.id,
            TransactionDateIndexRow.transaction_id,
            TransactionDateIndexRow.filing_date,
            TransactionDateIndexRow.eligible_from,
            TransactionDateIndexRow.eligible_to,
        ).where(TransactionDateIndexRow.bucket_id == bucket_id),
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
    session: Session,
    *,
    incoming: dict[str, IndexedTransactionDates],
    existing: dict[str, tuple[int, IndexedTransactionDates]],
) -> None:
    """Apply the canonical routing diff after its complete baseline assertion."""
    stale_ids = set(existing) - set(incoming)
    if stale_ids:
        session.execute(
            delete(TransactionDateIndexRow).where(
                TransactionDateIndexRow.bucket_id == bucket_id,
                TransactionDateIndexRow.transaction_id.in_(stale_ids),
            ),
        )

    new_rows: list[TransactionDateIndexRow] = []
    for transaction_id, dates in incoming.items():
        current = existing.get(transaction_id)
        if current is not None and current[1] == dates:
            continue  # unchanged: leave the existing row untouched
        if current is not None:
            session.execute(
                update(TransactionDateIndexRow)
                .where(TransactionDateIndexRow.id == current[0])
                .values(
                    filing_date=dates.filing_date,
                    filing_year=dates.filing_date.year,
                    eligible_from=dates.eligible_from,
                    eligible_to=dates.eligible_to,
                ),
            )
            continue
        new_rows.append(
            TransactionDateIndexRow(
                bucket_id=bucket_id,
                transaction_id=transaction_id,
                filing_date=dates.filing_date,
                filing_year=dates.filing_date.year,
                eligible_from=dates.eligible_from,
                eligible_to=dates.eligible_to,
            ),
        )
    if new_rows:
        session.add_all(new_rows)


def date_routing_unchanged(current: Transaction, replacement: Transaction) -> bool:
    """Determine whether an edit leaves the routing projection intact."""
    return current.transaction_id == replacement.transaction_id and IndexedTransactionDates.for_transaction(
        current
    ) == IndexedTransactionDates.for_transaction(replacement)
