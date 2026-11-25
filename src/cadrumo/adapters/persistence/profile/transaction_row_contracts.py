"""Strict encrypted transaction membership and timestamp payload contracts."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError
from pydantic_core import InitErrorDetails

from ....core.models import STRICT_FROZEN_CONFIG
from ....domain.transactions.models import Transaction


class TransactionMembershipIndex(BaseModel):
    """Per-bucket membership list: the transaction ids this bucket owns.

    The index is a single secure-object row keyed by ``bucket_id`` that bounds
    both reads and deletions to *this* bucket's rows. It is what preserves
    cross-bucket isolation when several buckets share one secure store: a load
    or a reconciliation reads this bucket's index by its exact key and never
    enumerates another bucket's transactions, and a reconciliation can only
    delete transaction ids the index lists. The heavy per-transaction payloads
    live in their own rows; the index carries only the (cheap) id list.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_ids: tuple[str, ...] = ()


#: The lifecycle timestamps ``Transaction`` defaults, so a stored row must carry them itself.
_PERSISTED_LIFECYCLE_TIMESTAMPS = ("created_at", "modified_at")


def require_persisted_transaction_timestamps(transaction: Transaction) -> None:
    """Refuse a decoded stored row that did not carry its mandatory D6 timestamps.

    ``Transaction`` defaults both lifecycle timestamps, so validating a row that
    lost them would silently stamp it. The decoded record's set fields name
    exactly the members the stored payload carried, so a defaulted timestamp is
    visible without parsing the row a second time. Their UTC rule is the
    model's own field check, which already ran during the decode.

    Raises:
        ValidationError: When the stored payload lacked ``created_at`` or
            ``modified_at``.
    """
    missing = [name for name in _PERSISTED_LIFECYCLE_TIMESTAMPS if name not in transaction.model_fields_set]
    if missing:
        raise ValidationError.from_exception_data(
            "Envelope[Transaction]",
            [InitErrorDetails(type="missing", loc=("payload", name), input=None) for name in missing],
        )
