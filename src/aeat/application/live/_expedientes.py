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
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.outbound.aeat.sede._declarations import Declaration
from ...core.config import Settings
from ...core.errors import AeatError


class ExpedientesSnapshotNotFoundError(AeatError):
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


def _load(settings: Settings, bucket_id: str) -> list[PersistedExpedientesSnapshot]:
    path = _storage_path(settings, bucket_id)
    if not path.exists():
        return []
    return [
        PersistedExpedientesSnapshot.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _save(
    settings: Settings,
    bucket_id: str,
    snapshots: list[PersistedExpedientesSnapshot],
) -> None:
    path = _storage_path(settings, bucket_id)
    payload = "\n".join(s.model_dump_json() for s in snapshots)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


class ExpedientesService:
    """Bucket-scoped persistence + read surface over expedientes snapshots.

    Structurally read-only per the live-AEAT charter. No submit, no
    acknowledge, no method that mutates AEAT state.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def capture(
        self,
        *,
        bucket_id: str,
        capture: ExpedientesCapture,
    ) -> PersistedExpedientesSnapshot:
        snapshot_id = _derive_snapshot_id(capture)
        persisted = PersistedExpedientesSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            declarations=capture.declarations,
            persisted_at=_now(),
        )
        snapshots = _load(self._settings, bucket_id)
        existing = next((s for s in snapshots if s.snapshot_id == snapshot_id), None)
        if existing is not None:
            return existing
        snapshots.append(persisted)
        _save(self._settings, bucket_id, snapshots)
        return persisted

    def list_snapshots(self, *, bucket_id: str) -> tuple[PersistedExpedientesSnapshot, ...]:
        return tuple(_load(self._settings, bucket_id))

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> PersistedExpedientesSnapshot:
        matches = [
            s
            for s in _load(self._settings, bucket_id)
            if s.snapshot_id == snapshot_id or s.snapshot_id.startswith(snapshot_id)
        ]
        if not matches:
            raise ExpedientesSnapshotNotFoundError(
                f"no expedientes snapshot matches {snapshot_id!r} in bucket {bucket_id!r}",
                suggestion="aeat app live expedientes list",
            )
        if len(matches) > 1:
            full_ids = sorted(s.snapshot_id for s in matches)
            raise ExpedientesSnapshotNotFoundError(
                f"prefix {snapshot_id!r} is ambiguous; matches {full_ids!r}",
                suggestion="provide a longer prefix",
            )
        return matches[0]

    def latest(
        self,
        *,
        bucket_id: str,
    ) -> PersistedExpedientesSnapshot | None:
        snapshots = _load(self._settings, bucket_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)


__all__ = [
    "ExpedientesCapture",
    "ExpedientesService",
    "ExpedientesSnapshotNotFoundError",
    "PersistedExpedientesSnapshot",
]
