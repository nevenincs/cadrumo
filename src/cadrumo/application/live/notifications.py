"""Bucket-scoped notifications snapshot service.

Wraps the read-only AEAT sede notifications adapter
(:mod:`cadrumo.adapters.outbound.aeat.sede.notifications`) with
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

from datetime import datetime
from typing import override

from pydantic import BaseModel, Field

from ...core.hashing import content_hash_hex, sha256_hex
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import SnapshotId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.protocols import BrowserSessionFactoryPort
from .errors import LiveApplicationInputError
from .notification_documents import NotificationDocumentService
from .notification_ports import (
    NotificationsPorts,
    NotificationsSnapshot,
    RemoteNotification,
)
from .session import active_verified_session
from ..auth.operator_scope_ports import OperatorScopePorts
from .snapshot_base import (
    SnapshotNotFoundError,
    StatelessSnapshotService,
)


class NotificationsSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when a snapshot lookup misses by id."""


class PersistedNotificationsSnapshot(BaseModel):
    """A captured snapshot persisted to the active bucket.

    ``snapshot_id`` is the SHA-256 hex of the canonical JSON form of the
    underlying :class:`NotificationsSnapshot`, so two equal snapshots
    serialise to identical ids and we can deduplicate captures cheaply.
    """

    model_config = STRICT_FROZEN_CONFIG

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
        return content_hash_hex(
            {
                "snapshot": snapshot.model_dump(mode="json"),
                "authenticated_identity": identity,
            },
        )
    canonical = snapshot.model_dump_json()
    return sha256_hex(canonical.encode("utf-8"))


def notifications_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    """Execute this public contract operation."""
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            translated_message="application.live.notifications.errors.bucket_id_blank",
        )
    if not trimmed_snapshot:
        raise LiveApplicationInputError(
            translated_message="application.live.notifications.errors.snapshot_id_blank",
        )
    return f"notifications-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


class _NotificationsCaptureRequest(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    snapshot: NotificationsSnapshot
    authenticated_identity: str | None = None


class NotificationsService(
    StatelessSnapshotService[PersistedNotificationsSnapshot, _NotificationsCaptureRequest],
):
    """Bucket-scoped persistence + read surface over notifications snapshots.

    The service is structurally read-only. There is no ``submit`` verb,
    no path that could trigger a write to AEAT, and no method that
    mutates AEAT-side state. The local persistence flow records what
    was already observed; future fetches re-record state on each
    capture and emit a fresh bucket event.

    Each public verb accepts ``bucket_id`` per call; storage is one
    encrypted secure-object row per captured snapshot.
    """

    def __init__(self, *, ports: NotificationsPorts) -> None:
        """Bind the service to the explicitly composed application capabilities."""
        super().__init__(repository_factory=ports.snapshot_repository_factory)

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
            capture=_NotificationsCaptureRequest(
                snapshot=snapshot,
                authenticated_identity=authenticated_identity,
            ),
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
    def _derive_snapshot_id(self, capture: _NotificationsCaptureRequest) -> str:
        return _derive_snapshot_id(
            capture.snapshot,
            authenticated_identity=capture.authenticated_identity,
        )

    @override
    def _build_payload(
        self,
        *,
        snapshot_id: str,
        bucket_id: str,
        capture: _NotificationsCaptureRequest,
    ) -> PersistedNotificationsSnapshot:
        snapshot = capture.snapshot
        return PersistedNotificationsSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            captured_at=snapshot.captured_at,
            source_url=str(snapshot.source_url),
            authenticated_identity=_normalise_authenticated_identity(capture.authenticated_identity),
            rows=snapshot.rows,
            persisted_at=now(),
        )


async def capture_notifications(
    *,
    bucket_id: str,
    ports: NotificationsPorts,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
) -> PersistedNotificationsSnapshot:
    """Capture the authenticated taxpayer's notifications as encrypted local evidence."""
    session, settings = await active_verified_session(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        browser_session_factory=browser_session_factory,
        operator_scope_ports=operator_scope_ports,
    )
    snapshot = await ports.snapshot_query.fetch(session, settings=settings)
    return NotificationsService(ports=ports).capture(
        bucket_id=bucket_id,
        snapshot=snapshot,
        authenticated_identity=session.identity_nif,
    )


def resolve_notification_row(
    *,
    bucket_id: str,
    certificado_id: str,
    ports: NotificationsPorts,
) -> RemoteNotification:
    """Resolve the newest stored notification row for one certificado identifier."""
    wanted = certificado_id.strip()
    snapshots = sorted(
        NotificationsService(ports=ports).list_snapshots(bucket_id=bucket_id),
        key=lambda snapshot: snapshot.captured_at,
        reverse=True,
    )
    for snapshot in snapshots:
        for row in snapshot.rows:
            if str(row.certificado_id) == wanted:
                return row
    raise LiveApplicationInputError(
        translated_message="application.live.notifications.errors.certificado_not_in_any_snapshot",
        context={"certificado_id": wanted, "snapshots_searched": str(len(snapshots))},
    )


async def pull_notification_document(
    *,
    bucket_id: str,
    certificado_id: str,
    ports: NotificationsPorts,
    service: NotificationDocumentService,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
):
    """Fetch encrypted custody for a notification that AEAT already records as read."""
    row = resolve_notification_row(
        bucket_id=bucket_id,
        certificado_id=certificado_id,
        ports=ports,
    )
    session, _settings = await active_verified_session(
        certificate_secret_backend_factory=certificate_secret_backend_factory,
        browser_session_factory=browser_session_factory,
        operator_scope_ports=operator_scope_ports,
    )
    return await service.pull_document(bucket_id=bucket_id, session=session, row=row)


__all__ = [
    "NotificationsService",
    "NotificationsSnapshotNotFoundError",
    "PersistedNotificationsSnapshot",
    "capture_notifications",
    "notifications_snapshot_object_key",
    "pull_notification_document",
    "resolve_notification_row",
]
