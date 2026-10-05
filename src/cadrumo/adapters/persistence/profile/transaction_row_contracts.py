"""Strict encrypted transaction membership and timestamp payload contracts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ....core.external_constants import UTF_8_ENCODING
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.time.utc import UtcInstant

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    pass


_JSON_OBJECT = TypeAdapter(dict[str, object])


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

    @classmethod
    def validate_payload(cls, payload: object) -> None:
        """Raise ``ValidationError`` when a persisted row lacks timestamp keys."""
        cls.model_validate(payload)


def decode_persisted_transaction_row(payload: bytes) -> dict[str, object] | None:
    """Return the parsed envelope dict for one persisted row, or ``None`` if not JSON.

    Centralises the single JSON decode of a stored row's plaintext bytes so
    the D6 timestamp guard and the authoritative :class:`Envelope` validation
    share one parse instead of each independently re-decoding the same bytes
    (a real O(n) cost at ledger scale: see the P95 scale benchmark in
    ``application/aggregation/tests/test_ledger_scale_benchmark.py``).
    """
    try:
        decoded: object = json.loads(payload.decode(UTF_8_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    try:
        return _JSON_OBJECT.validate_python(decoded)
    except ValidationError:
        return None


def validate_persisted_transaction_timestamps(decoded: dict[str, object]) -> None:
    """Reject a persisted per-transaction row missing the mandatory D6 timestamps.

    Takes the already-JSON-decoded envelope dict (see
    :func:`decode_persisted_transaction_row`) rather than re-parsing the raw
    bytes, so this guard adds only a cheap pydantic pass over the small
    ``{created_at, modified_at}`` sub-shape -- not a second full JSON decode
    of the whole row.
    """
    transaction_payload = decoded.get("payload")
    if not isinstance(transaction_payload, dict):
        return
    _PersistedTransactionTimestampWitness.validate_payload(_JSON_OBJECT.validate_python(transaction_payload))
