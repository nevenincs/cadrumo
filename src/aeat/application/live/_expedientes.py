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
exception class names, secure-object storage layout, and per-call
``bucket_id`` signatures are preserved exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, override

from pydantic import BaseModel, Field

from ...adapters.outbound.aeat.sede import Declaracion
from ...adapters.persistence.storage import LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core import STRICT_FROZEN_CONFIG
from ...core.config import Settings, load_settings
from ...core.hashing import sha256_hex
from ...core.identity import BucketId, SnapshotId
from ...core.time import now
from ._errors import LiveApplicationInputError
from ._snapshot_base import (
    SecureSnapshotRepository,
    SnapshotNotFoundError,
    StatelessSnapshotService,
)


class ExpedientesSnapshotNotFoundError(SnapshotNotFoundError):
    """Raised when an expedientes snapshot lookup misses by id."""


class ExpedientesCapture(BaseModel):
    """Slim wrapper around a Declaracion walker result.

    Mirrors the read-only marker pattern from
    :class:`NotificationsSnapshot`: ``mode='read'`` is the structural
    assertion that this capture cannot drive an AEAT-side mutation.
    """

    model_config = STRICT_FROZEN_CONFIG

    declarations: tuple[Declaracion, ...]
    captured_at: datetime
    source_url: str = Field(min_length=1)
    authenticated_identity: str | None = Field(default=None, max_length=32)
    mode: str = Field(default="read", pattern=r"^read$")


class PersistedExpedientesSnapshot(BaseModel):
    """Captured expedientes snapshot persisted to the active bucket."""

    model_config = STRICT_FROZEN_CONFIG

    snapshot_id: SnapshotId
    bucket_id: BucketId
    captured_at: datetime
    source_url: str = Field(min_length=1)
    authenticated_identity: str | None = Field(default=None, max_length=32)
    declarations: tuple[Declaracion, ...]
    persisted_at: datetime


def _derive_snapshot_id(capture: ExpedientesCapture) -> str:
    canonical = capture.model_dump_json()
    return sha256_hex(canonical.encode("utf-8"))


def expedientes_snapshot_object_key(bucket_id: str, snapshot_id: str) -> str:
    trimmed_bucket = bucket_id.strip()
    trimmed_snapshot = snapshot_id.strip()
    if not trimmed_bucket:
        raise LiveApplicationInputError(
            "bucket_id must not be blank",
            translated_message="application.live.expedientes.errors.bucket_id_blank",
        )
    if not trimmed_snapshot:
        raise LiveApplicationInputError(
            "snapshot_id must not be blank",
            translated_message="application.live.expedientes.errors.snapshot_id_blank",
        )
    return f"expedientes-snapshot:{trimmed_bucket}:{trimmed_snapshot}"


def _expedientes_repository(
    settings: Settings,
    bucket_id: str,
) -> SecureSnapshotRepository[PersistedExpedientesSnapshot]:
    return SecureSnapshotRepository(
        bucket_id=bucket_id,
        payload_model=PersistedExpedientesSnapshot,
        namespace_definition=LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE,
        object_key=expedientes_snapshot_object_key,
        not_found_factory=lambda snapshot_id: ExpedientesSnapshotNotFoundError(
            "no expedientes snapshot matches the requested id",
            suggestion="aeat app live expedientes list",
            translated_message="application.live.expedientes.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, full_ids: ExpedientesSnapshotNotFoundError(
            "expedientes snapshot prefix matches multiple snapshots",
            suggestion="provide a longer prefix",
            translated_message="application.live.expedientes.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(full_ids)},
        ),
        domain_label="expedientes",
        objects=secure_object_repository_for_bucket(bucket_id, settings),
    )


class ExpedientesService(StatelessSnapshotService[PersistedExpedientesSnapshot]):
    """Bucket-scoped persistence + read surface over expedientes snapshots.

    Structurally read-only per the live-AEAT charter. No submit, no
    acknowledge, no method that mutates AEAT state. Each public verb
    accepts ``bucket_id`` per call; storage is one encrypted secure-object
    row per captured snapshot.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()
        super().__init__(repository_factory=lambda bucket_id: _expedientes_repository(self._settings, bucket_id))

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

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-DISPATCH: SnapshotService[T] abstract hook
    # contract uses **kwargs to allow concrete subclasses to accept caller-
    # specific keyword arguments without a shared typed parameter set.
    def _derive_snapshot_id(self, **kwargs: Any) -> str:
        return _derive_snapshot_id(kwargs["capture"])

    @override
    # KWARGS-ANY-RATIONALE-SNAPSHOT-PAYLOAD: StatelessSnapshotService[T]
    # abstract _build_payload hook carries **kwargs: Any so concrete subclasses
    # accept caller-specific keyword arguments without a shared typed set.
    def _build_payload(self, *, snapshot_id: str, bucket_id: str, **kwargs: Any) -> PersistedExpedientesSnapshot:
        capture: ExpedientesCapture = kwargs["capture"]
        return PersistedExpedientesSnapshot(
            snapshot_id=snapshot_id,
            bucket_id=bucket_id,
            captured_at=capture.captured_at,
            source_url=capture.source_url,
            authenticated_identity=capture.authenticated_identity,
            declarations=capture.declarations,
            persisted_at=now(),
        )


__all__ = [
    "ExpedientesCapture",
    "ExpedientesService",
    "ExpedientesSnapshotNotFoundError",
    "PersistedExpedientesSnapshot",
    "expedientes_snapshot_object_key",
]
