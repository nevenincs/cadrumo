"""Inspect real encrypted repository state in owning fixtures."""

from __future__ import annotations

from sqlalchemy import select

from ...storage.sql.tables import transaction_date_index_table
from ..transaction_date_projection import IndexedTransactionDates
from ..transactions import TransactionCatalogueRepository


def all_date_index_rows(self: TransactionCatalogueRepository) -> dict[str, IndexedTransactionDates]:
    """Return every ``{transaction_id: routing dates}`` this bucket's date index records."""
    with self._objects.guarded_session_scope() as session:
        rows = session.execute(
            select(
                transaction_date_index_table.c.transaction_id,
                transaction_date_index_table.c.filing_date,
                transaction_date_index_table.c.eligible_from,
                transaction_date_index_table.c.eligible_to,
            ).where(transaction_date_index_table.c.bucket_id == self._bucket_id)
        ).all()
        return {
            str(transaction_id): IndexedTransactionDates(
                filing_date=filing_date, eligible_from=eligible_from, eligible_to=eligible_to
            )
            for transaction_id, filing_date, eligible_from, eligible_to in rows
        }
