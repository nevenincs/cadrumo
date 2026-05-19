"""Bucket-scoped expedientes snapshot service.

Wraps the read-only AEAT sede declarations walker
(:mod:`aeat.adapters.outbound.aeat.sede._declarations`) with
bucket-scoped persistence. Read-only by construction: no method calls
AEAT to mutate expediente state.

Verbs:
  capture(snapshot)   persist a fresh expedientes capture, deduplicated
  list_snapshots()    every captured snapshot, in capture order
  show(snapshot_id)   single snapshot by full id or unambiguous prefix
  latest()            most recent snapshot, or None

The fetch path (auth-gated walker, ``require_live_read`` invocation)
lives in the entrypoint that wires the adapter to this service.

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

from ...adapters.outbound.aeat.sede._declarations import Declaration
from ...core.config import Settings
from ...core.errors import AeatError
from ._errors import LiveApplicationInputError
from ._snapshot_base import SnapshotNotFoundError, StatelessSnapshotService


class ExpedientesSnapshotNotFoundError(SnapshotNotFoundError, AeatError):
    """Raised when an expedientes snapshot lookup misses by id."""


class ExpedientesCapture(BaseModel):
    """Slim wrapper around a Declaration walker result.

    Mirrors the read-only marker pattern from
    :class:`NotificationsSnapshot`: ``mode='read'`` is the structural
    assertion that this capture cannot drive an AEAT-side mutation.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    declarations: tuple[Declaration, ...]
    captured_at: datetime
    source_url: str = Field(min_length=1)
    mode: str = Field(default="read", pattern=r"^read$")


class PersistedExpedientesSnapshot(BaseModel):
    """Captured expedientes snapshot persisted to the active bucket."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    snapshot_id: str = Field(min_length=64, max_length=64)
    bucket_id: str = Field(min_length=1)
    captured_at: datetime
    source_url: str = Field(min_length=1)
    declarations: tuple[Declaration, ...]
    persisted_at: datetime


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _storage_path(settings: Settings, bucket_id: str) -> Path:
    root = settings.aeat_audit_dir / "live" / "expedientes"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{bucket_id}.jsonl"


def _derive_snapshot_id(capture: ExpedientesCapture) -> str:
    canonical = capture.model_dump_json()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _ExpedientesFileRepository:
    """File-system stateless repository for one bucket's expedientes snapshots.

    Structurally satisfies the ``SnapshotRepository`` protocol the
    :class:`StatelessSnapshotService` base consumes. Backing layout is
    one JSONL file per bucket under ``aeat_audit_dir/live/expedientes``.
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

    def _read_all(self) -> list[PersistedExpedientesSnapshot]:
        path = _storage_path(self._settings, self._bucket_id)
        if not path.exists():
            return []
        return [
            PersistedExpedientesSnapshot.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_all(self, snapshots: list[PersistedExpedientesSnapshot]) -> None:
        path = _storage_path(self._settings, self._bucket_id)
        payload = "\n".join(s.model_dump_json() for s in snapshots)
        if payload:
            payload += "\n"
        path.write_text(payload, encoding="utf-8")

    def exists(self, snapshot_id: str) -> bool:
        return any(s.snapshot_id == snapshot_id for s in self._read_all())

    def load(self, snapshot_id: str) -> PersistedExpedientesSnapshot:
        for snapshot in self._read_all():
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        raise ExpedientesSnapshotNotFoundError(
            f"no expedientes snapshot matches {snapshot_id!r} in bucket {self._bucket_id!r}",
            suggestion="aeat app live expedientes list",
        )

    def list_snapshots(self) -> tuple[PersistedExpedientesSnapshot, ...]:
        return tuple(self._read_all())

    def resolve(self, snapshot_id: str) -> PersistedExpedientesSnapshot:
        matches = [
            s
            for s in self._read_all()
            if s.snapshot_id == snapshot_id or s.snapshot_id.startswith(snapshot_id)
        ]
        if not matches:
            raise ExpedientesSnapshotNotFoundError(
                f"no expedientes snapshot matches {snapshot_id!r} in bucket {self._bucket_id!r}",
                suggestion="aeat app live expedientes list",
            )
        if len(matches) > 1:
            full_ids = sorted(s.snapshot_id for s in matches)
            raise ExpedientesSnapshotNotFoundError(
                f"prefix {snapshot_id!r} is ambiguous; matches {full_ids!r}",
                suggestion="provide a longer prefix",
            )
        return matches[0]

    def save(self, snapshot: PersistedExpedientesSnapshot) -> None:
        if snapshot.bucket_id != self._bucket_id:
            raise LiveApplicationInputError(
                f"expedientes snapshot bucket_id={snapshot.bucket_id!r} "
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


class _ExpedientesBucketService(StatelessSnapshotService[PersistedExpedientesSnapshot]):
    """Per-bucket stateless snapshot service wired to the shared base."""

    def __init__(self, *, bucket_id: str, repository: _ExpedientesFileRepository) -> None:
        super().__init__(bucket_id=bucket_id, repository=repository)

    def capture(self, *, capture: ExpedientesCapture) -> PersistedExpedientesSnapshot:
        return self._capture_stateless(capture=capture)

    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return _derive_snapshot_id(kwargs["capture"])

    def _build_payload(self, *, snapshot_id: str, **kwargs: Any) -> PersistedExpedientesSnapshot:
        capture: ExpedientesCapture = kwargs["capture"]
        return PersistedExpedientesSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=self._repository.bucket_id,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            declarations=capture.declarations,
            persisted_at=_now(),
        )


class ExpedientesService:
    """Bucket-scoped persistence + read surface over expedientes snapshots.

    Structurally read-only per the live-AEAT charter. No submit, no
    acknowledge, no method that mutates AEAT state.

    Each public verb accepts ``bucket_id`` per call; internally the
    service constructs a per-bucket :class:`_ExpedientesBucketService`
    bound to a file-system repository that satisfies the shared
    :class:`StatelessSnapshotService` base contract.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def _bucket_service(self, bucket_id: str) -> _ExpedientesBucketService:
        repository = _ExpedientesFileRepository(settings=self._settings, bucket_id=bucket_id)
        return _ExpedientesBucketService(bucket_id=repository.bucket_id, repository=repository)

    def capture(
        self,
        *,
        bucket_id: str,
        capture: ExpedientesCapture,
    ) -> PersistedExpedientesSnapshot:
        return self._bucket_service(bucket_id).capture(capture=capture)

    def list_snapshots(self, *, bucket_id: str) -> tuple[PersistedExpedientesSnapshot, ...]:
        return self._bucket_service(bucket_id).list_snapshots()

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> PersistedExpedientesSnapshot:
        return self._bucket_service(bucket_id).resolve_snapshot(snapshot_id)

    def latest(
        self,
        *,
        bucket_id: str,
    ) -> PersistedExpedientesSnapshot | None:
        snapshots = self._bucket_service(bucket_id).list_snapshots()
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)


__all__ = [
    "ExpedientesCapture",
    "ExpedientesService",
    "ExpedientesSnapshotNotFoundError",
    "PersistedExpedientesSnapshot",
]
