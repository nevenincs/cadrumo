"""Inspect real encrypted repository state in owning fixtures."""

from __future__ import annotations

from sqlalchemy import select

from ...storage.sql.orm import TransactionDateIndexRow
from ..transaction_date_projection import IndexedTransactionDates
from ..transactions import TransactionCatalogueRepository


def _all_date_index_rows(self: TransactionCatalogueRepository) -> dict[str, IndexedTransactionDates]:
    """Return every ``{transaction_id: routing dates}`` this bucket's date index records."""
    with self._objects.guarded_session_scope() as session:
        rows = session.execute(
            select(
                TransactionDateIndexRow.transaction_id,
                TransactionDateIndexRow.filing_date,
                TransactionDateIndexRow.eligible_from,
                TransactionDateIndexRow.eligible_to,
            ).where(TransactionDateIndexRow.bucket_id == self._bucket_id)
        ).all()
        return {
            str(transaction_id): IndexedTransactionDates(
                filing_date=filing_date, eligible_from=eligible_from, eligible_to=eligible_to
            )
            for transaction_id, filing_date, eligible_from, eligible_to in rows
        }
