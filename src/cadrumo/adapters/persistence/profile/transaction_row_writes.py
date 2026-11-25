"""Secure-object writes composing a transaction catalogue batch: rows, membership, deletions and figure traces.

A write that stops storing business figures a row's classification refuses
records each dropped figure in the bucket event history of the same batch;
the helpers here find such stored rows and compose that trace.

It works with :class:`Envelope`, :class:`SecureObjectRepository`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import TYPE_CHECKING

from ....domain.buckets.event import BucketEventHistoryCatalogue, BucketEventObjectType, BucketEventType
from ....domain.buckets.event_repository import append_bucket_event, build_bucket_event
from ....domain.transactions.models import Transaction, validate_stored_transaction_json
from ....domain.transactions.repository import transaction_index_object_key, transaction_object_key
from ....domain.transactions.withheld_figures import (
    WITHHELD_FIGURE_COUNT_KEY,
    figures_held_without_business,
    withheld_figures_event_entries,
)
from ..storage.secure_object_namespaces import BUCKET_EVENT_HISTORY_NAMESPACE, TRANSACTION_CATALOGUE_NAMESPACE

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ....core.secure_object_write import SecureObjectWrite
    from ..storage.sql.secure_object_records import SecureObjectDeletion
    from ..storage.sql.secure_objects import SecureObjectRepository


type FigureDrop = tuple[Mapping[str, object], datetime]
"""The business figures a write stops storing for one row, and when that write happens."""

_STORED_ROW_WRITE_ACTOR = "cadrumo.ledger.stored-row-write"
"""The actor of an event this repository records itself, for a drop no writer's event named."""

_WITHHELD_FIGURE_EVENT_PAYLOAD_VERSION = 1


def transaction_row_write(
    *,
    bucket_id: str,
    transaction_id: str,
    written_at: datetime,
    payload: bytes,
    expected_revision_id: str | None = None,
) -> SecureObjectWrite:
    """The encrypted-row write of one transaction, optionally guarded on its expected revision."""
    from ....core.secure_object_write import SecureObjectWrite

    return SecureObjectWrite(
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=transaction_object_key(bucket_id, transaction_id),
        classification=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        schema_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        written_at=written_at,
        payload=payload,
        expected_revision_id=expected_revision_id,
    )


def membership_index_write(
    *,
    bucket_id: str,
    written_at: datetime,
    payload: bytes,
    expected_revision_id: str | None = None,
) -> SecureObjectWrite:
    """The write of a bucket's membership index, optionally guarded on its expected revision."""
    from ....core.secure_object_write import SecureObjectWrite

    return SecureObjectWrite(
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=transaction_index_object_key(bucket_id),
        classification=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        schema_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        written_at=written_at,
        payload=payload,
        expected_revision_id=expected_revision_id,
    )


def transaction_row_deletion(
    *, bucket_id: str, transaction_id: str, expected_revision_id: str | None = None
) -> SecureObjectDeletion:
    """The removal of one transaction row by its key digest, optionally guarded on its opened revision."""
    from ..storage.crypto.encrypted_columns import secure_object_key_digest
    from ..storage.sql.secure_object_records import SecureObjectDeletion

    return SecureObjectDeletion(
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        hashed_object_key=secure_object_key_digest(transaction_object_key(bucket_id, transaction_id)),
        expected_revision_id=expected_revision_id,
    )


def stored_rows_holding_figures(
    objects: SecureObjectRepository,
    *,
    bucket_id: str,
    transaction_ids: Iterable[str],
    refuse_legacy: Callable[[tuple[str, ...]], None],
) -> dict[str, Transaction]:
    """Return the stored rows among ``transaction_ids`` that hold figures their classification refuses.

    ``objects`` is the :class:`SecureObjectRepository` it uses.
    """
    from ..storage.crypto.encrypted_columns import secure_object_key_digest
    from ..storage.envelope.contract import Envelope

    object_key_by_id = {
        transaction_id: transaction_object_key(bucket_id, transaction_id) for transaction_id in transaction_ids
    }
    if not object_key_by_id:
        return {}
    transaction_id_by_digest = {
        secure_object_key_digest(object_key): transaction_id for transaction_id, object_key in object_key_by_id.items()
    }
    holding: dict[str, Transaction] = {}
    for record in objects.load_many_current(
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key_by_id.values(),
        expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        current_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        refuse_legacy=refuse_legacy,
    ):
        transaction_id = transaction_id_by_digest.get(bytes(record.object_key))
        if transaction_id is None:
            continue
        stored_row = validate_stored_transaction_json(Envelope[Transaction], record.payload).payload
        if figures_held_without_business(stored_row):
            holding[transaction_id] = stored_row
    return holding


def with_withheld_figure_trace(
    objects: SecureObjectRepository,
    *,
    bucket_id: str,
    extra_writes: tuple[SecureObjectWrite, ...],
    drops: Mapping[str, FigureDrop],
) -> tuple[SecureObjectWrite, ...]:
    """Return ``extra_writes`` with the event history recording every figure the batch stops storing.

    A row whose stored form held business figures its classification
    refuses loses them on this write. The writer's own event of that row
    normally names them already; a drop no event of this batch names gets
    an event of its own in the same batch, so no write drops a figure
    silently. The event-history write the caller composed keeps its
    revision guard; a batch without one gets one composed against the
    history as it stands, guarded on that revision.

    ``objects`` is the :class:`SecureObjectRepository` it uses.
    """
    if not drops:
        return extra_writes
    from .buckets import BucketEventHistoryRepository

    history = BucketEventHistoryRepository(objects=objects)
    stored_history, stored_revision = history.load_revisioned()
    position = _event_history_write_position(extra_writes)
    if position is None:
        catalogue, expected_revision = stored_history, stored_revision
    else:
        catalogue, expected_revision = _composed_event_history(extra_writes[position])
    named = _transactions_named_with_withheld_figures(catalogue, stored_history)
    for transaction_id, (figures, occurred_at) in sorted(drops.items()):
        if transaction_id in named:
            continue
        catalogue = append_bucket_event(
            catalogue,
            build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.LEDGER_TRANSACTION_UPDATED,
                occurred_at=occurred_at,
                actor=_STORED_ROW_WRITE_ACTOR,
                object_type=BucketEventObjectType.LEDGER_TRANSACTION,
                object_id=transaction_id,
                payload={"mutation_kind": "withheld_figures_dropped", **withheld_figures_event_entries(figures)},
                payload_version=_WITHHELD_FIGURE_EVENT_PAYLOAD_VERSION,
            ),
        )
    trace = history.to_secure_object_write(catalogue, expected_revision_id=expected_revision)
    if position is None:
        return (*extra_writes, trace)
    return (*extra_writes[:position], trace, *extra_writes[position + 1 :])


def _event_history_write_position(extra_writes: tuple[SecureObjectWrite, ...]) -> int | None:
    """The index of the first bucket event-history write the caller composed, if any."""
    return next(
        (
            index
            for index, write in enumerate(extra_writes)
            if write.namespace == BUCKET_EVENT_HISTORY_NAMESPACE.namespace
        ),
        None,
    )


def _composed_event_history(composed: SecureObjectWrite) -> tuple[BucketEventHistoryCatalogue, str | None]:
    """The event history a caller's composed write carries, with that write's revision guard."""
    from ..storage.envelope.contract import Envelope

    catalogue = Envelope[BucketEventHistoryCatalogue].model_validate_json(composed.payload).payload
    return catalogue, composed.expected_revision_id


def _transactions_named_with_withheld_figures(
    catalogue: BucketEventHistoryCatalogue, stored_history: BucketEventHistoryCatalogue
) -> set[str]:
    """The transactions a new ledger event of this batch already records withheld figures for."""
    return {
        event.object_id
        for event_id, event in catalogue.events.items()
        if event_id not in stored_history.events
        and event.object_type is BucketEventObjectType.LEDGER_TRANSACTION
        and WITHHELD_FIGURE_COUNT_KEY in event.payload
    }
