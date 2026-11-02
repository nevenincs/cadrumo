"""Name the staged cells that would give a stored ledger row a new id.

``derive_transaction_id`` hashes the amount, the description, the effective date
and the own account, so staging a different value for any of them makes the
write produce a different row. The staged-check answer reports those fields so a
frontend can say so before anything is sent.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from decimal import Decimal, InvalidOperation

from .staged_check_contracts import LedgerStagedRow, StageFieldName


def _same_amount(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is right
    try:
        return Decimal(left) == Decimal(right)
    except InvalidOperation:
        return left == right


def _effective_date_moved(
    staged: AbstractSet[str], before: dict[str, str | None], after: dict[str, str | None]
) -> bool:
    if not staged & {"booked_date", "value_date"}:
        return False
    effective_before = before["value_date"] or before["booked_date"]
    effective_after = after["value_date"] or after["booked_date"]
    return effective_after != effective_before


def _amount_moved(staged: AbstractSet[str], before: dict[str, str | None], after: dict[str, str | None]) -> bool:
    return "amount" in staged and not _same_amount(after["amount"], before["amount"])


def _description_moved(staged: AbstractSet[str], before: dict[str, str | None], after: dict[str, str | None]) -> bool:
    # The writer trims a description before deriving the id from it.
    return "description" in staged and (after["description"] or "").strip() != (before["description"] or "").strip()


def _own_account_moved(staged: AbstractSet[str], before: dict[str, str | None], after: dict[str, str | None]) -> bool:
    return "own_account_id" in staged and (after["own_account_id"] or None) != before["own_account_id"]


def staged_identity_fields(
    row: LedgerStagedRow, before: dict[str, str | None], after: dict[str, str | None]
) -> tuple[StageFieldName, ...]:
    """Name the staged fields that give the row a new id: what ``derive_transaction_id`` hashes."""
    staged = {cell.field for cell in row.cells}
    found: list[StageFieldName] = []
    if _amount_moved(staged, before, after):
        found.append("amount")
    if _description_moved(staged, before, after):
        found.append("description")
    # ``derive_transaction_id`` hashes the value date when there is one, else the booked date.
    if _effective_date_moved(staged, before, after):
        found.append("value_date" if "value_date" in staged else "booked_date")
    if _own_account_moved(staged, before, after):
        found.append("own_account_id")
    return tuple(found)
