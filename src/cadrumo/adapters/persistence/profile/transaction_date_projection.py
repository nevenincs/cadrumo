"""Validated transaction date routing and bounded out-of-window read projections."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING

from ....domain.transactions.dates import transaction_eligible_date_span, transaction_filing_date
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import (
    OutOfWindowTransactionIndexEntry,
    Transaction,
    TransactionCatalogue,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    pass


# Row-level projections remain useful for small ledgers and compatibility
# consumers. At scale the compact count/date-span summary is the canonical
# diagnostic channel; materialising tens of thousands of Pydantic rows would
# make excluded transactions dominate a period-scoped read.
OUT_OF_WINDOW_ROW_PROJECTION_LIMIT = 1024


def catalogue_from_loaded_transactions(transactions: Iterable[Transaction]) -> TransactionCatalogue:
    """Assemble a catalogue from rows that already crossed the secure boundary.

    ``_load_transactions_by_ids`` has parsed each row through its encrypted
    envelope and checked that its embedded id matches the addressed object key.
    Running ``TransactionCatalogue.from_transactions`` here would repeat every
    transaction model validator for the same immutable objects. Keep the
    catalogue mapping frozen, while relying on those preceding row-level
    validation and identity checks for the member invariants.
    """
    members: dict[str, Transaction] = {}
    for transaction in transactions:
        if transaction.transaction_id in members:
            raise TransactionValidationError(f"duplicate transaction_id: {transaction.transaction_id}")
        members[transaction.transaction_id] = transaction
    return TransactionCatalogue.model_construct(transactions=MappingProxyType(members))


@dataclass(frozen=True, slots=True)
class IndexedTransactionDates:
    """The plaintext routing dates one :class:`TransactionDateIndexRow` records.

    Groups the filing date with the inclusive eligible-observation span so a
    row's index state is compared and written as one value: a change to
    either axis rewrites the row, and an unchanged row is left untouched.
    """

    filing_date: date
    eligible_from: date
    eligible_to: date

    @classmethod
    def for_transaction(cls, transaction: Transaction) -> IndexedTransactionDates:
        """Project one transaction's routing dates through the domain date owners."""
        eligible_from, eligible_to = transaction_eligible_date_span(transaction)
        return cls(
            filing_date=transaction_filing_date(transaction),
            eligible_from=eligible_from,
            eligible_to=eligible_to,
        )

    def overlaps(self, start: date, end: date) -> bool:
        """Return whether this row can file an observation inside ``[start, end]``."""
        return self.eligible_from <= end and self.eligible_to >= start


def project_out_of_window_index_entries(
    rows: tuple[tuple[str, date], ...],
) -> tuple[OutOfWindowTransactionIndexEntry, ...]:
    """Project small out-of-window sets in deterministic transaction-id order."""
    if len(rows) > OUT_OF_WINDOW_ROW_PROJECTION_LIMIT:
        return ()
    return tuple(
        OutOfWindowTransactionIndexEntry(transaction_id=transaction_id, filing_date=filing_date)
        for transaction_id, filing_date in sorted(rows)
    )
