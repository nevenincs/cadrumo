"""Bucket-scoped notifications snapshot service.

Wraps the read-only AEAT sede notifications adapter
(:mod:`aeat.adapters.outbound.aeat.sede._notifications`) with
bucket-scoped persistence and a read-only verb surface. The service
persists snapshots captured by an upstream fetch, exposes
list / show / latest, and never invokes
:func:`AeatAccessGate.require_live_write`.

Submission is permanently forbidden at this boundary: the service has
no ``submit`` method, no ``acknowledge`` method, and no method that
calls AEAT to mutate notification state. The acuse (read-receipt)
lifecycle is handled *locally* by tracking which snapshot rows the
operator has reviewed.

Verbs:
  capture(snapshot)   persist a fresh snapshot, emit bucket event
  latest()            return the most recent stored snapshot
  list_snapshots()    return every snapshot in capture order
  show(snapshot_id)   return one snapshot by id

The fetch path itself (HTML parse, auth-gated walker,
``require_live_read`` invocation) belongs to the entrypoint that wires
the adapter to this service; this module does not import anything
that drives a browser.

The lifecycle helpers (content-addressed id derivation, dedup on
re-capture, list/show/latest) are routed through the shared
:class:`StatelessSnapshotService` base; the public class identity,
exception class names, secure-object storage layout, and per-call
``bucket_id`` signatures are preserved exactly.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, override

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.outbound.aeat.sede import NotificationsSnapshot, RemoteNotification
from ...adapters.persistence.storage import LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core.config import Settings, load_settings
from ...core.identity import BucketId, SnapshotId
from ...core.time import now
from ._errors import LiveApplicationInputError
from ._snapshot_base import (
    SecureSnapshotRepository,
    SnapshotNotFoundError,
    StatelessSnapshotService,
    derive_snapshot_id_from_json,
)


class NotificationsSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when a snapshot lookup misses by id."""


class PersistedNotificationsSnapshot(BaseModel):
    """A captured snapshot persisted to the active bucket.

    ``snapshot_id`` is the SHA-256 hex of the canonical JSON form of the
    underlying :class:`NotificationsSnapshot`, so two equal snapshots
    serialise to identical ids and we can deduplicate captures cheaply.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    snapshot_id: SnapshotId
    bucket_id: BucketId
    captured_at: datetime
    source_url: str = Field(min_length=1)
    authenticated_identity: str | None = Field(default=None, min_length=1, max_length=32)
    rows: tuple[RemoteNotification, ...]
    persisted_at: datetime


def _normalise_authenticated_identity(authenticated_identity: str | None) -> str | None:
    identity = (authenticated_identity or "").strip().upper()
    return identity or None


def _derive_snapshot_id(
    snapshot: NotificationsSnapshot,
    *,
    authenticated_identity: str | None = None,
) -> str:
    identity = _normalise_authenticated_identity(authenticated_identity)
    if identity is not None:
        return derive_snapshot_id_from_json(
            {
                "snapshot": snapshot.model_dump(mode="json"),
                "authenticated_identity": identity,
            },
        )
    canonical = snapshot.model_dump_json()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def notifications_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            "bucket_id must not be blank",
            translated_message="application.live.notifications.errors.bucket_id_blank",
        )
    if not trimmed_snapshot:
        raise LiveApplicationInputError(
            "snapshot_id must not be blank",
            translated_message="application.live.notifications.errors.snapshot_id_blank",
        )
    return f"notifications-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def _notifications_repository(
    settings: Settings,
    bucket_id: str,
) -> SecureSnapshotRepository[PersistedNotificationsSnapshot]:
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=PersistedNotificationsSnapshot,
        namespace_definition=LIVE_NOTIFICATIONS_SNAPSHOT_NAMESPACE,
        object_key=notifications_snapshot_object_key,
        not_found_factory=lambda snapshot_id: NotificationsSnapshotNotFoundError(
            "no notifications snapshot matches the requested id",
            suggestion="aeat app live notifications list",
            translated_message="application.live.notifications.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: NotificationsSnapshotNotFoundError(
            "notifications snapshot prefix matches multiple snapshots",
            suggestion="provide a longer prefix",
            translated_message="application.live.notifications.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="notifications",
        objects=secure_object_repository_for_bucket(bucket_id, settings),
    )


class NotificationsService(StatelessSnapshotService[PersistedNotificationsSnapshot]):
    """Bucket-scoped persistence + read surface over notifications snapshots.

    The service is structurally read-only. There is no ``submit`` verb,
    no path that could trigger a write to AEAT, and no method that
    mutates AEAT-side state. The local persistence flow records what
    was already observed; future fetches re-record state on each
    capture and emit a fresh bucket event.

    Each public verb accepts ``bucket_id`` per call; storage is one
    encrypted secure-object row per captured snapshot.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()
        super().__init__(repository_factory=lambda bucket_id: _notifications_repository(self._settings, bucket_id))

    def capture(
        self,
        *,
        bucket_id: str,
        snapshot: NotificationsSnapshot,
        authenticated_identity: str | None = None,
    ) -> PersistedNotificationsSnapshot:
        """Persist a snapshot for the active bucket and return the :class:`PersistedNotificationsSnapshot`.

        The caller is responsible for emitting the corresponding
        ``live.notifications.snapshot_captured`` bucket event; this
        service does not couple to the event repository so the
        persistence can be tested in isolation.
        """
        return self._capture_stateless(
            bucket_id=bucket_id,
            snapshot=snapshot,
            authenticated_identity=authenticated_identity,
        )

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> PersistedNotificationsSnapshot:
        """Look up a snapshot by full id or any unambiguous prefix.

        Returns the :class:`PersistedNotificationsSnapshot` that matches
        ``snapshot_id`` within ``bucket_id``.
        """
        return self.resolve_snapshot(bucket_id=bucket_id, snapshot_id=snapshot_id)

    def latest(
        self,
        *,
        bucket_id: str,
    ) -> PersistedNotificationsSnapshot | None:
        """Return the most recent :class:`PersistedNotificationsSnapshot`, or None if none captured."""
        snapshots = self.list_snapshots(bucket_id=bucket_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: SnapshotService[T] abstract hook
    # contract uses **kwargs to allow concrete subclasses to accept caller-
    # specific keyword arguments without a shared typed parameter set.
    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return _derive_snapshot_id(
            kwargs["snapshot"],
            authenticated_identity=kwargs.get("authenticated_identity"),
        )

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-PAYLOAD: StatelessSnapshotService[T]
    # abstract _build_payload hook carries **kwargs: Any so concrete subclasses
    # accept caller-specific keyword arguments without a shared typed set.
    def _build_payload(self, *, snapshot_id: str, bucket_id: str, **kwargs: Any) -> PersistedNotificationsSnapshot:
        snapshot: NotificationsSnapshot = kwargs["snapshot"]
        return PersistedNotificationsSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            captured_at=snapshot.captured_at,
            source_url=str(snapshot.source_url),
            authenticated_identity=_normalise_authenticated_identity(kwargs.get("authenticated_identity")),
            rows=snapshot.rows,
            persisted_at=now(),
        )


__all__ = [
    "NotificationsService",
    "NotificationsSnapshotNotFoundError",
    "PersistedNotificationsSnapshot",
    "notifications_snapshot_object_key",
]
