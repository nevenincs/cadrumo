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
exception class names, file-storage layout, and per-call ``bucket_id``
signatures are preserved exactly.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.outbound.aeat.sede._notifications import (
    NotificationsSnapshot,
    RemoteNotification,
)
from ...core.config import Settings
from ...core.errors import AeatError
from ._errors import LiveApplicationInputError
from ._snapshot_base import SnapshotNotFoundError, StatelessSnapshotService


class NotificationsSnapshotNotFoundError(AeatError, SnapshotNotFoundError):
    """Raised when a snapshot lookup misses by id."""


class PersistedNotificationsSnapshot(BaseModel):
    """A captured snapshot persisted to the active bucket.

    ``snapshot_id`` is the SHA-256 hex of the canonical JSON form of the
    underlying :class:`NotificationsSnapshot`, so two equal snapshots
    serialise to identical ids and we can deduplicate captures cheaply.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    snapshot_id: str = Field(min_length=64, max_length=64)
    bucket_id: str = Field(min_length=1)
    captured_at: datetime
    source_url: str = Field(min_length=1)
    rows: tuple[RemoteNotification, ...]
    persisted_at: datetime


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _storage_path(settings: Settings, bucket_id: str) -> Path:
    root = settings.aeat_audit_dir / "live" / "notifications"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{bucket_id}.jsonl"


def _derive_snapshot_id(snapshot: NotificationsSnapshot) -> str:
    canonical = snapshot.model_dump_json()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _NotificationsFileRepository:
    """File-system stateless repository for one bucket's notifications snapshots.

    Structurally satisfies the ``SnapshotRepository`` protocol the
    :class:`StatelessSnapshotService` base consumes. Backing layout is
    one JSONL file per bucket under
    ``aeat_audit_dir/live/notifications``.
    """

    def __init__(self, *, settings: Settings, bucket_id: str) -> None:
        trimmed = bucket_id.strip()
        if not trimmed:
            raise LiveApplicationInputError("bucket_id must not be blank")
        self._settings = settings
        self._bucket_id = trimmed

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def _read_all(self) -> list[PersistedNotificationsSnapshot]:
        path = _storage_path(self._settings, self._bucket_id)
        if not path.exists():
            return []
        return [
            PersistedNotificationsSnapshot.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_all(self, snapshots: list[PersistedNotificationsSnapshot]) -> None:
        path = _storage_path(self._settings, self._bucket_id)
        payload = "\n".join(s.model_dump_json() for s in snapshots)
        if payload:
            payload += "\n"
        path.write_text(payload, encoding="utf-8")

    def exists(self, snapshot_id: str) -> bool:
        return any(s.snapshot_id == snapshot_id for s in self._read_all())

    def load(self, snapshot_id: str) -> PersistedNotificationsSnapshot:
        for snapshot in self._read_all():
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        raise NotificationsSnapshotNotFoundError(
            f"no notifications snapshot matches {snapshot_id!r} in bucket {self._bucket_id!r}",
            suggestion="aeat app live notifications list",
        )

    def list_snapshots(self) -> tuple[PersistedNotificationsSnapshot, ...]:
        return tuple(self._read_all())

    def resolve(self, snapshot_id: str) -> PersistedNotificationsSnapshot:
        matches = [
            s
            for s in self._read_all()
            if s.snapshot_id == snapshot_id or s.snapshot_id.startswith(snapshot_id)
        ]
        if not matches:
            raise NotificationsSnapshotNotFoundError(
                f"no notifications snapshot matches {snapshot_id!r} in bucket {self._bucket_id!r}",
                suggestion="aeat app live notifications list",
            )
        if len(matches) > 1:
            full_ids = sorted(s.snapshot_id for s in matches)
            raise NotificationsSnapshotNotFoundError(
                f"prefix {snapshot_id!r} is ambiguous; matches {full_ids!r}",
                suggestion="provide a longer prefix",
            )
        return matches[0]

    def save(self, snapshot: PersistedNotificationsSnapshot) -> None:
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"notifications snapshot bucket_id={snapshot.bucket_id!r} "
                f"does not match repository bucket {self._bucket_id!r}"
            )
        snapshots = self._read_all()
        for index, existing in enumerate(snapshots):
            if existing.snapshot_id == snapshot.snapshot_id:
                snapshots[index] = snapshot
                self._write_all(snapshots)
                return
        snapshots.append(snapshot)
        self._write_all(snapshots)


class _NotificationsBucketService(StatelessSnapshotService[PersistedNotificationsSnapshot]):
    """Per-bucket stateless snapshot service wired to the shared base."""

    def __init__(self, *, bucket_id: str, repository: _NotificationsFileRepository) -> None:
        super().__init__(bucket_id=bucket_id, repository=repository)

    def capture(self, *, snapshot: NotificationsSnapshot) -> PersistedNotificationsSnapshot:
        return self._capture_stateless(snapshot=snapshot)

    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return _derive_snapshot_id(kwargs["snapshot"])

    def _build_payload(self, *, snapshot_id: str, **kwargs: Any) -> PersistedNotificationsSnapshot:
        snapshot: NotificationsSnapshot = kwargs["snapshot"]
        return PersistedNotificationsSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            captured_at=snapshot.captured_at,
            source_url=str(snapshot.source_url),
            rows=snapshot.rows,
            persisted_at=_now(),
        )


class NotificationsService:
    """Bucket-scoped persistence + read surface over notifications snapshots.

    The service is structurally read-only. There is no ``submit`` verb,
    no path that could trigger a write to AEAT, and no method that
    mutates AEAT-side state. The local persistence flow records what
    was already observed; future fetches re-record state on each
    capture and emit a fresh bucket event.

    Each public verb accepts ``bucket_id`` per call; internally the
    service constructs a per-bucket :class:`_NotificationsBucketService`
    bound to a file-system repository that satisfies the shared
    :class:`StatelessSnapshotService` base contract.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def _bucket_service(self, bucket_id: str) -> _NotificationsBucketService:
        repository = _NotificationsFileRepository(settings=self._settings, bucket_id=bucket_id)
        return _NotificationsBucketService(bucket_id=repository.bucket_id, repository=repository)

    def capture(
        self,
        *,
        bucket_id: str,
        snapshot: NotificationsSnapshot,
    ) -> PersistedNotificationsSnapshot:
        """Persist a snapshot for the active bucket.

        Returns the persisted record. The caller is responsible for
        emitting the corresponding ``live.notifications.snapshot_captured``
        bucket event; this service does not couple to the event
        repository so the persistence can be tested in isolation.
        """
        return self._bucket_service(bucket_id).capture(snapshot=snapshot)

    def list_snapshots(self, *, bucket_id: str) -> tuple[PersistedNotificationsSnapshot, ...]:
        return self._bucket_service(bucket_id).list_snapshots()

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> PersistedNotificationsSnapshot:
        """Look up a snapshot by full id or any unambiguous prefix."""
        return self._bucket_service(bucket_id).resolve_snapshot(snapshot_id)

    def latest(
        self,
        *,
        bucket_id: str,
    ) -> PersistedNotificationsSnapshot | None:
        """Return the most recent snapshot, or None if none captured."""
        snapshots = self._bucket_service(bucket_id).list_snapshots()
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)


__all__ = [
    "NotificationsService",
    "NotificationsSnapshotNotFoundError",
    "PersistedNotificationsSnapshot",
]
