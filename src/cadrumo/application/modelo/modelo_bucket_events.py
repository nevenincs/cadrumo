"""Modelo bucket-event construction and emission."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from ...domain.buckets.event import BucketEvent, BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import build_bucket_event as _build_domain_bucket_event
from ...domain.buckets.event_repository import emit_bucket_event as _emit_domain_bucket_event
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol

_BUCKET_EVENT_PAYLOAD_VERSION = 2


def emit_modelo_bucket_event(
    *,
    repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
) -> BucketEvent:
    """Emit one :class:`BucketEvent` under the modelo payload contract.

    Modelo's narrow wrapper over :func:`~domain.buckets.event_repository.emit_bucket_event`: it
    supplies :data:`_BUCKET_EVENT_PAYLOAD_VERSION` so no modelo call site restates
    it, and adds nothing else. The shared derive-append-save sequence lives in the
    domain beside :func:`append_bucket_event`, because it composes only bucket
    domain types and every emitting domain needs it — keeping it here made this
    module a hub that peer application packages had to reach up into.

    The returned event is the durable bucket-scoped audit pointer for the modelo
    mutation. Payloads stay compact and reference the owning calculation revision,
    filing record, or work unit instead of duplicating their catalogued state.
    """
    return _emit_domain_bucket_event(
        repository=repository,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
    )


def build_modelo_bucket_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
    object_type: BucketEventObjectType,
    object_id: str,
    payload: Mapping[str, str],
) -> BucketEvent:
    """Derive one modelo :class:`BucketEvent` without persisting it.

    The non-saving counterpart of :func:`emit_modelo_bucket_event`, supplying the
    same :data:`_BUCKET_EVENT_PAYLOAD_VERSION` so a co-committed event cannot
    declare a different payload contract than an emitted one. Pair it with
    :func:`domain.buckets.event_repository.bucket_event_history_write` to commit the event in the same unit of
    work as the catalogues it records.
    """
    return _build_domain_bucket_event(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        payload_version=_BUCKET_EVENT_PAYLOAD_VERSION,
    )
