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
exception class names, file-storage layout, and per-call
``bucket_id`` signatures are preserved exactly.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.outbound.aeat.sede._declarations import Declaracion
from ...core.config import Settings, load_settings
from ...core.errors import AeatError
from ...core.time import _now
from .._storage_paths import storage_path
from ._snapshot_base import (
    JsonlSnapshotRepository,
    SnapshotNotFoundError,
    StatelessSnapshotService,
)


class ExpedientesSnapshotNotFoundError(AeatError, SnapshotNotFoundError):
    """Raised when an expedientes snapshot lookup misses by id."""


class ExpedientesCapture(BaseModel):
    """Slim wrapper around a Declaracion walker result.

    Mirrors the read-only marker pattern from
    :class:`NotificationsSnapshot`: ``mode='read'`` is the structural
    assertion that this capture cannot drive an AEAT-side mutation.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    declarations: tuple[Declaracion, ...]
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
    declarations: tuple[Declaracion, ...]
    persisted_at: datetime


def _derive_snapshot_id(capture: ExpedientesCapture) -> str:
    canonical = capture.model_dump_json()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _expedientes_repository(
    settings: Settings, bucket_id: str
) -> JsonlSnapshotRepository[PersistedExpedientesSnapshot]:
    return JsonlSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=PersistedExpedientesSnapshot,
        storage_path=lambda bucket: storage_path(settings.aeat_audit_dir / "live" / "expedientes", bucket),
        not_found_factory=lambda snapshot_id: ExpedientesSnapshotNotFoundError(
            f"no expedientes snapshot matches {snapshot_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app live expedientes list",
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: ExpedientesSnapshotNotFoundError(
            f"prefix {snapshot_id!r} is ambiguous; matches {list(full_ids)!r}",
            suggestion="provide a longer prefix",
        ),
        domain_label="expedientes",
    )


class ExpedientesService(StatelessSnapshotService[PersistedExpedientesSnapshot]):
    """Bucket-scoped persistence + read surface over expedientes snapshots.

    Structurally read-only per the live-AEAT charter. No submit, no
    acknowledge, no method that mutates AEAT state. Each public verb
    accepts ``bucket_id`` per call; storage is one JSONL file per bucket
    under ``aeat_audit_dir/live/expedientes``.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()
        super().__init__(
            repository_factory=lambda bucket_id: _expedientes_repository(self._settings, bucket_id)
        )

    def capture(
        self,
        *,
        bucket_id: str,
        capture: ExpedientesCapture,
    ) -> PersistedExpedientesSnapshot:
        return self._capture_stateless(bucket_id=bucket_id, capture=capture)

    def show(
        self,
        *,
        bucket_id: str,
        snapshot_id: str,
    ) -> PersistedExpedientesSnapshot:
        return self.resolve_snapshot(bucket_id=bucket_id, snapshot_id=snapshot_id)

    def latest(
        self,
        *,
        bucket_id: str,
    ) -> PersistedExpedientesSnapshot | None:
        snapshots = self.list_snapshots(bucket_id=bucket_id)
        if not snapshots:
            return None
        return max(snapshots, key=lambda s: s.captured_at)

    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return _derive_snapshot_id(kwargs["capture"])

    def _build_payload(
        self, *, snapshot_id: str, bucket_id: str, **kwargs: Any
    ) -> PersistedExpedientesSnapshot:
        capture: ExpedientesCapture = kwargs["capture"]
        return PersistedExpedientesSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            declarations=capture.declarations,
            persisted_at=_now(),
        )


__all__ = [
    "ExpedientesCapture",
    "ExpedientesService",
    "ExpedientesSnapshotNotFoundError",
    "PersistedExpedientesSnapshot",
]
