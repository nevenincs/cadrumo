"""Application-owned parsed-row double for the import classification seam."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.raw_transaction import RawTransaction


@dataclass(frozen=True, slots=True)
class ParsedLedgerRowFake:
    raw: RawTransaction
    direction: TransactionDirection
    own_account_id: str | None = None
    operation_date: date | None = None
