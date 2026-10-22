"""Strict encrypted transaction membership and timestamp payload contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from ....core.models import STRICT_FROZEN_CONFIG
from ....core.time.utc import UtcInstant


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


class _PersistedTransactionTimestampWitness(BaseModel):
    """Required lifecycle timestamps for one stored transaction row."""

    created_at: UtcInstant = Field()
    modified_at: UtcInstant = Field()


class _PersistedTransactionEnvelopeTimestampWitness(BaseModel):
    """The stored envelope reduced to the transaction timestamps it must carry."""

    payload: _PersistedTransactionTimestampWitness


def validate_persisted_transaction_timestamps(payload: bytes) -> None:
    """Reject a persisted per-transaction row missing the mandatory D6 timestamps.

    ``Transaction`` defaults both lifecycle timestamps, so the authoritative
    envelope validation alone would silently stamp a row that lost them. The
    witness is validated straight from the stored JSON bytes: the parse builds
    no Python object for the fields it ignores, where decoding the whole row
    into dictionaries first cost more than the two-field check itself.

    Only a timestamp failure inside an object-shaped ``payload`` is raised.
    Bytes that are not JSON, a non-object envelope, or a non-object payload
    pass through so the authoritative envelope validation reports them.

    Raises:
        ValidationError: When the payload lacks ``created_at`` or
            ``modified_at``, or either is not a UTC instant.
    """
    try:
        _PersistedTransactionEnvelopeTimestampWitness.model_validate_json(payload)
    except ValidationError as exc:
        if any(len(error["loc"]) > 1 for error in exc.errors()):
            raise
